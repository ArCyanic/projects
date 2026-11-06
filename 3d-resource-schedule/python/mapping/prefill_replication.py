"""Add Prefill replicas to frozen Decode Residency slots."""

import numpy as np
from deployment.residency import (
    Residency,
    moe_nodes_from_residency,
    replace_moe_residents,
)
from mapping.workload import ReplicaWorkload
from model import BlockTable
from numba import njit, prange


def augment_prefill_replicas(
    seed: Residency,
    block_table: BlockTable,
    workload: ReplicaWorkload,
    remaining_capacity: np.ndarray,
    replica_budget: int,
) -> Residency:
    """Add the requested copies by minimizing projected peak Node work."""
    node_count = len(remaining_capacity)
    moe = moe_nodes_from_residency(seed, block_table, node_count)
    moe_layers, moe_experts, _ = moe.shape
    resident_count = moe.sum(axis=2).astype(np.int16)
    capacity = remaining_capacity.astype(np.int32)
    applied_count = 0

    demand = workload.demand.astype(np.float64)
    scenario_scale = 1 / workload.window_token_count.astype(np.float64)
    service_ns = workload.expert_service_ns.astype(np.float64)
    node_work = workload.dense_node_work.copy()
    for layer in range(moe_layers):
        for expert in range(moe_experts):
            nodes = np.flatnonzero(moe[layer, expert])
            share = (
                demand[:, layer, expert]
                * service_ns[layer, expert]
                / resident_count[layer, expert]
            )
            node_work[:, nodes] += share[:, None]

    while applied_count < replica_budget:
        score = _score_replica_actions(
            moe,
            resident_count,
            capacity,
            demand,
            service_ns,
            node_work,
            scenario_scale,
        )
        actions = []
        for _ in range(node_count):
            flat_index = int(np.argmax(score))
            if not np.isfinite(score.ravel()[flat_index]):
                break
            layer_expert, node = divmod(int(flat_index), node_count)
            layer, expert = divmod(layer_expert, moe_experts)
            actions.append((layer, expert, node))
            score[layer, expert] = -np.inf
            score[:, :, node] = -np.inf

        applied = 0
        for layer, expert, node in actions:
            if applied_count == replica_budget:
                break
            if capacity[node] == 0:
                continue
            _apply_replica_action(
                layer,
                expert,
                node,
                moe,
                int(resident_count[layer, expert]),
                demand,
                service_ns,
                node_work,
            )
            moe[layer, expert, node] = True
            resident_count[layer, expert] += 1
            capacity[node] -= 1
            applied_count += 1
            applied += 1
        if not applied:
            break

    return replace_moe_residents(seed, block_table, moe)


@njit(cache=True, parallel=True)
def _score_replica_actions(
    moe: np.ndarray,
    resident_count: np.ndarray,
    remaining_capacity: np.ndarray,
    demand: np.ndarray,
    service_ns: np.ndarray,
    node_work: np.ndarray,
    scenario_scale: np.ndarray,
) -> np.ndarray:
    score = np.full(moe.shape, -np.inf, dtype=np.float64)
    for layer in prange(moe.shape[0]):
        for expert in range(moe.shape[1]):
            count = int(resident_count[layer, expert])
            if count == moe.shape[2]:
                continue
            gain = np.zeros(moe.shape[2], dtype=np.float64)
            for scenario in range(demand.shape[0]):
                total_work = demand[scenario, layer, expert] * service_ns[layer, expert]
                old_share = total_work / count
                new_share = total_work / (count + 1)
                current_peak = 0.0
                projected_base_peak = 0.0
                for node in range(moe.shape[2]):
                    current = node_work[scenario, node]
                    projected = current
                    if moe[layer, expert, node]:
                        projected += new_share - old_share
                    current_peak = max(current_peak, current)
                    projected_base_peak = max(projected_base_peak, projected)
                for node in range(moe.shape[2]):
                    if moe[layer, expert, node] or remaining_capacity[node] == 0:
                        continue
                    projected_peak = max(
                        projected_base_peak,
                        node_work[scenario, node] + new_share,
                    )
                    gain[node] += scenario_scale[scenario] * (
                        current_peak - projected_peak
                    )
            for node in range(moe.shape[2]):
                if not moe[layer, expert, node] and remaining_capacity[node] > 0:
                    score[layer, expert, node] = gain[node]
    return score


@njit(cache=True)
def _apply_replica_action(
    layer: int,
    expert: int,
    node: int,
    moe: np.ndarray,
    resident_count: int,
    demand: np.ndarray,
    service_ns: np.ndarray,
    node_work: np.ndarray,
) -> None:
    for scenario in range(demand.shape[0]):
        total_work = demand[scenario, layer, expert] * service_ns[layer, expert]
        old_share = total_work / resident_count
        new_share = total_work / (resident_count + 1)
        for physical_node in range(moe.shape[2]):
            if moe[layer, expert, physical_node]:
                node_work[scenario, physical_node] += new_share - old_share
        node_work[scenario, node] += new_share
