from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from cim_compiler.tool_paths import iree_compile_path, iree_import_onnx_path


class CompileError(RuntimeError):
    """Raised when the compiler pipeline cannot produce valid CIM artifacts."""


IREE_COMPILE_STAGES = {
    "preprocessing",
    "flow",
    "stream",
    "executable-configurations",
    "executable-targets",
    "hal",
}
PIPELINE_TARGETS = IREE_COMPILE_STAGES | {"payload", "vmfb"}
OPTIMIZATION_PIPELINES = (
    "direct",
    "packed",
    "heterogeneous",
    "replicated",
)
SRAM_ALLOCATIONS = ("sequential", "reuse")


def emit_pipeline_artifacts(
    model_path: str | Path,
    emit_dir: str | Path,
    *,
    compile_to: str = "payload",
    optimization_pipeline: str = "replicated",
    sram_allocation: str = "reuse",
    emit_stages: bool = False,
) -> dict[str, Path]:
    if emit_stages and compile_to not in {"payload", "vmfb"}:
        raise CompileError("--emit-stages requires a complete payload or vmfb compile")
    model = Path(model_path).resolve()
    output_dir = Path(emit_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    torch_mlir = output_dir / f"{model.stem}.onnx_torch.mlir"
    _run_iree_import_onnx(model, torch_mlir)
    emitted_paths = {"onnx_torch_mlir": torch_mlir}

    stages_dir = output_dir / "stages" if emit_stages else None
    if stages_dir:
        emitted_paths.update(
            stages_iree=stages_dir / "iree", stages_cim=stages_dir / "cim"
        )
    if compile_to == "payload":
        emitted_paths.update(
            _emit_payloads(
                model.stem,
                torch_mlir,
                output_dir,
                optimization_pipeline,
                sram_allocation,
                stages_dir,
            )
        )
    else:
        stage = None if compile_to == "vmfb" else compile_to
        suffix = "iree_linalg" if stage == "preprocessing" else stage
        key = f"{stage}_mlir" if stage else "vmfb"
        output = output_dir / (
            f"{model.stem}.{suffix}.mlir" if stage else f"{model.stem}.vmfb"
        )
        _run_iree_compile(
            torch_mlir,
            output,
            stage,
            optimization_pipeline,
            sram_allocation,
            dump_stages_dir=stages_dir,
        )
        emitted_paths[key] = output
    return emitted_paths


def _run_iree_import_onnx(model_path: Path, output_path: Path) -> None:
    completed = subprocess.run(
        [
            str(iree_import_onnx_path()),
            str(model_path),
            "--opset-version",
            "17",
            "-o",
            str(output_path),
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise CompileError((completed.stderr or completed.stdout).strip())


def _run_iree_compile(
    onnx_torch_mlir: Path,
    output_path: Path,
    compile_to: str | None,
    optimization_pipeline: str,
    sram_allocation: str,
    *,
    dump_isa_dir: Path | None = None,
    dump_stages_dir: Path | None = None,
) -> None:
    args = [
        str(iree_compile_path()),
        "--iree-plugin=cim",
        "--iree-input-type=onnx",
        "--iree-torch-use-strict-symbolic-shapes",
        "--iree-torch-decompose-complex-ops",
        "--iree-torch-enable-shape-refinement",
        "--iree-hal-target-device=local",
        "--iree-hal-local-target-device-backends=cim",
        "--iree-cim-hardware-profile=competition",
        f"--iree-cim-optimization-pipeline={optimization_pipeline}",
        f"--iree-cim-sram-allocation={sram_allocation}",
        "--iree-flow-inline-constants-max-byte-length=2147483647",
    ]
    if dump_isa_dir is not None:
        args.append(f"--iree-hal-dump-executable-binaries-to={dump_isa_dir}")
    if dump_stages_dir is not None:
        args.extend(
            [
                f"--dump-compilation-phases-to={dump_stages_dir / 'iree'}",
                f"--iree-cim-dump-physicalization-to={dump_stages_dir / 'cim'}",
            ]
        )
    if compile_to is not None:
        args.append(f"--compile-to={compile_to}")
    args.extend([str(onnx_torch_mlir), "-o", str(output_path)])
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise CompileError((completed.stderr or completed.stdout).strip())


def _emit_payloads(
    model_name: str,
    onnx_torch_mlir: Path,
    output_dir: Path,
    optimization_pipeline: str,
    sram_allocation: str,
    stages_dir: Path | None,
) -> dict[str, Path]:
    with tempfile.TemporaryDirectory(
        prefix=f"{model_name}.native.", dir=output_dir
    ) as dump_dir:
        compiler_output = Path(dump_dir) / (
            f"{model_name}.vmfb" if stages_dir else f"{model_name}.hal.mlir"
        )
        _run_iree_compile(
            onnx_torch_mlir,
            compiler_output,
            None if stages_dir else "hal",
            optimization_pipeline,
            sram_allocation,
            dump_isa_dir=Path(dump_dir),
            dump_stages_dir=stages_dir,
        )
        dumped = Path(dump_dir)
        payload = output_dir / f"{model_name}.cim.payload"
        isa = output_dir / f"{model_name}.cim.isa"
        shutil.copyfile(next(dumped.glob("*.cim.payload")), payload)
        shutil.copyfile(next(dumped.glob("*.cim.isa")), isa)
        return {"payload": payload, "isa": isa}
