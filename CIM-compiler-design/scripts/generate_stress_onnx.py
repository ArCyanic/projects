#!/usr/bin/env python3
"""Generate dedicated ONNX stress fixtures for extended profile validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

REPO_ROOT = Path(__file__).resolve().parents[1]
ONNX_DIR = REPO_ROOT / "onnx"


def _write(model: onnx.ModelProto, name: str) -> Path:
    ONNX_DIR.mkdir(parents=True, exist_ok=True)
    path = ONNX_DIR / f"{name}.onnx"
    onnx.save(model, path)
    return path


def build_stress_sram_slice() -> Path:
    """Single int8 Gemm with a moderate activation footprint."""
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [8, 256])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [8, 128])
    w = numpy_helper.from_array(
        np.random.randint(-4, 4, size=(128, 256), dtype=np.int8),
        name="W",
    )
    b = numpy_helper.from_array(np.zeros(128, dtype=np.int32), name="B")
    linear = helper.make_node("Gemm", ["X", "W", "B"], ["Y"], name="linear0")
    graph = helper.make_graph([linear], "stress_sram_slice", [x], [y], [w, b])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, "stress_sram_slice")


def build_stress_two_linear() -> Path:
    """Two chained Gemm layers to exercise multi-stage weight placement."""
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [4, 64])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [4, 32])
    w0 = numpy_helper.from_array(
        np.random.randint(-4, 4, size=(32, 64), dtype=np.int8),
        name="W0",
    )
    b0 = numpy_helper.from_array(np.zeros(32, dtype=np.int32), name="B0")
    w1 = numpy_helper.from_array(
        np.random.randint(-4, 4, size=(32, 32), dtype=np.int8),
        name="W1",
    )
    b1 = numpy_helper.from_array(np.zeros(32, dtype=np.int32), name="B1")
    linear0 = helper.make_node("Gemm", ["X", "W0", "B0"], ["mid"], name="linear0")
    linear1 = helper.make_node("Gemm", ["mid", "W1", "B1"], ["Y"], name="linear1")
    graph = helper.make_graph(
        [linear0, linear1],
        "stress_two_linear",
        [x],
        [y],
        [w0, b0, w1, b1],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, "stress_two_linear")


def build_stress_shared_weight() -> Path:
    """Two branches reading the same weight tensor."""
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [4, 32])
    y1 = helper.make_tensor_value_info("Y1", TensorProto.INT32, [4, 16])
    y2 = helper.make_tensor_value_info("Y2", TensorProto.INT32, [4, 16])
    w = numpy_helper.from_array(
        np.random.randint(-4, 4, size=(16, 32), dtype=np.int8),
        name="W",
    )
    b = numpy_helper.from_array(np.zeros(16, dtype=np.int32), name="B")
    linear0 = helper.make_node(
        "Gemm", ["X", "W", "B"], ["Y1"], name="linear0", transB=1
    )
    linear1 = helper.make_node(
        "Gemm", ["X", "W", "B"], ["Y2"], name="linear1", transB=1
    )
    graph = helper.make_graph(
        [linear0, linear1],
        "stress_shared_weight",
        [x],
        [y1, y2],
        [w, b],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, "stress_shared_weight")


def build_stress_branch_fanout() -> Path:
    """Three parallel Gemm branches from one input."""
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [4, 32])
    y0 = helper.make_tensor_value_info("Y0", TensorProto.INT32, [4, 8])
    y1 = helper.make_tensor_value_info("Y1", TensorProto.INT32, [4, 8])
    y2 = helper.make_tensor_value_info("Y2", TensorProto.INT32, [4, 8])
    weights = [
        numpy_helper.from_array(
            np.random.randint(-4, 4, size=(8, 32), dtype=np.int8),
            name=f"W{i}",
        )
        for i in range(3)
    ]
    biases = [
        numpy_helper.from_array(np.zeros(8, dtype=np.int32), name=f"B{i}")
        for i in range(3)
    ]
    nodes = [
        helper.make_node("Gemm", ["X", f"W{i}", f"B{i}"], [f"Y{i}"], name=f"linear{i}")
        for i in range(3)
    ]
    graph = helper.make_graph(
        nodes,
        "stress_branch_fanout",
        [x],
        [y0, y1, y2],
        weights + biases,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, "stress_branch_fanout")


def build_stress_partial_sum() -> Path:
    """Four sequential Gemm ops to stress partial-sum style lifetimes."""
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [2, 16])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [2, 8])
    initializers = []
    nodes = []
    prev = "X"
    for index in range(4):
        w = numpy_helper.from_array(
            np.random.randint(-4, 4, size=(8, 16 if index == 0 else 8), dtype=np.int8),
            name=f"W{index}",
        )
        b = numpy_helper.from_array(np.zeros(8, dtype=np.int32), name=f"B{index}")
        initializers.extend([w, b])
        out = "Y" if index == 3 else f"T{index + 1}"
        nodes.append(
            helper.make_node(
                "Gemm",
                [prev, f"W{index}", f"B{index}"],
                [out],
                name=f"linear{index}",
            )
        )
        prev = out
    graph = helper.make_graph(
        nodes,
        "stress_partial_sum",
        [x],
        [y],
        initializers,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, "stress_partial_sum")


def build_stress_stream_high_load() -> Path:
    """Shared large weights, mixed i32xi8 tail, and residual addends."""
    rng = np.random.default_rng(0)
    x0 = helper.make_tensor_value_info("X0", TensorProto.INT8, [8, 640])
    x1 = helper.make_tensor_value_info("X1", TensorProto.INT8, [8, 640])
    r0 = helper.make_tensor_value_info("R0", TensorProto.INT32, [8, 384])
    r1 = helper.make_tensor_value_info("R1", TensorProto.INT32, [8, 257])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [8, 257])
    value_info = [
        helper.make_tensor_value_info("A", TensorProto.INT32, [8, 384]),
        helper.make_tensor_value_info("B", TensorProto.INT32, [8, 384]),
        helper.make_tensor_value_info("S", TensorProto.INT32, [8, 384]),
        helper.make_tensor_value_info("SR", TensorProto.INT32, [8, 384]),
        helper.make_tensor_value_info("T", TensorProto.INT32, [8, 257]),
    ]
    w_shared = numpy_helper.from_array(
        rng.integers(-4, 4, size=(384, 640), dtype=np.int8),
        name="Wshared",
    )
    b_shared = numpy_helper.from_array(np.zeros(384, dtype=np.int32), name="Bshared")
    w_tail = numpy_helper.from_array(
        rng.integers(-4, 4, size=(257, 384), dtype=np.int8),
        name="Wtail",
    )
    b_tail = numpy_helper.from_array(np.zeros(257, dtype=np.int32), name="Btail")
    nodes = [
        helper.make_node("Gemm", ["X0", "Wshared", "Bshared"], ["A"], name="linear0"),
        helper.make_node("Gemm", ["X1", "Wshared", "Bshared"], ["B"], name="linear1"),
        helper.make_node("Add", ["A", "B"], ["S"], name="sum_shared"),
        helper.make_node("Add", ["S", "R0"], ["SR"], name="residual0"),
        helper.make_node("Gemm", ["SR", "Wtail", "Btail"], ["T"], name="linear2"),
        helper.make_node("Add", ["T", "R1"], ["Y"], name="residual1"),
    ]
    graph = helper.make_graph(
        nodes,
        "stress_stream_high_load",
        [x0, x1, r0, r1],
        [y],
        [w_shared, b_shared, w_tail, b_tail],
        value_info=value_info,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    return _write(model, "stress_stream_high_load")


def build_resource_showcase() -> Path:
    """Four same-activation branches for horizontal packing."""
    rng = np.random.default_rng(20260722)
    batch, input_width, branch_width = 80, 256, 64
    x = helper.make_tensor_value_info("X", TensorProto.INT8, [batch, input_width])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [batch, branch_width])
    initializers = []
    nodes = []
    for index in range(4):
        weight = f"W{index}"
        bias = f"B{index}"
        initializers.extend(
            [
                numpy_helper.from_array(
                    rng.integers(
                        -4, 4, size=(branch_width, input_width), dtype=np.int8
                    ),
                    name=weight,
                ),
                numpy_helper.from_array(
                    np.zeros(branch_width, dtype=np.int32), name=bias
                ),
            ]
        )
        nodes.append(
            helper.make_node(
                "Gemm",
                ["X", weight, bias],
                [f"P{index}"],
                name=f"ParallelLinear{index}",
            )
        )
    nodes.extend(
        [
            helper.make_node("Add", ["P0", "P1"], ["H0"], name="BranchAdd0"),
            helper.make_node("Add", ["P2", "P3"], ["H1"], name="BranchAdd1"),
            helper.make_node("Add", ["H0", "H1"], ["Y"], name="BranchMerge"),
        ]
    )
    value_info = [
        helper.make_tensor_value_info(name, TensorProto.INT32, [batch, branch_width])
        for name in ("P0", "P1", "P2", "P3", "H0", "H1")
    ]
    graph = helper.make_graph(
        nodes,
        "cim_resource_showcase",
        [x],
        [y],
        initializers,
        value_info=value_info,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 10
    model.producer_name = "CIM-compiler-design"
    model.producer_version = "2"
    return _write(model, "resource_showcase")


def _build_single_gemm_showcase(
    name: str, batch: int, inputs: int, outputs: int
) -> Path:
    rng = np.random.default_rng(20260722)
    x = helper.make_tensor_value_info("X", TensorProto.INT32, [batch, inputs])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [batch, outputs])
    weight = numpy_helper.from_array(
        rng.integers(-4, 4, size=(outputs, inputs), dtype=np.int8), name="W"
    )
    bias = numpy_helper.from_array(np.zeros(outputs, dtype=np.int32), name="B")
    linear = helper.make_node("Gemm", ["X", "W", "B"], ["Y"], name="linear", transB=1)
    graph = helper.make_graph([linear], name, [x], [y], [weight, bias])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    return _write(model, name)


def build_weight_replication_showcase() -> Path:
    """One shared weight used by consecutive activation rows."""
    return _build_single_gemm_showcase("weight_replication_showcase", 8, 256, 128)


def build_heterogeneous_fusion_showcase() -> Path:
    """Three independent MVM consumers with different K and N dimensions."""
    rng = np.random.default_rng(20260723)
    batch, inputs = 1, 128
    branch_k = (64, 96, 128)
    branch_n = (32, 64, 96)
    x = helper.make_tensor_value_info("X", TensorProto.INT32, [batch, inputs])
    initializers = []
    nodes = []
    for index, (k, n) in enumerate(zip(branch_k, branch_n)):
        producer_weight = f"U{index}"
        weight = f"W{index}"
        initializers.extend(
            [
                numpy_helper.from_array(
                    rng.integers(-4, 4, size=(k, inputs), dtype=np.int8),
                    name=producer_weight,
                ),
                numpy_helper.from_array(
                    rng.integers(-4, 4, size=(n, k), dtype=np.int8),
                    name=weight,
                ),
            ]
        )
        nodes.append(
            helper.make_node(
                "Gemm",
                ["X", producer_weight],
                [f"A{index}"],
                name=f"producer{index}",
                transB=1,
            )
        )
        nodes.append(
            helper.make_node(
                "Gemm",
                [f"A{index}", weight],
                [f"P{index}"],
                name=f"linear{index}",
                transB=1,
            )
        )
    graph = helper.make_graph(
        nodes,
        "heterogeneous_fusion_showcase",
        [x],
        [
            helper.make_tensor_value_info(
                f"P{index}", TensorProto.INT32, [batch, n]
            )
            for index, n in enumerate(branch_n)
        ],
        initializers,
        value_info=[
            helper.make_tensor_value_info(
                f"A{index}", TensorProto.INT32, [batch, k]
            )
            for index, k in enumerate(branch_k)
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 10
    model.producer_name = "CIM-compiler-design"
    model.producer_version = "2"
    return _write(model, "heterogeneous_fusion_showcase")


def build_integrated_showcase() -> Path:
    """One graph exercising packing, heterogeneous fusion, and replication."""
    rng = np.random.default_rng(20260724)
    inputs, narrow, wide = 64, 32, 64
    horizontal_batch, horizontal_inputs = 80, 256
    horizontal_input = helper.make_tensor_value_info(
        "HorizontalInput",
        TensorProto.INT8,
        [horizontal_batch, horizontal_inputs],
    )
    heterogeneous_input = helper.make_tensor_value_info(
        "HeterogeneousInput", TensorProto.INT32, [1, inputs]
    )
    rows = helper.make_tensor_value_info("Rows", TensorProto.INT32, [4, inputs])
    horizontal_output = helper.make_tensor_value_info(
        "HorizontalOutput", TensorProto.INT32, [horizontal_batch, wide]
    )
    heterogeneous_output = helper.make_tensor_value_info(
        "HeterogeneousOutput", TensorProto.INT32, [1, wide]
    )
    replicated_output = helper.make_tensor_value_info(
        "ReplicatedOutput", TensorProto.INT32, [4, wide]
    )

    weights = {
        "WH0": (wide, horizontal_inputs),
        "WH1": (wide, horizontal_inputs),
        "WH2": (wide, horizontal_inputs),
        "WH3": (wide, horizontal_inputs),
        "U0": (wide, inputs),
        "U1": (wide, inputs),
        "W0": (narrow, wide),
        "W1": (narrow, wide),
        "WR": (wide, inputs),
    }
    initializers = [
        numpy_helper.from_array(
            rng.integers(-4, 4, size=shape, dtype=np.int8), name=name
        )
        for name, shape in weights.items()
    ] + [
        numpy_helper.from_array(np.zeros(wide, dtype=np.int32), name=name)
        for name in ("BH0", "BH1", "BH2", "BH3")
    ]
    nodes = [
        helper.make_node("Gemm", ["HorizontalInput", "WH0", "BH0"], ["H0"]),
        helper.make_node("Gemm", ["HorizontalInput", "WH1", "BH1"], ["H1"]),
        helper.make_node("Gemm", ["HorizontalInput", "WH2", "BH2"], ["H2"]),
        helper.make_node("Gemm", ["HorizontalInput", "WH3", "BH3"], ["H3"]),
        helper.make_node("Add", ["H0", "H1"], ["H01"]),
        helper.make_node("Add", ["H2", "H3"], ["H23"]),
        helper.make_node("Add", ["H01", "H23"], ["HorizontalOutput"]),
        helper.make_node("Gemm", ["HeterogeneousInput", "U0"], ["A0"], transB=1),
        helper.make_node("Gemm", ["HeterogeneousInput", "U1"], ["A1"], transB=1),
        helper.make_node("Gemm", ["A0", "W0"], ["P0"], transB=1),
        helper.make_node("Gemm", ["A1", "W1"], ["P1"], transB=1),
        helper.make_node("Concat", ["P0", "P1"], ["HeterogeneousOutput"], axis=1),
        helper.make_node("Gemm", ["Rows", "WR"], ["ReplicatedOutput"], transB=1),
    ]
    value_info = [
        helper.make_tensor_value_info(name, TensorProto.INT32, shape)
        for name, shape in {
            "H0": (horizontal_batch, wide),
            "H1": (horizontal_batch, wide),
            "H2": (horizontal_batch, wide),
            "H3": (horizontal_batch, wide),
            "H01": (horizontal_batch, wide),
            "H23": (horizontal_batch, wide),
            "A0": (1, wide),
            "A1": (1, wide),
            "P0": (1, narrow),
            "P1": (1, narrow),
        }.items()
    ]
    graph = helper.make_graph(
        nodes,
        "integrated_showcase",
        [horizontal_input, heterogeneous_input, rows],
        [horizontal_output, heterogeneous_output, replicated_output],
        initializers,
        value_info=value_info,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 10
    model.producer_name = "CIM-compiler-design"
    model.producer_version = "1"
    return _write(model, "integrated_showcase")


def build_legalization_showcase() -> Path:
    """Two weights requiring complementary N and K Array tiling."""
    rng = np.random.default_rng(20260727)
    column_k, column_n = 128, 768
    row_k, row_n = 1536, 64
    column_input = helper.make_tensor_value_info(
        "ColumnInput", TensorProto.INT8, [1, column_k]
    )
    row_input = helper.make_tensor_value_info(
        "RowInput", TensorProto.INT8, [1, row_k]
    )
    column_output = helper.make_tensor_value_info(
        "ColumnOutput", TensorProto.INT32, [1, column_n]
    )
    row_output = helper.make_tensor_value_info(
        "RowOutput", TensorProto.INT32, [1, row_n]
    )
    initializers = [
        numpy_helper.from_array(
            rng.integers(
                -4, 5, size=(column_n, column_k), dtype=np.int8
            ),
            name="ColumnWeight",
        ),
        numpy_helper.from_array(
            rng.integers(-4, 5, size=(row_n, row_k), dtype=np.int8),
            name="RowWeight",
        ),
    ]
    graph = helper.make_graph(
        [
            helper.make_node(
                "MatMulInteger",
                ["ColumnInput", "ColumnWeight"],
                ["ColumnOutput"],
            ),
            helper.make_node(
                "MatMulInteger",
                ["RowInput", "RowWeight"],
                ["RowOutput"],
            ),
        ],
        "legalization_showcase",
        [column_input, row_input],
        [column_output, row_output],
        initializers,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 10
    model.producer_name = "CIM-compiler-design"
    model.producer_version = "1"
    return _write(model, "legalization_showcase")


def build_elementwise_showcase() -> Path:
    """One linear stage feeding the full Add/Sub/Mul/Div elementwise set."""
    rng = np.random.default_rng(20260726)
    batch, inputs, outputs = 4, 32, 16
    x = helper.make_tensor_value_info("X", TensorProto.INT32, [batch, inputs])
    y = helper.make_tensor_value_info("Y", TensorProto.INT32, [batch, outputs])
    # Non-splat constant operands keep every elementwise op observable: a splat
    # would collapse into an immediate and a random input could divide by zero.
    scale = rng.integers(2, 5, size=(batch, outputs), dtype=np.int32)
    divisor = rng.integers(3, 9, size=(batch, outputs), dtype=np.int32)
    divisor[::2] *= -1
    initializers = [
        numpy_helper.from_array(
            rng.integers(-4, 4, size=(outputs, inputs), dtype=np.int8), name="W0"
        ),
        numpy_helper.from_array(
            rng.integers(-4, 4, size=(outputs, inputs), dtype=np.int8), name="W1"
        ),
        numpy_helper.from_array(
            rng.integers(-64, 64, size=(batch, outputs), dtype=np.int32),
            name="Offset",
        ),
        numpy_helper.from_array(scale, name="Scale"),
        numpy_helper.from_array(divisor, name="Divisor"),
    ]
    nodes = [
        helper.make_node("Gemm", ["X", "W0"], ["P0"], name="linear0", transB=1),
        helper.make_node("Gemm", ["X", "W1"], ["P1"], name="linear1", transB=1),
        helper.make_node("Add", ["P0", "P1"], ["Sum"], name="add"),
        helper.make_node("Sub", ["Sum", "Offset"], ["Diff"], name="sub"),
        helper.make_node("Mul", ["Diff", "Scale"], ["Prod"], name="mul"),
        helper.make_node("Div", ["Prod", "Divisor"], ["Y"], name="div"),
    ]
    value_info = [
        helper.make_tensor_value_info(name, TensorProto.INT32, [batch, outputs])
        for name in ("P0", "P1", "Sum", "Diff", "Prod")
    ]
    graph = helper.make_graph(
        nodes,
        "elementwise_showcase",
        [x],
        [y],
        initializers,
        value_info=value_info,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 10
    model.producer_name = "CIM-compiler-design"
    model.producer_version = "1"
    return _write(model, "elementwise_showcase")


def main() -> int:
    builders = [
        build_stress_sram_slice,
        build_stress_two_linear,
        build_stress_shared_weight,
        build_stress_branch_fanout,
        build_stress_partial_sum,
        build_stress_stream_high_load,
        build_resource_showcase,
        build_weight_replication_showcase,
        build_heterogeneous_fusion_showcase,
        build_integrated_showcase,
        build_legalization_showcase,
        build_elementwise_showcase,
    ]
    for builder in builders:
        print(builder())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
