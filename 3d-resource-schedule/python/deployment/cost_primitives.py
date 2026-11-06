"""Atomic Weight-Cube cost primitives shared by compilation and evaluation."""

from math import ceil

from hardware_profile import HardwareProfile

INPUT_SLICE_ELEMENTS = 128
VERTICAL_MAX_DEPTH = 64
VERTICAL_CR_FIRST_FIXED_NS = 191
VERTICAL_DEPTH_NS = 202
FPIM_VECTOR_ADD_NS = 128


def activation_bytes(elements: int, bits: int) -> int:
    return (elements * bits + 7) // 8


def vertical_section_ns(
    hardware_profile: HardwareProfile,
    input_elements: int,
    output_elements: int,
    d_section: int,
) -> int:
    input_slices = (input_elements + INPUT_SLICE_ELEMENTS - 1) // INPUT_SLICE_ELEMENTS
    input_groups = (input_slices + d_section - 1) // d_section
    input_ns = ceil(
        activation_bytes(input_elements, hardware_profile.activation_bits)
        / hardware_profile.B_in_GBps
    )
    compute_ns = round(
        hardware_profile.compute_scale
        * (VERTICAL_DEPTH_NS * d_section + VERTICAL_CR_FIRST_FIXED_NS)
    )
    reduction_ns = round(
        hardware_profile.reduction_scale * FPIM_VECTOR_ADD_NS * (input_groups - 1)
    )
    output_ns = round(
        hardware_profile.out_scale
        * ceil(
            activation_bytes(output_elements, hardware_profile.activation_bits)
            / hardware_profile.B_out_GBps
        )
    )
    return input_ns + compute_ns + reduction_ns + output_ns
