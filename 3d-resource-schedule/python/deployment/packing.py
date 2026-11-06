"""Direct CSR 3D packing for static deployments."""

from dataclasses import dataclass

import numpy as np
from hardware_profile import HardwareProfile
from model import BLOCK_KINDS, BlockTable
from numba import njit

from deployment.residency import Residency
from deployment.weight_cubes import WeightCubeTable


@dataclass(slots=True)
class PackedWeightCubes:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    height: np.ndarray
    width: np.ndarray
    d_w: np.ndarray
    weight_cube_id: np.ndarray
    node_utilization: np.ndarray
    layer_utilization: np.ndarray

    @property
    def weight_cube_count(self) -> int:
        return len(self.z)


def _resident_boxes(
    residency: Residency, table: BlockTable
) -> tuple[np.ndarray, np.ndarray]:
    templates = (
        np.repeat(
            table.template_id.reshape(-1, BLOCK_KINDS),
            np.diff(residency.resident_ptr),
            axis=0,
        )
        .ravel()
        .astype(np.int32)
    )
    nodes = np.repeat(residency.resident_node, BLOCK_KINDS).astype(np.int16)
    return templates, nodes


def pack_residency(
    residency: Residency,
    block_table: BlockTable,
    weight_cubes: WeightCubeTable,
    hardware_profile: HardwareProfile,
) -> PackedWeightCubes:
    """Pack resident blocks and restore their canonical order once."""
    node_count = hardware_profile.mesh_node_count
    depth = hardware_profile.subcube_depth
    layer_height = hardware_profile.subcube_height
    layer_width = hardware_profile.subcube_width
    cube_id, nodes = _resident_boxes(residency, block_table)
    height = weight_cubes.height[cube_id]
    width = weight_cubes.width[cube_id]
    d_w = weight_cubes.d_w[cube_id]
    x, y, z, accepted, order = _pack_weight_cubes(
        nodes,
        height,
        width,
        d_w,
        node_count,
        depth,
        layer_height,
        layer_width,
        hardware_profile.unit_cube_height,
        hardware_profile.unit_cube_width,
    )
    if not accepted:
        raise ValueError("Residency does not fit the selected Hardware Profile")
    inverse = np.argsort(order)
    x, y, z = x[inverse], y[inverse], z[inverse]
    area = _physical_layer_area(node_count, depth, nodes, z, height, width, d_w)
    layer_capacity = layer_height * layer_width
    return PackedWeightCubes(
        x,
        y,
        z,
        height.astype(np.uint16),
        width.astype(np.uint16),
        d_w,
        cube_id,
        area.sum(axis=1) / (depth * layer_capacity),
        area / layer_capacity,
    )


def _physical_layer_area(
    node_count: int,
    subcube_depth: int,
    cube_node: np.ndarray,
    z: np.ndarray,
    height: np.ndarray,
    width: np.ndarray,
    cube_d_w: np.ndarray,
) -> np.ndarray:
    layer_area = np.zeros((node_count, subcube_depth), dtype=np.int64)
    footprint = height.astype(np.int64) * width.astype(np.int64)
    for depth_offset in range(int(cube_d_w.max())):
        active = cube_d_w > depth_offset
        np.add.at(
            layer_area,
            (cube_node[active], z[active] + depth_offset),
            footprint[active],
        )
    return layer_area


def first_fit_standard_moe_resident_capacity(
    dense_residency: Residency,
    block_table: BlockTable,
    weight_cubes: WeightCubeTable,
    hardware_profile: HardwareProfile,
) -> np.ndarray:
    """Return standard MoE resident slots above the fixed Dense residency."""
    nodes = hardware_profile.mesh_node_count
    depth = hardware_profile.subcube_depth
    height = hardware_profile.subcube_height
    width = hardware_profile.subcube_width
    fixed_ids, fixed_nodes = _resident_boxes(dense_residency, block_table)
    slot = block_table.slot(block_table.dense_layers, 0, 0)
    template_ids = block_table.template_id[slot : slot + BLOCK_KINDS]
    template = (
        weight_cubes.height[template_ids],
        weight_cubes.width[template_ids],
        weight_cubes.d_w[template_ids],
    )
    replica_area = int(np.sum(template[0].astype(np.int64) * template[1] * template[2]))
    replica_limit = (
        block_table.model_layers - block_table.dense_layers
    ) * block_table.expert_columns
    capacity = np.empty(nodes, dtype=np.int32)
    by_profile = {}
    for node in range(nodes):
        ids = fixed_ids[fixed_nodes == node]
        base = (
            weight_cubes.height[ids],
            weight_cubes.width[ids],
            weight_cubes.d_w[ids],
        )
        profile = tuple(sorted(zip(*base, strict=True)))
        if profile in by_profile:
            capacity[node] = by_profile[profile]
            continue
        used_area = int(np.sum(base[0].astype(np.int64) * base[1] * base[2]))
        low = 0
        high = min((depth * height * width - used_area) // replica_area, replica_limit)
        while low < high:
            count = (low + high + 1) // 2
            boxes = tuple(
                np.concatenate((fixed, np.tile(repeated, count)))
                for fixed, repeated in zip(base, template, strict=True)
            )
            accepted = _pack_weight_cubes(
                np.zeros(len(boxes[0]), dtype=np.int16),
                *boxes,
                1,
                depth,
                height,
                width,
                hardware_profile.unit_cube_height,
                hardware_profile.unit_cube_width,
            )[3]
            if accepted:
                low = count
            else:
                high = count - 1
        capacity[node] = low
        by_profile[profile] = low
    return capacity


def _pack_weight_cubes(
    node: np.ndarray,
    height: np.ndarray,
    width: np.ndarray,
    d_w: np.ndarray,
    node_count: int,
    subcube_depth: int,
    layer_height: int,
    layer_width: int,
    unit_height: int,
    unit_width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool, np.ndarray]:
    """Order fixed UnitBoxes and dispatch the canonical geometry kernel."""
    ordinal = np.arange(len(node), dtype=np.int64)
    order = np.lexsort(
        (
            ordinal,
            -d_w.astype(np.int64),
            -width.astype(np.int64),
            -height.astype(np.int64),
            node,
        )
    )
    ordered_node = node[order]
    box_height = height[order] // unit_height
    box_width = width[order] // unit_width
    box_d_w = d_w[order]
    node_cube_count = np.bincount(ordered_node, minlength=node_count)
    grid_height = layer_height // unit_height
    grid_width = layer_width // unit_width
    x = np.empty(len(order), dtype=np.uint16)
    y = np.empty(len(order), dtype=np.uint16)
    z = np.empty(len(order), dtype=np.int16)
    cube_start = 0
    accepted = True
    for cube_count in node_cube_count:
        cube_end = cube_start + cube_count
        if cube_count:
            node_d_w = box_d_w[cube_start:cube_end]
            if np.all(node_d_w == node_d_w[0]):
                cube_d_w = int(node_d_w[0])
                node_x, node_y, node_z, accepted = _pack_first_fit_indexed(
                    box_height[cube_start:cube_end],
                    box_width[cube_start:cube_end],
                    subcube_depth // cube_d_w,
                    grid_height,
                    grid_width,
                )
                node_z *= cube_d_w
            else:
                node_x, node_y, node_z, accepted = _pack_xy_skyline_indexed(
                    box_height[cube_start:cube_end],
                    box_width[cube_start:cube_end],
                    node_d_w,
                    subcube_depth,
                    grid_height,
                    grid_width,
                )
            x[cube_start:cube_end] = node_x
            y[cube_start:cube_end] = node_y
            z[cube_start:cube_end] = node_z
            if not accepted:
                break
        cube_start = cube_end
    x *= unit_width
    y *= unit_height
    return x, y, z, accepted, order


@njit(cache=True, nogil=True)
def _pack_xy_skyline_indexed(
    height: np.ndarray,
    width: np.ndarray,
    d_w: np.ndarray,
    subcube_depth: int,
    grid_height: int,
    grid_width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
    """Place mixed-D_w UnitBoxes at the lowest legal (z, y, x)."""
    x = np.empty(len(height), dtype=np.uint16)
    y = np.empty(len(height), dtype=np.uint16)
    z = np.empty(len(height), dtype=np.int16)
    top = np.zeros((grid_height, grid_width), dtype=np.int16)
    for cube in range(len(height)):
        cube_height = int(height[cube])
        cube_width = int(width[cube])
        cube_d_w = int(d_w[cube])
        selected_z, selected_y, selected_x = _lowest_skyline_position(
            top,
            cube_height,
            cube_width,
        )
        if selected_z + cube_d_w > subcube_depth:
            return x, y, z, False
        x[cube] = selected_x
        y[cube] = selected_y
        z[cube] = selected_z
        new_top = selected_z + cube_d_w
        top[
            selected_y : selected_y + cube_height,
            selected_x : selected_x + cube_width,
        ] = new_top
    return x, y, z, True


@njit(cache=True, nogil=True)
def _lowest_skyline_position(
    top: np.ndarray,
    cube_height: int,
    cube_width: int,
) -> tuple[int, int, int]:
    """Return the first footprint attaining the lowest legal z."""
    grid_height, grid_width = top.shape
    selected_z = np.iinfo(np.int16).max
    selected_y = 0
    selected_x = 0
    minimum_top = int(top.min())
    for y in range(grid_height - cube_height + 1):
        for x in range(grid_width - cube_width + 1):
            candidate_z = 0
            for offset_y in range(cube_height):
                for offset_x in range(cube_width):
                    cell_top = top[y + offset_y, x + offset_x]
                    candidate_z = max(candidate_z, cell_top)
                    if candidate_z >= selected_z:
                        break
                if candidate_z >= selected_z:
                    break
            if candidate_z < selected_z:
                selected_z = candidate_z
                selected_y = y
                selected_x = x
                if candidate_z == minimum_top:
                    return selected_z, selected_y, selected_x
    return selected_z, selected_y, selected_x


@njit(cache=True, nogil=True)
def _pack_first_fit_indexed(
    height: np.ndarray,
    width: np.ndarray,
    bin_count: int,
    layer_height: int,
    layer_width: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool]:
    cube_count = len(height)
    x = np.empty(cube_count, dtype=np.uint16)
    y = np.empty(cube_count, dtype=np.uint16)
    z = np.empty(cube_count, dtype=np.int16)
    shelf_layer = np.empty(cube_count, dtype=np.int16)
    shelf_y = np.empty(cube_count, dtype=np.uint16)
    shelf_height = np.empty(cube_count, dtype=np.uint16)
    shelf_width = np.empty(cube_count, dtype=np.uint16)
    used_height = np.zeros(bin_count, dtype=np.uint16)
    shelf_count = 0
    for cube in range(cube_count):
        cube_height = height[cube]
        cube_width = width[cube]
        selected = -1
        selected_layer = bin_count
        selected_y = layer_height
        for shelf in range(shelf_count):
            if (
                cube_height <= shelf_height[shelf]
                and shelf_width[shelf] + cube_width <= layer_width
                and (
                    shelf_layer[shelf] < selected_layer
                    or (
                        shelf_layer[shelf] == selected_layer
                        and shelf_y[shelf] < selected_y
                    )
                )
            ):
                selected = shelf
                selected_layer = shelf_layer[shelf]
                selected_y = shelf_y[shelf]

        if selected < 0:
            layer = 0
            while layer < bin_count and used_height[layer] + cube_height > layer_height:
                layer += 1
            if layer == bin_count:
                return x, y, z, False
            selected = shelf_count
            shelf_count += 1
            shelf_layer[selected] = layer
            shelf_y[selected] = used_height[layer]
            shelf_height[selected] = cube_height
            shelf_width[selected] = 0
            used_height[layer] += cube_height

        x[cube] = shelf_width[selected]
        y[cube] = shelf_y[selected]
        z[cube] = shelf_layer[selected]
        shelf_width[selected] += cube_width
    return x, y, z, True
