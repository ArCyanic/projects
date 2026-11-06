"""Import released MoE routing records and document their experiment splits."""

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from model import model_spec_json
from preprocessing.run import _model_spec

BEYOND_COMMIT = "47031eefc7808e996ecd5c01d7ed90aa32e32514"
PREFETCH_REVISION = "1d27a69e1b464c9bc9c840d3e42c2469df19a90d"
SPLIT_TOKENS = 4096


def write_hd_moe_qwen(path, output):
    """Preserve the released layer-aligned stream for a contiguous-split pilot."""
    layers = json.loads(path.read_text())
    if set(layers) != set(map(str, range(28))):
        raise ValueError("HD-MoE Qwen trace must cover all 28 layers")
    routes = np.stack([np.asarray(layers[str(i)]) for i in range(28)], axis=1)
    if routes.shape[1:] != (28, 8) or len(routes) < 3 * SPLIT_TOKENS:
        raise ValueError(f"Unexpected Qwen route dimensions: {routes.shape}")
    if routes.dtype.kind not in "iu" or routes.min() < 0 or routes.max() >= 64:
        raise ValueError("Invalid Qwen routed expert IDs")
    if not np.all(np.diff(np.sort(routes, axis=-1), axis=-1) > 0):
        raise ValueError("Repeated Qwen expert within a token/layer")
    spec = _model_spec("qwen2-57b-a14b")
    spec.revision = "checkpoint revision not reported by trace publisher"
    output.mkdir(parents=True, exist_ok=True)
    np.save(
        output / "activation_traces.npy", routes[: 3 * SPLIT_TOKENS].astype(np.uint8)
    )
    (output / "model.json").write_text(
        json.dumps(model_spec_json(spec), indent=2) + "\n"
    )
    (output / "routes.json").write_text(
        json.dumps(
            {"decode": "activation_traces.npy", "prefill": "activation_traces.npy"},
            indent=2,
        )
        + "\n"
    )
    metadata = {
        "source": {
            "url": "https://github.com/angerybob/HD-MoE",
            "revision": "94ba08ecaa01bbfe3ace2c56aab1698cdfcc7f8f",
            "file": "expert_trace/qwen/experts_reasoning_qwen.json",
            "model_id": spec.model_id,
            "workload": "MT-Bench reasoning",
            "phase": "inference; phase boundaries absent from released JSON",
            "license": "MIT",
        },
        "observed_tokens": len(routes),
        "split_rule": "first 12288 tokens in original order; three contiguous 4096-token blocks",
        "route_splits": {
            "train": [0, 4096],
            "validation": [4096, 8192],
            "test": [8192, 12288],
        },
        "request_boundaries": "not supplied; request-disjointness unverified",
        "top_k_order": "preserved from source",
        "shared_experts": "expanded by the execution model; source contains routed IDs only",
    }
    (output / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        f"{output}: {len(routes)} observed tokens; imported shape={(12288, 28, 8)}",
        flush=True,
    )


def load_moe_beyond(path):
    requests = []
    seen_prompts = set()
    duplicates = 0
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if "/training_data_eamc/" in name and name.endswith(".csv")
        )
        for name in names:
            layers = defaultdict(list)
            for row in csv.DictReader(io.StringIO(archive.read(name).decode())):
                if int(row["Batch Number"]) != 0:
                    raise ValueError(f"Unexpected batch in {name}")
                layers[int(row["Layer ID"])].append(row)
            if sorted(layers) != list(range(1, 27)):
                raise ValueError(f"Incomplete layers in {name}")
            tokens = tuple(row["Token"] for row in layers[1])
            for rows in layers.values():
                if tuple(row["Token"] for row in rows) != tokens:
                    raise ValueError(f"Token alignment differs across layers: {name}")
            if tokens in seen_prompts:
                duplicates += 1
                continue
            seen_prompts.add(tokens)
            routes = np.stack(
                [
                    np.asarray(
                        [json.loads(row["Activated Expert IDs"]) for row in layers[lid]]
                    )
                    for lid in range(1, 27)
                ],
                axis=1,
            )
            requests.append((str(Path(name).relative_to(Path(name).parts[0])), routes))
    source = {
        "url": "https://github.com/ngavhane/moe-beyond",
        "revision": BEYOND_COMMIT,
        "workload": "LDJnr/Puffin prompts released in training_data_eamc",
        "phase": "prefill",
        "capture": "single forward pass; load_in_8bit=True; 26 MoE gate hooks",
        "duplicate_prompts_removed": duplicates,
        "license": "not specified in repository",
    }
    return requests, source, "deepseek-v2-lite"


def load_mixtral_cache(path):
    import torch

    with (
        zipfile.ZipFile(path) as archive,
        archive.open("Traces/mixtral_trace.torch") as stream,
    ):
        traces = torch.load(stream, map_location="cpu", weights_only=True)
    requests = []
    for index, scores in enumerate(traces):
        if scores.ndim != 3 or scores.shape[0] != 32 or scores.shape[2] != 8:
            raise ValueError(f"Unexpected Mixtral score dimensions: {scores.shape}")
        if not torch.isfinite(scores).all():
            raise ValueError(f"Non-finite router scores in request {index}")
        # Use the same top-k operation as the authors' artifact notebook.
        routes = scores.transpose(0, 1).topk(2).indices.numpy()
        requests.append((f"mixtral-request-{index}", routes))
    source = {
        "url": "https://zenodo.org/records/15576758",
        "revision": "v1, 2025-06-02",
        "workload": "VMware/Open-instruct, as described in the paper",
        "phase": "inference; prefill/decode boundary not supplied",
        "capture": "32-layer, 8-expert router score tensors; authors' topk(2)",
        "checkpoint_variant": "base/instruct variant not specified by artifact",
        "license": "CC-BY-4.0",
    }
    return requests, source, "mixtral"


def load_prefetch_mlp(path):
    grouped = defaultdict(list)
    sources = []
    for chunk in sorted(path.glob("moe_trace_chunk_*.npz")):
        with np.load(chunk, allow_pickle=False) as data:
            routes, uids = data["routes"], data["prompt_uids"]
        for uid in dict.fromkeys(uids.tolist()):
            grouped[uid].append(routes[uids == uid])
        sources.append(json.loads(chunk.with_suffix(".json").read_text()))
    requests = [(uid, np.concatenate(parts)) for uid, parts in grouped.items()]
    source = {
        "url": "https://huggingface.co/datasets/bubblebird/PrefetchMLP",
        "revision": PREFETCH_REVISION,
        "workload": "UltraChat train_sft, GSM8K main, Magicoder evol",
        "phase": "decode",
        "capture": "decode_only=true; actual_selected_ids=true; aligned prompt_uids",
        "weight_precision": "not specified in released metadata",
        "license": "not specified in dataset card",
        "chunks": sources,
    }
    return requests, source, "deepseek-v2-lite"


def write_public_inputs(requests, source, model, output):
    spec = _model_spec(model)
    spec.revision = "checkpoint revision not reported by trace publisher"
    if model == "mixtral":
        spec.model_id = "Mixtral-8x7B (checkpoint variant unspecified by artifact)"
    shape = (spec.model_layers - spec.dense_layers, spec.top_k)
    unique = []
    seen_traces = set()
    for uid, routes in requests:
        if routes.ndim != 3 or routes.shape[1:] != shape or len(routes) == 0:
            raise ValueError(f"Unexpected route shape for {uid}: {routes.shape}")
        if (
            routes.dtype.kind not in "iu"
            or routes.min() < 0
            or routes.max() >= spec.routed_experts
        ):
            raise ValueError(f"Invalid expert IDs in {uid}")
        if not np.all(np.diff(np.sort(routes, axis=-1), axis=-1) > 0):
            raise ValueError(f"Repeated expert within a token/layer: {uid}")
        routes = routes.astype(np.uint8)
        key = routes.tobytes()
        if key in seen_traces:
            continue
        seen_traces.add(key)
        unique.append((uid, routes))
    order = np.random.default_rng(0).permutation(len(unique))
    cursor = 0
    arrays, selected = [], {}
    for split in ("train", "validation", "test"):
        remaining = SPLIT_TOKENS
        selected[split] = []
        while remaining:
            if cursor == len(order):
                raise ValueError(
                    "Insufficient distinct requests for three 4096-token splits"
                )
            uid, routes = unique[order[cursor]]
            cursor += 1
            take = min(remaining, len(routes))
            arrays.append(routes[:take])
            selected[split].append(
                {"request_id": uid, "tokens_used": take, "source_tokens": len(routes)}
            )
            remaining -= take
    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "activation_traces.npy", np.concatenate(arrays))
    (output / "routes.json").write_text(
        json.dumps(
            {"decode": "activation_traces.npy", "prefill": "activation_traces.npy"},
            indent=2,
        )
        + "\n"
    )
    (output / "model.json").write_text(
        json.dumps(model_spec_json(spec), indent=2) + "\n"
    )
    metadata = {
        "source": source,
        "observed_requests": len(requests),
        "observed_tokens": sum(len(routes) for _, routes in requests),
        "unique_requests": len(unique),
        "duplicate_complete_traces_removed": len(requests) - len(unique),
        "split_seed": 0,
        "split_rule": "shuffle whole requests; take 4096 tokens per split; discard unused tail of boundary request",
        "route_splits": {
            "train": [0, 4096],
            "validation": [4096, 8192],
            "test": [8192, 12288],
        },
        "requests": selected,
        "top_k_order": "preserved from source",
        "shared_experts": "expanded by the execution model; source contains routed IDs only",
    }
    (output / "source.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(
        f"{output}: {len(unique)} unique requests; shape={(12288, *shape)}", flush=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", choices=("moe-beyond", "mixtral-cache", "prefetch-mlp", "hd-moe-qwen")
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.source == "hd-moe-qwen":
        write_hd_moe_qwen(args.input, args.output_dir)
        return
    loader = {
        "moe-beyond": load_moe_beyond,
        "mixtral-cache": load_mixtral_cache,
        "prefetch-mlp": load_prefetch_mlp,
    }[args.source]
    write_public_inputs(*loader(args.input), args.output_dir)


if __name__ == "__main__":
    main()
