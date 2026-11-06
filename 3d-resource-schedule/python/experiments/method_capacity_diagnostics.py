"""Project the method-capacity curve through the canonical Profiler metrics."""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from experiments.inputs import load_preprocessed_inputs
from profiler.metrics.prefill import (
    compute_utilization_timeline,
    profile_prefill_execution,
)
from simulation import ExecutionWorkload, evaluate_deployments
from simulation.prefill.execution import (
    PREFILL_SCHEDULER,
    compile_prefill_executor,
    execute_prefill,
)
from simulation.workload import PREFILL_TOKEN_COUNTS, fixed_prefill_windows

TIMELINE_PROFILE = "planar"
TIMELINE_BANDWIDTH_GBPS = 2.0
TIMELINE_BIN_COUNT = 160


def run_method_capacity_diagnostics(
    output: Path,
    curve_paths: tuple[Path, ...],
    input_dir: Path,
) -> int:
    """Write aligned Decode decomposition, Prefill metrics, and load timelines."""
    curve_reports = tuple(
        json.loads(path.read_text(encoding="utf-8")) for path in curve_paths
    )
    profiles = {
        report["hardware_profile"]: _profile_curve(report, input_dir)
        for report in curve_reports
    }
    timeline_report = next(
        report
        for report in curve_reports
        if report["hardware_profile"] == TIMELINE_PROFILE
    )
    timeline = _prefill_load_timeline(timeline_report, input_dir)
    payload = {
        "schema": "method-capacity-diagnostics-v1",
        "prefill_scheduler": PREFILL_SCHEDULER,
        "curve_inputs": [str(path) for path in curve_paths],
        "prefill_token_counts": PREFILL_TOKEN_COUNTS,
        "profiles": profiles,
        "timeline": timeline,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"method-capacity-diagnostics out={output}")
    return 0


def _profile_curve(report, input_dir):
    return {
        bandwidth: _profile_bandwidth(report, bandwidth, input_dir)
        for bandwidth in report["bandwidths"]
    }


def _profile_bandwidth(report, bandwidth, input_dir):
    entry = report["bandwidths"][bandwidth]
    inputs = load_preprocessed_inputs(
        input_dir,
        report["hardware_profile"],
        float(bandwidth),
    )
    deployments = tuple(
        inputs.model.load_deployment(Path(point["deployment_artifact"]))
        for point in entry["curve"]
    )
    executions = evaluate_deployments(
        deployments,
        ExecutionWorkload(
            inputs.validation_routes,
            inputs.prefill_validation_routes,
            fixed_prefill_windows(1),
        ),
        "bottleneck",
    )
    return [
        {
            "point": point["point"],
            "role": point["role"],
            "capacity_budget_percent": point["capacity_budget_percent"],
            "decode_components_ns": _decode_components(execution.decode),
            "prefill": {
                str(token_count): _prefill_metrics(
                    row,
                    inputs.model.program.dependency_bound_ns,
                )
                for token_count, row in zip(
                    PREFILL_TOKEN_COUNTS,
                    execution.prefill,
                    strict=True,
                )
            },
        }
        for point, execution in zip(entry["curve"], executions, strict=True)
    ]


def _decode_components(measurement):
    components = measurement.components
    node = float(components.node_serialization_ns.mean())
    mesh = float(components.mesh_service_ns.mean())
    contention = float(components.collective_contention_ns.mean())
    return {
        "expert_compute_ns": float(measurement.latency_ns.mean())
        - node
        - mesh
        - contention,
        "node_serialization_ns": node,
        "mesh_service_ns": mesh,
        "collective_contention_ns": contention,
    }


def _prefill_metrics(execution, dependency_bound_ns):
    profile = profile_prefill_execution(
        execution,
        dependency_bound_ns,
        "bottleneck",
    )
    return {
        "makespan_ns": profile.objectives.makespan_mean_ns,
        "bottleneck": asdict(profile.bottleneck),
        "optimization_space": asdict(profile.optimization_space),
    }


def _prefill_load_timeline(report, input_dir):
    bandwidth = str(TIMELINE_BANDWIDTH_GBPS)
    inputs = load_preprocessed_inputs(
        input_dir,
        TIMELINE_PROFILE,
        TIMELINE_BANDWIDTH_GBPS,
    )
    point = report["bandwidths"][bandwidth]["curve"][-1]
    deployment = inputs.model.load_deployment(Path(point["deployment_artifact"]))
    executor = compile_prefill_executor(deployment)
    batches = {
        str(token_count): _timeline_batch(
            execute_prefill(
                executor,
                inputs.prefill_validation_routes[:token_count],
                "trace",
            ),
        )
        for token_count in PREFILL_TOKEN_COUNTS
    }
    return {
        "hardware_profile": TIMELINE_PROFILE,
        "link_bandwidth_GBps": TIMELINE_BANDWIDTH_GBPS,
        "point": point["point"],
        "route_split": "validation[0:B]",
        "bin_count": TIMELINE_BIN_COUNT,
        "batches": batches,
    }


def _timeline_batch(execution):
    makespan = execution.makespan_ns
    edges = np.linspace(0, makespan, TIMELINE_BIN_COUNT + 1)
    utilization = compute_utilization_timeline(execution, edges)
    aggregate = utilization.mean(axis=0)
    compute_service_exposure = float(
        execution.resources.compute_busy_ns.mean() / makespan
    )
    return {
        "makespan_ns": makespan,
        "time_fraction": ((edges[:-1] + edges[1:]) / (2 * makespan)).tolist(),
        "node_utilization": utilization.tolist(),
        "aggregate_utilization": aggregate.tolist(),
        "compute_service_exposure": compute_service_exposure,
        "idle_area": 1 - compute_service_exposure,
    }
