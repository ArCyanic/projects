import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_showcase_reports_each_ablation_edge(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/cim-showcase"),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    for edge in (
        "horizontal packing",
        "heterogeneous fusion",
        "weight replication",
        "SRAM lifetime reuse",
        "integrated",
        "two-dimensional legalization",
        "legalization tiles [K,N]: 128x384 + 128x384 + 768x64 + 768x64",
        "legalization MVM windows: 4",
    ):
        assert edge in completed.stdout
    assert (
        "heterogeneous fusion MVM windows: 6 -> 4 (33.3% reduction)" in completed.stdout
    )
    assert "integrated MVM windows: 24 -> 8" in completed.stdout


@pytest.mark.parametrize(
    ("case", "needs_import"),
    [
        ("read_suffix", True),
        ("export_suffix", True),
        ("cover_rows", False),
        ("inplace", True),
    ],
)
def test_boundary_import_requires_initialized_regions(
    tmp_path: Path, case: str, needs_import: bool
) -> None:
    source = (
        "%prefix : memref<2xi32, strided<[1]>>"
        if case == "inplace"
        else "%ones : memref<2xi32>"
    )
    body = {
        "read_suffix": """
          cim.elt <add> <vi> ins(%suffix : memref<2xi32, strided<[1], offset: 2>>)
            outs(%prefix : memref<2xi32, strided<[1]>>) <{immediate = 0 : i64}>""",
        "export_suffix": """
          cim.elt <add> <vi> ins(%ones : memref<2xi32>)
            outs(%suffix : memref<2xi32, strided<[1], offset: 2>>) <{immediate = 0 : i64}>""",
        "cover_rows": """
          %suffix_cast = memref.cast %suffix : memref<2xi32, strided<[1], offset: 2>> to memref<2xi32, strided<[1], offset: ?>>
          cim.elt <add> <vi> ins(%ones : memref<2xi32>)
            outs(%suffix_cast : memref<2xi32, strided<[1], offset: ?>>) <{immediate = 0 : i64}>
          cim.elt <add> <vi> ins(%ones : memref<2xi32>)
            outs(%tail : memref<2xi32, strided<[1], offset: 4>>) <{immediate = 0 : i64}>""",
        "inplace": "",
    }[case]
    program = tmp_path / "boundary.mlir"
    program.write_text(
        f"""
#layout = #hal.pipeline.layout<bindings = [#hal.pipeline.binding<storage_buffer>], flags = None>
module {{
  hal.executable public @probe {{
    hal.executable.variant public @cim_executable target(<"cim", "cim-executable", {{profile = "competition"}}>) {{
      hal.executable.export public @probe ordinal(0) layout(#layout)
      builtin.module {{
        memref.global "private" constant @ones : memref<2xi32> = dense<1>
        func.func @probe() {{
          %c0 = arith.constant 0 : index
          %ones = memref.get_global @ones : memref<2xi32>
          %input = hal.interface.binding.subspan layout(#layout) binding(0) offset(%c0) : memref<3x2xi32>
          %prefix = memref.subview %input[0, 0] [1, 2] [1, 1] : memref<3x2xi32> to memref<2xi32, strided<[1]>>
          %suffix = memref.subview %input[1, 0] [1, 2] [1, 1] : memref<3x2xi32> to memref<2xi32, strided<[1], offset: 2>>
          %tail = memref.subview %input[2, 0] [1, 2] [1, 1] : memref<3x2xi32> to memref<2xi32, strided<[1], offset: 4>>
          cim.elt <add> <vi> ins({source})
            outs(%prefix : memref<2xi32, strided<[1]>>) <{{immediate = 0 : i64}}>
          {body}
          return
        }}
      }}
    }}
  }}
}}
"""
    )
    result = subprocess.run(
        [
            str(ROOT / "iree-build/tools/iree-opt"),
            "--iree-plugin=cim",
            "--pass-pipeline=builtin.module(cim-materialize-sram)",
            str(program),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    binding = next(
        line.split(" = ")[0].strip()
        for line in lines
        if " = hal.interface.binding.subspan " in line
    )
    assert (
        any(line.strip().startswith(f"memref.copy {binding},") for line in lines)
        is needs_import
    ), result.stdout
