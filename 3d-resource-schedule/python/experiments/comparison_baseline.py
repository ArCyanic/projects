"""Evaluate the full-workload single-copy baseline shared with search."""

import argparse
import json
from pathlib import Path

import numpy as np
from deployment.capacity import compile_replica_space
from experiments.configuration import MODELS, bandwidths, inputs_path
from experiments.inputs import load_preprocessed_inputs
from mapping.decode_baseline import build_full_workload_baseline
from mapping.workload import compile_replica_workload
from simulation import ExecutionWorkload, evaluate_deployments
from simulation.statistics import latency_summary
from simulation.prefill.execution import (
    PREFILL_SCHEDULER,
)
from simulation.workload import PREFILL_TOKEN_COUNTS, fixed_prefill_windows


def evaluate_reference(output_dir, model, profile, input_dir):
    directory = output_dir / model / profile
    directory.mkdir(parents=True, exist_ok=True)
    inputs = load_preprocessed_inputs(input_dir, profile)
    space = compile_replica_space(inputs.model)
    workload = compile_replica_workload(
        inputs.model, space.dense_residency, inputs.prefill_train_routes
    )
    residency = build_full_workload_baseline(
        inputs.model.block_table,
        space.dense_residency,
        workload,
        space.moe_resident_capacity,
    )
    deployment = inputs.model.deploy(residency)
    artifact = directory / "deployment.npz"
    deployment.save(artifact)
    for bandwidth in bandwidths(model):
        inputs = load_preprocessed_inputs(input_dir, profile, bandwidth)
        deployment = inputs.model.load_deployment(artifact)
        splits = {}
        for split, routes, prefill_routes, count in (
            (
                "validation",
                inputs.validation_routes,
                inputs.prefill_validation_routes,
                1,
            ),
            ("test", inputs.test_routes, inputs.prefill_test_routes, 8),
        ):
            (execution,) = evaluate_deployments(
                (deployment,),
                ExecutionWorkload(routes, prefill_routes, fixed_prefill_windows(count)),
                "bottleneck",
            )
            decode = execution.decode
            executions = execution.prefill
            prefill = {}
            for i, tokens in enumerate(PREFILL_TOKEN_COUNTS):
                rows = executions[i * count : (i + 1) * count]
                times = np.asarray([row.makespan_ns for row in rows])
                prefill[str(tokens)] = {
                    **latency_summary(times),
                    "mean_compute_ns": float(
                        np.mean([row.resources.compute_busy_ns.mean() for row in rows])
                    ),
                    "peak_compute_ns": float(
                        np.mean([row.resources.compute_busy_ns.max() for row in rows])
                    ),
                    "peak_link_ns": float(
                        np.mean([row.resources.link_busy_ns.max() for row in rows])
                    ),
                    "compute_utilization": float(
                        np.mean(
                            [
                                row.resources.compute_busy_ns.mean() / row.makespan_ns
                                for row in rows
                            ]
                        )
                    ),
                    "window_makespan_ns": times.tolist(),
                }
            splits[split] = {
                "decode": {
                    **latency_summary(decode.latency_ns),
                    **{
                        name: float(getattr(decode.components, name).mean())
                        for name in (
                            "expert_compute_ns",
                            "node_serialization_ns",
                            "mesh_service_ns",
                            "collective_contention_ns",
                        )
                    },
                },
                "prefill": prefill,
            }
        payload = {
            "baseline": "full-workload-balanced-single-copy",
            "input_dir": str(input_dir),
            "hardware_profile": profile,
            "link_bandwidth_GBps": bandwidth,
            "deployment_artifact": str(artifact),
            "route_splits": inputs.route_splits,
            "prefill_scheduler": PREFILL_SCHEDULER,
            "validation_window_count": 1,
            "test_window_count": 8,
            "splits": splits,
        }
        output = directory / f"{bandwidth:g}.json"
        output.write_text(json.dumps(payload, indent=2) + "\n")
        print(
            f"comparison-baseline {model} {profile} {bandwidth:g} GB/s: {output}",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument(
        "--hardware-profile", choices=("planar", "vertical"), required=True
    )
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build/dac-paper-full-workload/comparison-baselines"),
    )
    args = parser.parse_args()
    evaluate_reference(
        args.output_dir,
        args.model,
        args.hardware_profile,
        inputs_path(args.model) if args.input_dir is None else args.input_dir,
    )


if __name__ == "__main__":
    main()
