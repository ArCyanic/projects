"""Decode bottleneck metrics derived from online route bindings."""

import numpy as np
from profiler.metrics.decode_structure import (
    measure_decode_structural_comparison,
)
from profiler.result import (
    DecodeBottleneck,
    DecodeDiagnostics,
    DecodeObjectives,
    DecodeProfile,
    DecodeStructuralComparison,
    ReportDepth,
)
from simulation.statistics import latency_summary
from simulation.decode import (
    DecodeExecutor,
    DecodeMeasurement,
)


def _decode_objectives(latency_array) -> DecodeObjectives:
    summary = latency_summary(latency_array)
    median, p99 = np.percentile(latency_array, (50, 99))
    return DecodeObjectives(
        summary["mean_ns"],
        float(median),
        summary["p95_ns"],
        float(p99),
        int(latency_array.min()),
        int(latency_array.max()),
    )


def profile_decode_measurement(
    routes: np.ndarray, measurement: DecodeMeasurement, depth: ReportDepth
) -> DecodeProfile:
    if depth == "objective":
        return DecodeProfile(_decode_objectives(measurement.latency_ns))

    latency_ns, bottleneck, structural_comparison, diagnostics = _decode_projection(
        routes,
        measurement,
        depth == "trace",
    )
    objectives = _decode_objectives(latency_ns)
    return DecodeProfile(
        objectives,
        bottleneck,
        structural_comparison,
        diagnostics if depth == "trace" else None,
    )


def _decode_projection(
    routes,
    measurement: DecodeMeasurement,
    collect_diagnostics: bool,
) -> tuple[
    np.ndarray,
    DecodeBottleneck,
    DecodeStructuralComparison,
    DecodeDiagnostics | None,
]:
    """Project batched critical-path facts into Decode metrics."""
    evaluator = measurement.context
    components = measurement.components
    expert_compute_ns = int(components.expert_compute_ns.sum())
    node_serialization_ns = int(components.node_serialization_ns.sum())
    mesh_service_ns = int(components.mesh_service_ns.sum())
    collective_contention_ns = int(components.collective_contention_ns.sum())
    critical_path_ns = int(measurement.latency_ns.sum())
    route_count = len(routes)
    objective_time_ns = critical_path_ns / route_count
    bottleneck = DecodeBottleneck(
        objective_time_ns,
        expert_compute_ns / route_count,
        node_serialization_ns / route_count,
        mesh_service_ns / route_count,
        collective_contention_ns / route_count,
        (expert_compute_ns + node_serialization_ns) / critical_path_ns,
        (mesh_service_ns + collective_contention_ns) / critical_path_ns,
    )
    structural_comparison = measure_decode_structural_comparison(
        evaluator,
        routes,
        measurement,
    )
    diagnostics = (
        _decode_diagnostics(evaluator, measurement) if collect_diagnostics else None
    )
    return measurement.latency_ns, bottleneck, structural_comparison, diagnostics


def _decode_diagnostics(
    evaluator: DecodeExecutor,
    measurement: DecodeMeasurement,
) -> DecodeDiagnostics:
    compiled = evaluator.residents
    facts = measurement.trace
    route_count = len(measurement.latency_ns)
    layer_components = facts.components_by_layer
    component_by_layer = np.stack(
        (
            layer_components.expert_compute_ns.sum(axis=0),
            layer_components.node_serialization_ns.sum(axis=0),
            layer_components.mesh_service_ns.sum(axis=0),
            layer_components.collective_contention_ns.sum(axis=0),
        ),
        axis=1,
    )
    critical_hops_by_layer = facts.critical_hops_by_route_layer.mean(axis=0)
    critical_serialization_count_by_layer = (
        facts.critical_serialization_count_by_route_layer.mean(axis=0)
    )
    resident_ids = facts.selected_resident_by_route_layer_rank.ravel()
    resident_ids = resident_ids[resident_ids >= 0]
    residents, binding_counts = np.unique(resident_ids, return_counts=True)
    moe = slice(compiled.dense_layers, compiled.model_layers)
    replica_count = np.diff(compiled.resident_ptr).reshape(
        compiled.model_layers,
        compiled.expert_columns,
    )[moe]
    return DecodeDiagnostics(
        (component_by_layer / route_count).tolist(),
        critical_serialization_count_by_layer.tolist(),
        critical_hops_by_layer.tolist(),
        facts.link_wait_ns_by_route_layer.mean(axis=0).tolist(),
        facts.input_node_by_route_layer.tolist(),
        facts.output_node_by_route_layer.tolist(),
        replica_count.tolist(),
        np.bincount(compiled.resident_node, minlength=compiled.node_count).tolist(),
        [
            {"resident_id": int(resident), "count": int(count)}
            for resident, count in zip(residents, binding_counts, strict=True)
        ],
    )
