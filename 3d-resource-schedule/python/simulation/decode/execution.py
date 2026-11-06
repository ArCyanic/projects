"""Decode multicast and reduction on a small 2D Mesh."""

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from numba import njit, prange

from simulation.collective import (
    CollectiveTopology,
    compile_collective_topology,
    compile_tree_parent,
)
from simulation.workload import ReportDepth
from simulation.decode.model import (
    DecodeComponentFacts,
    DecodeResidentTable,
    compile_decode_resident_table,
    resident_range,
)


class DecodeExecutor(NamedTuple):
    residents: DecodeResidentTable
    collective: CollectiveTopology

    @property
    def model_layers(self) -> int:
        return self.residents.model_layers

    @property
    def dense_layers(self) -> int:
        return self.residents.dense_layers

    @property
    def moe_rank_count(self) -> int:
        return self.residents.moe_rank_count

    @property
    def node_count(self) -> int:
        return self.residents.node_count


class DecodeCriticalPathWorkspace(NamedTuple):
    dispatch_parent: np.ndarray
    reduction_parent: np.ndarray
    reduction_ready: np.ndarray
    node_compute: np.ndarray


class DecodeCollectiveLayerPlan(NamedTuple):
    input_node: int
    output_node: int
    terminal_mask: int
    dispatch_parent: np.ndarray
    reduction_parent: np.ndarray


class DecodeLayerStructure(NamedTuple):
    critical_serialization_count: np.ndarray
    critical_hops: np.ndarray
    collective_contention_ns: np.ndarray


@dataclass(slots=True)
class DecodeTrace:
    components_by_layer: DecodeComponentFacts
    input_node_by_route_layer: np.ndarray
    output_node_by_route_layer: np.ndarray
    selected_resident_by_route_layer_rank: np.ndarray
    link_wait_ns_by_route_layer: np.ndarray
    critical_hops_by_route_layer: np.ndarray
    critical_serialization_count_by_route_layer: np.ndarray


@dataclass(slots=True)
class DecodeMeasurement:
    latency_ns: np.ndarray
    components: DecodeComponentFacts
    trace: DecodeTrace | None
    context: DecodeExecutor


def compile_decode_executor(deployment) -> DecodeExecutor:
    """Compile the canonical Decode Collective evaluator."""
    residents = compile_decode_resident_table(deployment.model, deployment.residency)
    collective = compile_collective_topology(
        deployment.model.hardware_profile.grid,
    )
    return DecodeExecutor(residents, collective)


def measure_decode_selected_nodes(
    evaluator: DecodeResidentTable,
    collective: CollectiveTopology,
    layer: int,
    selected_node: np.ndarray,
    selected_service_ns: np.ndarray,
    input_node: np.ndarray,
) -> tuple[
    np.ndarray,
    np.ndarray,
    DecodeComponentFacts,
    DecodeLayerStructure,
]:
    """Measure fixed terminal Nodes with the best Collective root and trees."""
    duration, output, components, structure = _measure_decode_selected_nodes(
        selected_node,
        selected_service_ns,
        input_node,
        evaluator,
        collective,
        layer,
    )
    return (
        duration,
        output,
        DecodeComponentFacts(*components.T),
        DecodeLayerStructure(*structure.T),
    )


def measure_decode_selected_nodes_at_root(
    evaluator: DecodeResidentTable,
    collective: CollectiveTopology,
    layer: int,
    selected_node: np.ndarray,
    selected_service_ns: np.ndarray,
    input_node: np.ndarray,
    output_node: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, DecodeComponentFacts]:
    """Measure fixed terminal Nodes and fixed reduction roots."""
    duration, components = _measure_decode_selected_nodes_at_root(
        selected_node,
        selected_service_ns,
        input_node,
        output_node,
        evaluator,
        collective,
        layer,
    )
    return duration, output_node.copy(), DecodeComponentFacts(*components.T)


def evaluate_decode_moe_layer_causal_routes(
    evaluator: DecodeResidentTable,
    collective: CollectiveTopology,
    layer: int,
    active_expert: np.ndarray,
    input_node: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Evaluate the selected causal branch without scheduling links."""
    return _evaluate_decode_moe_layer_causal_routes(
        active_expert,
        input_node,
        evaluator,
        collective,
        layer,
    )


def measure_decode_routes(
    executor: DecodeExecutor,
    routes: np.ndarray,
    depth: ReportDepth = "trace",
) -> DecodeMeasurement:
    """Execute Decode with aggregate facts and optional Collective diagnostics."""
    capture_trace = depth != "objective"
    measured = _measure_decode_collective_routes(
        routes, executor.residents, executor.collective, capture_trace
    )
    trace = None
    if capture_trace:
        by_layer = DecodeComponentFacts(*(measured[2][..., part] for part in range(4)))
        trace = DecodeTrace(by_layer, *measured[3:])
    return DecodeMeasurement(
        measured[0], DecodeComponentFacts(*measured[1].T), trace, executor
    )


@njit(inline="always")
def _select_dense_resident(
    compiled,
    collective,
    layer,
    input_node,
    input_ready,
):
    expert_slot = layer * compiled.expert_columns
    start, end = resident_range(compiled, expert_slot)
    selected = start
    selected_finish = np.iinfo(np.int64).max
    selected_node = compiled.node_count
    selected_start = input_ready
    for resident in range(start, end):
        node = compiled.resident_node[resident]
        compute_start = (
            input_ready
            + collective.hop_distance[input_node, node]
            * compiled.input_hop_service_ns[layer]
        )
        finish = compute_start + compiled.expert_service_ns[expert_slot]
        if finish < selected_finish or (
            finish == selected_finish and node < selected_node
        ):
            selected = resident
            selected_finish = finish
            selected_node = node
            selected_start = compute_start
    return selected, selected_node, selected_start, selected_finish


@njit(inline="always")
def _evaluate_decode_collective_route(
    route,
    compiled,
    collective,
    components_by_layer,
    input_node_by_layer,
    output_node_by_layer,
    selected_resident_by_layer_rank,
    link_wait_ns_by_layer,
    critical_hops_by_layer,
    critical_serialization_count_by_layer,
    capture_trace,
):
    ranks = compiled.moe_rank_count
    selected_resident = np.empty(ranks, dtype=np.int32)
    active_column = np.empty(ranks, dtype=np.int16)
    selected_node = np.empty(ranks, dtype=np.int16)
    selected_service_ns = np.empty(ranks, dtype=np.int64)
    input_node = 0
    input_ready = 0
    workspace = _allocate_decode_critical_path_workspace(collective)

    for layer in range(compiled.model_layers):
        layer_start = input_ready
        layer_source = input_node
        components_by_layer[layer] = 0
        if capture_trace:
            input_node_by_layer[layer] = input_node
            selected_resident_by_layer_rank[layer] = -1
            link_wait_ns_by_layer[layer] = 0
            critical_hops_by_layer[layer] = 0
            critical_serialization_count_by_layer[layer] = 0
        if layer < compiled.dense_layers:
            resident, input_node, compute_start, input_ready = _select_dense_resident(
                compiled, collective, layer, input_node, input_ready
            )
            components_by_layer[layer, 0] = compiled.expert_service_ns[
                layer * compiled.expert_columns
            ]
            components_by_layer[layer, 2] = compute_start - layer_start
            if capture_trace:
                output_node_by_layer[layer] = input_node
                selected_resident_by_layer_rank[layer, 0] = resident
                critical_hops_by_layer[layer] = collective.hop_distance[
                    layer_source, input_node
                ]
            continue

        for rank in range(ranks):
            active_column[rank] = (
                rank
                if rank < compiled.routed_column_offset
                else route[
                    layer - compiled.dense_layers, rank - compiled.routed_column_offset
                ]
                + compiled.routed_column_offset
            )
        output_node, _ = _select_collective_layer_decision(
            active_column,
            compiled,
            collective,
            layer,
            input_node,
            selected_resident,
            selected_node,
            selected_service_ns,
            workspace,
        )
        plan = _compile_collective_plan(
            selected_node,
            collective,
            input_node,
            output_node,
            workspace.dispatch_parent,
            workspace.reduction_parent,
        )
        input_ready, link_wait = _evaluate_collective_critical_path(
            selected_node,
            selected_service_ns,
            compiled.input_hop_service_ns[layer],
            compiled.output_hop_service_ns[layer],
            collective.hop_distance,
            input_ready,
            plan,
            workspace,
        )
        (
            components_by_layer[layer, 0],
            components_by_layer[layer, 1],
            components_by_layer[layer, 2],
            components_by_layer[layer, 3],
            critical_dispatch_hops,
            critical_return_hops,
            critical_serialization,
        ) = _collective_critical_components(
            selected_node,
            selected_service_ns,
            compiled,
            collective,
            layer,
            plan,
            input_ready - layer_start,
            workspace.node_compute,
        )
        input_node = output_node
        if capture_trace:
            selected_resident_by_layer_rank[layer] = selected_resident
            output_node_by_layer[layer] = output_node
            link_wait_ns_by_layer[layer] = link_wait
            critical_hops_by_layer[layer] = (
                critical_dispatch_hops + critical_return_hops
            )
            critical_serialization_count_by_layer[layer] = critical_serialization
    return input_ready


@njit(inline="always")
def _collective_critical_components(
    selected_node,
    selected_service_ns,
    compiled,
    collective,
    layer,
    plan,
    duration_ns,
    node_compute,
):
    critical_node = 0
    critical_finish = -1
    for node in range(compiled.node_count):
        if node_compute[node] == 0:
            continue
        dispatch_hops = collective.hop_distance[plan.input_node, node]
        return_hops = collective.hop_distance[node, plan.output_node]
        finish = (
            dispatch_hops * compiled.input_hop_service_ns[layer]
            + node_compute[node]
            + return_hops * compiled.output_hop_service_ns[layer]
        )
        if finish > critical_finish or (
            finish == critical_finish and node < critical_node
        ):
            critical_finish = finish
            critical_node = node

    critical_rank = 0
    critical_serialization_count = -1
    for rank in range(len(selected_node)):
        if selected_node[rank] == critical_node:
            critical_rank = rank
            critical_serialization_count += 1
    expert_compute = selected_service_ns[critical_rank]
    node_serialization = node_compute[critical_node] - expert_compute
    dispatch_hops = collective.hop_distance[plan.input_node, critical_node]
    return_hops = collective.hop_distance[critical_node, plan.output_node]
    mesh_service = (
        dispatch_hops * compiled.input_hop_service_ns[layer]
        + return_hops * compiled.output_hop_service_ns[layer]
    )
    collective_contention = (
        duration_ns - expert_compute - node_serialization - mesh_service
    )
    return (
        expert_compute,
        node_serialization,
        mesh_service,
        collective_contention,
        dispatch_hops,
        return_hops,
        critical_serialization_count,
    )


@njit(cache=True, parallel=True)
def _measure_decode_collective_routes(routes, compiled, collective, capture_trace):
    route_count = len(routes)
    captured_routes = route_count if capture_trace else 0
    layers = compiled.model_layers
    latency_ns = np.empty(route_count, dtype=np.int64)
    components = np.empty((route_count, 4), dtype=np.int64)
    layer_components = np.empty((captured_routes, layers, 4), dtype=np.int64)
    inputs = np.empty((captured_routes, layers), dtype=np.int16)
    outputs = np.empty_like(inputs)
    selected = np.empty(
        (captured_routes, layers, compiled.moe_rank_count), dtype=np.int32
    )
    link_wait = np.empty((captured_routes, layers), dtype=np.int64)
    hops = np.empty_like(inputs)
    serialization = np.empty_like(inputs)
    uncaptured_i16 = np.empty(0, dtype=np.int16)
    uncaptured_i32 = np.empty((0, compiled.moe_rank_count), dtype=np.int32)
    uncaptured_i64 = np.empty(0, dtype=np.int64)
    for route in prange(route_count):
        by_layer = np.empty((layers, 4), dtype=np.int64)
        latency_ns[route] = _evaluate_decode_collective_route(
            routes[route],
            compiled,
            collective,
            by_layer,
            inputs[route] if capture_trace else uncaptured_i16,
            outputs[route] if capture_trace else uncaptured_i16,
            selected[route] if capture_trace else uncaptured_i32,
            link_wait[route] if capture_trace else uncaptured_i64,
            hops[route] if capture_trace else uncaptured_i16,
            serialization[route] if capture_trace else uncaptured_i16,
            capture_trace,
        )
        components[route] = by_layer.sum(axis=0)
        if capture_trace:
            layer_components[route] = by_layer
    return (
        latency_ns,
        components,
        layer_components,
        inputs,
        outputs,
        selected,
        link_wait,
        hops,
        serialization,
    )


@njit(inline="always")
def _compile_collective_plan(
    selected_node,
    collective,
    input_node,
    output_node,
    dispatch_parent,
    reduction_parent,
):
    terminal_mask = 0
    for rank in range(len(selected_node)):
        terminal_mask |= 1 << selected_node[rank]
    compile_tree_parent(
        input_node,
        terminal_mask,
        collective,
        dispatch_parent,
    )
    compile_tree_parent(
        output_node,
        terminal_mask,
        collective,
        reduction_parent,
    )
    return DecodeCollectiveLayerPlan(
        input_node,
        output_node,
        terminal_mask,
        dispatch_parent,
        reduction_parent,
    )


@njit(inline="always")
def _root_latency_bounds(node_compute, compiled, collective, layer, input_node):
    """Four affine terms of the weighted Manhattan maximum over compute Nodes."""
    lower = np.iinfo(np.int64).min
    pp = pm = mp = mm = lower
    ready_max = 0
    input_service = compiled.input_hop_service_ns[layer]
    output_service = compiled.output_hop_service_ns[layer]
    for node in range(compiled.node_count):
        if node_compute[node] == 0:
            continue
        ready = (
            collective.hop_distance[input_node, node] * input_service
            + node_compute[node]
        )
        ready_max = max(ready_max, ready)
        p = collective.diagonal_coordinates[node, 0] * output_service
        q = collective.diagonal_coordinates[node, 1] * output_service
        pp = max(pp, ready - p)
        pm = max(pm, ready - q)
        mp = max(mp, ready + q)
        mm = max(mm, ready + p)
    return ready_max, pp, pm, mp, mm


@njit(inline="always")
def _root_latency(bounds, collective, output_node, output_service):
    if bounds[0] == 0:
        return 0
    p = collective.diagonal_coordinates[output_node, 0] * output_service
    q = collective.diagonal_coordinates[output_node, 1] * output_service
    return max(bounds[1] + p, bounds[2] + q, bounds[3] - q, bounds[4] - p)


@njit(inline="always")
def _select_collective_root(
    bounds, terminal_mask, compiled, collective, layer, input_node, limit
):
    dispatch_edges = np.int64(
        collective.tree_edge_count[input_node, terminal_mask | (1 << input_node)]
    )
    best = (np.iinfo(np.int64).max, np.iinfo(np.int64).max, 0)
    for root in range(compiled.node_count):
        latency = _root_latency(
            bounds, collective, root, compiled.output_hop_service_ns[layer]
        )
        if latency > limit:
            continue
        edges = dispatch_edges + np.int64(
            collective.tree_edge_count[root, terminal_mask | (1 << root)]
        )
        score = (latency, edges, root)
        # Numba requires direct comparison for tuple minima.
        best = score if score < best else best  # noqa: FURB136
    return best


@njit(inline="always")
def _binding_less(selected_node, selected_resident, best_resident, resident_node):
    for rank in range(len(selected_node)):
        incumbent = resident_node[best_resident[rank]]
        if selected_node[rank] != incumbent:
            return selected_node[rank] < incumbent
    # Preserve the original mixed-radix order when Node assignments coincide.
    for rank in range(len(selected_resident) - 1, -1, -1):
        if selected_resident[rank] != best_resident[rank]:
            return selected_resident[rank] < best_resident[rank]
    return False


@njit(inline="always")
def _select_collective_layer_decision(
    active_column,
    compiled,
    collective,
    layer,
    input_node,
    selected_resident,
    selected_node,
    selected_service_ns,
    workspace,
):
    ranks = len(active_column)
    node_compute = workspace.node_compute
    node_compute[:] = 0
    order = np.empty(ranks, dtype=np.int16)
    variable_count = 0
    terminal_mask = 0
    for rank in range(ranks):
        slot = layer * compiled.expert_columns + active_column[rank]
        start, end = resident_range(compiled, slot)
        if end - start == 1:
            node = compiled.resident_node[start]
            selected_resident[rank] = start
            selected_node[rank] = node
            selected_service_ns[rank] = compiled.expert_service_ns[slot]
            node_compute[node] += selected_service_ns[rank]
            terminal_mask |= 1 << node
        else:
            position = variable_count
            while position:
                previous_slot = (
                    layer * compiled.expert_columns + active_column[order[position - 1]]
                )
                previous_start, previous_end = resident_range(compiled, previous_slot)
                if previous_end - previous_start <= end - start:
                    break
                order[position] = order[position - 1]
                position -= 1
            order[position] = rank
            variable_count += 1
    fixed_bounds = _root_latency_bounds(
        node_compute, compiled, collective, layer, input_node
    )
    if variable_count == 0:
        latency, _, root = _select_collective_root(
            fixed_bounds,
            terminal_mask,
            compiled,
            collective,
            layer,
            input_node,
            np.iinfo(np.int64).max,
        )
        return root, latency
    next_choice = np.zeros(variable_count, dtype=np.int16)
    bounds = np.empty((variable_count + 1, 5), dtype=np.int64)
    bounds[0] = fixed_bounds
    best_output_node = 0
    best_causal = np.iinfo(np.int64).max
    best_flow_edges = np.iinfo(np.int64).max
    best_resident = np.empty(ranks, dtype=np.int32)
    input_service = compiled.input_hop_service_ns[layer]
    output_service = compiled.output_hop_service_ns[layer]
    depth = 0
    while depth >= 0:
        rank = order[depth]
        expert_slot = layer * compiled.expert_columns + active_column[rank]
        start, end = resident_range(compiled, expert_slot)
        if next_choice[depth] == end - start:
            next_choice[depth] = 0
            depth -= 1
            if depth >= 0:
                parent = order[depth]
                node_compute[selected_node[parent]] -= selected_service_ns[parent]
            continue
        choice = next_choice[depth]
        next_choice[depth] += 1
        resident = start + choice
        node = compiled.resident_node[resident]
        service = compiled.expert_service_ns[expert_slot]
        selected_resident[rank] = resident
        selected_node[rank] = node
        selected_service_ns[rank] = service
        node_compute[node] += service
        current = bounds[depth + 1]
        current[:] = bounds[depth]
        if node_compute[node]:
            ready = (
                collective.hop_distance[input_node, node] * input_service
                + node_compute[node]
            )
            p = collective.diagonal_coordinates[node, 0] * output_service
            q = collective.diagonal_coordinates[node, 1] * output_service
            current[0] = max(current[0], ready)
            current[1] = max(current[1], ready - p)
            current[2] = max(current[2], ready - q)
            current[3] = max(current[3], ready + q)
            current[4] = max(current[4], ready + p)
        lower = (
            0
            if current[0] == 0
            else max(
                (current[1] + current[4] + 1) // 2,
                (current[2] + current[3] + 1) // 2,
            )
        )
        if lower <= best_causal:
            if depth + 1 < variable_count:
                depth += 1
                continue
            terminal_mask = 0
            for terminal in selected_node:
                terminal_mask |= 1 << terminal
            score = _select_collective_root(
                current,
                terminal_mask,
                compiled,
                collective,
                layer,
                input_node,
                best_causal,
            )
            incumbent = (best_causal, best_flow_edges, best_output_node)
            if score < incumbent or (
                score == incumbent
                and _binding_less(
                    selected_node,
                    selected_resident,
                    best_resident,
                    compiled.resident_node,
                )
            ):
                best_causal, best_flow_edges, best_output_node = score
                best_resident[:] = selected_resident
        node_compute[node] -= service
    for rank in range(ranks):
        expert_slot = layer * compiled.expert_columns + active_column[rank]
        resident = best_resident[rank]
        selected_resident[rank] = resident
        selected_node[rank] = compiled.resident_node[resident]
        selected_service_ns[rank] = compiled.expert_service_ns[expert_slot]
    return best_output_node, best_causal


@njit(cache=True, parallel=True)
def _measure_decode_selected_nodes(
    selected_node,
    selected_service_ns,
    input_node,
    compiled,
    collective,
    layer,
):
    route_count, _ = selected_node.shape
    duration_ns = np.empty(route_count, dtype=np.int64)
    output_node = np.empty(route_count, dtype=np.int16)
    components = np.empty((route_count, 4), dtype=np.int64)
    structure = np.empty((route_count, 3), dtype=np.int64)
    for route in prange(route_count):
        workspace = _allocate_decode_critical_path_workspace(collective)
        # A local array alias keeps parfor's accumulation visible to root scoring.
        node_compute = workspace.node_compute
        node_compute[:] = 0
        terminal_mask = 0
        for rank in range(selected_node.shape[1]):
            node = selected_node[route, rank]
            node_compute[node] += selected_service_ns[route, rank]
            terminal_mask |= 1 << node
        bounds = _root_latency_bounds(
            node_compute,
            compiled,
            collective,
            layer,
            input_node[route],
        )
        _, _, best_output = _select_collective_root(
            bounds,
            terminal_mask,
            compiled,
            collective,
            layer,
            input_node[route],
            np.iinfo(np.int64).max,
        )

        measured = _measure_selected_route(
            selected_node[route],
            selected_service_ns[route],
            input_node[route],
            best_output,
            compiled,
            collective,
            layer,
            workspace,
        )
        duration_ns[route] = measured[0]
        output_node[route] = best_output
        components[route, 0] = measured[1]
        components[route, 1] = measured[2]
        components[route, 2] = measured[3]
        components[route, 3] = measured[4]
        structure[route, 0] = measured[7]
        structure[route, 1] = measured[5] + measured[6]
        structure[route, 2] = measured[4]
    return duration_ns, output_node, components, structure


@njit(cache=True, parallel=True)
def _measure_decode_selected_nodes_at_root(
    selected_node,
    selected_service_ns,
    input_node,
    output_node,
    compiled,
    collective,
    layer,
):
    route_count = len(selected_node)
    duration_ns = np.empty(route_count, dtype=np.int64)
    components = np.empty((route_count, 4), dtype=np.int64)
    for route in prange(route_count):
        workspace = _allocate_decode_critical_path_workspace(collective)
        measured = _measure_selected_route(
            selected_node[route],
            selected_service_ns[route],
            input_node[route],
            output_node[route],
            compiled,
            collective,
            layer,
            workspace,
        )
        duration_ns[route] = measured[0]
        components[route, 0] = measured[1]
        components[route, 1] = measured[2]
        components[route, 2] = measured[3]
        components[route, 3] = measured[4]
    return duration_ns, components


@njit(inline="always")
def _measure_selected_route(
    selected_node,
    selected_service_ns,
    input_node,
    output_node,
    compiled,
    collective,
    layer,
    workspace,
):
    plan = _compile_collective_plan(
        selected_node,
        collective,
        input_node,
        output_node,
        workspace.dispatch_parent,
        workspace.reduction_parent,
    )
    duration, _ = _evaluate_collective_critical_path(
        selected_node,
        selected_service_ns,
        compiled.input_hop_service_ns[layer],
        compiled.output_hop_service_ns[layer],
        collective.hop_distance,
        0,
        plan,
        workspace,
    )
    facts = _collective_critical_components(
        selected_node,
        selected_service_ns,
        compiled,
        collective,
        layer,
        plan,
        duration,
        workspace.node_compute,
    )
    return (
        duration,
        facts[0],
        facts[1],
        facts[2],
        facts[3],
        facts[4],
        facts[5],
        facts[6],
    )


@njit(cache=True, parallel=True)
def _evaluate_decode_moe_layer_causal_routes(
    active_expert,
    input_node,
    compiled,
    collective,
    layer,
):
    route_count = len(active_expert)
    duration_ns = np.empty(route_count, dtype=np.int64)
    output_node = np.empty(route_count, dtype=np.int16)
    for route in prange(route_count):
        ranks = compiled.moe_rank_count
        active_column = np.empty(ranks, dtype=np.int16)
        selected_resident = np.empty(ranks, dtype=np.int32)
        selected_node = np.empty(ranks, dtype=np.int16)
        selected_service_ns = np.empty(ranks, dtype=np.int64)
        workspace = _allocate_decode_critical_path_workspace(collective)
        for rank in range(ranks):
            active_column[rank] = (
                rank
                if rank < compiled.routed_column_offset
                else active_expert[route, rank - compiled.routed_column_offset]
                + compiled.routed_column_offset
            )
        output, causal = _select_collective_layer_decision(
            active_column,
            compiled,
            collective,
            layer,
            input_node[route],
            selected_resident,
            selected_node,
            selected_service_ns,
            workspace,
        )
        duration_ns[route] = causal
        output_node[route] = output
    return duration_ns, output_node


@njit(cache=True)
def _evaluate_collective_critical_path(
    selected_node,
    selected_service_ns,
    input_hop_ns,
    output_hop_ns,
    hop_distance,
    layer_start,
    plan,
    workspace,
):
    """Evaluate the two-tree DAG for equal-size MoE input and output vectors.

    Positive expert compute times put input transfers before result transfers
    on every shared directed link. The result transfer therefore has both
    reduction dependencies and the completed input transfer as predecessors.
    """
    node_count = len(workspace.node_compute)
    workspace.node_compute[:] = 0
    for rank in range(len(selected_node)):
        workspace.node_compute[selected_node[rank]] += selected_service_ns[rank]
    workspace.reduction_ready[:] = layer_start
    for node in range(node_count):
        if plan.terminal_mask & (1 << node):
            workspace.reduction_ready[node] += (
                hop_distance[plan.input_node, node] * input_hop_ns
                + workspace.node_compute[node]
            )
    waiting = 0
    # Every reduction parent is one hop closer to the root.
    for depth in range(hop_distance[plan.output_node].max(), 0, -1):
        for node in range(node_count):
            parent = plan.reduction_parent[node]
            if parent < 0 or hop_distance[plan.output_node, node] != depth:
                continue
            ready = workspace.reduction_ready[node]
            start = ready
            if plan.dispatch_parent[parent] == node:
                input_finish = (
                    layer_start + hop_distance[plan.input_node, parent] * input_hop_ns
                )
                start = max(start, input_finish)
            waiting += start - ready
            workspace.reduction_ready[parent] = max(
                workspace.reduction_ready[parent], start + output_hop_ns
            )
    return workspace.reduction_ready[plan.output_node], waiting


@njit(inline="always")
def _allocate_decode_critical_path_workspace(collective):
    node_count = collective.node_count
    return DecodeCriticalPathWorkspace(
        np.empty(node_count, dtype=np.int16),
        np.empty(node_count, dtype=np.int16),
        np.empty(node_count, dtype=np.int64),
        np.empty(node_count, dtype=np.int64),
    )
