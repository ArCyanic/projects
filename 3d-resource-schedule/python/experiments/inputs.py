"""Artifact-backed static inputs for formal experiments."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from deployment import DeploymentModel, compile_deployment_model
from hardware_profile import build_hardware_profile
from model import (
    build_block_table,
    model_spec_from_json,
)

ROUTE_SPLIT_SIZE = 4096
TRAIN_ROUTE_SLICE = slice(0, ROUTE_SPLIT_SIZE)
VALIDATION_ROUTE_SLICE = slice(ROUTE_SPLIT_SIZE, 2 * ROUTE_SPLIT_SIZE)
TEST_ROUTE_SLICE = slice(2 * ROUTE_SPLIT_SIZE, 3 * ROUTE_SPLIT_SIZE)


@dataclass(slots=True)
class ExperimentInputs:
    model: DeploymentModel
    evaluation_routes: np.ndarray
    prefill_evaluation_routes: np.ndarray

    @property
    def train_routes(self) -> np.ndarray:
        return self.evaluation_routes[TRAIN_ROUTE_SLICE]

    @property
    def validation_routes(self) -> np.ndarray:
        return self.evaluation_routes[VALIDATION_ROUTE_SLICE]

    @property
    def test_routes(self) -> np.ndarray:
        return self.evaluation_routes[TEST_ROUTE_SLICE]

    @property
    def prefill_train_routes(self) -> np.ndarray:
        return self.prefill_evaluation_routes[TRAIN_ROUTE_SLICE]

    @property
    def prefill_validation_routes(self) -> np.ndarray:
        return self.prefill_evaluation_routes[VALIDATION_ROUTE_SLICE]

    @property
    def prefill_test_routes(self) -> np.ndarray:
        return self.prefill_evaluation_routes[TEST_ROUTE_SLICE]

    @property
    def route_splits(self) -> dict[str, list[int]]:
        return {
            "train": [TRAIN_ROUTE_SLICE.start, TRAIN_ROUTE_SLICE.stop],
            "validation": [
                VALIDATION_ROUTE_SLICE.start,
                VALIDATION_ROUTE_SLICE.stop,
            ],
            "test": [TEST_ROUTE_SLICE.start, TEST_ROUTE_SLICE.stop],
        }


def load_preprocessed_inputs(
    input_dir: Path,
    hardware_profile_name: str,
    link_bandwidth_GBps: float | None = None,
    capacity_ratio: float = 1.5,
) -> ExperimentInputs:
    """Load one canonical MoE FFN preprocessing run."""
    with (input_dir / "model.json").open(encoding="utf-8") as handle:
        model_spec = model_spec_from_json(json.load(handle))
    route_files = json.loads((input_dir / "routes.json").read_text())
    routes = np.load(input_dir / route_files["decode"], mmap_mode="r")
    prefill_routes = np.load(input_dir / route_files["prefill"], mmap_mode="r")
    block_table = build_block_table(model_spec)
    hardware_profile = build_hardware_profile(
        hardware_profile_name,
        block_table.model_matrix_elements(),
        link_bandwidth_GBps,
        capacity_ratio,
    )
    return ExperimentInputs(
        compile_deployment_model(block_table, hardware_profile),
        routes,
        prefill_routes,
    )
