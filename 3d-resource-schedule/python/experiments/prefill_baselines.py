"""Compare simple replica dispatch policies on frozen seed0 deployments."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from experiments.configuration import MODELS
from experiments.inputs import load_preprocessed_inputs
from simulation.prefill.evaluation import execute_windows
from simulation.prefill.execution import (
    compile_prefill_executor,
)

POLICIES = ("round-robin", "cumulative-work")
POLICY_DEFINITIONS = {
    "round-robin": "Cycle each expert's copies; start at expert slot modulo copy count.",
    "cumulative-work": "Minimize cumulative assigned node work plus expert service; arrival breaks ties.",
}


def run_group(batch_root, model, profile, bandwidth, windows, token_counts, budget):
    directory = batch_root / model / profile
    envelope = json.loads((directory / "envelope.json").read_text())
    point = envelope["bandwidths"][str(float(bandwidth))]["curve"][budget]
    config = json.loads((directory / "configuration.json").read_text())
    inputs = load_preprocessed_inputs(Path(config["input_dir"]), profile, bandwidth)
    deployment = inputs.model.load_deployment(Path(point["deployment_artifact"]))
    cases = tuple(compile_prefill_executor(deployment, policy) for policy in POLICIES)
    window_specs = tuple(
        (window * 512, count) for count in token_counts for window in range(windows)
    )
    started = perf_counter()
    executions = execute_windows(
        cases, inputs.prefill_test_routes, window_specs, "bottleneck"
    )
    samples = []
    for policy, rows in zip(POLICIES, executions, strict=True):
        for (start, count), execution in zip(window_specs, rows, strict=True):
            work = execution.resources.compute_busy_ns
            links = execution.resources.link_busy_ns
            samples.append(
                {
                    "policy": policy,
                    "tokens": count,
                    "window": start // 512,
                    "makespan_ns": execution.makespan_ns,
                    "token_p95_ns": float(
                        np.percentile(execution.token_latency_ns, 95)
                    ),
                    "mean_compute_ns": float(work.mean()),
                    "peak_compute_ns": int(work.max()),
                    "peak_link_ns": int(links.max()),
                    "compute_utilization": float(
                        work.sum() / (len(work) * execution.makespan_ns)
                    ),
                }
            )
    samples.sort(key=lambda x: (POLICIES.index(x["policy"]), x["tokens"], x["window"]))
    summary = {}
    for policy in POLICIES:
        summary[policy] = {}
        for tokens in token_counts:
            rows = [
                x for x in samples if x["policy"] == policy and x["tokens"] == tokens
            ]
            summary[policy][str(tokens)] = {
                "mean_ns": float(np.mean([x["makespan_ns"] for x in rows])),
                "p95_ns": float(np.percentile([x["makespan_ns"] for x in rows], 95)),
                "compute_utilization": float(
                    np.mean([x["compute_utilization"] for x in rows])
                ),
                "mean_compute_ns": float(np.mean([x["mean_compute_ns"] for x in rows])),
                "peak_compute_ns": float(np.mean([x["peak_compute_ns"] for x in rows])),
                "peak_link_ns": float(np.mean([x["peak_link_ns"] for x in rows])),
            }
    return {
        "hardware_profile": profile,
        "link_bandwidth_GBps": bandwidth,
        "deployment_artifact": point["deployment_artifact"],
        "anchor": point["anchor"],
        "capacity_budget_percent": point["capacity_budget_percent"],
        "host_seconds": perf_counter() - started,
        "summary": summary,
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-root", type=Path, default=Path("build/dac-paper-full-workload")
    )
    parser.add_argument(
        "--model",
        choices=tuple(MODELS),
        default="deepseek-v3",
    )
    parser.add_argument(
        "--profiles",
        nargs="+",
        choices=("planar", "vertical"),
        default=["planar", "vertical"],
    )
    parser.add_argument("--bandwidths", nargs="+", type=float, default=[0.5, 2, 8])
    parser.add_argument("--tokens", nargs="+", type=int, default=[32, 128, 512])
    parser.add_argument("--windows", type=int, default=8)
    parser.add_argument("--budget", type=int, default=20)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "build/dac-paper-full-workload/prefill-baselines/baseline-mainline.json"
        ),
    )
    args = parser.parse_args()
    payload = {
        "model": args.model,
        "seed": 0,
        "test_route_split": [8192, 12288],
        "window_count": args.windows,
        "nominal_extra_replica_percent": args.budget,
        "tokens": args.tokens,
        "policy_definitions": POLICY_DEFINITIONS,
        "trees": "canonical shortest-path",
        "root": "minimum-edge minimum-depth geometry",
        "compute_order": "token-first, phase, ready-time, task-id",
        "groups": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for profile in args.profiles:
        for bandwidth in args.bandwidths:
            group = run_group(
                args.batch_root,
                args.model,
                profile,
                bandwidth,
                args.windows,
                args.tokens,
                args.budget,
            )
            payload["groups"].append(group)
            args.output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
            )
            print(
                profile,
                bandwidth,
                "completed",
                round(group["host_seconds"], 2),
                "s",
                flush=True,
            )
            for policy, metrics in group["summary"].items():
                print(
                    policy,
                    {t: round(m["mean_ns"] / 1e6, 4) for t, m in metrics.items()},
                    flush=True,
                )


if __name__ == "__main__":
    main()
