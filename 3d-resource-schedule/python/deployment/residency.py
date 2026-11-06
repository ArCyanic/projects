"""Canonical CSR Residency and MoE-node materialization."""

from dataclasses import dataclass

import numpy as np
from model import BlockTable


@dataclass(slots=True)
class Residency:
    resident_ptr: np.ndarray
    resident_node: np.ndarray

    @property
    def resident_count(self) -> int:
        return len(self.resident_node)


def build_dense_residency(
    block_table: BlockTable,
    grid: tuple[int, int],
) -> Residency:
    """Build the fixed Dense Residency."""
    node_count = grid[0] * grid[1]
    active = np.zeros(
        (block_table.expert_slot_count, node_count),
        dtype=np.bool_,
    )
    dense_ordinal = np.arange(block_table.dense_layers, dtype=np.int32)
    dense_slot = dense_ordinal * block_table.expert_columns
    active[dense_slot, dense_ordinal % node_count] = True

    return _residency_from_node_mask(active)


def replace_moe_residents(
    residency: Residency,
    block_table: BlockTable,
    moe_node: np.ndarray,
) -> Residency:
    """Replace all MoE residents while preserving fixed Dense Residency."""
    node_count = moe_node.shape[2]
    active = _residency_node_mask(residency, block_table, node_count)
    active[block_table.dense_layers * block_table.expert_columns :] = moe_node.reshape(
        -1, node_count
    )
    return _residency_from_node_mask(active)


def _residency_node_mask(
    residency: Residency,
    block_table: BlockTable,
    node_count: int,
) -> np.ndarray:
    resident_count = np.diff(residency.resident_ptr)
    active = np.zeros(
        (block_table.expert_slot_count, node_count),
        dtype=np.bool_,
    )
    active[
        np.repeat(np.arange(block_table.expert_slot_count), resident_count),
        residency.resident_node,
    ] = True
    return active


def _residency_from_node_mask(active: np.ndarray) -> Residency:
    resident_ptr = np.empty(len(active) + 1, dtype=np.int32)
    resident_ptr[0] = 0
    np.cumsum(active.sum(axis=1), out=resident_ptr[1:])
    return Residency(
        resident_ptr,
        np.nonzero(active)[1].astype(np.int8),
    )


def moe_nodes_from_residency(
    residency: Residency,
    block_table: BlockTable,
    node_count: int,
) -> np.ndarray:
    """Extract complete MoE resident sets from the canonical CSR."""
    active = _residency_node_mask(residency, block_table, node_count)
    return active[block_table.dense_layers * block_table.expert_columns :].reshape(
        block_table.model_layers - block_table.dense_layers,
        block_table.expert_columns,
        node_count,
    )
