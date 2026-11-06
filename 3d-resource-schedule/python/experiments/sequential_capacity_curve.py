"""Grow and refine one cumulative replica-capacity path."""

import json
import subprocess
from pathlib import Path
from time import perf_counter

from deployment.capacity import load_replica_space_artifact
from deployment.residency import moe_nodes_from_residency
from experiments.evaluation import measure_capacity_deployments
from experiments.inputs import load_preprocessed_inputs
from mapping.decode_baseline import build_full_workload_baseline
from mapping.prefill_replication import augment_prefill_replicas
from mapping.refinement import refine_deployment
from mapping.workload import compile_mapping_problem
from simulation.prefill.execution import PREFILL_SCHEDULER
from simulation.workload import PREFILL_TOKEN_COUNTS


def run_sequential_capacity_curve(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    link_bandwidth_gbps: float,
    replica_space_artifact: Path,
    anchor_deployment_artifact: Path,
    validation_window_count: int,
    maximum_prefill_regret: float,
    maximum_capacity_budget_percent: int,
    resume_report: Path | None,
) -> int:
    """Write one add-refine path whose selected point seeds the next budget."""
    started = perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    inputs = load_preprocessed_inputs(
        input_dir,
        hardware_profile,
        link_bandwidth_gbps,
    )
    space = load_replica_space_artifact(replica_space_artifact, inputs.model)
    problem = compile_mapping_problem(
        inputs.model, space, inputs.train_routes, inputs.prefill_train_routes
    )
    if resume_report is None:
        baseline_residency = build_full_workload_baseline(
            inputs.model.block_table,
            space.dense_residency,
            problem.workload,
            space.moe_resident_capacity,
        )
        baseline = inputs.model.deploy(baseline_residency)
        current = inputs.model.load_deployment(anchor_deployment_artifact)
        zero_artifact = output.with_name(f"{output.stem}.budget-00.npz")
        current.save(zero_artifact)
        baseline_metrics, zero_metrics = measure_capacity_deployments(
            (baseline, current),
            inputs.validation_routes,
            inputs.prefill_validation_routes,
            validation_window_count,
        )
        payload = {
            "schema": "sequential-capacity-curve-v1",
            "recipe": "sequential-capacity-curve",
            "git_commit": subprocess.check_output(
                ("git", "rev-parse", "HEAD"), text=True
            ).strip(),
            "hardware_profile": hardware_profile,
            "link_bandwidth_GBps": link_bandwidth_gbps,
            "validation_window_count": validation_window_count,
            "replica_space_artifact": str(replica_space_artifact),
            "anchor_deployment_artifact": str(anchor_deployment_artifact),
            "maximum_prefill_regret": maximum_prefill_regret,
            "prefill_scheduler": PREFILL_SCHEDULER,
            "input_dir": str(input_dir),
            "prefill_token_counts": PREFILL_TOKEN_COUNTS,
            "baseline_metrics": baseline_metrics,
            "points": [
                {
                    "capacity_budget_percent": 0,
                    "requested_replica_count": 0,
                    "added_replica_count": 0,
                    "deployment_artifact": str(zero_artifact),
                    "metrics": zero_metrics,
                    "host_seconds": {"total": 0.0},
                }
            ],
        }
    else:
        payload = json.loads(resume_report.read_text(encoding="utf-8"))
        current = inputs.model.load_deployment(
            Path(payload["points"][-1]["deployment_artifact"])
        )
        payload["git_commit"] = subprocess.check_output(
            ("git", "rev-parse", "HEAD"), text=True
        ).strip()
    first_new_percent = len(payload["points"])
    requested_budget_percents = tuple(
        range(first_new_percent, maximum_capacity_budget_percent + 1)
    )
    capped_budgets = tuple(
        space.model_relative_replica_budget(percent / 100)
        for percent in requested_budget_percents
    )
    budgets = tuple(dict.fromkeys(capped_budgets))
    new_budget_percents = tuple(
        100 * budget / space.required_moe_resident_count for budget in budgets
    )
    payload["capacity_budget_percents"] = [
        point["capacity_budget_percent"] for point in payload["points"]
    ] + list(new_budget_percents)
    initial_budget = payload["points"][-1]["requested_replica_count"]
    for point_index, (percent, previous_budget, budget) in enumerate(
        zip(
            new_budget_percents,
            (initial_budget, *budgets)[:-1],
            budgets,
            strict=True,
        ),
        start=first_new_percent,
    ):
        point_started = perf_counter()
        added_budget = budget - previous_budget
        current_nodes = moe_nodes_from_residency(
            current.residency,
            inputs.model.block_table,
            inputs.model.hardware_profile.mesh_node_count,
        )
        capacity_residency = augment_prefill_replicas(
            current.residency,
            inputs.model.block_table,
            problem.workload,
            space.moe_resident_capacity - current_nodes.sum(axis=(0, 1)),
            added_budget,
        )
        capacity_deployment = inputs.model.deploy(capacity_residency)
        refinement = refine_deployment(
            problem, capacity_residency, maximum_prefill_regret=maximum_prefill_regret
        )
        current = refinement.deployment
        capacity_artifact = output.with_name(
            f"{output.stem}.budget-{point_index:02d}.capacity.npz"
        )
        artifact = output.with_name(f"{output.stem}.budget-{point_index:02d}.npz")
        capacity_deployment.save(capacity_artifact)
        current.save(artifact)
        capacity_metrics, selected_metrics = measure_capacity_deployments(
            (capacity_deployment, current),
            inputs.validation_routes,
            inputs.prefill_validation_routes,
            validation_window_count,
        )
        payload["points"].append(
            {
                "capacity_budget_percent": percent,
                "requested_replica_count": budget,
                "added_replica_count": added_budget,
                "capacity_deployment_artifact": str(capacity_artifact),
                "deployment_artifact": str(artifact),
                "refinement": refinement.to_payload(),
                "capacity_metrics": capacity_metrics,
                "metrics": selected_metrics,
                "host_seconds": {
                    "refinement": refinement.host_seconds,
                    "total": perf_counter() - point_started,
                },
            }
        )
        payload["host_seconds"] = perf_counter() - started
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"sequential-capacity profile={hardware_profile} "
            f"budget={percent:.3f}% refinement={refinement.host_seconds:.3f}s",
            flush=True,
        )
    return 0
