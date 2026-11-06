"""Cumulative-work dispatch and geometric reduction roots for Prefill."""

import numpy as np
from numba import njit


@njit(cache=True)
def select_cumulative_work_moe_residents(
    active_slots,
    resident_ptr,
    resident_node,
    expert_service_ns,
    cumulative_compute_work_ns,
    input_hops,
    hop_service_ns,
):
    """Balance assigned work, then input travel time, Node and resident ID."""
    selected = np.empty(len(active_slots), dtype=np.int32)
    working_work = cumulative_compute_work_ns.copy()
    maximum = np.iinfo(np.int64).max
    for rank in range(len(active_slots)):
        slot = active_slots[rank]
        best = (maximum, maximum, len(working_work), len(resident_node))
        for resident in range(resident_ptr[slot], resident_ptr[slot + 1]):
            node = resident_node[resident]
            score = (
                working_work[node] + expert_service_ns[slot],
                input_hops[node] * hop_service_ns,
                node,
                resident,
            )
            if score < best:
                best = score
        selected[rank] = best[3]
        working_work[best[2]] = best[0]
    return selected


@njit(cache=True)
def select_geometry_reduction_root(terminal_mask, topology):
    """Select a minimum-edge, minimum-depth reduction root."""
    selected = 0
    selected_edges = topology.node_count + 1
    selected_depth = topology.node_count + 1
    selected_total = np.iinfo(np.int64).max
    for candidate in range(topology.node_count):
        required = terminal_mask | (1 << candidate)
        edges = int(topology.tree_edge_count[candidate, required])
        depth = 0
        total = 0
        for terminal in range(topology.node_count):
            if terminal_mask & (1 << terminal):
                distance = int(topology.hop_distance[candidate, terminal])
                depth = max(depth, distance)
                total += distance
        if (
            edges < selected_edges
            or (edges == selected_edges and depth < selected_depth)
            or (
                edges == selected_edges
                and depth == selected_depth
                and total < selected_total
            )
            or (
                edges == selected_edges
                and depth == selected_depth
                and total == selected_total
                and candidate < selected
            )
        ):
            selected = candidate
            selected_edges = edges
            selected_depth = depth
            selected_total = total
    return selected
