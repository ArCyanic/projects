"""Canonical Prefill objectives, bottlenecks, and optimization space."""

import numpy as np
from profiler.result import (
    PrefillDiagnostics,
    PrefillObjectives,
    PrefillOptimizationSpace,
    PrefillProfile,
    ReportDepth,
    ResourceBottleneck,
)
from simulation.prefill.telemetry import PrefillExecution


def profile_prefill(
    executions: tuple[PrefillExecution, ...],
    batch_size: int,
    dependency_bound_ns: int,
    depth: ReportDepth,
) -> PrefillProfile:
    makespan = np.asarray(
        [execution.makespan_ns for execution in executions],
        dtype=np.int64,
    )
    token_latency = np.concatenate(
        [execution.token_latency_ns for execution in executions]
    )
    objectives = PrefillObjectives(
        batch_size,
        len(executions),
        float(makespan.mean()),
        float(np.percentile(makespan, 95)),
        float(np.mean(batch_size * 1e9 / makespan)),
        float(np.percentile(token_latency, 50)),
        float(np.percentile(token_latency, 95)),
        float(np.percentile(token_latency, 99)),
    )
    if depth == "objective":
        return PrefillProfile(objectives)

    per_execution = tuple(
        _prefill_projection(execution, dependency_bound_ns) for execution in executions
    )
    objective_time = objectives.makespan_mean_ns
    mean_compute = float(np.mean([item[0] for item in per_execution]))
    peak_compute = float(np.mean([item[1] for item in per_execution]))
    mean_communication = float(np.mean([item[2] for item in per_execution]))
    peak_communication = float(np.mean([item[3] for item in per_execution]))
    dependency = float(per_execution[0][4])
    resource_bound = float(np.mean([item[5] for item in per_execution]))
    bottleneck = ResourceBottleneck(
        objective_time,
        peak_compute,
        peak_communication,
        peak_compute / objective_time,
        peak_communication / objective_time,
    )
    optimization = PrefillOptimizationSpace(
        mean_compute,
        peak_compute,
        mean_compute / objective_time,
        (peak_compute - mean_compute) / objective_time,
        mean_communication,
        peak_communication,
        mean_communication / objective_time,
        (peak_communication - mean_communication) / objective_time,
        dependency,
        objective_time - resource_bound,
        (objective_time - resource_bound) / objective_time,
    )
    diagnostics = _prefill_diagnostics(executions) if depth == "trace" else None
    return PrefillProfile(objectives, bottleneck, optimization, diagnostics)


def profile_prefill_execution(
    execution: PrefillExecution,
    dependency_bound_ns: int,
    depth: ReportDepth = "trace",
) -> PrefillProfile:
    """Project one explicit Prefill execution through the canonical Profiler."""
    return profile_prefill(
        (execution,),
        len(execution.token_latency_ns),
        dependency_bound_ns,
        depth,
    )


def compute_utilization_timeline(
    execution: PrefillExecution,
    edges_ns: np.ndarray,
) -> np.ndarray:
    """Integrate traced compute intervals on shared, possibly nonuniform bins."""
    busy_ns = np.zeros(
        (len(execution.resources.compute_busy_ns), len(edges_ns) - 1),
        dtype=np.float64,
    )
    trace = execution.diagnostics
    for start, finish, node in zip(
        trace.compute_interval_start_ns,
        trace.compute_interval_finish_ns,
        trace.compute_interval_node,
        strict=True,
    ):
        first = int(np.searchsorted(edges_ns, start, side="right") - 1)
        stop = int(np.searchsorted(edges_ns, finish, side="left"))
        for bin_index in range(first, stop):
            busy_ns[node, bin_index] += min(
                finish, edges_ns[bin_index + 1]
            ) - max(start, edges_ns[bin_index])
    return busy_ns / np.diff(edges_ns)


def _prefill_projection(
    execution,
    dependency_bound_ns,
) -> tuple[float, float, float, float, int, int]:
    resources = execution.resources
    mean_compute = float(resources.compute_busy_ns.mean())
    peak_compute = float(resources.compute_busy_ns.max())
    mean_communication = float(resources.link_busy_ns.mean())
    peak_communication = float(resources.link_busy_ns.max())
    resource_bound = max(
        dependency_bound_ns,
        int(peak_compute),
        int(peak_communication),
    )
    return (
        mean_compute,
        peak_compute,
        mean_communication,
        peak_communication,
        dependency_bound_ns,
        resource_bound,
    )


def _prefill_diagnostics(
    executions: tuple[PrefillExecution, ...],
) -> PrefillDiagnostics:
    diagnostics = tuple(execution.diagnostics for execution in executions)
    resources = tuple(execution.resources for execution in executions)
    return PrefillDiagnostics(
        batch_makespan_ns=[execution.makespan_ns for execution in executions],
        aggregate_compute_queue_wait_ns=sum(item.queue_wait_ns for item in diagnostics),
        aggregate_compute_service_ns=sum(item.service_ns for item in diagnostics),
        aggregate_link_queue_wait_ns=sum(item.transfer_wait_ns for item in diagnostics),
        compute_work_by_node_ns=np.sum(
            [item.compute_busy_ns for item in resources],
            axis=0,
        ).tolist(),
        link_work_by_directed_link_ns=np.sum(
            [item.link_busy_ns for item in resources],
            axis=0,
        ).tolist(),
        max_compute_queue_depth=max(
            item.max_compute_queue_depth for item in diagnostics
        ),
        max_link_queue_depth=max(item.max_link_queue_depth for item in diagnostics),
        resident_binding_count=np.sum(
            [item.resident_binding_count for item in diagnostics],
            axis=0,
        ).tolist(),
        reduction_executions_by_layer_node=np.sum(
            [item.reduction_executions_by_layer_node for item in diagnostics],
            axis=0,
        ).tolist(),
        moe_input_count=np.sum(
            [item.moe_input_count for item in diagnostics],
            axis=0,
        ).tolist(),
        moe_binding_count=np.sum(
            [item.moe_binding_count for item in diagnostics],
            axis=0,
        ).tolist(),
        input_node_by_token_moe_layer=np.concatenate(
            [item.input_node_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        reduction_node_by_token_moe_layer=np.concatenate(
            [item.reduction_node_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        compute_work_by_layer_node_ns=np.sum(
            [item.compute_work_by_layer_node_ns for item in diagnostics],
            axis=0,
        ).tolist(),
        compute_queue_wait_by_layer_node_ns=np.sum(
            [item.compute_queue_wait_by_layer_node_ns for item in diagnostics],
            axis=0,
        ).tolist(),
        link_work_by_layer_link_ns=np.sum(
            [item.link_work_by_layer_link_ns for item in diagnostics],
            axis=0,
        ).tolist(),
        link_queue_wait_by_layer_link_ns=np.sum(
            [item.link_queue_wait_by_layer_link_ns for item in diagnostics],
            axis=0,
        ).tolist(),
        layer_release_ns_by_token=np.concatenate(
            [item.layer_release_ns_by_token for item in diagnostics],
            axis=0,
        ).tolist(),
        layer_finish_ns_by_token=np.concatenate(
            [item.layer_finish_ns_by_token for item in diagnostics],
            axis=0,
        ).tolist(),
        terminal_count_by_token_moe_layer=np.concatenate(
            [item.terminal_count_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        dispatch_tree_edges_by_token_moe_layer=np.concatenate(
            [item.dispatch_tree_edges_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        reduction_tree_edges_by_token_moe_layer=np.concatenate(
            [item.reduction_tree_edges_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        collective_link_wait_ns_by_token_moe_layer=np.concatenate(
            [item.collective_link_wait_ns_by_token_moe_layer for item in diagnostics],
            axis=0,
        ).tolist(),
        compute_interval_start_ns_by_window=[
            item.compute_interval_start_ns for item in diagnostics
        ],
        compute_interval_finish_ns_by_window=[
            item.compute_interval_finish_ns for item in diagnostics
        ],
        compute_interval_node_by_window=[
            item.compute_interval_node for item in diagnostics
        ],
        compute_interval_token_by_window=[
            item.compute_interval_token for item in diagnostics
        ],
        event_count=sum(item.event_count for item in diagnostics),
    )
