"""Train-window demand, coactivation and fixed Dense compute work."""

from dataclasses import dataclass

import numpy as np
from deployment import DeploymentModel
from deployment.capacity import ReplicaSpace
from deployment.residency import Residency

REPLICA_WINDOW_SIZE = 256


@dataclass(slots=True)
class ReplicaWorkload:
    demand: np.ndarray
    window_token_count: np.ndarray
    same_layer_coactivation: np.ndarray
    expert_service_ns: np.ndarray
    dense_node_work: np.ndarray


def windowed_route_statistics(
    routes: np.ndarray,
    shared_experts: int,
    routed_experts: int,
    window_size: int = REPLICA_WINDOW_SIZE,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    route_count, moe_layers, top_k = routes.shape
    window_count = (route_count + window_size - 1) // window_size
    demand = np.zeros(
        (window_count, moe_layers, shared_experts + routed_experts),
        dtype=np.int16,
    )
    coactivation = np.zeros(
        (
            moe_layers,
            shared_experts + routed_experts,
            shared_experts + routed_experts,
        ),
        dtype=np.int32,
    )
    route_ids = np.arange(route_count)
    windows = route_ids // window_size
    routed_offset = shared_experts
    routed_routes = routes.astype(np.int16)
    for shared in range(shared_experts):
        np.add.at(demand, (windows, slice(None), shared), 1)
    if shared_experts:
        coactivation[:, :shared_experts, :shared_experts] = route_count
        for shared in range(shared_experts):
            coactivation[:, shared, shared] = 0
    for layer in range(moe_layers):
        for rank in range(top_k):
            routed = routed_routes[:, layer, rank] + routed_offset
            np.add.at(demand, (windows, layer, routed), 1)
            for shared in range(shared_experts):
                np.add.at(coactivation[layer], (shared, routed), 1)
                np.add.at(coactivation[layer], (routed, shared), 1)
            for paired_rank in range(rank + 1, top_k):
                left = routed_routes[:, layer, rank] + routed_offset
                right = routed_routes[:, layer, paired_rank] + routed_offset
                np.add.at(coactivation[layer], (left, right), 1)
                np.add.at(coactivation[layer], (right, left), 1)
    window_tokens = np.minimum(
        window_size,
        route_count - np.arange(window_count) * window_size,
    ).astype(np.int16)
    return demand, window_tokens, coactivation


def compile_replica_workload(
    model: DeploymentModel,
    dense_residency: Residency,
    routes: np.ndarray,
) -> ReplicaWorkload:
    table = model.block_table
    demand, window_tokens, coactivation = windowed_route_statistics(
        routes,
        table.shared_experts,
        table.routed_experts,
        REPLICA_WINDOW_SIZE,
    )
    service_ns = model.expert_service_ns.reshape(
        table.model_layers, table.expert_columns
    )
    dense_node_work = np.zeros(
        (len(window_tokens), model.hardware_profile.mesh_node_count), dtype=np.float64
    )
    token_count = window_tokens.astype(np.float64)
    for layer in range(table.dense_layers):
        slot = table.expert_slot(layer, 0)
        node = int(dense_residency.resident_node[dense_residency.resident_ptr[slot]])
        dense_node_work[:, node] += token_count * service_ns[layer, 0]
    return ReplicaWorkload(
        demand,
        window_tokens,
        coactivation,
        service_ns[table.dense_layers :],
        dense_node_work,
    )


@dataclass(slots=True)
class MappingProblem:
    model: DeploymentModel
    replica_space: ReplicaSpace
    decode_routes: np.ndarray
    prefill_routes: np.ndarray
    workload: ReplicaWorkload


def compile_mapping_problem(
    model: DeploymentModel,
    replica_space: ReplicaSpace,
    decode_routes: np.ndarray,
    prefill_routes: np.ndarray,
) -> MappingProblem:
    return MappingProblem(
        model,
        replica_space,
        decode_routes,
        prefill_routes,
        compile_replica_workload(model, replica_space.dense_residency, prefill_routes),
    )
