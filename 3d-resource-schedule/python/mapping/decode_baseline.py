"""One-copy placement balanced by complete Dense and MoE compute work."""

import numpy as np
from deployment.residency import (
    Residency,
    replace_moe_residents,
)
from mapping.workload import ReplicaWorkload
from model import BlockTable


def build_full_workload_baseline(
    block_table: BlockTable,
    dense_residency: Residency,
    workload: ReplicaWorkload,
    node_capacity: np.ndarray,
) -> Residency:
    """Balance one-copy compute work including the fixed Dense placement."""
    demand = workload.demand.sum(axis=0) * workload.expert_service_ns
    coactivation = workload.same_layer_coactivation
    layer_count, expert_count = demand.shape
    node_count = len(node_capacity)
    resident = np.zeros((layer_count, expert_count, node_count), dtype=np.bool_)
    occupancy = np.zeros(node_count, dtype=np.int32)
    node_demand = workload.dense_node_work.sum(axis=0).astype(np.int64)

    for layer in range(layer_count):
        for expert in np.lexsort((np.arange(expert_count), -demand[layer])):
            node = min(
                (
                    node
                    for node in range(node_count)
                    if occupancy[node] < node_capacity[node]
                ),
                key=lambda node: (
                    node_demand[node],
                    coactivation[layer, expert, resident[layer, :, node]].sum(),
                    occupancy[node],
                    node,
                ),
            )
            resident[layer, expert, node] = True
            occupancy[node] += 1
            node_demand[node] += demand[layer, expert]

    return replace_moe_residents(dense_residency, block_table, resident)
