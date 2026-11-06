"""Replay frozen seed0 deployments for the paper's mapping/scheduling mechanisms."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from experiments.dataflow_linear_ablation import run_dataflow_linear_ablation
from experiments.inputs import load_preprocessed_inputs
from numba import njit
from profiler.metrics.prefill import (
    compute_utilization_timeline,
    profile_prefill_execution,
)
from simulation.collective import compile_tree_parent
from simulation.decode import compile_decode_executor, measure_decode_routes
from simulation.prefill.execution import compile_prefill_executor, execute_prefill
from simulation.statistics import latency_summary

PROFILES = ("planar", "vertical")
BANDWIDTHS = (0.5, 2.0, 8.0)


def _decode_summary(measurement):
    return {
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


def _mapping_replay(batch_root):
    cases, controls, spatial_cases = [], [], []
    for profile in PROFILES:
        directory = batch_root / "deepseek-v3" / profile
        configuration = json.loads((directory / "configuration.json").read_text())
        input_dir = Path(configuration["input_dir"])
        sources = [
            json.loads((directory / f"{bandwidth:g}-hypergraph.json").read_text())
            for bandwidth in BANDWIDTHS
        ]
        assert len({source["baseline_deployment_artifact"] for source in sources}) == 1
        assert all(source["train_route_split"] == [0, 1024] for source in sources)
        assert all(source["node_capacity"] == sources[0]["node_capacity"] for source in sources)
        controls.append(
            {
                "hardware_profile": profile,
                "input_dir": str(input_dir),
                "initialization": sources[0]["baseline_deployment_artifact"],
                "training_route_split": sources[0]["train_route_split"],
                "node_capacity": sources[0]["node_capacity"],
                "source_reports": [str(directory / f"{bandwidth:g}-hypergraph.json") for bandwidth in BANDWIDTHS],
            }
        )
        for bandwidth in BANDWIDTHS:
            inputs = load_preprocessed_inputs(input_dir, profile, bandwidth)
            dense_nodes = None
            for layout_bandwidth in BANDWIDTHS:
                artifact = directory / f"{layout_bandwidth:g}-hypergraph.deployment.npz"
                deployment = inputs.model.load_deployment(artifact)
                residents = deployment.residency
                dense_end = inputs.model.block_table.dense_layers * inputs.model.block_table.expert_columns
                assert np.all(np.diff(residents.resident_ptr)[dense_end:] == 1)
                current_dense = residents.resident_node[: residents.resident_ptr[dense_end]]
                if dense_nodes is None:
                    dense_nodes = current_dense
                else:
                    np.testing.assert_array_equal(current_dense, dense_nodes)
                executor = compile_decode_executor(deployment)
                measurement = measure_decode_routes(executor, inputs.test_routes)
                row = {
                    "hardware_profile": profile,
                    "evaluation_bandwidth_GBps": bandwidth,
                    "layout_bandwidth_GBps": layout_bandwidth,
                    "deployment_artifact": str(artifact),
                    **_decode_summary(measurement),
                }
                cases.append(row)
                if profile == "planar" and bandwidth == 2.0 and layout_bandwidth in (0.5, 8.0):
                    trace = measurement.trace
                    extra, packets = _spatial_facts(
                        trace.selected_resident_by_route_layer_rank,
                        executor.residents.resident_node,
                        trace.input_node_by_route_layer,
                        trace.output_node_by_route_layer,
                        executor.collective,
                        executor.dense_layers,
                    )
                    links = [
                        (source, destination)
                        for source in range(executor.node_count)
                        for destination in range(source + 1, executor.node_count)
                        if executor.collective.hop_distance[source, destination] == 1
                    ]
                    spatial_cases.append(
                        {
                            "layout_bandwidth_GBps": layout_bandwidth,
                            "node_extra_experts_per_layer": extra.tolist(),
                            "tree_packets_per_link_per_layer": [
                                float(packets[source, destination] + packets[destination, source])
                                for source, destination in links
                            ],
                        }
                    )
                print(
                    f"single-copy profile={profile} eval={bandwidth:g} "
                    f"mapping={layout_bandwidth:g} mean-ms={row['mean_ns'] / 1e6:.6f}",
                    flush=True,
                )
    return {
        "copies_per_expert": 1,
        "controls": controls,
        "cases": cases,
        "spatial": {
            "hardware_profile": "planar",
            "evaluation_bandwidth_GBps": 2.0,
            "grid": [4, 4],
            "links": links,
            "cases": spatial_cases,
        },
    }


@njit(cache=True)
def _spatial_facts(selected, resident_nodes, sources, roots, topology, dense):
    extra = np.zeros(topology.node_count)
    packets = np.zeros((topology.node_count, topology.node_count))
    counts = np.zeros(topology.node_count, dtype=np.int64)
    parent = np.empty(topology.node_count, dtype=np.int8)
    for route in range(selected.shape[0]):
        for layer in range(dense, selected.shape[1]):
            counts[:] = 0
            mask = 0
            for rank in range(selected.shape[2]):
                node = resident_nodes[selected[route, layer, rank]]
                counts[node] += 1
                mask |= 1 << node
            for node in range(topology.node_count):
                extra[node] += max(0, counts[node] - 1)
            compile_tree_parent(sources[route, layer], mask, topology, parent)
            for node in range(topology.node_count):
                if parent[node] >= 0:
                    packets[parent[node], node] += 1
            compile_tree_parent(roots[route, layer], mask, topology, parent)
            for node in range(topology.node_count):
                if parent[node] >= 0:
                    packets[node, parent[node]] += 1
    route_layers = selected.shape[0] * (selected.shape[1] - dense)
    return extra / route_layers, packets / route_layers


def _scheduling(batch_root, artifact_dir):
    reports = []
    for profile in PROFILES:
        directory = batch_root / "deepseek-v3" / profile
        configuration = json.loads((directory / "configuration.json").read_text())
        envelope = json.loads((directory / "envelope.json").read_text())
        for bandwidth in BANDWIDTHS:
            point = envelope["bandwidths"][str(bandwidth)]["curve"][20]
            output = artifact_dir / f"{profile}-{bandwidth:g}-dataflow.json"
            run_dataflow_linear_ablation(
                output,
                Path(configuration["input_dir"]),
                profile,
                bandwidth,
                Path(point["deployment_artifact"]),
                8,
            )
            reports.append(json.loads(output.read_text()) | {"source": str(output)})
    return reports


def _endpoint_replay(batch_root, scheduling):
    cases = []
    for profile in PROFILES:
        directory = batch_root / "deepseek-v3" / profile
        configuration = json.loads((directory / "configuration.json").read_text())
        envelope = json.loads((directory / "envelope.json").read_text())
        for bandwidth in (0.5, 8.0):
            inputs = load_preprocessed_inputs(Path(configuration["input_dir"]), profile, bandwidth)
            resident_counts = []
            for layout_bandwidth in (0.5, 8.0):
                point = envelope["bandwidths"][str(layout_bandwidth)]["curve"][20]
                artifact = Path(point["deployment_artifact"])
                deployment = inputs.model.load_deployment(artifact)
                dense_end = inputs.model.block_table.dense_layers * inputs.model.block_table.expert_columns
                resident_counts.append(int(np.diff(deployment.residency.resident_ptr)[dense_end:].sum()))
                if bandwidth == layout_bandwidth:
                    report = next(
                        row for row in scheduling
                        if row["hardware_profile"] == profile
                        and row["link_bandwidth_GBps"] == bandwidth
                    )
                    metrics = report["decode"]["stages"][2]
                else:
                    metrics = _decode_summary(
                        measure_decode_routes(compile_decode_executor(deployment), inputs.test_routes)
                    )
                cases.append(
                    {
                        "hardware_profile": profile,
                        "evaluation_bandwidth_GBps": bandwidth,
                        "layout_bandwidth_GBps": layout_bandwidth,
                        "deployment_artifact": str(artifact),
                        "anchor": point["anchor"],
                        "capacity_budget_percent": point["capacity_budget_percent"],
                        "moe_resident_count": resident_counts[-1],
                        "mean_ns": metrics["mean_ns"],
                        "p95_ns": metrics["p95_ns"],
                        "components_ns": metrics["components_ns"],
                    }
                )
            assert resident_counts[0] == resident_counts[1]
    return cases


def _prefill_timeline(batch_root, artifact_dir):
    directory = batch_root / "deepseek-v3" / "planar"
    configuration = json.loads((directory / "configuration.json").read_text())
    envelope = json.loads((directory / "envelope.json").read_text())
    artifact = Path(envelope["bandwidths"]["2.0"]["curve"][20]["deployment_artifact"])
    inputs = load_preprocessed_inputs(Path(configuration["input_dir"]), "planar", 2.0)
    deployment = inputs.model.load_deployment(artifact)
    policies = ("round-robin", "cumulative-work")
    executions = [
        execute_prefill(
            compile_prefill_executor(deployment, policy),
            inputs.prefill_test_routes[:128],
            "trace",
        )
        for policy in policies
    ]
    assert executions[0].resources.compute_busy_ns.sum() == executions[1].resources.compute_busy_ns.sum()
    edges = np.linspace(0, max(row.makespan_ns for row in executions), 257)
    cases = []
    for policy, execution in zip(policies, executions, strict=True):
        trace = execution.diagnostics
        trace_path = artifact_dir / f"prefill-planar-2-T128-window-0-{policy}.npz"
        np.savez_compressed(
            trace_path,
            start_ns=np.asarray(trace.compute_interval_start_ns, dtype=np.int64),
            finish_ns=np.asarray(trace.compute_interval_finish_ns, dtype=np.int64),
            node=np.asarray(trace.compute_interval_node, dtype=np.int16),
            token=np.asarray(trace.compute_interval_token, dtype=np.int16),
            node_compute_work_ns=execution.resources.compute_busy_ns,
            token_latency_ns=execution.token_latency_ns,
        )
        projection = profile_prefill_execution(
            execution, inputs.model.program.dependency_bound_ns, "bottleneck"
        )
        cases.append(
            {
                "policy": policy,
                "makespan_ns": execution.makespan_ns,
                "node_compute_work_ns": execution.resources.compute_busy_ns.tolist(),
                "node_utilization": compute_utilization_timeline(execution, edges).tolist(),
                "bottleneck": asdict(projection.bottleneck),
                "optimization_space": asdict(projection.optimization_space),
                "raw_trace": str(trace_path),
            }
        )
    return {
        "hardware_profile": "planar",
        "link_bandwidth_GBps": 2.0,
        "deployment_artifact": str(artifact),
        "test_window": 0,
        "token_count": 128,
        "route_interval": [8192, 8320],
        "time_edges_ns": edges.tolist(),
        "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-root", type=Path, default=Path("build/dac-paper-full-workload"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("build/paper-mechanisms"))
    parser.add_argument("--output", type=Path, default=Path("paper/data/mechanisms.json"))
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    mapping = _mapping_replay(args.batch_root)
    scheduling = _scheduling(args.batch_root, args.artifact_dir)
    payload = {
        "schema": "paper-mechanisms-v1",
        "model": "deepseek-v3",
        "source_batch": str(args.batch_root),
        "test_route_split": [8192, 12288],
        "decode_route_count": 4096,
        "prefill_windows_per_size": 8,
        "single_copy_mapping": mapping,
        "endpoint_cross_replay": _endpoint_replay(args.batch_root, scheduling),
        "scheduling": scheduling,
        "prefill_timeline": _prefill_timeline(args.batch_root, args.artifact_dir),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"paper-mechanisms out={args.output}", flush=True)


if __name__ == "__main__":
    main()
