"""Evaluate the linear scheduling axes on one frozen deployment."""

import json
from pathlib import Path
from time import perf_counter

import numpy as np
from experiments.inputs import load_preprocessed_inputs
from simulation.statistics import latency_summary
from simulation.decode import compile_decode_executor, measure_decode_routes
from simulation.decode.comparison import measure_nearest_decode_routes
from simulation.prefill.evaluation import execute_windows
from simulation.prefill.execution import (
    PREFILL_SCHEDULER,
    compile_prefill_executor,
)
from simulation.workload import PREFILL_TOKEN_COUNTS, fixed_prefill_windows


def run_dataflow_linear_ablation(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    link_bandwidth_GBps: float,
    deployment_artifact: Path,
    test_window_count: int,
) -> int:
    """Write Decode and Prefill linear-axis results for one frozen deployment."""
    inputs = load_preprocessed_inputs(
        input_dir,
        hardware_profile,
        link_bandwidth_GBps,
    )
    deployment = inputs.model.load_deployment(deployment_artifact)
    started = perf_counter()
    decode = _decode_linear_stages(
        compile_decode_executor(deployment),
        inputs.test_routes,
    )
    prefill = _prefill_linear_stages(
        compile_prefill_executor(deployment),
        inputs.prefill_test_routes,
        test_window_count,
    )
    payload = {
        "schema": "dataflow-linear-ablation-v6",
        "prefill_scheduler": PREFILL_SCHEDULER,
        "input_dir": str(input_dir),
        "hardware_profile": hardware_profile,
        "link_bandwidth_GBps": link_bandwidth_GBps,
        "deployment_artifact": str(deployment_artifact),
        "test_route_split": inputs.route_splits["test"],
        "test_window_count": test_window_count,
        "decode": decode,
        "prefill": prefill,
        "host_seconds": perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"dataflow-linear-ablation profile={hardware_profile} "
        f"bandwidth={link_bandwidth_GBps:g} out={output}"
    )
    return 0


def _decode_linear_stages(executor, routes):
    production = measure_decode_routes(executor, routes)
    source_root = measure_nearest_decode_routes(executor, routes, production, False)
    dynamic_root = measure_nearest_decode_routes(executor, routes, production, True)
    return {
        "stages": (
            _latency_report("nearest-source-root", source_root),
            _latency_report("nearest-dynamic-root", dynamic_root),
            _latency_report("joint-replica-root", production),
        )
    }


def _prefill_linear_stages(executor, routes, window_count):
    if not 1 <= window_count <= len(routes) // 512:
        raise ValueError("test-window-count exceeds the Test split")
    windows = fixed_prefill_windows(window_count)
    stage_policies = (
        ("round-robin-canonical-tree", "round-robin"),
        ("minimum-cumulative-load-canonical-tree", "cumulative-work"),
    )
    cases = tuple(
        compile_prefill_executor(executor.deployment, policy)
        for _, policy in stage_policies
    )
    executions = execute_windows(cases, routes, windows, "objective")
    makespans = np.asarray([[row.makespan_ns for row in rows] for rows in executions])
    makespans = makespans.reshape(
        len(stage_policies), len(PREFILL_TOKEN_COUNTS), window_count
    )
    reports = []
    for stage_index, (name, _) in enumerate(stage_policies):
        by_token_count = {}
        for token_index, token_count in enumerate(PREFILL_TOKEN_COUNTS):
            makespan = makespans[stage_index, token_index]
            by_token_count[str(token_count)] = {
                **latency_summary(makespan),
            }
        reports.append({"stage": name, "metrics": by_token_count})
    return {"stages": tuple(reports)}


def _latency_report(stage, measurement):
    return {
        "stage": stage,
        **latency_summary(measurement.latency_ns),
        "components_ns": {
            name: float(getattr(measurement.components, name).mean())
            for name in (
                "expert_compute_ns",
                "node_serialization_ns",
                "mesh_service_ns",
                "collective_contention_ns",
            )
        },
    }
