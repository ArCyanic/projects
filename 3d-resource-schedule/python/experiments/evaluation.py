"""Formal experiment metrics projected from shared physical execution facts."""

import json

import numpy as np
from deployment import Deployment
from simulation import DeploymentExecution, ExecutionWorkload, evaluate_deployments
from simulation.workload import fixed_prefill_windows
from simulation.statistics import latency_summary


def prefill_makespans(execution: DeploymentExecution) -> dict[str, np.ndarray]:
    counts = tuple(
        dict.fromkeys(len(row.token_latency_ns) for row in execution.prefill)
    )
    return {
        str(count): np.asarray(
            [
                row.makespan_ns
                for row in execution.prefill
                if len(row.token_latency_ns) == count
            ],
            dtype=np.int64,
        )
        for count in counts
    }


def deployment_metrics(execution: DeploymentExecution) -> dict[str, object]:
    return {
        "decode": latency_summary(execution.decode.latency_ns),
        "prefill": {
            count: latency_summary(times)
            for count, times in prefill_makespans(execution).items()
        },
    }


def measure_capacity_deployments(
    deployments: tuple[Deployment, ...],
    routes: np.ndarray,
    prefill_routes: np.ndarray,
    window_count: int,
) -> tuple[dict[str, object], ...]:
    executions = evaluate_deployments(
        deployments,
        ExecutionWorkload(routes, prefill_routes, fixed_prefill_windows(window_count)),
    )
    summaries = []
    for execution in executions:
        metrics = deployment_metrics(execution)
        metrics["decode"].update(
            {
                name: float(getattr(execution.decode.components, name).mean())
                for name in ("node_serialization_ns", "mesh_service_ns")
            }
        )
        summaries.append(metrics)
    return tuple(summaries)


def measure_frozen_deployments(deployments, inputs, output):
    executions = evaluate_deployments(
        tuple(deployments.values()),
        ExecutionWorkload(
            inputs.test_routes, inputs.prefill_test_routes, fixed_prefill_windows(8)
        ),
    )
    metrics, samples = {}, {}
    for name, execution in zip(deployments, executions, strict=True):
        samples[f"{name}_decode_ns"] = execution.decode.latency_ns
        values = deployment_metrics(execution)
        for count, times in prefill_makespans(execution).items():
            samples[f"{name}_prefill_{count}_ns"] = times
            values["prefill"][count]["window_ns"] = times.tolist()
        metrics[name] = values
    np.savez_compressed(output / "test-samples.npz", **samples)
    return metrics


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
