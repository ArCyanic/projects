"""Capture-specific state and raw facts for Prefill execution."""

from dataclasses import dataclass

import numpy as np
from deployment import Deployment
from simulation.workload import ReportDepth


@dataclass(slots=True)
class PrefillResourceFacts:
    compute_busy_ns: np.ndarray
    link_busy_ns: np.ndarray


@dataclass(slots=True)
class PrefillTrace:
    moe_input_count: np.ndarray
    moe_binding_count: np.ndarray
    queue_wait_ns: int
    service_ns: int
    transfer_wait_ns: int
    max_compute_queue_depth: int
    max_link_queue_depth: int
    resident_binding_count: np.ndarray
    event_count: int
    reduction_executions_by_layer_node: np.ndarray
    input_node_by_token_moe_layer: np.ndarray
    reduction_node_by_token_moe_layer: np.ndarray
    layer_release_ns_by_token: np.ndarray
    layer_finish_ns_by_token: np.ndarray
    compute_work_by_layer_node_ns: np.ndarray
    compute_queue_wait_by_layer_node_ns: np.ndarray
    link_work_by_layer_link_ns: np.ndarray
    link_queue_wait_by_layer_link_ns: np.ndarray
    terminal_count_by_token_moe_layer: np.ndarray
    dispatch_tree_edges_by_token_moe_layer: np.ndarray
    reduction_tree_edges_by_token_moe_layer: np.ndarray
    collective_link_wait_ns_by_token_moe_layer: np.ndarray
    compute_interval_start_ns: list[int]
    compute_interval_finish_ns: list[int]
    compute_interval_node: list[int]
    compute_interval_token: list[int]


@dataclass(slots=True)
class PrefillExecution:
    token_latency_ns: np.ndarray
    resources: PrefillResourceFacts | None
    diagnostics: PrefillTrace | None

    @property
    def makespan_ns(self) -> int:
        return int(self.token_latency_ns.max())


def allocate_prefill_execution(
    capture: ReportDepth,
    deployment: Deployment,
    token_count: int,
    link_count: int,
) -> PrefillExecution:
    layer_count = deployment.model.block_table.model_layers
    mesh_node_count = deployment.model.hardware_profile.mesh_node_count
    resources = (
        PrefillResourceFacts(
            np.zeros(mesh_node_count, dtype=np.int64),
            np.zeros(link_count, dtype=np.int64),
        )
        if capture != "objective"
        else None
    )

    moe_layers = layer_count - deployment.model.block_table.dense_layers
    diagnostics = None
    if capture == "trace":
        layer_token_shape = (token_count, layer_count)
        layer_node_shape = (layer_count, mesh_node_count)
        layer_link_shape = (layer_count, link_count)
        token_moe_layer_shape = (token_count, moe_layers)
        moe_shape = (
            moe_layers,
            deployment.model.block_table.expert_columns,
            mesh_node_count,
        )
        diagnostics = PrefillTrace(
            moe_input_count=np.zeros(moe_shape, dtype=np.int32),
            moe_binding_count=np.zeros(moe_shape, dtype=np.int32),
            queue_wait_ns=0,
            service_ns=0,
            transfer_wait_ns=0,
            max_compute_queue_depth=0,
            max_link_queue_depth=0,
            resident_binding_count=np.zeros(
                deployment.residency.resident_count,
                dtype=np.int64,
            ),
            event_count=0,
            reduction_executions_by_layer_node=np.zeros(
                layer_node_shape,
                dtype=np.int64,
            ),
            input_node_by_token_moe_layer=np.full(
                token_moe_layer_shape,
                -1,
                dtype=np.int8,
            ),
            reduction_node_by_token_moe_layer=np.full(
                token_moe_layer_shape,
                -1,
                dtype=np.int8,
            ),
            layer_release_ns_by_token=np.zeros(
                layer_token_shape,
                dtype=np.int64,
            ),
            layer_finish_ns_by_token=np.zeros(
                layer_token_shape,
                dtype=np.int64,
            ),
            compute_work_by_layer_node_ns=np.zeros(
                layer_node_shape,
                dtype=np.int64,
            ),
            compute_queue_wait_by_layer_node_ns=np.zeros(
                layer_node_shape,
                dtype=np.int64,
            ),
            link_work_by_layer_link_ns=np.zeros(
                layer_link_shape,
                dtype=np.int64,
            ),
            link_queue_wait_by_layer_link_ns=np.zeros(
                layer_link_shape,
                dtype=np.int64,
            ),
            terminal_count_by_token_moe_layer=np.zeros(
                token_moe_layer_shape,
                dtype=np.uint8,
            ),
            dispatch_tree_edges_by_token_moe_layer=np.zeros(
                token_moe_layer_shape,
                dtype=np.uint8,
            ),
            reduction_tree_edges_by_token_moe_layer=np.zeros(
                token_moe_layer_shape,
                dtype=np.uint8,
            ),
            collective_link_wait_ns_by_token_moe_layer=np.zeros(
                token_moe_layer_shape,
                dtype=np.int64,
            ),
            compute_interval_start_ns=[],
            compute_interval_finish_ns=[],
            compute_interval_node=[],
            compute_interval_token=[],
        )
    return PrefillExecution(
        np.zeros(token_count, dtype=np.int64),
        resources,
        diagnostics,
    )
