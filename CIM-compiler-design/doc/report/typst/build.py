"""Compile the formal design report and refresh diagram PDFs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DIAGRAMS = (
    "cim-ir-pass-isa-mapping",
    "hardware-execution-model",
    "integrated-before-after",
    "iree-cim-architecture",
    "legalization-before-after",
    "numeric-verification-paths",
    "optimization-evidence",
    "sram-lifetime-before-after",
    "two-level-tiling-pass-scope",
    "weight-optimization-primitives",
)


def render_diagrams() -> None:
    drawio = shutil.which("drawio")
    if drawio is None:
        drawio = "/Applications/draw.io.app/Contents/MacOS/draw.io"
        if not Path(drawio).exists():
            return
    output_dir = HERE / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = HERE.parent / "assets"
    for name in DIAGRAMS:
        source = source_dir / f"{name}.drawio"
        if not source.exists():
            continue
        subprocess.run(
            [
                drawio,
                "--export",
                "--format",
                "pdf",
                "--crop",
                "--output",
                str(output_dir / f"{name}.pdf"),
                str(source),
            ],
            check=True,
        )


def compile_report() -> None:
    typst = shutil.which("typst")
    if typst is None:
        raise RuntimeError("typst is required to compile the report")
    output_dir = ROOT / "output" / "pdf"
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            typst,
            "compile",
            "--root",
            str(ROOT),
            str(HERE / "formal-report.typ"),
            str(output_dir / "cim-compiler-design-formal.pdf"),
        ],
        check=True,
    )
    subprocess.run(
        [
            typst,
            "compile",
            "--root",
            str(ROOT),
            str(HERE / "presentation.typ"),
            str(output_dir / "cim-compiler-presentation.pdf"),
        ],
        check=True,
    )


def main() -> None:
    render_diagrams()
    compile_report()


if __name__ == "__main__":
    main()
