"""Typed Performance Profiler results and their canonical JSON projection."""

from dataclasses import dataclass, fields

from simulation.workload import ReportDepth


@dataclass(slots=True)
class DecodeObjectives:
    latency_mean_ns: float
    latency_median_ns: float
    latency_p95_ns: float
    latency_p99_ns: float
    latency_min_ns: int
    latency_max_ns: int


@dataclass(slots=True)
class PrefillObjectives:
    batch_size: int
    batch_count: int
    makespan_mean_ns: float
    makespan_p95_ns: float
    throughput_mean_tokens_s: float
    token_latency_p50_ns: float
    token_latency_p95_ns: float
    token_latency_p99_ns: float


@dataclass(slots=True)
class ResourceBottleneck:
    objective_time_ns: float
    compute_resource_bound_ns: float
    communication_resource_bound_ns: float
    compute_pressure: float
    communication_pressure: float


@dataclass(slots=True)
class DecodeBottleneck:
    objective_time_ns: float
    expert_compute_ns: float
    node_serialization_ns: float
    mesh_service_ns: float
    collective_contention_ns: float
    compute_pressure: float
    communication_pressure: float


@dataclass(slots=True)
class DecodeStructuralComparison:
    critical_serialization_count: float
    serialization_heuristic_reference_count: float
    critical_hops: float
    communication_reference_hops: int
    structural_reference_latency_ns: float


@dataclass(slots=True)
class PrefillOptimizationSpace:
    mean_compute_work_ns: float
    peak_compute_work_ns: float
    compute_service_exposure: float
    compute_balance_headroom: float
    mean_communication_work_ns: float
    peak_communication_work_ns: float
    communication_service_exposure: float
    communication_balance_headroom: float
    dependency_bound_ns: float
    execution_residual_ns: float
    execution_headroom: float


@dataclass(slots=True)
class DecodeDiagnostics:
    decode_component_by_layer_ns: list[list[float]]
    critical_serialization_count_by_layer: list[float]
    critical_hops_by_layer: list[float]
    collective_link_wait_by_layer_ns: list[float]
    input_node_by_route_layer: list[list[int]]
    output_node_by_route_layer: list[list[int]]
    replica_count_by_moe_layer_expert: list[list[int]]
    node_occupancy: list[int]
    resident_binding_count: list[dict[str, int]]


@dataclass(slots=True)
class PrefillDiagnostics:
    batch_makespan_ns: list[int]
    aggregate_compute_queue_wait_ns: int
    aggregate_compute_service_ns: int
    aggregate_link_queue_wait_ns: int
    compute_work_by_node_ns: list[int]
    link_work_by_directed_link_ns: list[int]
    max_compute_queue_depth: int
    max_link_queue_depth: int
    resident_binding_count: list[int]
    reduction_executions_by_layer_node: list[list[int]]
    moe_input_count: list[list[list[int]]]
    moe_binding_count: list[list[list[int]]]
    input_node_by_token_moe_layer: list[list[int]]
    reduction_node_by_token_moe_layer: list[list[int]]
    compute_work_by_layer_node_ns: list[list[int]]
    compute_queue_wait_by_layer_node_ns: list[list[int]]
    link_work_by_layer_link_ns: list[list[int]]
    link_queue_wait_by_layer_link_ns: list[list[int]]
    layer_release_ns_by_token: list[list[int]]
    layer_finish_ns_by_token: list[list[int]]
    terminal_count_by_token_moe_layer: list[list[int]]
    dispatch_tree_edges_by_token_moe_layer: list[list[int]]
    reduction_tree_edges_by_token_moe_layer: list[list[int]]
    collective_link_wait_ns_by_token_moe_layer: list[list[int]]
    compute_interval_start_ns_by_window: list[list[int]]
    compute_interval_finish_ns_by_window: list[list[int]]
    compute_interval_node_by_window: list[list[int]]
    compute_interval_token_by_window: list[list[int]]
    event_count: int


@dataclass(slots=True)
class DecodeProfile:
    objectives: DecodeObjectives
    bottleneck: DecodeBottleneck | None = None
    structural_comparison: DecodeStructuralComparison | None = None
    diagnostics: DecodeDiagnostics | None = None


@dataclass(slots=True)
class PrefillProfile:
    objectives: PrefillObjectives
    bottleneck: ResourceBottleneck | None = None
    optimization_space: PrefillOptimizationSpace | None = None
    diagnostics: PrefillDiagnostics | None = None


@dataclass(slots=True)
class ProfilingResult:
    hardware_profile_id: str
    decode_route_count: int
    report_depth: ReportDepth
    decode: DecodeProfile
    prefill: tuple[PrefillProfile, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "performance-profiler-v4",
            "hardware_profile_id": self.hardware_profile_id,
            "decode_route_count": self.decode_route_count,
            "report_depth": self.report_depth,
            "decode": _decode_payload(self.decode),
            "prefill": [_prefill_payload(profile) for profile in self.prefill],
        }


def _decode_payload(profile: DecodeProfile) -> dict[str, object]:
    payload: dict[str, object] = {
        "objectives": _record_payload(profile.objectives),
    }
    if profile.bottleneck is not None:
        payload["bottleneck"] = _record_payload(profile.bottleneck)
        payload["structural_comparison"] = _record_payload(
            profile.structural_comparison
        )
    if profile.diagnostics is not None:
        payload["diagnostics"] = _record_payload(profile.diagnostics)
    return payload


def _prefill_payload(profile: PrefillProfile) -> dict[str, object]:
    objectives = _record_payload(profile.objectives)
    payload: dict[str, object] = {
        "batch_size": objectives.pop("batch_size"),
        "objectives": objectives,
    }
    if profile.bottleneck is not None:
        payload["bottleneck"] = _record_payload(profile.bottleneck)
        payload["optimization_space"] = _record_payload(profile.optimization_space)
    if profile.diagnostics is not None:
        payload["diagnostics"] = _record_payload(profile.diagnostics)
    return payload


def _record_payload(record) -> dict[str, object]:
    return {field.name: getattr(record, field.name) for field in fields(record)}
