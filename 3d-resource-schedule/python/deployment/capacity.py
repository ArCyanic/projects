"""Shared artifact-backed workload and deployment preparation."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from deployment.model import DeploymentModel
from deployment.packing import first_fit_standard_moe_resident_capacity
from deployment.residency import Residency, build_dense_residency


@dataclass(slots=True)
class ReplicaSpace:
    dense_residency: Residency
    moe_resident_capacity: np.ndarray
    required_moe_resident_count: int

    @property
    def available_replica_capacity(self) -> int:
        return int(self.moe_resident_capacity.sum()) - self.required_moe_resident_count

    def model_relative_replica_budget(
        self,
        fraction: float,
    ) -> int:
        """Return a model-relative copy budget capped by physical capacity."""
        return min(
            round(self.required_moe_resident_count * fraction),
            self.available_replica_capacity,
        )


def compile_replica_space(model: DeploymentModel) -> ReplicaSpace:
    """Compile the complete-resident capacity of the fixed hardware."""
    block_table = model.block_table
    dense_residency = build_dense_residency(
        block_table,
        model.hardware_profile.grid,
    )
    capacity = first_fit_standard_moe_resident_capacity(
        dense_residency,
        block_table,
        model.weight_cubes,
        model.hardware_profile,
    )
    required_residents = (block_table.model_layers - block_table.dense_layers) * (
        block_table.expert_columns
    )
    return ReplicaSpace(
        dense_residency,
        capacity,
        required_residents,
    )


def write_replica_space_artifact(path: Path, space: ReplicaSpace) -> None:
    np.savez(
        path,
        schema="moe-replica-space-v3",
        dense_resident_ptr=space.dense_residency.resident_ptr,
        dense_resident_node=space.dense_residency.resident_node,
        moe_resident_capacity=space.moe_resident_capacity,
    )


def load_replica_space_artifact(
    path: Path,
    model: DeploymentModel,
) -> ReplicaSpace:
    with np.load(path) as artifact:
        dense_residency = Residency(
            artifact["dense_resident_ptr"],
            artifact["dense_resident_node"],
        )
        capacity = artifact["moe_resident_capacity"]
    block_table = model.block_table
    return ReplicaSpace(
        dense_residency,
        capacity,
        (block_table.model_layers - block_table.dense_layers)
        * block_table.expert_columns,
    )
