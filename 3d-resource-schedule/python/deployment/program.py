"""Compile the static execution program shared by Decode and Prefill."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from hardware_profile import HardwareProfile
from model import DOWN, GATE_UP, BlockTable

from deployment.costs import CostModel
from deployment.weight_cubes import WeightCubeTable

ENTRY = 0
WEIGHTED = 1
WEIGHTED_COMBINE = 5
SINK = 6

NO_NODE_BINDING = 0
SELECTED_RESIDENT = 1
MOE_REDUCTION = 2


@dataclass(slots=True)
class ExecutionProgram:
    entry_task_id: int
    sink_task_id: int
    moe_rank_count: int
    task_kind: np.ndarray
    model_layer: np.ndarray
    rank_in_layer: np.ndarray
    block_kind: np.ndarray
    weight_cube_id: np.ndarray
    node_binding_mode: np.ndarray
    predecessor_ptr: np.ndarray
    predecessor_ids: np.ndarray
    successor_ptr: np.ndarray
    successor_ids: np.ndarray
    topological_order: np.ndarray
    layer_rank_ptr: np.ndarray
    rank_input_task_id: np.ndarray
    rank_gate_task_id: np.ndarray
    rank_output_task_id: np.ndarray
    task_service_ns: np.ndarray
    task_hop_service_ns: np.ndarray
    dependency_bound_ns: int

    @property
    def task_count(self) -> int:
        return len(self.task_kind)


def compile_execution_program(
    table: BlockTable,
    weight_cubes: WeightCubeTable,
    hardware_profile: HardwareProfile,
) -> ExecutionProgram:
    """Compile one hardware-specific task graph and all of its costs."""
    moe_rank_count = table.active_moe_ranks
    task_kind: list[int] = []
    model_layer: list[int] = []
    rank_in_layer: list[int] = []
    block_kind: list[int] = []
    weight_cube_id: list[int] = []
    node_binding_mode: list[int] = []
    dependencies: list[list[int]] = []
    layer_rank_ptr = [0]
    rank_input_task_id: list[int] = []
    rank_gate_task_id: list[int] = []
    rank_output_task_id: list[int] = []

    def add_task(
        kind: int,
        layer: int,
        rank: int,
        block: int,
        cube: int,
        inputs: Sequence[int],
        binding_mode: int = SELECTED_RESIDENT,
    ) -> int:
        task_id = len(task_kind)
        task_kind.append(kind)
        model_layer.append(layer)
        rank_in_layer.append(rank)
        block_kind.append(block)
        weight_cube_id.append(cube)
        node_binding_mode.append(binding_mode)
        dependencies.append(list(inputs))
        return task_id

    def build_expert_tasks(
        layer: int,
        rank: int,
        expert_column: int,
        inputs: Sequence[int],
    ) -> tuple[int, int]:
        gate = add_task(
            WEIGHTED,
            layer,
            rank,
            GATE_UP,
            int(table.template_id[table.slot(layer, expert_column, GATE_UP)]),
            inputs,
        )
        down = add_task(
            WEIGHTED,
            layer,
            rank,
            DOWN,
            int(table.template_id[table.slot(layer, expert_column, DOWN)]),
            (gate,),
        )
        return gate, down

    entry_task_id = add_task(
        ENTRY,
        -1,
        -1,
        -1,
        -1,
        (),
        NO_NODE_BINDING,
    )
    topological_order = [entry_task_id]
    previous_outputs = [entry_task_id]
    for layer in range(table.model_layers):
        ranks = range(1) if layer < table.dense_layers else range(moe_rank_count)
        layer_gate_tasks = []
        layer_down_tasks = []
        expert_outputs = []
        for rank in ranks:
            expert_column = (
                0
                if layer < table.dense_layers
                else min(rank, table.routed_column_offset)
            )
            gate, expert_output = build_expert_tasks(
                layer,
                rank,
                expert_column,
                previous_outputs,
            )
            layer_gate_tasks.append(gate)
            layer_down_tasks.append(expert_output)
            expert_outputs.append(expert_output)
            rank_input_task_id.append(previous_outputs[0])
            rank_gate_task_id.append(gate)
            rank_output_task_id.append(expert_output)
        topological_order.extend(layer_gate_tasks)
        topological_order.extend(layer_down_tasks)
        if layer < table.dense_layers:
            previous_outputs = expert_outputs
        else:
            combine = add_task(
                WEIGHTED_COMBINE,
                layer,
                -1,
                -1,
                -1,
                expert_outputs,
                MOE_REDUCTION,
            )
            topological_order.append(combine)
            previous_outputs = [combine]
        layer_rank_ptr.append(len(rank_output_task_id))
    sink_task_id = add_task(
        SINK,
        table.model_layers,
        -1,
        -1,
        -1,
        previous_outputs,
        NO_NODE_BINDING,
    )
    topological_order.append(sink_task_id)

    predecessor_count = np.fromiter(
        (len(items) for items in dependencies), dtype=np.int32
    )
    predecessor_ptr = np.empty(len(task_kind) + 1, dtype=np.int32)
    predecessor_ptr[0] = 0
    np.cumsum(predecessor_count, out=predecessor_ptr[1:])
    predecessor_ids = np.fromiter(
        (dependency for items in dependencies for dependency in items),
        dtype=np.int32,
    )
    successors: list[list[int]] = [[] for _ in task_kind]
    for target, sources in enumerate(dependencies):
        for source in sources:
            successors[source].append(target)
    successor_count = np.fromiter((len(items) for items in successors), dtype=np.int32)
    successor_ptr = np.empty(len(task_kind) + 1, dtype=np.int32)
    successor_ptr[0] = 0
    np.cumsum(successor_count, out=successor_ptr[1:])
    successor_ids = np.fromiter(
        (successor for items in successors for successor in items),
        dtype=np.int32,
    )
    task_kind_array = np.asarray(task_kind, dtype=np.int8)
    weight_cube_id_array = np.asarray(weight_cube_id, dtype=np.int32)
    topological_order_array = np.asarray(topological_order, dtype=np.int32)
    rank_gate_task_id_array = np.asarray(rank_gate_task_id, dtype=np.int32)
    rank_output_task_id_array = np.asarray(rank_output_task_id, dtype=np.int32)

    cost_model = CostModel(hardware_profile)
    task_service_ns = np.zeros(len(task_kind), dtype=np.int64)
    for task in np.flatnonzero(task_kind_array == WEIGHTED):
        cube = int(weight_cube_id_array[task])
        task_service_ns[task] = cost_model.weight_cube_ns(weight_cubes, cube)

    task_output_bytes = np.zeros(len(task_kind), dtype=np.int32)
    first_template = int(table.template_id[table.slot(0, 0, GATE_UP)])
    task_output_bytes[entry_task_id] = cost_model.activation_bytes(
        int(table.template_input_elements[first_template])
    )
    for task in topological_order_array:
        kind = int(task_kind_array[task])
        if kind == ENTRY:
            continue
        if kind == WEIGHTED:
            cube = int(weight_cube_id_array[task])
            task_output_bytes[task] = cost_model.activation_bytes(
                int(weight_cubes.output_elements[cube])
            )
            continue
        inputs = predecessor_ids[
            int(predecessor_ptr[task]) : int(predecessor_ptr[task + 1])
        ]
        if kind == WEIGHTED_COMBINE:
            task_output_bytes[task] = task_output_bytes[inputs].max()

    task_hop_service_ns = np.ceil(
        task_output_bytes / hardware_profile.link_bandwidth_GBps
    ).astype(np.int64)
    dependency_finish = np.zeros(len(task_kind), dtype=np.int64)
    for task in topological_order_array:
        start = int(predecessor_ptr[task])
        end = int(predecessor_ptr[task + 1])
        dependency_finish[task] = (
            dependency_finish[predecessor_ids[start:end]].max(initial=0)
            + task_service_ns[task]
        )
    return ExecutionProgram(
        entry_task_id,
        sink_task_id,
        moe_rank_count,
        task_kind_array,
        np.asarray(model_layer, dtype=np.int8),
        np.asarray(rank_in_layer, dtype=np.int8),
        np.asarray(block_kind, dtype=np.int8),
        weight_cube_id_array,
        np.asarray(node_binding_mode, dtype=np.int8),
        predecessor_ptr,
        predecessor_ids,
        successor_ptr,
        successor_ids,
        topological_order_array,
        np.asarray(layer_rank_ptr, dtype=np.int32),
        np.asarray(rank_input_task_id, dtype=np.int32),
        rank_gate_task_id_array,
        rank_output_task_id_array,
        task_service_ns,
        task_hop_service_ns,
        int(dependency_finish[sink_task_id]),
    )
