import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")


def optimize(source: str, pipeline: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            str(ROOT / "iree-build/tools/iree-opt"),
            "--iree-plugin=cim",
            f"--pass-pipeline=builtin.module({pipeline})",
        ],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("resource", [False, True])
def test_packed_weight_preserves_byte_view_shift(resource: bool) -> None:
    source = (FIXTURES / "weight-byte-view.mlir").read_text()
    if resource:
        source = source.replace("dense<[99, 98, 1, 2, 3, 4]>", "dense_resource<w>")
        source += (
            '\n{-# dialect_resources: {builtin: {w: "0x08000000636201020304"}} #-}\n'
        )
    result = optimize(source, "cim-pack-horizontal-mvms")
    assert result.returncode == 0, result.stderr
    assert "dense<[[1, 2, 1, 2], [3, 4, 3, 4]]>" in result.stdout


def test_heterogeneous_fusion_preserves_activation_indexing() -> None:
    result = optimize(
        (FIXTURES / "hetero-transpose-map.mlir").read_text(),
        "cim-fuse-heterogeneous-contractions",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("linalg.matmul") == 2
    assert "tensor.concat" not in result.stdout


@pytest.mark.parametrize(
    "fixture", ["unsigned-named", "unsigned-generic", "transposed-activation"]
)
def test_contraction_conversion_rejects_incompatible_semantics(fixture: str) -> None:
    result = optimize(
        (FIXTURES / f"{fixture}.mlir").read_text(),
        "func.func(cim-convert-linalg-to-cim)",
    )
    assert result.returncode != 0
    assert "failed to legalize operation" in result.stderr


@pytest.mark.parametrize("pipeline", ["direct", "heterogeneous"])
def test_resource_weight_participates_in_complete_deployment(
    tmp_path: Path, pipeline: str
) -> None:
    source = (FIXTURES / "weight-inventory.mlir").read_text()
    source = source.replace("dense<3>", "dense_resource<large_weight>")
    source += (
        '\n{-# dialect_resources: {builtin: {large_weight: "0x08000000'
        + "03" * (768 * 512)
        + '"}} #-}\n'
    )
    result = subprocess.run(
        [
            str(ROOT / "iree-build/tools/iree-compile"),
            "--iree-plugin=cim",
            "--iree-input-type=none",
            "--iree-hal-target-device=local",
            "--iree-hal-local-target-device-backends=cim",
            "--iree-flow-inline-constants-max-byte-length=2147483647",
            f"--iree-cim-optimization-pipeline={pipeline}",
            "-",
            "-o",
            str(tmp_path / "inventory.vmfb"),
        ],
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("base", "coefficient", "memref_type", "accepted"),
    [
        (16, 4, "memref<1xi8>", True),
        (2**32 - 1, 0, "memref<1xi8>", True),
        (-1, 0, "memref<1xi8>", False),
        (16, -4, "memref<1xi8>", False),
        (2**32, 0, "memref<1xi8>", False),
        (0, 2**32, "memref<1xi8>", False),
        (0, 0, f"memref<{2**32}xi8>", False),
        (0, 0, f"memref<2xi32, strided<[{2**30}]>>", False),
        (0, 0, "memref<2xi8, strided<[-1], offset: 1>>", False),
    ],
)
def test_payload_address_fields_are_representable(
    base: int, coefficient: int, memref_type: str, accepted: bool
) -> None:
    source = f"""
#layout = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer>], flags = None>
module {{
  hal.executable public @probe {{
    hal.executable.variant public @cim_executable target(<"cim", "cim-executable", {{profile = "competition"}}>) {{
      hal.executable.export public @probe ordinal(0) layout(#layout)
      builtin.module {{
        func.func @probe() {{
          %x = hal.interface.workgroup.id[0] : index
          %addr = affine.apply affine_map<(x) -> ({base} + {coefficient} * x)> (%x)
          %v = hal.interface.binding.subspan layout(#layout) binding(0) offset(%addr) : {memref_type}
          memref.copy %v, %v : {memref_type} to {memref_type}
          return
        }}
      }}
    }}
  }}
}}
"""
    result = optimize(source, "hal.executable(iree-hal-serialize-all-executables)")
    assert (result.returncode == 0) == accepted, result.stderr
    if not accepted:
        assert (
            "CIM payload geometry requires nonnegative 32-bit fields" in result.stderr
        )
