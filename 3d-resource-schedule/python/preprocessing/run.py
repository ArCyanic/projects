"""Generate canonical MoE FFN preprocessing artifacts."""

import argparse
from pathlib import Path

from model import GatedMLPSpec, MoEModelSpec
from preprocessing.routes import FORMAL_ROUTE_COUNT, generate_routes, write_inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        suggest_on_error=True,
        description="Generate supported MoE FFN inputs.",
    )
    parser.add_argument(
        "model",
        choices=("mixtral", "deepseek-v3", "deepseek-v2-lite", "qwen2-57b-a14b"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--route-count", type=int, default=FORMAL_ROUTE_COUNT)
    parser.add_argument("--route-seed", type=int, default=0)
    args = parser.parse_args(argv)
    spec = _model_spec(args.model)
    routes = generate_routes(spec, args.route_count, args.route_seed)
    write_inputs(args.output_dir, spec, routes, args.route_seed)
    print(
        f"model={spec.model_id} routes={len(routes)} seed={args.route_seed} "
        f"layers={routes.shape[1]} top_k={spec.top_k} out={args.output_dir}"
    )
    return 0


def _model_spec(model: str) -> MoEModelSpec:
    if model == "mixtral":
        return MoEModelSpec(
            model_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
            revision="eba92302a2861cdc0098cc54bc9f17cb2c47eb61",
            model_layers=32,
            dense_layers=0,
            shared_experts=0,
            routed_experts=8,
            top_k=2,
            moe_mlp=GatedMLPSpec(4096, 14336),
        )
    if model == "deepseek-v3":
        return MoEModelSpec(
            model_id="deepseek-ai/DeepSeek-V3",
            revision="transformers-5.12.1-config",
            model_layers=61,
            dense_layers=3,
            shared_experts=1,
            routed_experts=256,
            top_k=8,
            moe_mlp=GatedMLPSpec(7168, 2048),
            dense_mlp=GatedMLPSpec(7168, 18432),
        )
    if model == "qwen2-57b-a14b":
        return MoEModelSpec(
            model_id="Qwen/Qwen2-57B-A14B-Instruct",
            revision="50896d66b39f1425d63720541a66c7df13e053c0",
            model_layers=28,
            dense_layers=0,
            shared_experts=8,
            routed_experts=64,
            top_k=8,
            moe_mlp=GatedMLPSpec(3584, 2560),
        )
    return MoEModelSpec(
        model_id="deepseek-ai/DeepSeek-V2-Lite-Chat",
        revision="85864749cd611b4353ce1decdb286193298f64c7",
        model_layers=27,
        dense_layers=1,
        shared_experts=2,
        routed_experts=64,
        top_k=6,
        moe_mlp=GatedMLPSpec(2048, 1408),
        dense_mlp=GatedMLPSpec(2048, 10944),
    )


if __name__ == "__main__":
    raise SystemExit(main())
