"""Rebuild the seed0 DAC experiment batch through 20% replication."""

import argparse
import json
from pathlib import Path

import numpy as np
from deployment.capacity import (
    compile_replica_space,
    write_replica_space_artifact,
)
from deployment.residency import replace_moe_residents
from experiments.configuration import (
    FINAL_BUDGET_PERCENT,
    MODELS,
    PROFILES,
    bandwidths,
    endpoint_test_path,
    inputs_path,
)
from experiments.dataflow_linear_ablation import run_dataflow_linear_ablation
from experiments.decode_hypergraph_mapping import run_decode_hypergraph_mapping
from experiments.inputs import load_preprocessed_inputs
from experiments.method_capacity_diagnostics import run_method_capacity_diagnostics
from experiments.method_curve_frozen_test import run_method_curve_frozen_test
from experiments.sequential_anchor_envelope import (
    run_sequential_anchor_envelope,
    summarize_envelope,
)
from experiments.sequential_capacity_curve import run_sequential_capacity_curve
from experiments.zero_copy_mapping_analysis import run_zero_copy_mapping_analysis
from mapping.decode_baseline import build_full_workload_baseline
from mapping.workload import compile_replica_workload
from profiler.metrics.decode_structure import measure_decode_structural_comparison
from simulation.decode import compile_decode_executor, measure_decode_routes


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare(root, model, profile, input_dir=None):
    input_dir = inputs_path(model) if input_dir is None else input_dir
    directory = root / model / profile
    directory.mkdir(parents=True, exist_ok=True)
    inputs = load_preprocessed_inputs(input_dir, profile)
    space = compile_replica_space(inputs.model)
    write_replica_space_artifact(directory / "space.npz", space)
    workload = compile_replica_workload(
        inputs.model, space.dense_residency, inputs.prefill_train_routes
    )
    residency = build_full_workload_baseline(
        inputs.model.block_table,
        space.dense_residency,
        workload,
        space.moe_resident_capacity,
    )
    baseline = inputs.model.deploy(residency)
    baseline.save(directory / "balanced.npz")
    hw = inputs.model.hardware_profile
    write(
        directory / "configuration.json",
        {
            "input_dir": str(input_dir),
            "route_files": read(input_dir / "routes.json"),
            "node_geometry": [hw.subcube_height, hw.subcube_width, hw.subcube_depth],
            "mesh": list(hw.grid),
            "capacity_ratio": hw.capacity_ratio,
            "required_moe_residents": space.required_moe_resident_count,
            "available_replica_capacity": space.available_replica_capacity,
        },
    )
    if model == "deepseek-v3" and profile == "planar":
        table = inputs.model.block_table
        shape = (table.model_layers - table.dense_layers, table.expert_columns)
        nodes = np.arange(np.prod(shape)).reshape(shape) % hw.mesh_node_count
        resident = np.zeros((*shape, hw.mesh_node_count), dtype=np.bool_)
        np.put_along_axis(resident, nodes[:, :, None], True, axis=2)
        round_robin = inputs.model.deploy(
            replace_moe_residents(space.dense_residency, table, resident)
        )
        round_robin.save(directory / "round-robin.npz")
    print(f"Prepared {directory}: depth={hw.subcube_depth}", flush=True)


def search(root, model, profile, maximum_prefill_regret, input_dir=None):
    input_dir = inputs_path(model) if input_dir is None else input_dir
    directory = root / model / profile
    balanced_paths, hypergraph_paths = [], []
    for bw in bandwidths(model):
        prefix = f"{bw:g}"
        hypergraph = directory / f"{prefix}-hypergraph.json"
        run_decode_hypergraph_mapping(
            hypergraph,
            input_dir,
            profile,
            bw,
            directory / "balanced.npz",
            1024,
        )
        for anchor, paths in (
            ("balanced", balanced_paths),
            ("hypergraph", hypergraph_paths),
        ):
            source = (
                directory / "balanced.npz"
                if anchor == "balanced"
                else hypergraph.with_suffix(".deployment.npz")
            )
            output = directory / f"{prefix}-{anchor}-curve.json"
            run_sequential_capacity_curve(
                output,
                input_dir,
                profile,
                bw,
                directory / "space.npz",
                source,
                1,
                maximum_prefill_regret,
                FINAL_BUDGET_PERCENT,
                None,
            )
            paths.append(output)
    run_sequential_anchor_envelope(
        directory / "envelope.json",
        tuple(balanced_paths),
        tuple(hypergraph_paths),
    )


def evaluate(root, model, profile, input_dir=None):
    input_dir = inputs_path(model) if input_dir is None else input_dir
    directory = root / model / profile
    envelope_path = directory / "envelope.json"
    envelope = read(envelope_path)
    selected = envelope["bandwidths"]["2.0"]["curve"][FINAL_BUDGET_PERCENT]
    frozen_points = directory / "frozen-points.json"
    write(
        frozen_points,
        {
            "bandwidths": {
                "2.0": {
                    "curve": [
                        {
                            "point": "baseline-zero",
                            "deployment_artifact": str(directory / "balanced.npz"),
                        },
                        selected,
                    ]
                }
            }
        },
    )
    for label, point in (
        ("baseline", "baseline-zero"),
        ("selected-20pct", selected["point"]),
    ):
        run_method_curve_frozen_test(
            directory / f"{label}-test.json",
            input_dir,
            profile,
            2.0,
            frozen_points,
            point,
            8,
        )
    for bw in bandwidths(model):
        endpoint = envelope["bandwidths"][str(bw)]["curve"][FINAL_BUDGET_PERCENT]
        if bw != 2.0:
            run_method_curve_frozen_test(
                endpoint_test_path(directory, bw),
                input_dir,
                profile,
                bw,
                envelope_path,
                endpoint["point"],
                8,
            )
        run_dataflow_linear_ablation(
            directory / f"{bw:g}-dataflow.json",
            input_dir,
            profile,
            bw,
            Path(endpoint["deployment_artifact"]),
            8,
        )


def single_copy(root):
    directory = root / "deepseek-v3" / "planar"
    run_zero_copy_mapping_analysis(
        root / "supplementary" / "zero-copy.json",
        inputs_path("deepseek-v3"),
        "planar",
        directory / "space.npz",
        directory / "round-robin.npz",
        directory / "balanced.npz",
        tuple(
            directory / f"{bw:g}-hypergraph.deployment.npz"
            for bw in bandwidths("deepseek-v3")
        ),
    )


def mechanisms(root):
    directory = root / "deepseek-v3" / "planar"
    envelope = read(directory / "envelope.json")
    cases = []
    for bw in (0.5, 8.0):
        inputs = load_preprocessed_inputs(inputs_path("deepseek-v3"), "planar", bw)
        for layout_bw in (0.5, 8.0):
            selected = envelope["bandwidths"][str(layout_bw)]["curve"][
                FINAL_BUDGET_PERCENT
            ]
            artifact = Path(selected["deployment_artifact"])
            deployment = inputs.model.load_deployment(artifact)
            executor = compile_decode_executor(deployment)
            measurement = measure_decode_routes(executor, inputs.validation_routes)
            structure = measure_decode_structural_comparison(
                executor, inputs.validation_routes, measurement
            )
            cases.append(
                {
                    "bandwidth": bw,
                    "layout_bandwidth": layout_bw,
                    "layout_anchor": selected["anchor"],
                    "capacity_budget_percent": selected["capacity_budget_percent"],
                    "deployment_artifact": str(artifact),
                    "serial": structure.critical_serialization_count,
                    "hops": structure.critical_hops,
                    "latency_ms": float(measurement.latency_ns.mean()) / 1e6,
                }
            )
    write(
        root / "cross-replay.json",
        {
            "hardware_profile": "planar",
            "nominal_extra_replica_percent": FINAL_BUDGET_PERCENT,
            "evaluation_split": "validation",
            "cases": cases,
        },
    )
    run_method_capacity_diagnostics(
        root / "diagnostics.json",
        tuple(root / "deepseek-v3" / profile / "envelope.json" for profile in PROFILES),
        inputs_path("deepseek-v3"),
    )


def test_metrics(path):
    report = read(path)
    return {
        key: report[key] for key in ("decode", "prefill", "deployment_artifact")
    } | {"test_report": str(path)}


def reference_metrics(root, model, profile, bandwidth, split):
    path = root / "comparison-baselines" / model / profile / f"{bandwidth:g}.json"
    report = read(path)
    return report["splits"][split] | {
        "deployment_artifact": report["deployment_artifact"],
        "source": str(path),
        "split": split,
    }


def collect(root):
    initial_envelope = read(root / "deepseek-v3" / "planar" / "envelope.json")
    maximum_prefill_regret = initial_envelope["maximum_prefill_regret"]
    prefill_scheduler = read(
        Path(initial_envelope["bandwidths"]["2.0"]["path_inputs"]["compute-balanced"])
    )["prefill_scheduler"]
    main, tests, dataflow = {}, [], []
    for profile in PROFILES:
        directory = root / "deepseek-v3" / profile
        envelope_path = directory / "envelope.json"
        main[profile] = summarize_envelope(read(envelope_path), envelope_path)
        for bw, entry in main[profile].items():
            entry["baseline"] = reference_metrics(
                root, "deepseek-v3", profile, float(bw), "validation"
            )
            for path, target in (
                (endpoint_test_path(directory, float(bw)), tests),
                (directory / f"{float(bw):g}-dataflow.json", dataflow),
            ):
                target.append(read(path) | {"source": str(path)})
    diagnostics_path = root / "diagnostics.json"
    diagnostics = read(diagnostics_path)
    planar_envelope = read(root / "deepseek-v3" / "planar" / "envelope.json")
    deployments = {}
    for bw, entry in planar_envelope["bandwidths"].items():
        endpoint = entry["curve"][FINAL_BUDGET_PERCENT]
        deployments[bw] = {
            "anchor": endpoint["anchor"],
            "capacity_budget_percent": endpoint["capacity_budget_percent"],
            "deployment_artifact": endpoint["deployment_artifact"],
            "decode_components_ns": diagnostics["profiles"]["planar"][bw][
                FINAL_BUDGET_PERCENT
            ]["decode_components_ns"],
        }
    paper = {
        "source_note": f"Generated by experiments.paper_run collect from {root}; seed0, current 1.5x capacity rule.",
        "nominal_extra_replica_percent": FINAL_BUDGET_PERCENT,
        "maximum_prefill_regret": maximum_prefill_regret,
        "prefill_scheduler": prefill_scheduler,
        "baseline": "full-workload-balanced-single-copy",
        "initialization": "full-workload-balanced-and-hypergraph-paths",
        "main": main,
        "dataflow": dataflow,
        "test": tests,
        "deployment_analysis": {
            "hardware_profile": "planar",
            "source": str(diagnostics_path),
            "bandwidths": deployments,
        },
        "cross_replay": read(root / "cross-replay.json")["cases"],
        "resource_diagnostics": {
            "source": str(diagnostics_path),
            "planar_2gbps_budget20": diagnostics["profiles"]["planar"]["2.0"][
                FINAL_BUDGET_PERCENT
            ],
        },
    }
    models = []
    for model, name in MODELS.items():
        profiles = {}
        for profile in PROFILES:
            directory = root / model / profile
            config = read(directory / "configuration.json")
            entry = read(directory / "envelope.json")["bandwidths"]["2.0"]
            point = entry["curve"][FINAL_BUDGET_PERCENT]
            balanced = read(Path(entry["path_inputs"]["compute-balanced"]))
            profiles[profile] = {
                "required_moe_residents": config["required_moe_residents"],
                "extra_replicas": balanced["points"][FINAL_BUDGET_PERCENT][
                    "requested_replica_count"
                ],
                "realized_extra_replica_percent": point["capacity_budget_percent"],
                "node_geometry": config["node_geometry"],
                "selected_anchor": point["anchor"],
                "effective_maximum_prefill_regret": entry["anchor_comparison"][
                    FINAL_BUDGET_PERCENT
                ]["effective_maximum_prefill_regret"],
                "baseline": reference_metrics(root, model, profile, 2.0, "test"),
                "selected": test_metrics(directory / "selected-20pct-test.json"),
            }
        models.append(
            {
                "name": name,
                "input_dir": str(inputs_path(model)),
                "routing_data": "synthetic" if model == "deepseek-v3" else "public",
                "specification": read(inputs_path(model) / "model.json"),
                "profiles": profiles,
            }
        )
    cross = {
        "seed": 0,
        "link_bandwidth_GBps": 2.0,
        "nominal_extra_replica_percent": FINAL_BUDGET_PERCENT,
        "baseline": "full-workload-balanced-single-copy",
        "initialization": "full-workload-balanced-and-hypergraph-paths",
        "mesh": [4, 4],
        "capacity_ratio": 1.5,
        "mapping_scope": "Dense + MoE",
        "workload": "public routing datasets for Qwen2-57B-A14B and DeepSeek-V2-Lite; synthetic routes for DeepSeek-V3",
        "train_route_split": [0, 4096],
        "hypergraph_train_route_count": 1024,
        "validation_route_split": [4096, 8192],
        "test_route_split": [8192, 12288],
        "validation_window_count": 1,
        "test_window_count": 8,
        "prefill_token_counts": [32, 128, 512],
        "maximum_prefill_regret": maximum_prefill_regret,
        "prefill_scheduler": prefill_scheduler,
        "models": models,
    }
    write(Path("paper/data/results-20pct.json"), paper)
    write(Path("artifacts/results/cross-model-20pct.json"), cross)
    print(
        "Updated paper/data/results-20pct.json and artifacts/results/cross-model-20pct.json"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("build/dac-paper-full-workload")
    )
    stages = parser.add_subparsers(dest="stage", required=True)
    for name in ("prepare", "search", "evaluate"):
        stage = stages.add_parser(name)
        stage.add_argument("--model", choices=MODELS, required=True)
        stage.add_argument("--input-dir", type=Path)
        stage.add_argument("--hardware-profile", choices=PROFILES, required=True)
        if name == "search":
            stage.add_argument("--maximum-prefill-regret", type=float, default=0.02)
    stages.add_parser("mechanisms")
    stages.add_parser("single-copy", help="Run the supplementary single-copy study.")
    stages.add_parser("collect")
    args = parser.parse_args()
    if args.stage == "search":
        search(
            args.output_dir,
            args.model,
            args.hardware_profile,
            args.maximum_prefill_regret,
            args.input_dir,
        )
    elif args.stage in ("prepare", "evaluate"):
        {"prepare": prepare, "evaluate": evaluate}[args.stage](
            args.output_dir,
            args.model,
            args.hardware_profile,
            args.input_dir,
        )
    elif args.stage == "mechanisms":
        mechanisms(args.output_dir)
    elif args.stage == "single-copy":
        single_copy(args.output_dir)
    else:
        collect(args.output_dir)


if __name__ == "__main__":
    main()
