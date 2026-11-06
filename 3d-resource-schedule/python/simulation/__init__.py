"""Physical evaluation of deployments against explicit phase workloads."""

from dataclasses import dataclass

from deployment import Deployment

from simulation.decode import (
    DecodeMeasurement,
    compile_decode_executor,
    measure_decode_routes,
)
from simulation.prefill.evaluation import execute_windows
from simulation.prefill.execution import compile_prefill_executor
from simulation.prefill.telemetry import PrefillExecution
from simulation.workload import ExecutionWorkload, ReportDepth


@dataclass(slots=True)
class DeploymentExecution:
    decode: DecodeMeasurement
    prefill: tuple[PrefillExecution, ...]


def evaluate_deployments(
    deployments: tuple[Deployment, ...],
    workload: ExecutionWorkload,
    depth: ReportDepth = "objective",
) -> tuple[DeploymentExecution, ...]:
    prefill = (
        execute_windows(
            tuple(compile_prefill_executor(deployment) for deployment in deployments),
            workload.prefill_routes,
            workload.prefill_windows,
            depth,
        )
        if workload.prefill_windows
        else ((),) * len(deployments)
    )
    return tuple(
        DeploymentExecution(
            measure_decode_routes(
                compile_decode_executor(deployment), workload.decode_routes, depth
            ),
            executions,
        )
        for deployment, executions in zip(deployments, prefill, strict=True)
    )


__all__ = (
    "DeploymentExecution",
    "ExecutionWorkload",
    "ReportDepth",
    "evaluate_deployments",
)
