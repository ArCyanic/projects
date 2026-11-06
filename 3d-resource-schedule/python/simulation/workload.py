"""Shared workload identities for formal profiling and validation."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

type ReportDepth = Literal["objective", "bottleneck", "trace"]
REPORT_DEPTHS: tuple[ReportDepth, ...] = ("objective", "bottleneck", "trace")

PREFILL_TOKEN_COUNTS = (32, 128, 512)
PREFILL_EVALUATION_WINDOW_LIMIT = 8


@dataclass(slots=True)
class ExecutionWorkload:
    decode_routes: np.ndarray
    prefill_routes: np.ndarray
    prefill_windows: tuple[tuple[int, int], ...]


def fixed_prefill_windows(window_count: int) -> tuple[tuple[int, int], ...]:
    """Use the same 512-route stride for every formal Prefill batch size."""
    return tuple(
        (window * 512, tokens)
        for tokens in PREFILL_TOKEN_COUNTS
        for window in range(window_count)
    )


def evaluation_workload(
    decode_routes: np.ndarray,
    prefill_routes: np.ndarray,
    token_counts: tuple[int, ...] = PREFILL_TOKEN_COUNTS,
) -> ExecutionWorkload:
    windows = []
    for token_count in token_counts:
        batch_count = min(
            PREFILL_EVALUATION_WINDOW_LIMIT, len(prefill_routes) // token_count
        )
        windows.extend(
            (int(start), token_count)
            for start in np.linspace(
                0,
                len(prefill_routes) - token_count,
                batch_count,
                dtype=np.int64,
            )
        )
    return ExecutionWorkload(decode_routes, prefill_routes, tuple(windows))
