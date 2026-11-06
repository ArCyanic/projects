"""Compile logical matrix templates into physical Weight-Cubes."""

from dataclasses import dataclass
from math import ceil

import numpy as np
from hardware_profile import HardwareProfile
from model import BLOCK_KINDS, BlockTable

from deployment.cost_primitives import (
    VERTICAL_MAX_DEPTH,
    vertical_section_ns,
)


@dataclass(slots=True)
class WeightCubeTable:
    input_elements: np.ndarray
    output_elements: np.ndarray
    weight_columns: np.ndarray
    height: np.ndarray
    width: np.ndarray
    d_w: np.ndarray
    section_count: np.ndarray

    @property
    def weight_cube_count(self) -> int:
        return len(self.height)

    def template_physical_cells(self, template: int) -> int:
        return (
            int(self.height[template])
            * int(self.width[template])
            * int(self.d_w[template])
        )

    def expert_physical_cells(
        self,
        block_table: BlockTable,
        layer: int,
        expert_column: int,
    ) -> int:
        return sum(
            self.template_physical_cells(
                int(
                    block_table.template_id[
                        block_table.slot(layer, expert_column, block)
                    ]
                )
            )
            for block in range(BLOCK_KINDS)
        )

    def model_physical_cells(self, block_table: BlockTable) -> int:
        return sum(
            self.expert_physical_cells(block_table, layer, expert_column)
            for layer in range(block_table.model_layers)
            for expert_column in (
                (0,)
                if layer < block_table.dense_layers
                else range(block_table.expert_columns)
            )
        )


def build_weight_cube_table(
    block_table: BlockTable,
    hardware_profile: HardwareProfile,
) -> WeightCubeTable:
    """Compile each model matrix template into one sectioned Weight-Cube."""
    compile_shape = (
        _planar_shape if hardware_profile.compute_model == "planar" else _vertical_shape
    )
    geometry = np.asarray(
        [
            compile_shape(int(inputs), int(columns), hardware_profile)
            for inputs, columns in zip(
                block_table.template_input_elements,
                block_table.template_weight_columns,
                strict=True,
            )
        ],
        dtype=np.int32,
    )
    return WeightCubeTable(
        block_table.template_input_elements,
        block_table.template_output_elements,
        block_table.template_weight_columns,
        geometry[:, 0],
        geometry[:, 1],
        geometry[:, 2].astype(np.int16),
        geometry[:, 3].astype(np.int16),
    )


def _vertical_shape(
    input_elements: int,
    weight_columns: int,
    hardware_profile: HardwareProfile,
) -> tuple[int, int, int, int]:
    unit_height = hardware_profile.unit_cube_height
    input_slices = _aligned(input_elements, unit_height) // unit_height
    d_section = _vertical_d_section(input_elements, input_slices, hardware_profile)
    input_groups = ceil(input_slices / d_section)
    base_height = unit_height * input_groups
    height_sections = ceil(base_height / hardware_profile.subcube_height)
    width_sections = ceil(weight_columns / hardware_profile.subcube_width)
    section_count = height_sections * width_sections
    cube_height = _aligned(
        ceil(base_height / height_sections),
        unit_height,
    )
    cube_width = _aligned(
        ceil(weight_columns / width_sections),
        hardware_profile.unit_cube_width,
    )
    return cube_height, cube_width, d_section * section_count, section_count


def _vertical_d_section(
    input_elements: int,
    input_slices: int,
    hardware_profile: HardwareProfile,
) -> int:
    candidates = range(1, min(input_slices, VERTICAL_MAX_DEPTH) + 1)
    return min(
        candidates,
        key=lambda candidate: (
            vertical_section_ns(
                hardware_profile,
                input_elements,
                0,
                candidate,
            ),
            ceil(input_slices / candidate) * candidate,
            candidate,
        ),
    )


def _planar_shape(
    input_elements: int,
    weight_columns: int,
    hardware_profile: HardwareProfile,
) -> tuple[int, int, int, int]:
    height_sections = (
        input_elements + hardware_profile.subcube_height - 1
    ) // hardware_profile.subcube_height
    width_sections = (
        weight_columns + hardware_profile.subcube_width - 1
    ) // hardware_profile.subcube_width
    section_count = height_sections * width_sections
    return (
        _aligned(
            (input_elements + height_sections - 1) // height_sections,
            hardware_profile.unit_cube_height,
        ),
        _aligned(
            (weight_columns + width_sections - 1) // width_sections,
            hardware_profile.unit_cube_width,
        ),
        section_count,
        section_count,
    )


def _aligned(elements: int, unit: int) -> int:
    return ((elements + unit - 1) // unit) * unit
