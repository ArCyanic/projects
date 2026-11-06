"""Select the per-budget envelope of two sequential capacity paths."""

import json
from pathlib import Path


def summarize_envelope(envelope: dict, source: Path) -> dict:
    """Project raw search reports into the metrics consumed by figure builders."""
    bandwidths = {}
    for bandwidth, entry in envelope["bandwidths"].items():
        paths = {
            name: json.loads(Path(path).read_text(encoding="utf-8"))
            for name, path in entry["path_inputs"].items()
        }
        bandwidths[bandwidth] = {
            "source": str(source),
            "baseline": paths["compute-balanced"]["points"][0]["metrics"],
            "selected": [
                {
                    "budget": point["capacity_budget_percent"],
                    "anchor": point["anchor"],
                    "decode": point["decode_validation"],
                    "prefill": point["prefill_validation"],
                }
                for point in entry["curve"]
            ],
            "paths": {
                name: [
                    {
                        "budget": point["capacity_budget_percent"],
                        "metrics": point["metrics"],
                    }
                    for point in report["points"]
                ]
                for name, report in paths.items()
            },
            "path_sources": entry["path_inputs"],
            "path_runtime_s": {
                name: report["host_seconds"] for name, report in paths.items()
            },
        }
    return bandwidths


def run_sequential_anchor_envelope(
    output: Path,
    balanced_paths: tuple[Path, ...],
    hypergraph_paths: tuple[Path, ...],
) -> int:
    balanced = {
        report["link_bandwidth_GBps"]: (path, report)
        for path in balanced_paths
        for report in (json.loads(path.read_text(encoding="utf-8")),)
    }
    hypergraph = {
        report["link_bandwidth_GBps"]: (path, report)
        for path in hypergraph_paths
        for report in (json.loads(path.read_text(encoding="utf-8")),)
    }
    profile = next(iter(balanced.values()))[1]["hardware_profile"]
    maximum_prefill_regret = next(iter(balanced.values()))[1]["maximum_prefill_regret"]
    bandwidths = {}
    for bandwidth in sorted(balanced):
        balanced_path, balanced_report = balanced[bandwidth]
        hypergraph_path, hypergraph_report = hypergraph[bandwidth]
        curve = []
        comparisons = []
        for balanced_point, hypergraph_point in zip(
            balanced_report["points"],
            hypergraph_report["points"],
            strict=True,
        ):
            candidates = {
                "compute-balanced": balanced_point,
                "hypergraph": hypergraph_point,
            }
            selected, regrets, effective_prefill_regret = select_sequential_anchor(
                {name: point["metrics"] for name, point in candidates.items()},
                maximum_prefill_regret,
            )
            point = candidates[selected]
            curve.append(
                {
                    "point": (
                        f"sequential-capacity-{point['capacity_budget_percent']}"
                    ),
                    "role": "sequential-capacity",
                    "capacity_budget_percent": point["capacity_budget_percent"],
                    "anchor": selected,
                    "deployment_artifact": point["deployment_artifact"],
                    "decode_validation": point["metrics"]["decode"],
                    "prefill_validation": point["metrics"]["prefill"],
                }
            )
            comparisons.append(
                {
                    "capacity_budget_percent": point["capacity_budget_percent"],
                    "selected_anchor": selected,
                    "prefill_regret": regrets,
                    "effective_maximum_prefill_regret": effective_prefill_regret,
                }
            )
        bandwidths[str(bandwidth)] = {
            "curve": curve,
            "anchor_comparison": comparisons,
            "path_inputs": {
                "compute-balanced": str(balanced_path),
                "hypergraph": str(hypergraph_path),
            },
        }
    payload = {
        "schema": "sequential-anchor-envelope-v1",
        "hardware_profile": profile,
        "maximum_prefill_regret": maximum_prefill_regret,
        "bandwidths": bandwidths,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"sequential-anchor-envelope profile={profile} out={output}")
    return 0


def select_sequential_anchor(metrics, maximum_prefill_regret):
    """Apply the smallest feasible Prefill gate, then select Decode mean."""
    best_prefill = {
        tokens: min(report["prefill"][tokens]["mean_ns"] for report in metrics.values())
        for tokens in ("32", "128", "512")
    }
    regrets = {
        name: max(
            report["prefill"][tokens]["mean_ns"] / best_prefill[tokens] - 1
            for tokens in best_prefill
        )
        for name, report in metrics.items()
    }
    effective_prefill_regret = max(maximum_prefill_regret, min(regrets.values()))
    eligible = tuple(
        name for name in metrics if regrets[name] <= effective_prefill_regret
    )
    selected = min(
        eligible,
        key=lambda name: metrics[name]["decode"]["mean_ns"],
    )
    return selected, regrets, effective_prefill_regret
