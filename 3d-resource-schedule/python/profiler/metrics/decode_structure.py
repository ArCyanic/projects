"""Dual-axis structural comparison for Decode Mapping."""

import numpy as np
from numba import njit, prange
from profiler.result import DecodeStructuralComparison
from simulation.decode import DecodeExecutor, DecodeMeasurement


def measure_decode_structural_comparison(
    evaluator: DecodeExecutor,
    routes: np.ndarray,
    measurement: DecodeMeasurement,
) -> DecodeStructuralComparison:
    """Compare current critical structure with the dual-axis reference."""
    reference_by_layer = serialization_reference_by_layer(evaluator, routes)
    facts = measurement.trace
    route_count = len(routes)
    moe = slice(evaluator.dense_layers, evaluator.model_layers)
    critical_serialization_count = float(
        facts.critical_serialization_count_by_route_layer[:, moe].sum() / route_count
    )
    critical_hops = float(
        facts.critical_hops_by_route_layer[:, moe].sum() / route_count
    )
    serialization_heuristic_reference_count = float(reference_by_layer.sum())
    communication_reference_hops = 2 * (evaluator.model_layers - evaluator.dense_layers)
    structural_reference_latency_ns = _structural_reference_latency_ns(
        evaluator,
        measurement,
        reference_by_layer,
    )
    return DecodeStructuralComparison(
        critical_serialization_count,
        serialization_heuristic_reference_count,
        critical_hops,
        communication_reference_hops,
        structural_reference_latency_ns,
    )


def _structural_reference_latency_ns(
    evaluator: DecodeExecutor,
    measurement: DecodeMeasurement,
    serialization_reference_count_by_layer: np.ndarray,
) -> float:
    compiled = evaluator.residents
    components = measurement.trace.components_by_layer
    dense = slice(0, compiled.dense_layers)
    moe = slice(compiled.dense_layers, compiled.model_layers)
    route_count = len(measurement.latency_ns)
    dense_ns = (
        sum(
            values[:, dense].sum()
            for values in (
                components.expert_compute_ns,
                components.node_serialization_ns,
                components.mesh_service_ns,
                components.collective_contention_ns,
            )
        )
        / route_count
    )
    moe_expert_ns = components.expert_compute_ns[:, moe].sum() / route_count
    service_ns = np.empty(len(serialization_reference_count_by_layer))
    for moe_layer in range(len(service_ns)):
        model_layer = compiled.dense_layers + moe_layer
        slot = model_layer * compiled.expert_columns
        service_ns[moe_layer] = compiled.expert_service_ns[slot]
    serialization_ns = float(np.dot(serialization_reference_count_by_layer, service_ns))
    communication_ns = float(
        (compiled.input_hop_service_ns[moe] + compiled.output_hop_service_ns[moe]).sum()
    )
    return float(dense_ns + moe_expert_ns + serialization_ns + communication_ns)


def serialization_reference_by_layer(
    evaluator: DecodeExecutor,
    routes: np.ndarray,
) -> np.ndarray:
    """Build the replica-aware serialization reference for every MoE layer."""
    compiled = evaluator.residents
    layer_count = compiled.model_layers - compiled.dense_layers
    active = np.empty(
        (len(routes), layer_count, compiled.moe_rank_count),
        dtype=np.int16,
    )
    active[:, :, : compiled.routed_column_offset] = np.arange(
        compiled.routed_column_offset,
        dtype=np.int16,
    )
    active[:, :, compiled.routed_column_offset :] = (
        routes.astype(np.int16) + compiled.routed_column_offset
    )
    replica_count = np.diff(compiled.resident_ptr).reshape(
        compiled.model_layers,
        compiled.expert_columns,
    )[compiled.dense_layers :]
    return _replica_aware_serialization_reference(
        active,
        replica_count,
        compiled.node_count,
    )


@njit(cache=True, parallel=True)
def _replica_aware_serialization_reference(active, replica_count, node_count):
    route_count, layer_count, rank_count = active.shape
    expert_count = replica_count.shape[1]
    reference = np.empty(layer_count, dtype=np.float64)
    for layer in prange(layer_count):
        frequency = np.zeros(expert_count, dtype=np.int64)
        coactivation = np.zeros((expert_count, expert_count), dtype=np.int64)
        for route in range(route_count):
            for left in range(rank_count):
                left_expert = active[route, layer, left]
                frequency[left_expert] += 1
                for right in range(left + 1, rank_count):
                    right_expert = active[route, layer, right]
                    coactivation[left_expert, right_expert] += 1
                    coactivation[right_expert, left_expert] += 1

        placement = np.zeros((expert_count, node_count), dtype=np.bool_)
        remaining = replica_count[layer].copy()
        node_demand = np.zeros(node_count, dtype=np.float64)
        for _ in range(remaining.sum()):
            expert = -1
            for candidate in range(expert_count):
                if remaining[candidate] == 0:
                    continue
                if expert < 0 or (
                    frequency[candidate] * replica_count[layer, expert]
                    > frequency[expert] * replica_count[layer, candidate]
                ):
                    expert = candidate
            target = -1
            target_conflict = 0.0
            for node in range(node_count):
                if placement[expert, node]:
                    continue
                conflict = 0.0
                for colocated in range(expert_count):
                    if placement[colocated, node]:
                        conflict += coactivation[expert, colocated] / (
                            replica_count[layer, expert]
                            * replica_count[layer, colocated]
                        )
                if (
                    target < 0
                    or conflict < target_conflict
                    or (
                        conflict == target_conflict
                        and node_demand[node] < node_demand[target]
                    )
                ):
                    target = node
                    target_conflict = conflict
            placement[expert, target] = True
            node_demand[target] += frequency[expert] / replica_count[layer, expert]
            remaining[expert] -= 1

        serialization = 0
        selected_rank = np.empty(rank_count, dtype=np.bool_)
        node_load = np.empty(node_count, dtype=np.int16)
        for route in range(route_count):
            selected_rank[:] = False
            node_load[:] = 0
            for _ in range(rank_count):
                rank = -1
                for candidate in range(rank_count):
                    if selected_rank[candidate]:
                        continue
                    if rank < 0:
                        rank = candidate
                        continue
                    candidate_expert = active[route, layer, candidate]
                    rank_expert = active[route, layer, rank]
                    if replica_count[layer, candidate_expert] < replica_count[
                        layer, rank_expert
                    ] or (
                        replica_count[layer, candidate_expert]
                        == replica_count[layer, rank_expert]
                        and candidate_expert < rank_expert
                    ):
                        rank = candidate
                selected_rank[rank] = True
                expert = active[route, layer, rank]
                node = -1
                for candidate in range(node_count):
                    if placement[expert, candidate] and (
                        node < 0 or node_load[candidate] < node_load[node]
                    ):
                        node = candidate
                node_load[node] += 1
            serialization += node_load.max() - 1
        reference[layer] = serialization / route_count
    return reference
