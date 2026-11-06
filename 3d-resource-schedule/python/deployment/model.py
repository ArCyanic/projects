"""Shared model/hardware compilation and complete-copy deployment construction."""

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from hardware_profile import HardwareProfile
from model import BLOCK_KINDS, BlockTable

from deployment.costs import compile_expert_service_ns
from deployment.packing import PackedWeightCubes, pack_residency
from deployment.program import ExecutionProgram, compile_execution_program
from deployment.residency import Residency
from deployment.weight_cubes import WeightCubeTable, build_weight_cube_table


@dataclass(slots=True)
class DeploymentModel:
    block_table: BlockTable
    weight_cubes: WeightCubeTable
    hardware_profile: HardwareProfile
    program: ExecutionProgram
    expert_service_ns: np.ndarray

    def deploy(self, residency: Residency) -> "Deployment":
        return Deployment(self, residency)

    def load_deployment(self, path: Path) -> "Deployment":
        with np.load(path) as artifact:
            residency = Residency(artifact["resident_ptr"], artifact["resident_node"])
        return self.deploy(residency)


@dataclass(slots=True)
class DeploymentSummary:
    resident_count: int
    dense_replica_count: int
    shared_replica_count: int
    routed_replica_count: int
    template_weight_cube_count: int
    weight_cube_count: int
    model_physical_cells: int
    replica_physical_cells: int
    storage_overhead: float
    subcube_depth: int
    used_layer_count: int
    node_utilization_min: float
    node_utilization_mean: float
    node_utilization_max: float
    active_layer_utilization_min: float
    active_layer_utilization_mean: float
    active_layer_utilization_max: float
    resident_count_by_node: tuple[int, ...]
    resident_physical_cells_by_node: tuple[int, ...]
    shared_resident_counts_by_layer: tuple[tuple[int, ...], ...]
    routed_resident_counts_by_layer: tuple[tuple[int, ...], ...]

    @property
    def moe_extra_replica_count(self) -> int:
        return self.shared_replica_count + self.routed_replica_count

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class Deployment:
    model: DeploymentModel
    residency: Residency

    def save(self, path: Path) -> None:
        np.savez(
            path,
            resident_ptr=self.residency.resident_ptr,
            resident_node=self.residency.resident_node,
        )

    def pack(self) -> PackedWeightCubes:
        return pack_residency(
            self.residency,
            self.model.block_table,
            self.model.weight_cubes,
            self.model.hardware_profile,
        )

    def summary(self) -> DeploymentSummary:
        residency = self.residency
        packing = self.pack()
        model_cells = self.model.weight_cubes.model_physical_cells(
            self.model.block_table
        )
        active_layers = packing.layer_utilization[packing.layer_utilization > 0]
        table = self.model.block_table
        counts = np.diff(residency.resident_ptr).reshape(-1, table.expert_columns)
        shared_counts = counts[table.dense_layers :, : table.shared_experts]
        routed_counts = counts[table.dense_layers :, table.shared_experts :]
        node_count = self.model.hardware_profile.mesh_node_count
        resident_count_by_node = np.bincount(
            residency.resident_node,
            minlength=node_count,
        )
        physical_cells_by_node = np.zeros(node_count, dtype=np.int64)
        template_cells = np.asarray(
            [
                self.model.weight_cubes.template_physical_cells(template)
                for template in range(self.model.weight_cubes.weight_cube_count)
            ],
            dtype=np.int64,
        )
        np.add.at(
            physical_cells_by_node,
            residency.resident_node,
            np.repeat(
                template_cells[table.template_id.reshape(-1, BLOCK_KINDS)].sum(axis=1),
                counts.ravel(),
            ),
        )
        storage_cells = int(physical_cells_by_node.sum()) - model_cells
        return DeploymentSummary(
            int(residency.resident_count),
            int((counts[: table.dense_layers, 0] - 1).sum()),
            int((shared_counts - 1).sum()),
            int((routed_counts - 1).sum()),
            int(self.model.weight_cubes.weight_cube_count),
            int(packing.weight_cube_count),
            int(model_cells),
            int(storage_cells),
            storage_cells / model_cells,
            self.model.hardware_profile.subcube_depth,
            int(active_layers.size),
            float(packing.node_utilization.min()),
            float(packing.node_utilization.mean()),
            float(packing.node_utilization.max()),
            float(active_layers.min()),
            float(active_layers.mean()),
            float(active_layers.max()),
            tuple(int(count) for count in resident_count_by_node),
            tuple(int(cells) for cells in physical_cells_by_node),
            tuple(map(tuple, shared_counts.tolist())),
            tuple(map(tuple, routed_counts.tolist())),
        )


def compile_deployment_model(
    block_table: BlockTable,
    hardware_profile: HardwareProfile,
) -> DeploymentModel:
    cubes = build_weight_cube_table(block_table, hardware_profile)
    return DeploymentModel(
        block_table,
        cubes,
        hardware_profile,
        compile_execution_program(block_table, cubes, hardware_profile),
        compile_expert_service_ns(block_table, cubes, hardware_profile),
    )
