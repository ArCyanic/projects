"""Canonical MoE FFN model contract and block address table."""

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

GATE_UP = 0
DOWN = 1
BLOCK_KINDS = 2


@dataclass(slots=True)
class GatedMLPSpec:
    input_elements: int
    intermediate_elements: int


@dataclass(slots=True)
class MoEModelSpec:
    model_id: str
    revision: str
    model_layers: int
    dense_layers: int
    shared_experts: int
    routed_experts: int
    top_k: int
    moe_mlp: GatedMLPSpec
    dense_mlp: GatedMLPSpec | None = None

    @property
    def expert_columns(self) -> int:
        return self.shared_experts + self.routed_experts


@dataclass(slots=True)
class BlockTable:
    model_layers: int
    dense_layers: int
    shared_experts: int
    routed_experts: int
    top_k: int
    template_id: np.ndarray
    template_input_elements: np.ndarray
    template_output_elements: np.ndarray
    template_weight_columns: np.ndarray

    @property
    def expert_columns(self) -> int:
        return self.shared_experts + self.routed_experts

    @property
    def routed_column_offset(self) -> int:
        return self.shared_experts

    @property
    def active_moe_ranks(self) -> int:
        return self.shared_experts + self.top_k

    @property
    def expert_slot_count(self) -> int:
        return self.model_layers * self.expert_columns

    def expert_slot(self, layer: int, expert_column: int) -> int:
        return layer * self.expert_columns + expert_column

    def slot(self, layer: int, expert_column: int, block_kind: int) -> int:
        return self.expert_slot(layer, expert_column) * BLOCK_KINDS + block_kind

    def model_matrix_elements(self) -> int:
        templates = self.template_id[self.template_id >= 0]
        return int(
            np.sum(
                self.template_input_elements[templates].astype(np.int64)
                * self.template_weight_columns[templates]
            )
        )


def model_spec_json(spec: MoEModelSpec) -> dict[str, Any]:
    return {"schema": "moe-ffn-model-v2", **asdict(spec)}


def model_spec_from_json(artifact: dict[str, Any]) -> MoEModelSpec:
    return MoEModelSpec(
        model_id=artifact["model_id"],
        revision=artifact["revision"],
        model_layers=artifact["model_layers"],
        dense_layers=artifact["dense_layers"],
        shared_experts=artifact["shared_experts"],
        routed_experts=artifact["routed_experts"],
        top_k=artifact["top_k"],
        moe_mlp=GatedMLPSpec(**artifact["moe_mlp"]),
        dense_mlp=(
            GatedMLPSpec(**artifact["dense_mlp"])
            if artifact["dense_mlp"] is not None
            else None
        ),
    )


def build_block_table(spec: MoEModelSpec) -> BlockTable:
    """Compile one model spec into the integer block address space."""
    mlps = tuple(mlp for mlp in (spec.dense_mlp, spec.moe_mlp) if mlp)
    template_input_elements = np.asarray(
        [
            value
            for mlp in mlps
            for value in (mlp.input_elements, mlp.intermediate_elements)
        ],
        dtype=np.int32,
    )
    template_output_elements = np.asarray(
        [
            value
            for mlp in mlps
            for value in (mlp.intermediate_elements, mlp.input_elements)
        ],
        dtype=np.int32,
    )
    template_weight_columns = template_output_elements.copy()
    template_weight_columns[::2] *= 2

    template_id = np.full(
        spec.model_layers * spec.expert_columns * BLOCK_KINDS,
        -1,
        dtype=np.int8,
    )
    table = BlockTable(
        spec.model_layers,
        spec.dense_layers,
        spec.shared_experts,
        spec.routed_experts,
        spec.top_k,
        template_id,
        template_input_elements,
        template_output_elements,
        template_weight_columns,
    )
    template = 0
    dense_template = template if spec.dense_mlp else -1
    template += 2 * (spec.dense_mlp is not None)
    moe_template = template

    for layer in range(table.model_layers):
        if layer < table.dense_layers:
            columns = ((0, dense_template),)
        else:
            columns = ((column, moe_template) for column in range(table.expert_columns))
        for expert_column, block_template in columns:
            template_id[table.slot(layer, expert_column, GATE_UP)] = block_template
            template_id[table.slot(layer, expert_column, DOWN)] = block_template + 1
    return table
