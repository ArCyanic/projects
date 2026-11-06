"""Measure Decode and Prefill sensitivity to Mesh link bandwidth."""

import json
from pathlib import Path

from experiments.inputs import load_preprocessed_inputs
from profiler import profile
from simulation.workload import PREFILL_TOKEN_COUNTS, evaluation_workload

BANDWIDTHS_GBPS = (0.25, 0.5, 0.75, 1.0, 2.0)


def run_communication_sensitivity(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    deployment_artifact: Path,
) -> int:
    trials = []
    for bandwidth in BANDWIDTHS_GBPS:
        inputs = load_preprocessed_inputs(input_dir, hardware_profile, bandwidth)
        workload = evaluation_workload(
            inputs.test_routes, inputs.prefill_test_routes, PREFILL_TOKEN_COUNTS
        )
        deployment = inputs.model.load_deployment(deployment_artifact)
        trials.append(
            {
                "bandwidth_GBps": bandwidth,
                "profile": profile(
                    deployment,
                    workload,
                    "bottleneck",
                ).to_payload(),
            }
        )

    payload = {
        "schema": "communication-sensitivity-v7",
        "input_dir": str(input_dir),
        "hardware_profile": hardware_profile,
        "deployment_artifact": str(deployment_artifact),
        "deployment": "stage1-optimized",
        "route_slice": inputs.route_splits["test"],
        "bandwidths_GBps": BANDWIDTHS_GBPS,
        "baseline_bandwidth_GBps": 1.0,
        "prefill_token_counts": PREFILL_TOKEN_COUNTS,
        "trials": trials,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0
