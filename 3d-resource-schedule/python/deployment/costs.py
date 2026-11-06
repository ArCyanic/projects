"""Planar Weight-Cube and 2D-Mesh service-time model."""

from dataclasses import dataclass
from math import ceil

import numpy as np
from hardware_profile import HardwareProfile
from model import BLOCK_KINDS, BlockTable

from deployment.cost_primitives import (
    INPUT_SLICE_ELEMENTS,
    activation_bytes,
    vertical_section_ns,
)
from deployment.weight_cubes import WeightCubeTable

_PLANAR_INVOCATION_NS = 2000
_ICCD_TAIL_ANCHOR_NS = 2750
_ICCD_REDUCTION_ANCHOR_LEVELS = 6
_ICCD_OUT_ANCHOR_TILES = 14
_OUTPUT_TILE_ELEMENTS = 512


@dataclass(slots=True)
class CostModel:
    hardware_profile: HardwareProfile

    def weight_cube_ns(
        self,
        weight_cubes: WeightCubeTable,
        cube: int,
    ) -> int:
        input_elements = int(weight_cubes.input_elements[cube])
        output_elements = int(weight_cubes.output_elements[cube])
        d_w = int(weight_cubes.d_w[cube])
        section_count = int(weight_cubes.section_count[cube])
        width_sections = ceil(
            int(weight_cubes.weight_columns[cube]) / int(weight_cubes.width[cube])
        )
        height_sections = section_count // width_sections
        if self.hardware_profile.compute_model == "planar":
            input_elements = ceil(input_elements / height_sections)
            output_elements = ceil(output_elements / width_sections)
            input_slices = (
                input_elements + INPUT_SLICE_ELEMENTS - 1
            ) // INPUT_SLICE_ELEMENTS
            compute_ns = round(
                self.hardware_profile.compute_scale * _PLANAR_INVOCATION_NS
            )
            input_issue_ns = ceil(
                activation_bytes(
                    INPUT_SLICE_ELEMENTS,
                    self.hardware_profile.activation_bits,
                )
                / self.hardware_profile.B_in_GBps
            )
            input_compute_span_ns = compute_ns + input_issue_ns * (input_slices - 1)
            reduction_levels = (input_slices - 1).bit_length()
            output_tiles = (
                output_elements + _OUTPUT_TILE_ELEMENTS - 1
            ) // _OUTPUT_TILE_ELEMENTS
            reduction_fraction = self.hardware_profile.iccd_tail_reduction_fraction
            reduction_ns = round(
                self.hardware_profile.reduction_scale
                * _ICCD_TAIL_ANCHOR_NS
                * reduction_fraction
                * reduction_levels
                / _ICCD_REDUCTION_ANCHOR_LEVELS
            )
            out_ns = round(
                self.hardware_profile.out_scale
                * _ICCD_TAIL_ANCHOR_NS
                * (1 - reduction_fraction)
                * output_tiles
                / _ICCD_OUT_ANCHOR_TILES
            )
            return section_count * (input_compute_span_ns + reduction_ns + out_ns)

        d_section = d_w // section_count
        return (
            vertical_section_ns(
                self.hardware_profile,
                ceil(input_elements / height_sections),
                ceil(output_elements / width_sections),
                d_section,
            )
            * section_count
        )

    def link_service_ns(self, payload_bytes: int) -> int:
        bandwidth = self.hardware_profile.link_bandwidth_GBps
        return ceil(payload_bytes / bandwidth)

    def activation_bytes(self, elements: int) -> int:
        return activation_bytes(elements, self.hardware_profile.activation_bits)


def compile_expert_service_ns(
    block_table: BlockTable,
    weight_cubes: WeightCubeTable,
    hardware_profile: HardwareProfile,
) -> np.ndarray:
    """Compile complete gate-up/down service for each logical expert slot."""
    cost_model = CostModel(hardware_profile)
    template_service_ns = np.asarray(
        [
            cost_model.weight_cube_ns(weight_cubes, template)
            for template in range(weight_cubes.weight_cube_count)
        ],
        dtype=np.int64,
    )
    return template_service_ns[block_table.template_id.reshape(-1, BLOCK_KINDS)].sum(
        axis=1
    )
