"""Performance metrics projected from the shared physical execution."""

from deployment import Deployment
from simulation import evaluate_deployments
from simulation.workload import REPORT_DEPTHS, ExecutionWorkload, ReportDepth

from profiler.metrics.decode import profile_decode_measurement
from profiler.metrics.prefill import profile_prefill, profile_prefill_execution
from profiler.result import ProfilingResult


def profile(
    deployment: Deployment,
    workload: ExecutionWorkload,
    depth: ReportDepth = "bottleneck",
) -> ProfilingResult:
    (execution,) = evaluate_deployments((deployment,), workload, depth)
    decode = profile_decode_measurement(workload.decode_routes, execution.decode, depth)
    token_counts = tuple(dict.fromkeys(count for _, count in workload.prefill_windows))
    prefill = tuple(
        profile_prefill(
            tuple(
                item
                for item in execution.prefill
                if len(item.token_latency_ns) == count
            ),
            count,
            deployment.model.program.dependency_bound_ns,
            depth,
        )
        for count in token_counts
    )
    return ProfilingResult(
        deployment.model.hardware_profile.hardware_id,
        len(workload.decode_routes),
        depth,
        decode,
        prefill,
    )


__all__ = (
    "REPORT_DEPTHS",
    "ExecutionWorkload",
    "ProfilingResult",
    "ReportDepth",
    "profile",
    "profile_prefill_execution",
)
