"""Closed entry point for the supported artifact-backed experiments."""

import argparse
import os
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True,
        description="Run one supported artifact-backed evaluation recipe.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output", type=Path, required=True)
    common.add_argument("--input-dir", type=Path, required=True)
    common.add_argument("--hardware-profile", required=True)
    bandwidth = argparse.ArgumentParser(add_help=False)
    bandwidth.add_argument("--link-bandwidth-gbps", type=float, required=True)
    deployment = argparse.ArgumentParser(add_help=False)
    deployment.add_argument("--deployment-artifact", type=Path, required=True)
    recipes = parser.add_subparsers(dest="recipe", required=True)
    recipes.add_parser("communication-sensitivity", parents=[common, deployment])
    method_capacity_plot = recipes.add_parser("method-capacity-plot")
    method_capacity_plot.add_argument(
        "--input", type=Path, action="append", required=True
    )
    method_capacity_plot.add_argument("--output-prefix", type=Path, required=True)
    sequential_anchor_envelope = recipes.add_parser("sequential-anchor-envelope")
    sequential_anchor_envelope.add_argument("--output", type=Path, required=True)
    sequential_anchor_envelope.add_argument(
        "--balanced", type=Path, action="append", required=True
    )
    sequential_anchor_envelope.add_argument(
        "--hypergraph", type=Path, action="append", required=True
    )
    method_capacity_diagnostics = recipes.add_parser("method-capacity-diagnostics")
    method_capacity_diagnostics.add_argument(
        "--curve", type=Path, action="append", required=True
    )
    method_capacity_diagnostics.add_argument("--input-dir", type=Path, required=True)
    method_capacity_diagnostics.add_argument("--output", type=Path, required=True)
    method_capacity_diagnostics_plot = recipes.add_parser(
        "method-capacity-diagnostics-plot"
    )
    method_capacity_diagnostics_plot.add_argument("--input", type=Path, required=True)
    method_capacity_diagnostics_plot.add_argument(
        "--output-dir", type=Path, required=True
    )
    zero_copy_mapping_analysis = recipes.add_parser(
        "zero-copy-mapping-analysis", parents=[common]
    )
    zero_copy_mapping_analysis.add_argument(
        "--replica-space-artifact", type=Path, required=True
    )
    zero_copy_mapping_analysis.add_argument(
        "--round-robin-artifact", type=Path, required=True
    )
    zero_copy_mapping_analysis.add_argument(
        "--balanced-artifact", type=Path, required=True
    )
    zero_copy_mapping_analysis.add_argument(
        "--hypergraph-artifact", type=Path, action="append", required=True
    )
    zero_copy_mapping_plot = recipes.add_parser("zero-copy-mapping-plot")
    zero_copy_mapping_plot.add_argument("--input", type=Path, required=True)
    zero_copy_mapping_plot.add_argument("--output-dir", type=Path, required=True)
    qkvo_obstruction_plot = recipes.add_parser("qkvo-obstruction-plot")
    qkvo_obstruction_plot.add_argument("--input", type=Path, required=True)
    qkvo_obstruction_plot.add_argument("--output", type=Path, required=True)
    communication_sensitivity_plot = recipes.add_parser(
        "communication-sensitivity-plot"
    )
    communication_sensitivity_plot.add_argument("--input", type=Path, required=True)
    communication_sensitivity_plot.add_argument(
        "--vertical-input",
        type=Path,
        required=True,
    )
    communication_sensitivity_plot.add_argument("--output", type=Path, required=True)
    recipes.add_parser("replica-space", parents=[common])
    solution = recipes.add_parser("solution", parents=[deployment])
    solution.add_argument("--output-dir", type=Path, required=True)
    solution.add_argument("--input-dir", type=Path, required=True)
    solution.add_argument("--hardware-profile", required=True)
    decode_hypergraph_mapping = recipes.add_parser(
        "decode-hypergraph-mapping", parents=[common]
    )
    decode_hypergraph_mapping.add_argument("--link-bandwidth-gbps", type=float)
    decode_hypergraph_mapping.add_argument(
        "--baseline-deployment-artifact", type=Path, required=True
    )
    decode_hypergraph_mapping.add_argument(
        "--train-route-count", type=int, default=1024
    )
    method_curve_frozen_test = recipes.add_parser(
        "method-curve-frozen-test", parents=[common, bandwidth]
    )
    method_curve_frozen_test.add_argument(
        "--method-curve-report", type=Path, required=True
    )
    method_curve_frozen_test.add_argument("--point", required=True)
    method_curve_frozen_test.add_argument(
        "--test-window-count", type=int, required=True
    )
    dataflow_linear_ablation = recipes.add_parser(
        "dataflow-linear-ablation", parents=[common, bandwidth, deployment]
    )
    dataflow_linear_ablation.add_argument(
        "--test-window-count", type=int, required=True
    )
    dataflow_linear_plot = recipes.add_parser("dataflow-linear-plot")
    dataflow_linear_plot.add_argument(
        "--input", type=Path, action="append", required=True
    )
    dataflow_linear_plot.add_argument("--output", type=Path, required=True)
    sequential_capacity_curve = recipes.add_parser(
        "sequential-capacity-curve", parents=[common, bandwidth]
    )
    sequential_capacity_curve.add_argument(
        "--replica-space-artifact", type=Path, required=True
    )
    sequential_capacity_curve.add_argument(
        "--anchor-deployment-artifact", type=Path, required=True
    )
    sequential_capacity_curve.add_argument(
        "--validation-window-count", type=int, default=1
    )
    sequential_capacity_curve.add_argument(
        "--maximum-prefill-regret", type=float, default=0.02
    )
    sequential_capacity_curve.add_argument(
        "--maximum-capacity-budget-percent", type=int, default=20
    )
    sequential_capacity_curve.add_argument("--resume-report", type=Path)
    args = parser.parse_args(argv)
    print(f"experiment pid={os.getpid()} recipe={args.recipe}")

    if args.recipe == "method-capacity-plot":
        from experiments.plots.method_capacity import run_method_capacity_plot

        return run_method_capacity_plot(tuple(args.input), args.output_prefix)
    if args.recipe == "sequential-anchor-envelope":
        from experiments.sequential_anchor_envelope import (
            run_sequential_anchor_envelope,
        )

        return run_sequential_anchor_envelope(
            args.output,
            tuple(args.balanced),
            tuple(args.hypergraph),
        )
    if args.recipe == "method-capacity-diagnostics":
        from experiments.method_capacity_diagnostics import (
            run_method_capacity_diagnostics,
        )

        return run_method_capacity_diagnostics(
            args.output,
            tuple(args.curve),
            args.input_dir,
        )
    if args.recipe == "method-capacity-diagnostics-plot":
        from experiments.plots.method_capacity_diagnostics import (
            run_method_capacity_diagnostics_plot,
        )

        return run_method_capacity_diagnostics_plot(
            args.input,
            args.output_dir,
        )
    if args.recipe == "dataflow-linear-plot":
        from experiments.plots.dataflow_linear import run_dataflow_linear_plot

        return run_dataflow_linear_plot(tuple(args.input), args.output)
    if args.recipe == "zero-copy-mapping-analysis":
        from experiments.zero_copy_mapping_analysis import (
            run_zero_copy_mapping_analysis,
        )

        return run_zero_copy_mapping_analysis(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.replica_space_artifact,
            args.round_robin_artifact,
            args.balanced_artifact,
            tuple(args.hypergraph_artifact),
        )
    if args.recipe == "zero-copy-mapping-plot":
        from experiments.plots.zero_copy_mapping import run_zero_copy_mapping_plot

        return run_zero_copy_mapping_plot(args.input, args.output_dir)
    if args.recipe == "qkvo-obstruction-plot":
        from experiments.plots.qkvo_obstruction import run_qkvo_obstruction_plot

        return run_qkvo_obstruction_plot(args.input, args.output)
    if args.recipe == "communication-sensitivity-plot":
        from experiments.plots.communication_sensitivity import (
            run_communication_sensitivity_plot,
        )

        return run_communication_sensitivity_plot(
            args.input,
            args.vertical_input,
            args.output,
        )

    if args.recipe == "replica-space":
        from deployment.capacity import (
            compile_replica_space,
            write_replica_space_artifact,
        )
        from experiments.inputs import load_preprocessed_inputs

        inputs = load_preprocessed_inputs(args.input_dir, args.hardware_profile)
        space = compile_replica_space(inputs.model)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_replica_space_artifact(args.output, space)
        print(
            f"replica-space profile={args.hardware_profile} "
            f"capacity={int(space.moe_resident_capacity.sum())} "
            f"out={args.output}"
        )
        return 0

    if args.recipe == "solution":
        from experiments.solution import run_solution_export

        return run_solution_export(
            output_dir=args.output_dir,
            input_dir=args.input_dir,
            hardware_profile=args.hardware_profile,
            deployment_artifact=args.deployment_artifact,
        )

    if args.recipe == "communication-sensitivity":
        from experiments.communication_sensitivity import (
            run_communication_sensitivity,
        )

        return run_communication_sensitivity(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.deployment_artifact,
        )
    if args.recipe == "decode-hypergraph-mapping":
        from experiments.decode_hypergraph_mapping import (
            run_decode_hypergraph_mapping,
        )

        return run_decode_hypergraph_mapping(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.link_bandwidth_gbps,
            args.baseline_deployment_artifact,
            args.train_route_count,
        )
    if args.recipe == "method-curve-frozen-test":
        from experiments.method_curve_frozen_test import run_method_curve_frozen_test

        return run_method_curve_frozen_test(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.link_bandwidth_gbps,
            args.method_curve_report,
            args.point,
            args.test_window_count,
        )
    if args.recipe == "dataflow-linear-ablation":
        from experiments.dataflow_linear_ablation import (
            run_dataflow_linear_ablation,
        )

        return run_dataflow_linear_ablation(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.link_bandwidth_gbps,
            args.deployment_artifact,
            args.test_window_count,
        )
    if args.recipe == "sequential-capacity-curve":
        from experiments.sequential_capacity_curve import (
            run_sequential_capacity_curve,
        )

        return run_sequential_capacity_curve(
            args.output,
            args.input_dir,
            args.hardware_profile,
            args.link_bandwidth_gbps,
            args.replica_space_artifact,
            args.anchor_deployment_artifact,
            args.validation_window_count,
            args.maximum_prefill_regret,
            args.maximum_capacity_budget_percent,
            args.resume_report,
        )
    raise AssertionError(args.recipe)


if __name__ == "__main__":
    raise SystemExit(main())
