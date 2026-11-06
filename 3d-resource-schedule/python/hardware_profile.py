"""Hardware geometry consumed by mapping and estimation."""

from dataclasses import dataclass
from math import ceil
from typing import Literal

import numpy as np

type ComputeModel = Literal[
    "planar",
    "vertical",
]
type InputComputeRelation = Literal[
    "pipeline",
    "barrier",
]

_LINK_BANDWIDTH_GBPS = {
    "planar": 0.5,
    "vertical": 0.5,
}
FORMAL_LINK_BANDWIDTHS_GBPS = (0.5, 2.0, 8.0)
PAPER_HIGH_LINK_BANDWIDTH_GBPS = 2.0
_INPUT_OUTPUT_BANDWIDTH_GBPS = {
    "planar": 2.0,
    "vertical": 1.0,
}
_PRECISION_BITS = {
    "planar": 8,
    "vertical": 5,
}


@dataclass(slots=True)
class HardwareProfile:
    hardware_id: str
    grid: tuple[int, int]
    subcube_depth: int
    subcube_height: int
    subcube_width: int
    weight_bits: int
    activation_bits: int
    compute_model: ComputeModel
    input_compute_relation: InputComputeRelation
    link_bandwidth_GBps: float
    B_in_GBps: float
    B_out_GBps: float
    mesh_node_count: int
    path_ptr: np.ndarray
    path_link_ids: np.ndarray
    capacity_ratio: float = 1.5
    compute_scale: float = 1.0
    reduction_scale: float = 1.0
    out_scale: float = 1.0
    iccd_tail_reduction_fraction: float = 0.5

    @property
    def unit_cube_height(self) -> int:
        return 128

    @property
    def unit_cube_width(self) -> int:
        return 512 if self.compute_model == "planar" else 128


def build_hardware_profile(
    name: ComputeModel,
    model_matrix_elements: int,
    link_bandwidth_GBps: float | None = None,
    capacity_ratio: float = 1.5,
) -> HardwareProfile:
    grid = (4, 4)
    subcube_height = 8192
    subcube_width = 16384
    subcube_depth = ceil(
        model_matrix_elements
        * capacity_ratio
        / (grid[0] * grid[1] * subcube_height * subcube_width)
    )
    path_ptr, path_link_ids = _mesh_xy_paths(grid)
    precision_bits = _PRECISION_BITS[name]
    input_output_bandwidth_GBps = _INPUT_OUTPUT_BANDWIDTH_GBPS[name]
    mesh_bandwidth_GBps = (
        _LINK_BANDWIDTH_GBPS[name]
        if link_bandwidth_GBps is None
        else link_bandwidth_GBps
    )
    ratio_id = f"{capacity_ratio:g}".replace(".", "p")
    hardware_id = f"{name}_8192x16384_{ratio_id}x"
    if mesh_bandwidth_GBps != _LINK_BANDWIDTH_GBPS[name]:
        hardware_id = f"{hardware_id}_{mesh_bandwidth_GBps:g}gbps"
    return HardwareProfile(
        hardware_id=hardware_id,
        grid=grid,
        subcube_depth=subcube_depth,
        subcube_height=subcube_height,
        subcube_width=subcube_width,
        weight_bits=precision_bits,
        activation_bits=precision_bits,
        compute_model=name,
        input_compute_relation="pipeline" if name == "planar" else "barrier",
        link_bandwidth_GBps=mesh_bandwidth_GBps,
        B_in_GBps=input_output_bandwidth_GBps,
        B_out_GBps=input_output_bandwidth_GBps,
        mesh_node_count=grid[0] * grid[1],
        path_ptr=path_ptr,
        path_link_ids=path_link_ids,
        capacity_ratio=capacity_ratio,
    )


def _mesh_xy_paths(grid: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Compile directed XY paths into CSR link IDs."""
    rows, columns = grid
    node_count = rows * columns
    coordinates = np.asarray(
        [divmod(node, columns) for node in range(node_count)],
        dtype=np.int16,
    )
    distance = np.abs(coordinates[:, None] - coordinates[None, :]).sum(axis=2)
    link_id = {
        (source, destination): index
        for index, (source, destination) in enumerate(
            (source, destination)
            for source in range(node_count)
            for destination in range(node_count)
            if distance[source, destination] == 1
        )
    }
    path_ptr = np.empty(node_count * node_count + 1, dtype=np.int32)
    path_ptr[0] = 0
    path_link_ids: list[int] = []
    for source in range(node_count):
        source_row, source_column = divmod(source, columns)
        for destination in range(node_count):
            destination_row, destination_column = divmod(destination, columns)
            current = source
            current_column = source_column
            while current_column != destination_column:
                current_column += 1 if current_column < destination_column else -1
                next_node = source_row * columns + current_column
                path_link_ids.append(link_id[current, next_node])
                current = next_node
            current_row = source_row
            while current_row != destination_row:
                current_row += 1 if current_row < destination_row else -1
                next_node = current_row * columns + destination_column
                path_link_ids.append(link_id[current, next_node])
                current = next_node
            path_ptr[source * node_count + destination + 1] = len(path_link_ids)
    return path_ptr, np.asarray(path_link_ids, dtype=np.int16)
