"""Deterministic discrete-event simulation for Prefill Tokens."""

import heapq
from dataclasses import dataclass
from typing import Literal

import numpy as np
from deployment import Deployment
from deployment.program import (
    MOE_REDUCTION,
    WEIGHTED,
    ExecutionProgram,
)
from model import DOWN, GATE_UP
from simulation.collective import (
    CollectiveTopology,
    compile_collective_topology,
    compile_tree_parent,
)
from simulation.prefill.selection import (
    select_cumulative_work_moe_residents,
    select_geometry_reduction_root,
)
from simulation.prefill.telemetry import (
    PrefillExecution,
    allocate_prefill_execution,
)
from simulation.workload import ReportDepth

_RELEASE = 0
_DISPATCH = 1

_TASK_FINISH = 0
_LINK_RELEASE = 1
_COMPUTE_DISPATCH = 2

_POINT_TO_POINT = 0
_DISPATCH_TREE_EDGE = 1
_REDUCTION_TREE_EDGE = 2
type PrefillDispatch = Literal["cumulative-work", "round-robin"]

PREFILL_SCHEDULER = "minimum-cumulative-work-canonical-tree"


@dataclass(slots=True)
class _Transfer:
    owner: int
    successor_task: int
    path_end: int
    hop_service_ns: int
    layer: int
    token: int
    destination_node: int


@dataclass(slots=True)
class PrefillExecutor:
    deployment: Deployment
    program: ExecutionProgram
    dispatch: PrefillDispatch
    collective: CollectiveTopology
    link_count: int
    reduction_task_id: np.ndarray
    moe_dispatch_layer_by_task: np.ndarray
    moe_output_layer_by_task: np.ndarray
    dispatch_hop_service_ns: np.ndarray
    reduction_hop_service_ns: np.ndarray
    compute_phase: np.ndarray
    layer_boundary_task_id: np.ndarray


def compile_prefill_executor(
    deployment: Deployment,
    dispatch: PrefillDispatch = "cumulative-work",
) -> PrefillExecutor:
    """Compile one of the two supported dispatch methods on the shared DES."""
    program = deployment.model.program
    collective = compile_collective_topology(deployment.model.hardware_profile.grid)
    link_count = collective.link_count
    reduction_task_id = np.full(
        deployment.model.block_table.model_layers,
        -1,
        dtype=np.int32,
    )
    reduction_tasks = np.flatnonzero(program.node_binding_mode == MOE_REDUCTION)
    reduction_task_id[program.model_layer[reduction_tasks]] = reduction_tasks
    moe_dispatch_layer_by_task = np.full(program.task_count, -1, dtype=np.int8)
    moe_output_layer_by_task = np.full(program.task_count, -1, dtype=np.int8)
    dispatch_hop_service_ns = np.zeros(
        deployment.model.block_table.model_layers,
        dtype=np.int64,
    )
    reduction_hop_service_ns = np.zeros(
        deployment.model.block_table.model_layers,
        dtype=np.int64,
    )
    for layer in range(
        deployment.model.block_table.dense_layers,
        deployment.model.block_table.model_layers,
    ):
        rank_start = int(program.layer_rank_ptr[layer])
        rank_end = int(program.layer_rank_ptr[layer + 1])
        boundary_task = int(program.rank_input_task_id[rank_start])
        moe_dispatch_layer_by_task[boundary_task] = layer
        dispatch_hop_service_ns[layer] = program.task_hop_service_ns[boundary_task]
        for rank in range(rank_start, rank_end):
            output_task = int(program.rank_output_task_id[rank])
            moe_output_layer_by_task[output_task] = layer
        reduction_hop_service_ns[layer] = program.task_hop_service_ns[
            program.rank_output_task_id[rank_start]
        ]
    layer_boundary_task_id = np.empty(
        deployment.model.block_table.model_layers,
        dtype=np.int32,
    )
    for layer in range(deployment.model.block_table.model_layers):
        rank = int(program.layer_rank_ptr[layer])
        layer_boundary_task_id[layer] = (
            int(reduction_task_id[layer])
            if layer >= deployment.model.block_table.dense_layers
            else int(program.rank_output_task_id[rank])
        )
    return PrefillExecutor(
        deployment,
        program,
        dispatch,
        collective,
        link_count,
        reduction_task_id,
        moe_dispatch_layer_by_task,
        moe_output_layer_by_task,
        dispatch_hop_service_ns,
        reduction_hop_service_ns,
        (program.block_kind != DOWN).astype(np.int8),
        layer_boundary_task_id,
    )


def execute_prefill(
    executor: PrefillExecutor,
    routes: np.ndarray,
    capture: ReportDepth,
) -> PrefillExecution:
    """Execute cumulative-work dispatch with fixed shortest-path trees."""
    simulation = (
        _RoundRobinPrefillSimulation
        if executor.dispatch == "round-robin"
        else _PrefillSimulation
    )
    return simulation(executor, routes, capture).run()


class _PrefillSimulation:
    def __init__(
        self,
        executor: PrefillExecutor,
        routes: np.ndarray,
        capture: ReportDepth,
    ) -> None:
        deployment = executor.deployment
        program = executor.program
        self.deployment = deployment
        self.program = program
        self.routes = routes
        self.token_count = len(routes)
        self.template_task_count = program.task_count
        runtime_task_count = self.token_count * program.task_count
        self.mesh_node_count = deployment.model.hardware_profile.mesh_node_count
        self.collective = executor.collective
        link_count = executor.link_count
        self.execution = allocate_prefill_execution(
            capture,
            deployment,
            self.token_count,
            link_count,
        )
        self.resources = self.execution.resources
        self.diagnostics = self.execution.diagnostics
        self.link_queue_depth = (
            np.zeros(link_count, dtype=np.int32)
            if self.diagnostics is not None
            else None
        )
        self.expert_service = deployment.model.expert_service_ns
        self.reduction_task_id = executor.reduction_task_id
        self.moe_dispatch_layer_by_task = executor.moe_dispatch_layer_by_task
        self.moe_output_layer_by_task = executor.moe_output_layer_by_task
        self.dispatch_hop_service_ns = executor.dispatch_hop_service_ns
        self.reduction_hop_service_ns = executor.reduction_hop_service_ns
        self.compute_phase = executor.compute_phase
        self.layer_boundary_task_id = executor.layer_boundary_task_id
        self.physical_node = np.full(
            runtime_task_count,
            -1,
            dtype=np.int16,
        )
        self.moe_layer_count = (
            deployment.model.block_table.model_layers
            - deployment.model.block_table.dense_layers
        )
        collective_shape = (
            self.token_count,
            self.moe_layer_count,
            self.mesh_node_count,
        )
        self.terminal_mask = np.zeros(
            (self.token_count, self.moe_layer_count),
            dtype=np.uint16,
        )
        self.dispatch_vertex_mask = np.zeros_like(self.terminal_mask)
        self.dispatch_parent = np.full(collective_shape, -1, dtype=np.int8)
        self.reduction_parent = np.full(collective_shape, -1, dtype=np.int8)
        self.reduction_local_pending = np.zeros(collective_shape, dtype=np.int16)
        self.reduction_child_pending = np.zeros(collective_shape, dtype=np.int8)
        self.reduction_ready_ns = np.zeros(collective_shape, dtype=np.int64)
        self.reduction_released = np.zeros(collective_shape, dtype=np.bool_)
        self.dispatch_successors: list[tuple[int, ...] | None] = [None] * (
            self.token_count * self.moe_layer_count * self.mesh_node_count
        )

        self.compute_available = np.zeros(self.mesh_node_count, dtype=np.int64)
        self.cumulative_compute_work = np.zeros(self.mesh_node_count, dtype=np.int64)
        self.compute_ready: list[list[tuple[int, int, int, int]]] = [
            [] for _ in range(self.mesh_node_count)
        ]
        self.compute_dispatch_pending = np.zeros(self.mesh_node_count, dtype=np.bool_)

        self.link_available = np.zeros(link_count, dtype=np.int64)

        moe_rank_count = program.moe_rank_count
        self.active_slots = np.empty(moe_rank_count, dtype=np.int32)
        self.token_latency = self.execution.token_latency_ns
        self.events: list[tuple[int, int, int, int, int, int]] = []
        self.transfers: list[_Transfer] = []
        self.sequence = 0
        self.completed_tokens = 0

    def run(self) -> PrefillExecution:
        entry_task_id = self.program.entry_task_id
        for token in range(self.token_count):
            task_id = token * self.template_task_count + entry_task_id
            self.physical_node[task_id] = 0
            self._enqueue_task(task_id, 0)

        while self.completed_tokens < self.token_count:
            now, _, _, kind, first, second = heapq.heappop(self.events)
            if self.diagnostics is not None:
                self.diagnostics.event_count += 1
            if kind == _TASK_FINISH:
                self._finish_task(first, now)
            elif kind == _LINK_RELEASE:
                self._release_link(first, second, now)
            else:
                self._dispatch_compute(first, now)

        return self.execution

    def _push_event(
        self,
        time: int,
        priority: int,
        kind: int,
        first: int,
        second: int = 0,
    ) -> None:
        heapq.heappush(
            self.events,
            (time, priority, self.sequence, kind, first, second),
        )
        self.sequence += 1

    def _enqueue_task(self, task_id: int, now: int) -> None:
        template_task = task_id % self.template_task_count
        if self.program.task_kind[template_task] != WEIGHTED:
            duration = int(self.program.task_service_ns[template_task])
            if self.diagnostics is not None:
                self.diagnostics.service_ns += duration
            self._push_event(now + duration, _RELEASE, _TASK_FINISH, task_id)
            return
        token = task_id // self.template_task_count
        node = int(self.physical_node[task_id])
        phase = int(self.compute_phase[template_task])
        item = token, phase, now, task_id
        ready = self.compute_ready[node]
        heapq.heappush(ready, item)
        if self.diagnostics is not None:
            self.diagnostics.max_compute_queue_depth = max(
                self.diagnostics.max_compute_queue_depth,
                len(ready),
            )
        if (
            self.compute_available[node] <= now
            and not self.compute_dispatch_pending[node]
        ):
            self.compute_dispatch_pending[node] = True
            self._push_event(now, _DISPATCH, _COMPUTE_DISPATCH, node)

    def _dispatch_compute(self, node: int, now: int) -> None:
        self.compute_dispatch_pending[node] = False
        ready = self.compute_ready[node]
        if not ready:
            return
        _, _, ready_time, task_id = heapq.heappop(ready)

        duration = int(self.program.task_service_ns[task_id % self.template_task_count])
        wait = now - ready_time
        if self.diagnostics is not None:
            self.diagnostics.queue_wait_ns += wait
            self.diagnostics.service_ns += duration
            template_task = task_id % self.template_task_count
            layer = int(self.program.model_layer[template_task])
            self.diagnostics.compute_work_by_layer_node_ns[layer, node] += duration
            self.diagnostics.compute_queue_wait_by_layer_node_ns[layer, node] += wait
        if self.resources is not None:
            self.resources.compute_busy_ns[node] += duration
        finish = now + duration
        if self.diagnostics is not None:
            self.diagnostics.compute_interval_start_ns.append(now)
            self.diagnostics.compute_interval_finish_ns.append(finish)
            self.diagnostics.compute_interval_node.append(node)
            self.diagnostics.compute_interval_token.append(
                task_id // self.template_task_count
            )
        self.compute_available[node] = finish
        self._push_event(finish, _RELEASE, _TASK_FINISH, task_id)

    def _finish_task(self, task_id: int, now: int) -> None:
        template_task = task_id % self.template_task_count
        token = task_id // self.template_task_count
        if template_task == self.program.sink_task_id:
            self.token_latency[token] = now
            self.completed_tokens += 1
            return
        node = int(self.physical_node[task_id])
        if self.diagnostics is not None and (
            self.program.node_binding_mode[template_task] == MOE_REDUCTION
        ):
            layer = int(self.program.model_layer[template_task])
            self.diagnostics.reduction_executions_by_layer_node[layer, node] += 1
        if self.diagnostics is not None:
            layer = int(self.program.model_layer[template_task])
            if (
                0 <= layer < self.deployment.model.block_table.model_layers
                and template_task == self.layer_boundary_task_id[layer]
            ):
                self.diagnostics.layer_finish_ns_by_token[token, layer] = now
        dispatch_layer = int(self.moe_dispatch_layer_by_task[template_task])
        if dispatch_layer >= 0:
            self._bind_layer(token, dispatch_layer, now)
            self._release_dispatch_node(token, dispatch_layer, node, now)
            self._continue_compute(node, now)
            return
        output_layer = int(self.moe_output_layer_by_task[template_task])
        if output_layer >= 0:
            self._finish_moe_output(token, output_layer, node, now)
            self._continue_compute(node, now)
            return
        successor_start = int(self.program.successor_ptr[template_task])
        successor = int(self.program.successor_ids[successor_start])
        layer = int(self.program.model_layer[successor])
        if self.program.block_kind[successor] == GATE_UP:
            self._bind_layer(token, layer, now)
        successor_task = token * self.template_task_count + successor
        destination = int(self.physical_node[successor_task])
        if successor == self.program.sink_task_id or destination == node:
            self._enqueue_task(successor_task, now)
        else:
            self._emit_point_to_point(
                node,
                destination,
                successor_task,
                int(self.program.task_hop_service_ns[template_task]),
                layer,
                now,
            )

        self._continue_compute(node, now)

    def _continue_compute(self, node: int, now: int) -> None:
        if (
            self.compute_ready[node]
            and self.compute_available[node] <= now
            and not self.compute_dispatch_pending[node]
        ):
            self.compute_dispatch_pending[node] = True
            self._push_event(now, _DISPATCH, _COMPUTE_DISPATCH, node)

    def _bind_layer(self, token: int, layer: int, now: int) -> None:
        if self.diagnostics is not None:
            self.diagnostics.layer_release_ns_by_token[token, layer] = now
        table = self.deployment.model.block_table
        residency = self.deployment.residency
        program = self.program
        token_offset = token * self.template_task_count
        rank_start = int(program.layer_rank_ptr[layer])
        rank_end = int(program.layer_rank_ptr[layer + 1])
        ranks = rank_end - rank_start
        if layer < table.dense_layers:
            self.active_slots[0] = table.expert_slot(layer, 0)
            selection = (int(residency.resident_ptr[self.active_slots[0]]),)
        else:
            route = self.routes[token, layer - table.dense_layers]
            for rank in range(ranks):
                expert = (
                    rank
                    if rank < table.shared_experts
                    else int(route[rank - table.shared_experts]) + table.shared_experts
                )
                slot = table.expert_slot(layer, expert)
                self.active_slots[rank] = slot
            boundary_task = token_offset + int(program.rank_input_task_id[rank_start])
            input_node = int(self.physical_node[boundary_task])
            selection = self._select_moe_residents(ranks, input_node, layer)
            terminal_mask = 0
            for resident in selection:
                terminal_mask |= 1 << int(residency.resident_node[resident])
            reduction_node = select_geometry_reduction_root(
                terminal_mask, self.collective
            )
            reduction_task = token_offset + int(self.reduction_task_id[layer])
            self.physical_node[reduction_task] = reduction_node
            moe_layer = layer - table.dense_layers
            if self.diagnostics is not None:
                self.diagnostics.input_node_by_token_moe_layer[token, moe_layer] = (
                    input_node
                )
                self.diagnostics.reduction_node_by_token_moe_layer[token, moe_layer] = (
                    reduction_node
                )
                for rank, resident in enumerate(selection):
                    expert = (
                        rank
                        if rank < table.shared_experts
                        else int(route[rank - table.shared_experts])
                        + table.shared_experts
                    )
                    node = int(residency.resident_node[resident])
                    self.diagnostics.moe_input_count[moe_layer, expert, input_node] += 1
                    self.diagnostics.moe_binding_count[moe_layer, expert, node] += 1

        for rank, resident in enumerate(selection):
            resident = int(resident)
            node = int(residency.resident_node[resident])
            if self.diagnostics is not None:
                self.diagnostics.resident_binding_count[resident] += 1
            rank_index = rank_start + rank
            gate = int(program.rank_gate_task_id[rank_index])
            down = int(program.rank_output_task_id[rank_index])
            self.physical_node[token_offset + gate] = node
            self.physical_node[token_offset + down] = node
            self.cumulative_compute_work[node] += self.expert_service[
                self.active_slots[rank]
            ]

        if layer >= table.dense_layers:
            self._compile_moe_collective(
                token, layer, selection, input_node, reduction_node
            )

    def _select_moe_residents(self, ranks, input_node, layer):
        return select_cumulative_work_moe_residents(
            self.active_slots[:ranks],
            self.deployment.residency.resident_ptr,
            self.deployment.residency.resident_node,
            self.expert_service,
            self.cumulative_compute_work,
            self.collective.hop_distance[input_node],
            int(self.dispatch_hop_service_ns[layer]),
        )

    def _compile_moe_collective(
        self,
        token: int,
        layer: int,
        selection: np.ndarray,
        input_node: int,
        reduction_node: int,
    ) -> None:
        moe_layer = layer - self.deployment.model.block_table.dense_layers
        terminal_mask = 0
        for resident in selection:
            terminal_mask |= 1 << int(
                self.deployment.residency.resident_node[int(resident)]
            )
        self.terminal_mask[token, moe_layer] = terminal_mask
        dispatch_parent = self.dispatch_parent[token, moe_layer]
        reduction_parent = self.reduction_parent[token, moe_layer]
        dispatch_vertices = compile_tree_parent(
            input_node,
            terminal_mask,
            self.collective,
            dispatch_parent,
        )
        compile_tree_parent(
            reduction_node,
            terminal_mask,
            self.collective,
            reduction_parent,
        )
        self.dispatch_vertex_mask[token, moe_layer] = dispatch_vertices
        child_pending = self.reduction_child_pending[token, moe_layer]
        for node in range(self.mesh_node_count):
            parent = int(reduction_parent[node])
            if parent >= 0:
                child_pending[parent] += 1

        token_offset = token * self.template_task_count
        rank_start = int(self.program.layer_rank_ptr[layer])
        rank_end = int(self.program.layer_rank_ptr[layer + 1])
        local_pending = self.reduction_local_pending[token, moe_layer]
        for rank in range(rank_start, rank_end):
            output_task = token_offset + int(self.program.rank_output_task_id[rank])
            local_pending[int(self.physical_node[output_task])] += 1

        boundary_task = int(self.program.rank_input_task_id[rank_start])
        successor_start = int(self.program.successor_ptr[boundary_task])
        successor_end = int(self.program.successor_ptr[boundary_task + 1])
        grouped: list[list[int]] = [[] for _ in range(self.mesh_node_count)]
        for successor in self.program.successor_ids[successor_start:successor_end]:
            runtime_task = token_offset + int(successor)
            grouped[int(self.physical_node[runtime_task])].append(runtime_task)
        base = (token * self.moe_layer_count + moe_layer) * self.mesh_node_count
        for node, tasks in enumerate(grouped):
            if tasks:
                self.dispatch_successors[base + node] = tuple(tasks)

        if self.diagnostics is not None:
            required_dispatch = terminal_mask | (1 << input_node)
            required_reduction = terminal_mask | (1 << reduction_node)
            self.diagnostics.terminal_count_by_token_moe_layer[
                token,
                moe_layer,
            ] = terminal_mask.bit_count()
            self.diagnostics.dispatch_tree_edges_by_token_moe_layer[
                token,
                moe_layer,
            ] = self.collective.tree_edge_count[
                input_node,
                required_dispatch,
            ]
            self.diagnostics.reduction_tree_edges_by_token_moe_layer[
                token,
                moe_layer,
            ] = self.collective.tree_edge_count[
                reduction_node,
                required_reduction,
            ]

    def _release_dispatch_node(
        self,
        token: int,
        layer: int,
        node: int,
        now: int,
    ) -> None:
        moe_layer = layer - self.deployment.model.block_table.dense_layers
        terminal_mask = int(self.terminal_mask[token, moe_layer])
        if terminal_mask & (1 << node):
            index = (
                token * self.moe_layer_count + moe_layer
            ) * self.mesh_node_count + node
            for task in self.dispatch_successors[index]:
                self._enqueue_task(task, now)
        parent = self.dispatch_parent[token, moe_layer]
        vertices = int(self.dispatch_vertex_mask[token, moe_layer])
        service = int(self.dispatch_hop_service_ns[layer])
        for child in range(self.mesh_node_count):
            if vertices & (1 << child) and int(parent[child]) == node:
                self._emit_collective_edge(
                    _DISPATCH_TREE_EDGE,
                    token,
                    layer,
                    node,
                    child,
                    service,
                    now,
                )

    def _finish_moe_output(
        self,
        token: int,
        layer: int,
        node: int,
        now: int,
    ) -> None:
        moe_layer = layer - self.deployment.model.block_table.dense_layers
        self.reduction_local_pending[token, moe_layer, node] -= 1
        self.reduction_ready_ns[token, moe_layer, node] = max(
            int(self.reduction_ready_ns[token, moe_layer, node]),
            now,
        )
        self._release_reduction_node(token, layer, node)

    def _arrive_reduction_node(
        self,
        token: int,
        layer: int,
        node: int,
        now: int,
    ) -> None:
        moe_layer = layer - self.deployment.model.block_table.dense_layers
        self.reduction_child_pending[token, moe_layer, node] -= 1
        self.reduction_ready_ns[token, moe_layer, node] = max(
            int(self.reduction_ready_ns[token, moe_layer, node]),
            now,
        )
        self._release_reduction_node(token, layer, node)

    def _release_reduction_node(
        self,
        token: int,
        layer: int,
        node: int,
    ) -> None:
        moe_layer = layer - self.deployment.model.block_table.dense_layers
        if (
            self.reduction_released[token, moe_layer, node]
            or self.reduction_local_pending[token, moe_layer, node] != 0
            or self.reduction_child_pending[token, moe_layer, node] != 0
        ):
            return
        self.reduction_released[token, moe_layer, node] = True
        ready = int(self.reduction_ready_ns[token, moe_layer, node])
        parent = int(self.reduction_parent[token, moe_layer, node])
        if parent < 0:
            combine_task = token * self.template_task_count + int(
                self.reduction_task_id[layer]
            )
            self._enqueue_task(combine_task, ready)
            return
        self._emit_collective_edge(
            _REDUCTION_TREE_EDGE,
            token,
            layer,
            node,
            parent,
            int(self.reduction_hop_service_ns[layer]),
            ready,
        )

    def _emit_collective_edge(
        self,
        owner: int,
        token: int,
        layer: int,
        source: int,
        destination: int,
        hop_service_ns: int,
        now: int,
    ) -> None:
        pair = source * self.mesh_node_count + destination
        path_start = int(self.deployment.model.hardware_profile.path_ptr[pair])
        path_end = int(self.deployment.model.hardware_profile.path_ptr[pair + 1])
        transfer_id = len(self.transfers)
        self.transfers.append(
            _Transfer(
                owner,
                -1,
                path_end,
                hop_service_ns,
                layer,
                token,
                destination,
            )
        )
        self._enqueue_link(transfer_id, path_start, now)

    def _emit_point_to_point(
        self,
        source: int,
        destination: int,
        successor_task: int,
        hop_service_ns: int,
        layer: int,
        now: int,
    ) -> None:
        pair = source * self.mesh_node_count + destination
        path_start = int(self.deployment.model.hardware_profile.path_ptr[pair])
        path_end = int(self.deployment.model.hardware_profile.path_ptr[pair + 1])
        transfer_id = len(self.transfers)
        self.transfers.append(
            _Transfer(
                _POINT_TO_POINT,
                successor_task,
                path_end,
                hop_service_ns,
                layer,
                -1,
                destination,
            )
        )
        self._enqueue_link(transfer_id, path_start, now)

    def _enqueue_link(self, transfer_id: int, path_index: int, now: int) -> None:
        link = int(self.deployment.model.hardware_profile.path_link_ids[path_index])
        start = max(now, int(self.link_available[link]))
        hop_service_ns = self.transfers[transfer_id].hop_service_ns
        finish = start + hop_service_ns
        wait = start - now
        if self.diagnostics is not None:
            self.diagnostics.transfer_wait_ns += wait
            transfer = self.transfers[transfer_id]
            layer = transfer.layer
            if layer >= 0:
                self.diagnostics.link_work_by_layer_link_ns[layer, link] += (
                    hop_service_ns
                )
                self.diagnostics.link_queue_wait_by_layer_link_ns[layer, link] += wait
            if transfer.owner != _POINT_TO_POINT:
                moe_layer = layer - self.deployment.model.block_table.dense_layers
                self.diagnostics.collective_link_wait_ns_by_token_moe_layer[
                    transfer.token,
                    moe_layer,
                ] += wait
        self.link_available[link] = finish
        if self.resources is not None:
            self.resources.link_busy_ns[link] += hop_service_ns
        if self.diagnostics is not None:
            self.link_queue_depth[link] += 1
            self.diagnostics.max_link_queue_depth = max(
                self.diagnostics.max_link_queue_depth,
                int(self.link_queue_depth[link]),
            )
        self._push_event(
            finish,
            _RELEASE,
            _LINK_RELEASE,
            transfer_id,
            path_index,
        )

    def _release_link(self, transfer_id: int, path_index: int, now: int) -> None:
        link = int(self.deployment.model.hardware_profile.path_link_ids[path_index])
        if self.diagnostics is not None:
            self.link_queue_depth[link] -= 1
        transfer = self.transfers[transfer_id]
        next_path_index = path_index + 1
        if next_path_index < transfer.path_end:
            self._enqueue_link(transfer_id, next_path_index, now)
        elif transfer.owner == _POINT_TO_POINT:
            self._enqueue_task(transfer.successor_task, now)
        elif transfer.owner == _DISPATCH_TREE_EDGE:
            self._release_dispatch_node(
                transfer.token,
                transfer.layer,
                transfer.destination_node,
                now,
            )
        else:
            self._arrive_reduction_node(
                transfer.token,
                transfer.layer,
                transfer.destination_node,
                now,
            )


class _RoundRobinPrefillSimulation(_PrefillSimulation):
    def __init__(self, executor, routes, capture):
        super().__init__(executor, routes, capture)
        self.replica_counter = np.arange(
            len(self.deployment.residency.resident_ptr) - 1, dtype=np.int64
        )

    def _select_moe_residents(self, ranks, input_node, layer):
        selected = np.empty(ranks, dtype=np.int32)
        for rank in range(ranks):
            slot = self.active_slots[rank]
            ptr = self.deployment.residency.resident_ptr
            start, end = ptr[slot], ptr[slot + 1]
            selected[rank] = start + self.replica_counter[slot] % (end - start)
            self.replica_counter[slot] += 1
        return selected
