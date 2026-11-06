"""Export the final spatial mapping and static logical schedule."""

import json
from pathlib import Path
from typing import TextIO

from deployment import Deployment
from deployment.program import (
    ENTRY,
    SINK,
    WEIGHTED,
    WEIGHTED_COMBINE,
    ExecutionProgram,
)
from experiments.inputs import load_preprocessed_inputs
from model import DOWN, GATE_UP

SPATIAL_MAPPING_FILE = "spatial_mapping.jsonl"
STATIC_SCHEDULE_FILE = "static_schedule.jsonl"

_BLOCK_NAMES = {GATE_UP: "gate_up", DOWN: "down"}
_TASK_NAMES = {
    ENTRY: "entry",
    WEIGHTED: "weighted",
    WEIGHTED_COMBINE: "weighted_combine",
    SINK: "sink",
}


def run_solution_export(
    output_dir: Path,
    input_dir: Path,
    hardware_profile: str,
    deployment_artifact: Path,
) -> int:
    inputs = load_preprocessed_inputs(input_dir, hardware_profile)
    deployment = inputs.model.load_deployment(deployment_artifact)
    write_solution(output_dir, deployment)
    print(f"solution out={output_dir}")
    return 0


def write_solution(
    output_dir: Path,
    deployment: Deployment,
) -> None:
    """Write the two files that constitute one competition Solution."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / SPATIAL_MAPPING_FILE).open("w", encoding="utf-8") as output:
        _write_spatial_mapping(output, deployment)
    with (output_dir / STATIC_SCHEDULE_FILE).open("w", encoding="utf-8") as output:
        _write_static_schedule(output, deployment.model.program)


def _write_spatial_mapping(output: TextIO, deployment: Deployment) -> None:
    table = deployment.model.block_table
    weights = deployment.model.weight_cubes
    residency = deployment.residency
    packed = deployment.pack()
    columns = deployment.model.hardware_profile.grid[1]

    for layer in range(table.model_layers):
        expert_columns = (
            (0,) if layer < table.dense_layers else range(table.expert_columns)
        )
        for expert_column in expert_columns:
            expert_slot = table.expert_slot(layer, expert_column)
            resident_start = int(residency.resident_ptr[expert_slot])
            resident_end = int(residency.resident_ptr[expert_slot + 1])
            if layer < table.dense_layers:
                expert_kind = "dense"
                expert_id = None
            elif expert_column < table.routed_column_offset:
                expert_kind = "shared"
                expert_id = expert_column
            else:
                expert_kind = "routed"
                expert_id = expert_column - table.routed_column_offset

            for replica, resident_id in enumerate(range(resident_start, resident_end)):
                sub_cube = int(residency.resident_node[resident_id])
                sub_cube_row, sub_cube_column = divmod(sub_cube, columns)
                for block_kind in (GATE_UP, DOWN):
                    packed_index = resident_id * 2 + block_kind
                    logical_weight_cube_id = int(packed.weight_cube_id[packed_index])
                    _write_json_line(
                        output,
                        {
                            "weight_cube_id": packed_index,
                            "resident_id": resident_id,
                            "layer": layer,
                            "expert_kind": expert_kind,
                            "expert_id": expert_id,
                            "replica": replica,
                            "block": _BLOCK_NAMES[block_kind],
                            "logical_weight_cube_id": logical_weight_cube_id,
                            "input_elements": int(
                                weights.input_elements[logical_weight_cube_id]
                            ),
                            "output_elements": int(
                                weights.output_elements[logical_weight_cube_id]
                            ),
                            "sub_cube": sub_cube,
                            "sub_cube_row": sub_cube_row,
                            "sub_cube_column": sub_cube_column,
                            "x": int(packed.x[packed_index]),
                            "y": int(packed.y[packed_index]),
                            "z": int(packed.z[packed_index]),
                            "height": int(packed.height[packed_index]),
                            "width": int(packed.width[packed_index]),
                            "d_w": int(packed.d_w[packed_index]),
                        },
                    )


def _write_static_schedule(output: TextIO, dataflow: ExecutionProgram) -> None:
    for order, task_id_value in enumerate(dataflow.topological_order):
        task_id = int(task_id_value)
        predecessor_start = int(dataflow.predecessor_ptr[task_id])
        predecessor_end = int(dataflow.predecessor_ptr[task_id + 1])
        model_layer = int(dataflow.model_layer[task_id])
        rank_in_layer = int(dataflow.rank_in_layer[task_id])
        block_kind = int(dataflow.block_kind[task_id])
        template_weight_cube_id = int(dataflow.weight_cube_id[task_id])
        _write_json_line(
            output,
            {
                "order": order,
                "task_id": task_id,
                "task": _TASK_NAMES[int(dataflow.task_kind[task_id])],
                "layer": None if model_layer < 0 else model_layer,
                "rank_in_layer": None if rank_in_layer < 0 else rank_in_layer,
                "block": _BLOCK_NAMES.get(block_kind),
                "logical_weight_cube_id": (
                    None if template_weight_cube_id < 0 else template_weight_cube_id
                ),
                "predecessors": [
                    int(predecessor)
                    for predecessor in dataflow.predecessor_ids[
                        predecessor_start:predecessor_end
                    ]
                ],
            },
        )


def _write_json_line(output: TextIO, record: dict[str, object]) -> None:
    output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    output.write("\n")
