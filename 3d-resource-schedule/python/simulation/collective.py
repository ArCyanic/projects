"""Shared shortest-path Collective topology for a small 2D Mesh."""

from functools import cache
from typing import NamedTuple

import numpy as np
from numba import njit


class CollectiveTopology(NamedTuple):
    node_count: int
    link_count: int
    hop_distance: np.ndarray
    best_vertex_mask: np.ndarray
    tree_edge_count: np.ndarray
    predecessor_mask: np.ndarray
    link_id: np.ndarray
    diagonal_coordinates: np.ndarray


@cache
def compile_collective_topology(
    grid: tuple[int, int],
) -> CollectiveTopology:
    """Compile canonical minimum-edge shortest-path trees for one Mesh grid."""
    rows, columns = grid
    node_count = rows * columns
    coordinates = np.asarray(
        [divmod(node, columns) for node in range(node_count)],
        dtype=np.int16,
    )
    distance = np.abs(coordinates[:, None] - coordinates[None, :]).sum(axis=2)
    predecessor_mask = np.zeros((node_count, node_count), dtype=np.uint16)
    for root in range(node_count):
        for node in range(node_count):
            for predecessor in range(node_count):
                if (
                    distance[root, predecessor] + 1 == distance[root, node]
                    and distance[predecessor, node] == 1
                ):
                    predecessor_mask[root, node] |= np.uint16(1 << predecessor)

    link_id = np.full((node_count, node_count), -1, dtype=np.int16)
    link = 0
    for source in range(node_count):
        for destination in range(node_count):
            if distance[source, destination] == 1:
                link_id[source, destination] = link
                link += 1

    best_vertex_mask = _compile_best_vertex_masks(predecessor_mask)
    tree_edge_count = _compile_tree_edge_count(best_vertex_mask)
    return CollectiveTopology(
        node_count,
        link,
        distance.astype(np.int8),
        best_vertex_mask,
        tree_edge_count,
        predecessor_mask,
        link_id,
        np.column_stack(
            (coordinates.sum(axis=1), coordinates[:, 0] - coordinates[:, 1])
        ).astype(np.int8),
    )


@njit(inline="always")
def compile_tree_parent(root, terminal_mask, topology, parent):
    """Materialize the canonical tree as one parent per included Node."""
    required = terminal_mask | (1 << root)
    vertices = int(topology.best_vertex_mask[root, required])
    parent[:] = -1
    for node in range(topology.node_count):
        if node == root or vertices & (1 << node) == 0:
            continue
        candidates = int(topology.predecessor_mask[root, node]) & vertices
        parent[node] = _least_node(candidates, topology.node_count)
    return vertices


@njit(inline="always")
def _least_node(mask, node_count):
    for node in range(node_count):
        if mask & (1 << node):
            return node
    return -1


@njit(cache=True)
def _compile_best_vertex_masks(predecessor_mask):
    node_count = predecessor_mask.shape[0]
    mask_count = 1 << node_count
    best = np.empty((node_count, mask_count), dtype=np.uint16)
    cost = np.empty(mask_count, dtype=np.int16)
    for root in range(node_count):
        cost[:] = node_count + 1
        root_bit = 1 << root
        for mask in range(mask_count):
            best[root, mask] = np.uint16(mask)
            if mask & root_bit == 0:
                continue
            feasible = True
            vertices = 0
            for node in range(node_count):
                if mask & (1 << node) == 0:
                    continue
                vertices += 1
                if node != root and predecessor_mask[root, node] & mask == 0:
                    feasible = False
                    break
            if feasible:
                cost[mask] = vertices
        for bit in range(node_count):
            bit_value = 1 << bit
            for mask in range(mask_count):
                if mask & bit_value:
                    continue
                superset = mask | bit_value
                candidate = best[root, superset]
                if cost[superset] < cost[mask] or (
                    cost[superset] == cost[mask] and candidate < best[root, mask]
                ):
                    best[root, mask] = candidate
                    cost[mask] = cost[superset]
    return best


@njit(cache=True)
def _compile_tree_edge_count(best_vertex_mask):
    node_count, mask_count = best_vertex_mask.shape
    tree_edge_count = np.empty((node_count, mask_count), dtype=np.uint8)
    for root in range(node_count):
        for mask in range(mask_count):
            vertices = int(best_vertex_mask[root, mask])
            edges = 0
            for node in range(node_count):
                if node == root or vertices & (1 << node) == 0:
                    continue
                edges += 1
            tree_edge_count[root, mask] = edges
    return tree_edge_count
