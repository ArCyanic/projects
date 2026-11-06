"""Physical nearest-copy treatments used by scheduling comparisons."""

import numpy as np
from numba import njit, prange

from simulation.decode.execution import (
    DecodeMeasurement,
    measure_decode_selected_nodes,
    measure_decode_selected_nodes_at_root,
)
from simulation.decode.model import DecodeComponentFacts, resident_range


def measure_nearest_decode_routes(executor, routes, production, dynamic_root):
    """Measure latency and its components with source or dynamic reduction roots."""
    dense_layers = executor.dense_layers
    dense = slice(0, dense_layers)
    components = production.trace.components_by_layer
    names = (
        "expert_compute_ns",
        "node_serialization_ns",
        "mesh_service_ns",
        "collective_contention_ns",
    )
    totals = [getattr(components, name)[:, dense].sum(axis=1) for name in names]
    initial_input = production.trace.input_node_by_route_layer[:, dense_layers]
    latency = totals[0].copy()
    for part in totals[1:]:
        latency += part
    input_node = initial_input.copy()
    for moe_layer in range(routes.shape[1]):
        layer = executor.dense_layers + moe_layer
        selected_node, selected_service = _nearest_selected_nodes(
            executor.residents,
            layer,
            routes[:, moe_layer],
            input_node,
            executor.collective.hop_distance,
        )
        if dynamic_root:
            duration, input_node, layer_components, _ = measure_decode_selected_nodes(
                executor.residents,
                executor.collective,
                layer,
                selected_node,
                selected_service,
                input_node,
            )
        else:
            duration, input_node, layer_components = measure_decode_selected_nodes_at_root(
                executor.residents,
                executor.collective,
                layer,
                selected_node,
                selected_service,
                input_node,
                input_node,
            )
        latency += duration
        for total, name in zip(totals, names, strict=True):
            total += getattr(layer_components, name)
    return DecodeMeasurement(latency, DecodeComponentFacts(*totals), None, executor)


@njit(cache=True, parallel=True)
def _nearest_selected_nodes(residents, layer, active_expert, input_node, hop_distance):
    route_count = len(active_expert)
    rank_count = residents.moe_rank_count
    selected_node = np.empty((route_count, rank_count), dtype=np.int16)
    selected_service = np.empty((route_count, rank_count), dtype=np.int64)
    for route in prange(route_count):
        for rank in range(rank_count):
            expert = (
                rank
                if rank < residents.routed_column_offset
                else active_expert[route, rank - residents.routed_column_offset]
                + residents.routed_column_offset
            )
            slot = layer * residents.expert_columns + expert
            start, end = resident_range(residents, slot)
            best_hops = residents.node_count
            best_node = residents.node_count
            for resident in range(start, end):
                node = residents.resident_node[resident]
                hops = hop_distance[input_node[route], node]
                if hops < best_hops or (hops == best_hops and node < best_node):
                    best_hops = hops
                    best_node = node
            selected_node[route, rank] = best_node
            selected_service[route, rank] = residents.expert_service_ns[slot]
    return selected_node, selected_service
