"""Latency summaries use NumPy's linear percentile definition."""

import numpy as np


def latency_summary(latency: np.ndarray) -> dict[str, float]:
    return {
        "mean_ns": float(latency.mean()),
        "p95_ns": float(np.percentile(latency, 95)),
    }
