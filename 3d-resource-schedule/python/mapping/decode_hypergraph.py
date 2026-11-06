"""Stateful additive hypergraph objective for one-copy Decode Mapping."""

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from numba import njit, prange
from simulation.decode import DecodeExecutor, measure_decode_routes

DECODE_HYPERGRAPH_STALL_NODE_PASSES = 8


class DecodeHypergraph(NamedTuple):
    routes: np.ndarray
    initial_input_node: np.ndarray
    expert_service_ns: np.ndarray
    hop_distance: np.ndarray
    tree_edge_count: np.ndarray
    input_hop_service_ns: np.ndarray
    output_hop_service_ns: np.ndarray
    routed_column_offset: int
    incident_ptr: np.ndarray
    incident_route: np.ndarray
    incident_position_by_route_layer_rank: np.ndarray


class DecodeHypergraphMeasurement(NamedTuple):
    node_serialization_ns: np.ndarray
    mesh_service_ns: np.ndarray
    input_node: np.ndarray
    output_node: np.ndarray

    @property
    def objective_ns(self) -> int:
        return int(self.node_serialization_ns.sum() + self.mesh_service_ns.sum())


class _LayerGainState(NamedTuple):
    measurement: DecodeHypergraphMeasurement
    suffix_ns: np.ndarray
    gain_ns: np.ndarray
    incident_gain_ns: np.ndarray
    locked: np.ndarray


@dataclass(slots=True)
class DecodeHypergraphMove:
    layer: int
    expert: int
    source_node: int
    target_node: int
    predicted_gain_ns: int


@dataclass(slots=True)
class DecodeHypergraphSolution:
    resident_node: np.ndarray
    initial_objective_ns: int
    final_objective_ns: int
    final_sweep_improvement_ns: int
    sweep_count: int
    moves: list[DecodeHypergraphMove]


def compile_decode_hypergraph(
    executor: DecodeExecutor,
    routes: np.ndarray,
) -> tuple[DecodeHypergraph, np.ndarray]:
    """Compile route hyperedges and the current one-copy Node labeling."""
    residents = executor.residents
    dense_layers = residents.dense_layers
    moe_layers = residents.model_layers - dense_layers
    first_slot = dense_layers * residents.expert_columns
    resident_node = residents.resident_node[
        residents.resident_ptr[first_slot:-1]
    ].reshape(moe_layers, residents.expert_columns)
    expert_service_ns = residents.expert_service_ns.reshape(
        residents.model_layers, residents.expert_columns
    )[dense_layers:]

    physical = measure_decode_routes(executor, routes)
    active_expert = np.empty(
        (len(routes), moe_layers, residents.moe_rank_count),
        dtype=np.int16,
    )
    for rank in range(residents.moe_rank_count):
        active_expert[:, :, rank] = (
            rank
            if rank < residents.routed_column_offset
            else routes[:, :, rank - residents.routed_column_offset].astype(np.int16)
            + residents.routed_column_offset
        )
    slot = (
        np.arange(moe_layers, dtype=np.int32)[None, :, None] * residents.expert_columns
        + active_expert
    )
    incident_slot = slot.ravel()
    incident_route = np.broadcast_to(
        np.arange(len(routes), dtype=np.int32)[:, None, None],
        active_expert.shape,
    ).ravel()
    order = np.argsort(incident_slot, kind="stable")
    incident_ptr = np.empty(
        moe_layers * residents.expert_columns + 1,
        dtype=np.int32,
    )
    incident_ptr[0] = 0
    np.cumsum(
        np.bincount(
            incident_slot,
            minlength=moe_layers * residents.expert_columns,
        ),
        out=incident_ptr[1:],
    )
    incident_position = np.empty_like(order)
    incident_position[order] = np.arange(len(order), dtype=np.int64)
    return (
        DecodeHypergraph(
            routes,
            physical.trace.input_node_by_route_layer[:, dense_layers],
            expert_service_ns,
            executor.collective.hop_distance,
            executor.collective.tree_edge_count,
            residents.input_hop_service_ns[dense_layers:],
            residents.output_hop_service_ns[dense_layers:],
            residents.routed_column_offset,
            incident_ptr,
            incident_route[order],
            incident_position.reshape(active_expert.shape),
        ),
        resident_node,
    )


def measure_decode_hypergraph(
    hypergraph: DecodeHypergraph,
    resident_node: np.ndarray,
) -> DecodeHypergraphMeasurement:
    """Measure additive critical serialization and communication time."""
    return DecodeHypergraphMeasurement(
        *_measure_decode_hypergraph(hypergraph, resident_node)
    )


def optimize_decode_hypergraph(
    hypergraph: DecodeHypergraph,
    resident_node: np.ndarray,
    node_capacity: np.ndarray,
) -> DecodeHypergraphSolution:
    """Descend the stateful Hypergraph objective to a neighborhood optimum."""
    initial_objective_ns = measure_decode_hypergraph(
        hypergraph,
        resident_node,
    ).objective_ns
    objective_ns = initial_objective_ns
    final_sweep_improvement_ns = 0
    moves: list[DecodeHypergraphMove] = []
    sweep_count = 0
    while True:
        candidate_node, candidate_moves = _decode_hypergraph_fm_sweep(
            hypergraph,
            resident_node,
            node_capacity,
        )
        if not candidate_moves:
            break
        candidate_objective_ns = measure_decode_hypergraph(
            hypergraph,
            candidate_node,
        ).objective_ns
        if candidate_objective_ns >= objective_ns:
            break
        improvement_ns = objective_ns - candidate_objective_ns
        resident_node = candidate_node
        objective_ns = candidate_objective_ns
        final_sweep_improvement_ns = improvement_ns
        moves.extend(candidate_moves)
        sweep_count += 1
    return DecodeHypergraphSolution(
        resident_node,
        initial_objective_ns,
        objective_ns,
        final_sweep_improvement_ns,
        sweep_count,
        moves,
    )


def _decode_hypergraph_fm_sweep(
    hypergraph: DecodeHypergraph,
    resident_node: np.ndarray,
    node_capacity: np.ndarray,
) -> tuple[np.ndarray, list[DecodeHypergraphMove]]:
    resident_node = resident_node.copy()
    measurement = measure_decode_hypergraph(hypergraph, resident_node)
    sweep_moves = []
    suffix_ns = _decode_hypergraph_suffix(hypergraph, resident_node)
    for layer in range(resident_node.shape[0]):
        resident_node, layer_moves = _decode_hypergraph_fm_layer(
            hypergraph,
            resident_node,
            node_capacity,
            layer,
            measurement,
            suffix_ns[layer + 1],
        )
        if layer_moves:
            sweep_moves.extend(layer_moves)
            measurement = measure_decode_hypergraph(
                hypergraph,
                resident_node,
            )
    return resident_node, sweep_moves


def _decode_hypergraph_fm_layer(
    hypergraph: DecodeHypergraph,
    resident_node: np.ndarray,
    node_capacity: np.ndarray,
    layer: int,
    measurement: DecodeHypergraphMeasurement,
    suffix_ns: np.ndarray,
) -> tuple[np.ndarray, list[DecodeHypergraphMove]]:
    """Return the best positive prefix of one exact conditional FM pass."""
    start = resident_node.copy()
    resident_node = start.copy()
    layer_measurement = DecodeHypergraphMeasurement(
        measurement.node_serialization_ns[:, layer].copy(),
        measurement.mesh_service_ns[:, layer].copy(),
        measurement.input_node[:, layer].copy(),
        measurement.output_node[:, layer].copy(),
    )
    gain_ns, incident_gain_ns = _decode_hypergraph_layer_gain(
        hypergraph, resident_node, layer_measurement, suffix_ns, layer
    )
    locked = np.zeros(resident_node.shape[1], dtype=np.bool_)
    state = _LayerGainState(
        layer_measurement, suffix_ns, gain_ns, incident_gain_ns, locked
    )
    occupancy = np.bincount(
        resident_node.ravel(),
        minlength=len(node_capacity),
    )
    sequence = []
    cumulative_gain_ns = 0
    best_gain_ns = 0
    best_prefix = 0
    for _ in range(resident_node.shape[1]):
        legal_gain = gain_ns.copy()
        legal_gain[locked] = np.iinfo(np.int64).min
        for target_node in range(len(node_capacity)):
            if occupancy[target_node] >= node_capacity[target_node]:
                legal_gain[:, target_node] = np.iinfo(np.int64).min
        legal_gain[
            np.arange(len(locked)),
            resident_node[layer],
        ] = np.iinfo(np.int64).min
        flat_move = int(np.argmax(legal_gain))
        predicted_gain_ns = int(legal_gain.ravel()[flat_move])
        if predicted_gain_ns == np.iinfo(np.int64).min:
            break
        expert, target_node = np.unravel_index(flat_move, legal_gain.shape)
        source_node = int(resident_node[layer, expert])
        resident_node[layer, expert] = target_node
        occupancy[source_node] -= 1
        occupancy[target_node] += 1
        locked[expert] = True
        _update_decode_hypergraph_layer_gain(
            hypergraph, resident_node, state, layer, expert
        )
        move = DecodeHypergraphMove(
            layer,
            int(expert),
            source_node,
            int(target_node),
            predicted_gain_ns,
        )
        sequence.append(move)
        cumulative_gain_ns += predicted_gain_ns
        if cumulative_gain_ns > best_gain_ns:
            best_gain_ns = cumulative_gain_ns
            best_prefix = len(sequence)
        if len(sequence) - best_prefix >= DECODE_HYPERGRAPH_STALL_NODE_PASSES * len(
            node_capacity
        ):
            break
    resident_node = start
    for move in sequence[:best_prefix]:
        resident_node[move.layer, move.expert] = move.target_node
    return resident_node, sequence[:best_prefix]


@njit(cache=True, parallel=True)
def _measure_decode_hypergraph(graph, resident_node):
    routes = graph.routes
    route_count, layer_count, _ = routes.shape
    node_count = graph.hop_distance.shape[0]
    node_serialization_ns = np.empty((route_count, layer_count), dtype=np.int64)
    mesh_service_ns = np.empty_like(node_serialization_ns)
    input_node_by_layer = np.empty_like(node_serialization_ns, dtype=np.int16)
    output_node_by_layer = np.empty_like(node_serialization_ns, dtype=np.int16)
    for route in prange(route_count):
        node_compute = np.empty(node_count, dtype=np.int64)
        node_rank_count = np.empty(node_count, dtype=np.int16)
        last_service = np.empty(node_count, dtype=np.int64)
        node_base = np.empty(node_count, dtype=np.int64)
        input_node = graph.initial_input_node[route]
        for layer in range(layer_count):
            input_node_by_layer[route, layer] = input_node
            terminal_mask = _compile_hyperedge_loads(
                routes[route, layer],
                layer,
                resident_node,
                graph.expert_service_ns,
                graph.routed_column_offset,
                -1,
                -1,
                node_compute,
                node_rank_count,
                last_service,
            )
            serialization, mesh, output = _measure_hyperedge_loads(
                input_node,
                layer,
                node_compute,
                node_rank_count,
                last_service,
                node_base,
                terminal_mask,
                graph.hop_distance,
                graph.tree_edge_count,
                graph.input_hop_service_ns,
                graph.output_hop_service_ns,
            )
            node_serialization_ns[route, layer] = serialization
            mesh_service_ns[route, layer] = mesh
            output_node_by_layer[route, layer] = output
            input_node = output
    return (
        node_serialization_ns,
        mesh_service_ns,
        input_node_by_layer,
        output_node_by_layer,
    )


@njit(cache=True, parallel=True)
def _decode_hypergraph_suffix(graph, resident_node):
    routes = graph.routes
    expert_service_ns = graph.expert_service_ns
    hop_distance = graph.hop_distance
    tree_edge_count = graph.tree_edge_count
    input_hop_service_ns = graph.input_hop_service_ns
    output_hop_service_ns = graph.output_hop_service_ns
    routed_column_offset = graph.routed_column_offset
    route_count, layer_count, _ = routes.shape
    node_count = hop_distance.shape[0]
    suffix_ns = np.zeros(
        (layer_count + 1, route_count, node_count),
        dtype=np.int64,
    )
    for layer in range(layer_count - 1, -1, -1):
        for route in prange(route_count):
            node_compute_ns = np.empty(node_count, dtype=np.int64)
            node_rank_count = np.empty(node_count, dtype=np.int16)
            last_service_ns = np.empty(node_count, dtype=np.int64)
            node_base_ns = np.empty(node_count, dtype=np.int64)
            terminal_mask = _compile_hyperedge_loads(
                routes[route, layer],
                layer,
                resident_node,
                expert_service_ns,
                routed_column_offset,
                -1,
                -1,
                node_compute_ns,
                node_rank_count,
                last_service_ns,
            )
            for input_node in range(node_count):
                serialization_ns, mesh_ns, output_node = _measure_hyperedge_loads(
                    input_node,
                    layer,
                    node_compute_ns,
                    node_rank_count,
                    last_service_ns,
                    node_base_ns,
                    terminal_mask,
                    hop_distance,
                    tree_edge_count,
                    input_hop_service_ns,
                    output_hop_service_ns,
                )
                suffix_ns[layer, route, input_node] = (
                    serialization_ns
                    + mesh_ns
                    + suffix_ns[layer + 1, route, output_node]
                )
    return suffix_ns


@njit(cache=True, parallel=True)
def _decode_hypergraph_layer_gain(graph, resident_node, measured, suffix_ns, layer):
    routes = graph.routes
    incident_ptr = graph.incident_ptr
    incident_route = graph.incident_route
    expert_service_ns = graph.expert_service_ns
    hop_distance = graph.hop_distance
    tree_edge_count = graph.tree_edge_count
    input_hop_service_ns = graph.input_hop_service_ns
    output_hop_service_ns = graph.output_hop_service_ns
    routed_column_offset = graph.routed_column_offset
    input_node = measured.input_node
    node_serialization_ns = measured.node_serialization_ns
    mesh_service_ns = measured.mesh_service_ns
    output_node = measured.output_node
    expert_count = resident_node.shape[1]
    node_count = hop_distance.shape[0]
    gain_ns = np.zeros((expert_count, node_count), dtype=np.int64)
    layer_incident_start = incident_ptr[layer * expert_count]
    layer_incident_end = incident_ptr[(layer + 1) * expert_count]
    incident_gain_ns = np.empty(
        (layer_incident_end - layer_incident_start, node_count),
        dtype=np.int64,
    )
    for candidate in prange(expert_count * node_count):
        target_node = candidate % node_count
        expert = candidate // node_count
        if target_node == resident_node[layer, expert]:
            continue
        node_compute = np.empty(node_count, dtype=np.int64)
        node_rank_count = np.empty(node_count, dtype=np.int16)
        last_service = np.empty(node_count, dtype=np.int64)
        node_base = np.empty(node_count, dtype=np.int64)
        gain = 0
        expert_slot = layer * expert_count + expert
        for incident in range(
            incident_ptr[expert_slot],
            incident_ptr[expert_slot + 1],
        ):
            route = incident_route[incident]
            terminal_mask = _compile_hyperedge_loads(
                routes[route, layer],
                layer,
                resident_node,
                expert_service_ns,
                routed_column_offset,
                expert,
                target_node,
                node_compute,
                node_rank_count,
                last_service,
            )
            candidate_serialization_ns, candidate_mesh_ns, candidate_output = (
                _measure_hyperedge_loads(
                    input_node[route],
                    layer,
                    node_compute,
                    node_rank_count,
                    last_service,
                    node_base,
                    terminal_mask,
                    hop_distance,
                    tree_edge_count,
                    input_hop_service_ns,
                    output_hop_service_ns,
                )
            )
            contribution_ns = (
                node_serialization_ns[route]
                + mesh_service_ns[route]
                + suffix_ns[route, output_node[route]]
                - candidate_serialization_ns
                - candidate_mesh_ns
                - suffix_ns[route, candidate_output]
            )
            incident_gain_ns[
                incident - layer_incident_start,
                target_node,
            ] = contribution_ns
            gain += contribution_ns
        gain_ns[expert, target_node] = gain
    return gain_ns, incident_gain_ns


@njit(cache=True)
def _update_decode_hypergraph_layer_gain(
    graph, resident_node, state, layer, moved_expert
):
    routes = graph.routes
    incident_ptr = graph.incident_ptr
    incident_route = graph.incident_route
    expert_service_ns = graph.expert_service_ns
    hop_distance = graph.hop_distance
    tree_edge_count = graph.tree_edge_count
    input_hop_service_ns = graph.input_hop_service_ns
    output_hop_service_ns = graph.output_hop_service_ns
    routed_column_offset = graph.routed_column_offset
    incident_position_by_route_layer_rank = graph.incident_position_by_route_layer_rank
    input_node = state.measurement.input_node
    node_serialization_ns = state.measurement.node_serialization_ns
    mesh_service_ns = state.measurement.mesh_service_ns
    output_node = state.measurement.output_node
    suffix_ns = state.suffix_ns
    gain_ns = state.gain_ns
    incident_gain_ns = state.incident_gain_ns
    locked = state.locked
    expert_count = resident_node.shape[1]
    node_count = hop_distance.shape[0]
    layer_incident_start = incident_ptr[layer * expert_count]
    moved_slot = layer * expert_count + moved_expert
    node_compute = np.empty(node_count, dtype=np.int64)
    node_rank_count = np.empty(node_count, dtype=np.int16)
    last_service = np.empty(node_count, dtype=np.int64)
    node_base = np.empty(node_count, dtype=np.int64)
    for incident in range(
        incident_ptr[moved_slot],
        incident_ptr[moved_slot + 1],
    ):
        route = incident_route[incident]
        after_terminal_mask = _compile_hyperedge_loads(
            routes[route, layer],
            layer,
            resident_node,
            expert_service_ns,
            routed_column_offset,
            -1,
            -1,
            node_compute,
            node_rank_count,
            last_service,
        )
        after_serialization_ns, after_mesh_ns, after_output = _measure_hyperedge_loads(
            input_node[route],
            layer,
            node_compute,
            node_rank_count,
            last_service,
            node_base,
            after_terminal_mask,
            hop_distance,
            tree_edge_count,
            input_hop_service_ns,
            output_hop_service_ns,
        )
        after_total_ns = (
            after_serialization_ns + after_mesh_ns + suffix_ns[route, after_output]
        )
        rank_count = routed_column_offset + routes.shape[2]
        for rank in range(rank_count):
            expert = (
                rank
                if rank < routed_column_offset
                else routes[route, layer, rank - routed_column_offset]
                + routed_column_offset
            )
            if locked[expert]:
                continue
            for target_node in range(node_count):
                if target_node == resident_node[layer, expert]:
                    continue
                new_terminal_mask = _compile_hyperedge_loads(
                    routes[route, layer],
                    layer,
                    resident_node,
                    expert_service_ns,
                    routed_column_offset,
                    expert,
                    target_node,
                    node_compute,
                    node_rank_count,
                    last_service,
                )
                new_serialization_ns, new_mesh_ns, new_output = (
                    _measure_hyperedge_loads(
                        input_node[route],
                        layer,
                        node_compute,
                        node_rank_count,
                        last_service,
                        node_base,
                        new_terminal_mask,
                        hop_distance,
                        tree_edge_count,
                        input_hop_service_ns,
                        output_hop_service_ns,
                    )
                )
                new_contribution_ns = after_total_ns - (
                    new_serialization_ns + new_mesh_ns + suffix_ns[route, new_output]
                )
                local_incident = (
                    incident_position_by_route_layer_rank[route, layer, rank]
                    - layer_incident_start
                )
                gain_ns[expert, target_node] += (
                    new_contribution_ns - incident_gain_ns[local_incident, target_node]
                )
                incident_gain_ns[local_incident, target_node] = new_contribution_ns
        node_serialization_ns[route] = after_serialization_ns
        mesh_service_ns[route] = after_mesh_ns
        output_node[route] = after_output


@njit(inline="always")
def _compile_hyperedge_loads(
    routed_expert,
    layer,
    resident_node,
    expert_service_ns,
    routed_column_offset,
    moved_expert,
    target_node,
    node_compute_ns,
    node_rank_count,
    last_service_ns,
):
    node_compute_ns[:] = 0
    node_rank_count[:] = 0
    last_service_ns[:] = 0
    terminal_mask = 0
    rank_count = routed_column_offset + len(routed_expert)
    for rank in range(rank_count):
        expert = (
            rank
            if rank < routed_column_offset
            else routed_expert[rank - routed_column_offset] + routed_column_offset
        )
        node = target_node if expert == moved_expert else resident_node[layer, expert]
        service_ns = expert_service_ns[layer, expert]
        terminal_mask |= 1 << node
        node_compute_ns[node] += service_ns
        node_rank_count[node] += 1
        last_service_ns[node] = service_ns
    return terminal_mask


@njit(inline="always")
def _measure_hyperedge_loads(
    input_node,
    layer,
    node_compute_ns,
    node_rank_count,
    last_service_ns,
    node_base_ns,
    terminal_mask,
    hop_distance,
    tree_edge_count,
    input_hop_service_ns,
    output_hop_service_ns,
):
    node_count = len(node_compute_ns)
    for node in range(node_count):
        node_base_ns[node] = (
            hop_distance[input_node, node] * input_hop_service_ns[layer]
            + node_compute_ns[node]
        )
    dispatch_edges = tree_edge_count[
        input_node,
        terminal_mask | (1 << input_node),
    ]
    best_output_node = 0
    best_causal_ns = np.iinfo(np.int64).max
    best_flow_edges = np.iinfo(np.int64).max
    for output_node in range(node_count):
        causal_ns = 0
        for node in range(node_count):
            if node_rank_count[node] == 0:
                continue
            branch_ns = (
                node_base_ns[node]
                + hop_distance[node, output_node] * output_hop_service_ns[layer]
            )
            causal_ns = max(causal_ns, branch_ns)
        reduction_edges = tree_edge_count[
            output_node,
            terminal_mask | (1 << output_node),
        ]
        flow_edges = dispatch_edges + reduction_edges
        if (
            causal_ns < best_causal_ns
            or (causal_ns == best_causal_ns and flow_edges < best_flow_edges)
            or (
                causal_ns == best_causal_ns
                and flow_edges == best_flow_edges
                and output_node < best_output_node
            )
        ):
            best_output_node = output_node
            best_causal_ns = causal_ns
            best_flow_edges = flow_edges

    critical_node = 0
    critical_finish_ns = -1
    for node in range(node_count):
        if node_rank_count[node] == 0:
            continue
        finish_ns = (
            node_base_ns[node]
            + hop_distance[node, best_output_node] * output_hop_service_ns[layer]
        )
        if finish_ns > critical_finish_ns or (
            finish_ns == critical_finish_ns and node < critical_node
        ):
            critical_node = node
            critical_finish_ns = finish_ns

    serialization_ns = node_compute_ns[critical_node] - last_service_ns[critical_node]
    mesh_ns = (
        hop_distance[input_node, critical_node] * input_hop_service_ns[layer]
        + hop_distance[critical_node, best_output_node] * output_hop_service_ns[layer]
    )
    return serialization_ns, mesh_ns, best_output_node
