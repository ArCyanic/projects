"""Parallel execution of explicit Prefill windows."""

import numpy as np
from parallelism import PROCESS_CONTEXT, executor_worker_count
from simulation.prefill.execution import (
    PrefillExecutor,
    execute_prefill,
)
from simulation.prefill.telemetry import PrefillExecution
from simulation.workload import ReportDepth

_worker_executors: tuple[PrefillExecutor, ...]
_worker_routes: np.ndarray


def execute_windows(
    executors: tuple[PrefillExecutor, ...],
    routes: np.ndarray,
    windows: tuple[tuple[int, int], ...],
    capture: ReportDepth,
) -> tuple[tuple[PrefillExecution, ...], ...]:
    jobs = tuple(
        (candidate, start, token_count, capture)
        for candidate in range(len(executors))
        for start, token_count in windows
    )
    with PROCESS_CONTEXT.Pool(
        executor_worker_count(len(jobs)),
        initializer=_initialize_worker,
        initargs=(executors, routes),
    ) as workers:
        executions = tuple(workers.map(_execute_job, jobs, chunksize=1))
    window_count = len(windows)
    return tuple(
        executions[candidate * window_count : (candidate + 1) * window_count]
        for candidate in range(len(executors))
    )


def _initialize_worker(
    executors: tuple[PrefillExecutor, ...],
    routes: np.ndarray,
) -> None:
    global _worker_executors, _worker_routes
    _worker_executors = executors
    _worker_routes = routes


def _execute_job(
    job: tuple[int, int, int, ReportDepth],
) -> PrefillExecution:
    candidate, start, token_count, capture = job
    return execute_prefill(
        _worker_executors[candidate],
        _worker_routes[start : start + token_count],
        capture,
    )
