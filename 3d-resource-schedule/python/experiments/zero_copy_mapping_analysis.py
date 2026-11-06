"""Evaluate zero-copy Mapping methods and the Hypergraph capacity mechanism."""

import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np
from deployment.capacity import load_replica_space_artifact
from deployment.residency import moe_nodes_from_residency, replace_moe_residents
from experiments.inputs import load_preprocessed_inputs
from mapping.decode_hypergraph import (
    compile_decode_hypergraph,
    optimize_decode_hypergraph,
)
from mapping.workload import compile_mapping_problem
from profiler.metrics.decode_structure import measure_decode_structural_comparison
from simulation.collective import compile_collective_topology
from simulation.decode import (
    DecodeExecutor,
    compile_decode_executor,
    measure_decode_routes,
)
from simulation.decode.model import compile_decode_resident_table
from simulation.prefill.evaluation import execute_windows
from simulation.prefill.execution import compile_prefill_executor


def run_zero_copy_mapping_analysis(
    output: Path,
    input_dir: Path,
    hardware_profile: str,
    replica_space_artifact: Path,
    round_robin_artifact: Path,
    balanced_artifact: Path,
    hypergraph_artifacts: tuple[Path, ...],
) -> int:
    """Write the zero-copy comparison and three-bandwidth capacity analysis."""
    started = perf_counter()
    bandwidths = (0.5, 2.0, 8.0)
    output.parent.mkdir(parents=True, exist_ok=True)

    by_bandwidth = {}
    for bandwidth, hypergraph_artifact in zip(
        bandwidths,
        hypergraph_artifacts,
        strict=True,
    ):
        inputs = load_preprocessed_inputs(input_dir, hardware_profile, bandwidth)
        space = load_replica_space_artifact(replica_space_artifact, inputs.model)
        problem = compile_mapping_problem(
            inputs.model, space, inputs.train_routes, inputs.prefill_train_routes
        )
        deployments = {
            "round-robin": inputs.model.load_deployment(round_robin_artifact),
            "compute-balanced": inputs.model.load_deployment(balanced_artifact),
            "capacity-constrained-hypergraph": inputs.model.load_deployment(
                hypergraph_artifact
            ),
        }
        by_bandwidth[str(bandwidth)] = _evaluate_methods(
            deployments,
            problem,
            inputs,
        )
        unconstrained = _unconstrained_hypergraph(
            deployments["compute-balanced"], inputs.train_routes[:1024]
        )
        by_bandwidth[str(bandwidth)]["capacity-relaxed-hypergraph"] = _evaluate_relaxed(
            unconstrained, problem, inputs
        )

    payload = {
        "schema": "zero-copy-mapping-analysis-v2",
        "hardware_profile": hardware_profile,
        "bandwidths_GBps": bandwidths,
        "capacity_ablation_bandwidth_GBps": bandwidths[0],
        "bandwidths": by_bandwidth,
        "host_seconds": perf_counter() - started,
    }
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"zero-copy-mapping-analysis out={output}")
    return 0


def _unconstrained_hypergraph(deployment, routes):
    executor = compile_decode_executor(deployment)
    hypergraph, resident_node = compile_decode_hypergraph(executor, routes)
    relaxed_capacity = np.full(
        executor.node_count,
        resident_node.size,
        dtype=np.int32,
    )
    solution = optimize_decode_hypergraph(
        hypergraph,
        resident_node,
        relaxed_capacity,
    )
    resident = np.zeros(
        (*solution.resident_node.shape, executor.node_count),
        dtype=np.bool_,
    )
    np.put_along_axis(
        resident,
        solution.resident_node[:, :, None],
        True,
        axis=2,
    )
    return replace_moe_residents(
        deployment.residency,
        deployment.model.block_table,
        resident,
    )


def _evaluate_methods(deployments, problem, inputs):
    names = tuple(deployments)
    prefill = execute_windows(
        tuple(compile_prefill_executor(deployments[name]) for name in names),
        inputs.prefill_validation_routes,
        ((0, 512),),
        "objective",
    )
    reports = {}
    for name, executions in zip(names, prefill, strict=True):
        deployment = deployments[name]
        executor = compile_decode_executor(deployment)
        decode = measure_decode_routes(executor, inputs.validation_routes)
        structure = measure_decode_structural_comparison(
            executor,
            inputs.validation_routes,
            decode,
        )
        node_mask = moe_nodes_from_residency(
            deployment.residency,
            inputs.model.block_table,
            inputs.model.hardware_profile.mesh_node_count,
        )
        reports[name] = {
            "decode_mean_ns": float(decode.latency_ns.mean()),
            "decode_p95_ns": float(np.percentile(decode.latency_ns, 95)),
            "prefill_T512_ns": executions[0].makespan_ns,
            "structure": asdict(structure),
            "node_occupancy": node_mask.sum(axis=(0, 1)).tolist(),
            "node_compute_work_ns": _node_compute_work(
                node_mask,
                problem.workload,
            ).tolist(),
        }
    return reports


def _evaluate_relaxed(residency, problem, inputs):
    executor = DecodeExecutor(
        compile_decode_resident_table(inputs.model, residency),
        compile_collective_topology(inputs.model.hardware_profile.grid),
    )
    decode = measure_decode_routes(executor, inputs.validation_routes)
    structure = measure_decode_structural_comparison(
        executor,
        inputs.validation_routes,
        decode,
    )
    node_mask = moe_nodes_from_residency(
        residency,
        inputs.model.block_table,
        inputs.model.hardware_profile.mesh_node_count,
    )
    return {
        "decode_mean_ns": float(decode.latency_ns.mean()),
        "decode_p95_ns": float(np.percentile(decode.latency_ns, 95)),
        "prefill_T512_ns": None,
        "structure": asdict(structure),
        "node_occupancy": node_mask.sum(axis=(0, 1)).tolist(),
        "node_compute_work_ns": _node_compute_work(
            node_mask,
            problem.workload,
        ).tolist(),
    }


def _node_compute_work(node_mask, workload):
    demand = workload.demand.sum(axis=0).astype(np.float64)
    service = workload.expert_service_ns.astype(np.float64)
    work = np.zeros(node_mask.shape[2], dtype=np.float64)
    for layer in range(node_mask.shape[0]):
        for expert in range(node_mask.shape[1]):
            nodes = np.flatnonzero(node_mask[layer, expert])
            work[nodes] += demand[layer, expert] * service[layer, expert] / len(nodes)
    return work
