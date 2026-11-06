"""Optimize one-copy Decode Mapping with the additive route hypergraph."""

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np
from deployment.capacity import compile_replica_space
from deployment.residency import replace_moe_residents
from experiments.inputs import load_preprocessed_inputs
from mapping.decode_hypergraph import (
    compile_decode_hypergraph,
    optimize_decode_hypergraph,
)
from simulation.decode import compile_decode_executor, measure_decode_routes
from simulation.statistics import latency_summary


def run_decode_hypergraph_mapping(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    link_bandwidth_GBps: float | None,
    baseline_deployment_artifact: Path,
    train_route_count: int,
) -> int:
    """Write the layer-FM optimum and Train/Validation evaluation."""
    inputs = load_preprocessed_inputs(
        input_dir,
        hardware_profile,
        link_bandwidth_GBps,
    )
    baseline = inputs.model.load_deployment(baseline_deployment_artifact)
    train_routes = np.asarray(inputs.train_routes[:train_route_count])
    executor = compile_decode_executor(baseline)
    hypergraph, resident_node = compile_decode_hypergraph(
        executor,
        train_routes,
    )
    node_capacity = compile_replica_space(inputs.model).moe_resident_capacity

    started = perf_counter()
    solution = optimize_decode_hypergraph(
        hypergraph,
        resident_node,
        node_capacity,
    )
    host_seconds = perf_counter() - started
    resident = np.zeros(
        (*solution.resident_node.shape, len(node_capacity)),
        dtype=np.bool_,
    )
    np.put_along_axis(
        resident,
        solution.resident_node[:, :, None],
        True,
        axis=2,
    )
    deployment = inputs.model.deploy(
        replace_moe_residents(
            baseline.residency,
            inputs.model.block_table,
            resident,
        )
    )
    deployment_artifact = output.with_suffix(".deployment.npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    deployment.save(deployment_artifact)

    payload = {
        "schema": "decode-hypergraph-mapping-v5",
        "recipe": "decode-hypergraph-mapping",
        "hardware_profile": hardware_profile,
        "link_bandwidth_GBps": inputs.model.hardware_profile.link_bandwidth_GBps,
        "baseline": "full-workload-balanced-single-copy",
        "baseline_deployment_artifact": str(baseline_deployment_artifact),
        "deployment_artifact": str(deployment_artifact),
        "train_route_count": len(train_routes),
        "train_route_split": [0, len(train_routes)],
        "validation_route_split": inputs.route_splits["validation"],
        "node_capacity": node_capacity.tolist(),
        "baseline_node_occupancy": np.bincount(
            resident_node.ravel(),
            minlength=len(node_capacity),
        ).tolist(),
        "final_node_occupancy": np.bincount(
            solution.resident_node.ravel(),
            minlength=len(node_capacity),
        ).tolist(),
        "baseline_train": _decode_metrics(baseline, train_routes),
        "selected_train": _decode_metrics(deployment, train_routes),
        "baseline_validation": _decode_metrics(baseline, inputs.validation_routes),
        "selected_validation": _decode_metrics(deployment, inputs.validation_routes),
        "hypergraph": {
            "initial_objective_ns": solution.initial_objective_ns,
            "final_objective_ns": solution.final_objective_ns,
            "improvement_percent": 100
            * (1 - solution.final_objective_ns / solution.initial_objective_ns),
            "accepted_move_count": len(solution.moves),
            "sweep_count": solution.sweep_count,
            "final_sweep_improvement_ns": solution.final_sweep_improvement_ns,
            "final_sweep_improvement_percent": 100
            * solution.final_sweep_improvement_ns
            / solution.final_objective_ns,
            "moves": [asdict(move) for move in solution.moves],
            "host_seconds": host_seconds,
        },
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"decode-hypergraph-mapping profile={hardware_profile} "
        f"moves={len(solution.moves)} "
        f"train-improvement={payload['hypergraph']['improvement_percent']:.3f}% "
        f"host-seconds={host_seconds:.3f} out={output}"
    )
    return 0


def _decode_metrics(deployment, routes) -> dict[str, float]:
    result = measure_decode_routes(compile_decode_executor(deployment), routes)
    components = result.components
    route_count = len(routes)
    moe = slice(deployment.model.block_table.dense_layers, None)
    return {
        **latency_summary(result.latency_ns),
        "node_serialization_ns": float(
            components.node_serialization_ns.sum() / route_count
        ),
        "mesh_service_ns": float(components.mesh_service_ns.sum() / route_count),
        "collective_contention_ns": float(
            components.collective_contention_ns.sum() / route_count
        ),
        "critical_hops_per_route": float(
            result.trace.critical_hops_by_route_layer[:, moe].sum() / route_count
        ),
        "critical_serialization_ns_per_route": float(
            result.trace.components_by_layer.node_serialization_ns[:, moe].sum()
            / route_count
        ),
    }
