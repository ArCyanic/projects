"""Shared native tool paths for the CIM compiler toolchain."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_tool(env_var: str, default_path: Path, label: str) -> Path:
    configured = os.environ.get(env_var)
    resolved = Path(configured) if configured else default_path
    if not resolved.exists():
        raise FileNotFoundError(f"{label} not found: {resolved}")
    return resolved


def iree_compile_path() -> Path:
    return _resolve_tool(
        "CIM_IREE_COMPILE",
        REPO_ROOT / "iree-build" / "tools" / "iree-compile",
        "iree-compile",
    )


def iree_import_onnx_path() -> Path:
    configured = os.environ.get("CIM_IREE_IMPORT_ONNX")
    if configured:
        return _resolve_tool(
            "CIM_IREE_IMPORT_ONNX", Path(configured), "iree-import-onnx"
        )
    repo_tool = REPO_ROOT / "iree-build" / "tools" / "iree-import-onnx"
    if repo_tool.exists():
        return repo_tool
    resolved = shutil.which("iree-import-onnx")
    if not resolved:
        raise FileNotFoundError(f"iree-import-onnx not found: {repo_tool}")
    return Path(resolved)
