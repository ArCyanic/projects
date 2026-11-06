"""Static costs and resident tables used by Decode Collective execution."""

from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from deployment import DeploymentModel
from deployment.residency import Residency
from numba import njit


class DecodeResidentTable(NamedTuple):
    model_layers: int
    dense_layers: int
    expert_columns: int
    routed_column_offset: int
    moe_rank_count: int
    resident_ptr: np.ndarray
    resident_node: np.ndarray
    node_count: int
    expert_service_ns: np.ndarray
    input_hop_service_ns: np.ndarray
    output_hop_service_ns: np.ndarray


@dataclass(slots=True)
class DecodeComponentFacts:
    expert_compute_ns: np.ndarray
    node_serialization_ns: np.ndarray
    mesh_service_ns: np.ndarray
    collective_contention_ns: np.ndarray


def compile_decode_resident_table(
    model: DeploymentModel,
    residency: Residency,
) -> DecodeResidentTable:
    block_table = model.block_table
    hardware_profile = model.hardware_profile
    program = model.program
    input_hop_service_ns = np.empty(block_table.model_layers, dtype=np.int64)
    output_hop_service_ns = np.empty(block_table.model_layers, dtype=np.int64)
    for layer in range(block_table.model_layers):
        rank = int(program.layer_rank_ptr[layer])
        input_task = int(program.rank_input_task_id[rank])
        input_hop_service_ns[layer] = program.task_hop_service_ns[input_task]
        output_hop_service_ns[layer] = program.task_hop_service_ns[
            program.rank_output_task_id[rank]
        ]

    return DecodeResidentTable(
        block_table.model_layers,
        block_table.dense_layers,
        block_table.expert_columns,
        block_table.routed_column_offset,
        block_table.active_moe_ranks,
        residency.resident_ptr,
        residency.resident_node,
        hardware_profile.mesh_node_count,
        model.expert_service_ns,
        input_hop_service_ns,
        output_hop_service_ns,
    )


@njit(inline="always")
def resident_range(compiled, expert_slot):
    return compiled.resident_ptr[expert_slot], compiled.resident_ptr[expert_slot + 1]
