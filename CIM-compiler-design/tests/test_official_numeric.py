import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

import onnx
from onnx import helper, numpy_helper

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_MODELS = [
    ("int8_linear_model", "int8_linear_graph"),
    ("int8_linear_add", "int8_linear_add_very_large_graph"),
    ("four_operator_sequential", "four_operator_int8_graph"),
    ("residual_four_op", "residual_graph"),
    ("three_branch_four_op", "three_branch_graph"),
]
SHOWCASE_MODELS = [
    ("resource_showcase", "cim_resource_showcase"),
    ("weight_replication_showcase", "weight_replication_showcase"),
    ("heterogeneous_fusion_showcase", "heterogeneous_fusion_showcase"),
    ("integrated_showcase", "integrated_showcase"),
    ("legalization_showcase", "legalization_showcase"),
    ("elementwise_showcase", "elementwise_showcase"),
]
MODELS = OFFICIAL_MODELS + SHOWCASE_MODELS


def attribute(node: onnx.NodeProto, name: str, default):
    for candidate in node.attribute:
        if candidate.name == name:
            return helper.get_attribute_value(candidate)
    return default


def contest_weight_layout(lhs: tuple[int, ...], rhs: tuple[int, ...]) -> bool:
    """Contest models ship [N, K] weights that the compiler transposes.

    Mirrors ``hasContestRHSShape`` in ``CIMNormalizeONNXLinear.cpp``: an
    untransposed RHS whose trailing dimension matches the LHS contraction
    dimension is a contest-style weight, not a standard ONNX operand.
    """
    return len(rhs) == 2 and lhs[-1] == rhs[1]


def ort_reference_outputs(
    model_path: Path, inputs: list[np.ndarray], temp_dir: Path
) -> list[np.ndarray]:
    """Run an ORT-compatible projection of a contest or showcase model."""
    import onnxruntime as ort

    model = onnx.load(model_path)
    dtypes = {
        value.name: value.type.tensor_type.elem_type
        for value in [
            *model.graph.input,
            *model.graph.value_info,
            *model.graph.output,
        ]
        if value.type.tensor_type.elem_type
    }
    dtypes.update(
        {
            initializer.name: initializer.data_type
            for initializer in model.graph.initializer
        }
    )
    initializers = {
        initializer.name: numpy_helper.to_array(initializer)
        for initializer in model.graph.initializer
    }
    shapes = {
        value.name: tuple(
            dimension.dim_value for dimension in value.type.tensor_type.shape.dim
        )
        for value in [
            *model.graph.input,
            *model.graph.value_info,
            *model.graph.output,
        ]
    }
    shapes.update({name: tuple(value.shape) for name, value in initializers.items()})
    nodes = []
    added_initializers = []
    for node in model.graph.node:
        if node.op_type == "MatMulInteger":
            rhs = f"{node.input[1]}__ort_rhs"
            rhs_values = initializers[node.input[1]]
            if contest_weight_layout(shapes[node.input[0]], shapes[node.input[1]]):
                rhs_values = rhs_values.T
            added_initializers.append(numpy_helper.from_array(rhs_values, rhs))
            nodes.append(
                helper.make_node("MatMulInteger", [node.input[0], rhs], node.output)
            )
            dtypes[node.output[0]] = onnx.TensorProto.INT32
        elif node.op_type == "Gemm":
            for name, default in (("alpha", 1.0), ("beta", 1.0), ("transA", 0)):
                assert attribute(node, name, default) == default, (
                    f"ORT projection requires default Gemm {name}; "
                    "provide an independent expected output for this case"
                )
            output = node.output[0]
            rhs = f"{node.input[1]}__ort_rhs"
            rhs_values = initializers[node.input[1]]
            if attribute(node, "transB", 0) or contest_weight_layout(
                shapes[node.input[0]], shapes[node.input[1]]
            ):
                rhs_values = rhs_values.T
            if dtypes[node.input[0]] == onnx.TensorProto.INT8:
                rhs_values = rhs_values.astype(np.int8)
                op_type = "MatMulInteger"
            else:
                rhs_values = rhs_values.astype(np.int32)
                op_type = "MatMul"
            added_initializers.append(numpy_helper.from_array(rhs_values, rhs))
            product = f"{output}__ort_product" if len(node.input) == 3 else output
            nodes.append(helper.make_node(op_type, [node.input[0], rhs], [product]))
            if len(node.input) == 3:
                nodes.append(
                    helper.make_node("Add", [product, node.input[2]], [output])
                )
            dtypes[output] = onnx.TensorProto.INT32
        else:
            nodes.append(node)
            dtypes[node.output[0]] = dtypes[node.input[0]]
    del model.graph.node[:]
    model.graph.node.extend(nodes)
    model.graph.initializer.extend(added_initializers)
    model.ir_version = 10
    canonical_path = temp_dir / f"{model_path.stem}.ort.onnx"
    onnx.checker.check_model(model)
    onnx.save(model, canonical_path)
    session = ort.InferenceSession(
        str(canonical_path), providers=["CPUExecutionProvider"]
    )
    feeds = {meta.name: array for meta, array in zip(session.get_inputs(), inputs)}
    return session.run(None, feeds)


def _compile_model(model_path: Path, emit_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/cim-compile"),
            str(model_path),
            "--emit-dir",
            str(emit_dir),
            "--compile-to",
            "vmfb",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _assert_model_runs_bit_exact(
    model_path: Path,
    function_name: str,
    emit_dir: Path,
    inputs: list[np.ndarray],
    *,
    expected_outputs: list[np.ndarray] | None = None,
) -> None:
    model = onnx.load(model_path)
    compile_result = _compile_model(model_path, emit_dir)
    assert compile_result.returncode == 0, compile_result.stderr

    input_paths = []
    for index, array in enumerate(inputs):
        path = emit_dir / f"input_{index}.npy"
        np.save(path, array)
        input_paths.append(path)
    output_paths = [
        emit_dir / f"actual_{index}.npy" for index in range(len(model.graph.output))
    ]
    run_result = subprocess.run(
        [
            str(ROOT / "iree-build/tools/iree-run-module"),
            f"--module={emit_dir / f'{model_path.stem}.vmfb'}",
            "--device=cim",
            f"--function={function_name}",
            *(f"--input=@{path}" for path in input_paths),
            *(f"--output=@{path}" for path in output_paths),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert run_result.returncode == 0, run_result.stderr
    if expected_outputs is None:
        expected_outputs = ort_reference_outputs(model_path, inputs, emit_dir.parent)
    for output_path, expected in zip(output_paths, expected_outputs):
        np.testing.assert_array_equal(np.load(output_path), expected)


@pytest.mark.parametrize(("model_name", "function_name"), MODELS)
def test_model_runs_bit_exact(
    tmp_path: Path, model_name: str, function_name: str
) -> None:
    model_path = ROOT / f"onnx/{model_name}.onnx"
    model = onnx.load(model_path)
    rng = np.random.default_rng(20260722)
    inputs = []
    for value in model.graph.input:
        shape = tuple(dim.dim_value for dim in value.type.tensor_type.shape.dim)
        if value.type.tensor_type.elem_type == onnx.TensorProto.INT8:
            array = rng.integers(-128, 128, size=shape, dtype=np.int8)
        else:
            array = rng.integers(-1024, 1024, size=shape, dtype=np.int32)
        inputs.append(array)
    _assert_model_runs_bit_exact(
        model_path, function_name, tmp_path / "artifacts", inputs
    )


@pytest.mark.parametrize(
    ("case", "diagnostic"),
    [
        ("alpha", "requires transA=0, alpha=1 and beta=1"),
        ("beta", "requires transA=0, alpha=1 and beta=1"),
        ("transA", "requires transA=0, alpha=1 and beta=1"),
        ("uint8", "failed to legalize operation"),
        ("runtime_weight", "requires an immutable static i8 constant"),
    ],
)
def test_unsupported_linear_contract_is_rejected(
    tmp_path: Path, case: str, diagnostic: str
) -> None:
    dtype = onnx.TensorProto.UINT8 if case == "uint8" else onnx.TensorProto.INT8
    weight = np.array([[1, 2], [3, 4]], dtype=np.uint8 if case == "uint8" else np.int8)
    inputs = [helper.make_tensor_value_info("A", dtype, [2, 2])]
    initializers = []
    if case == "runtime_weight":
        inputs.append(helper.make_tensor_value_info("W", dtype, [2, 2]))
    else:
        initializers.append(numpy_helper.from_array(weight, "W"))
    attrs = {}
    if case in {"alpha", "beta", "transA"}:
        attrs[case] = 1 if case == "transA" else 2.0
    node = helper.make_node(
        "MatMulInteger" if case == "uint8" else "Gemm", ["A", "W"], ["Y"], **attrs
    )
    graph = helper.make_graph(
        [node],
        "unsupported_linear",
        inputs,
        [helper.make_tensor_value_info("Y", onnx.TensorProto.INT32, [2, 2])],
        initializers,
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    model_path = tmp_path / f"{case}.onnx"
    onnx.save(model, model_path)
    result = _compile_model(model_path, tmp_path / "artifacts")
    assert result.returncode > 0, result.stderr
    assert diagnostic in result.stderr


def test_native_signed_gemm_preserves_alpha_and_bias(tmp_path: Path) -> None:
    activation = np.array([[-128, 2, 3], [4, -5, 127]], dtype=np.int8)
    weight = np.array([[1, -2, 3], [-4, 5, -6]], dtype=np.int8)
    bias = np.array([1, -3], dtype=np.int32)
    graph = helper.make_graph(
        [helper.make_node("Gemm", ["A", "W", "B"], ["Y"], transB=1, alpha=2.0)],
        "native_signed_gemm",
        [helper.make_tensor_value_info("A", onnx.TensorProto.INT8, [2, 3])],
        [helper.make_tensor_value_info("Y", onnx.TensorProto.INT32, [2, 2])],
        [numpy_helper.from_array(weight, "W"), numpy_helper.from_array(bias, "B")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    model_path = tmp_path / "native_signed_gemm.onnx"
    onnx.save(model, model_path)
    expected = 2 * (activation.astype(np.int32) @ weight.astype(np.int32).T) + bias
    _assert_model_runs_bit_exact(
        model_path,
        graph.name,
        tmp_path / "artifacts",
        [activation],
        expected_outputs=[expected],
    )
