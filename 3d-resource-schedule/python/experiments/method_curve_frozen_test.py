"""Evaluate one frozen low-copy Deployment on the Test split."""

import json
from pathlib import Path
from time import perf_counter

from experiments.evaluation import deployment_metrics
from experiments.inputs import load_preprocessed_inputs
from simulation import ExecutionWorkload, evaluate_deployments
from simulation.prefill.execution import PREFILL_SCHEDULER
from simulation.workload import PREFILL_TOKEN_COUNTS, fixed_prefill_windows


def run_method_curve_frozen_test(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    link_bandwidth_GBps: float,
    method_curve_report: Path,
    point: str,
    test_window_count: int,
) -> int:
    """Write frozen Decode and Prefill Test metrics without selecting candidates."""
    inputs = load_preprocessed_inputs(
        input_dir,
        hardware_profile,
        link_bandwidth_GBps,
    )
    if not 1 <= test_window_count <= len(inputs.prefill_test_routes) // 512:
        raise ValueError("test-window-count exceeds the Test split")
    with method_curve_report.open(encoding="utf-8") as handle:
        curve_report = json.load(handle)
    curve = curve_report["bandwidths"][str(link_bandwidth_GBps)]["curve"]
    selected = next(item for item in curve if item["point"] == point)
    deployment_artifact = Path(selected["deployment_artifact"])
    deployment = inputs.model.load_deployment(deployment_artifact)
    started = perf_counter()
    (evaluation,) = evaluate_deployments(
        (deployment,),
        ExecutionWorkload(
            inputs.test_routes,
            inputs.prefill_test_routes,
            fixed_prefill_windows(test_window_count),
        ),
    )
    payload = {
        "schema": "method-curve-frozen-test-v1",
        "recipe": "method-curve-frozen-test",
        "hardware_profile": hardware_profile,
        "link_bandwidth_GBps": link_bandwidth_GBps,
        "method_curve_report": str(method_curve_report),
        "point": point,
        "deployment_artifact": str(deployment_artifact),
        "test_route_split": inputs.route_splits["test"],
        "test_window_count": test_window_count,
        "prefill_token_counts": PREFILL_TOKEN_COUNTS,
        "prefill_scheduler": PREFILL_SCHEDULER,
        "input_dir": str(input_dir),
        **deployment_metrics(evaluation),
        "host_seconds": perf_counter() - started,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"method-curve-frozen-test profile={hardware_profile} "
        f"bandwidth={link_bandwidth_GBps:g} out={output}"
    )
    return 0
