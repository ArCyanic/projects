"""Process and native-thread parallelism for the Python 3.14 mainline."""

import os
import platform
from multiprocessing import get_context

CPU_BUDGET_ENV = "NPU_WORKERS"
DEFAULT_CPU_BUDGET = {
    "Darwin": 8,
    "Linux": 32,
}
CPU_BUDGET = max(
    1,
    min(
        int(os.environ.get(CPU_BUDGET_ENV, DEFAULT_CPU_BUDGET[platform.system()])),
        os.process_cpu_count() or 1,
    ),
)

os.environ["NUMBA_THREADING_LAYER"] = "workqueue"
os.environ["NUMBA_NUM_THREADS"] = str(CPU_BUDGET)
os.environ["OMP_NUM_THREADS"] = str(CPU_BUDGET)

PROCESS_CONTEXT = get_context()


def executor_worker_count(job_count: int) -> int:
    """Bound workers by the process CPU budget and submitted jobs."""
    return max(1, min(CPU_BUDGET, job_count))
