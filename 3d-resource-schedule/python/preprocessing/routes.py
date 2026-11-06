"""Topic-correlated synthetic MoE routes and final input artifacts."""

import json
import random
from collections.abc import Collection
from itertools import accumulate
from pathlib import Path

import numpy as np
from compression import zstd
from model import MoEModelSpec, model_spec_json
from numpy.typing import NDArray

FORMAL_ROUTE_COUNT = 40_960
FORMAL_ROUTE_SEED = 0
ZIPF_ALPHA = 1.2
TOPIC_LAYOUT_SEED = 2024
TOPIC_REGIME_TOKEN_COUNT = 192
DOMINANT_TOPIC_PROBABILITY = 0.5

type RouteArray = NDArray[np.uint8]


def generate_routes(
    spec: MoEModelSpec,
    route_count: int = FORMAL_ROUTE_COUNT,
    route_seed: int = FORMAL_ROUTE_SEED,
) -> RouteArray:
    rng = random.Random(route_seed)
    topic_count = min(16, max(1, spec.routed_experts // 4))
    global_take = max(1, spec.top_k // 4)
    clusters = _topic_clusters(spec.routed_experts, topic_count)
    clustered_take = min(len(clusters[0]), spec.top_k - global_take)
    cumulative_weights = list(
        accumulate(_zipf_weights(spec.routed_experts, ZIPF_ALPHA))
    )
    topics = _topic_sequence(rng, topic_count, route_count)
    routes = np.empty(
        (route_count, spec.model_layers - spec.dense_layers, spec.top_k),
        dtype=np.uint8,
    )
    for trace in range(route_count):
        for layer in range(routes.shape[1]):
            cluster = (5 * topics[trace] + 3 * layer) % topic_count
            members = clusters[cluster]
            row = rng.sample(members, clustered_take)
            row.extend(
                _weighted_unique_sample(
                    rng,
                    cumulative_weights,
                    spec.top_k - clustered_take,
                    members,
                )
            )
            routes[trace, layer] = sorted(row)
    return routes


def write_inputs(
    output_dir: Path,
    spec: MoEModelSpec,
    routes: RouteArray,
    route_seed: int = FORMAL_ROUTE_SEED,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "model.json").write_text(
        json.dumps(model_spec_json(spec), indent=2) + "\n",
        encoding="utf-8",
    )
    np.save(output_dir / "activation_traces.npy", routes)
    (output_dir / "routes.json").write_text(
        json.dumps(
            {"decode": "activation_traces.npy", "prefill": "activation_traces.npy"},
            indent=2,
        )
        + "\n"
    )
    _write_audit(
        output_dir / "activation_trace.json.zst",
        spec,
        routes,
        route_seed,
    )


def _write_audit(
    path: Path,
    spec: MoEModelSpec,
    routes: RouteArray,
    route_seed: int,
) -> None:
    metadata = {
        "schema": "activation-trace-v2",
        "model": spec.model_id,
        "workload": {
            "strategy": "topic_correlated",
            "seed": route_seed,
            "zipf_alpha": ZIPF_ALPHA,
            "topic_regime_token_count": TOPIC_REGIME_TOKEN_COUNT,
            "dominant_topic_probability": DOMINANT_TOPIC_PROBABILITY,
        },
        "moe_layer_offset": spec.dense_layers,
        "num_moe_layers": spec.model_layers - spec.dense_layers,
        "num_routed_experts": spec.routed_experts,
        "top_k": spec.top_k,
    }
    with zstd.open(path, "wt", encoding="utf-8", newline="") as audit:
        audit.write(json.dumps(metadata, separators=(",", ":"))[:-1])
        audit.write(',"requests":[')
        for request_id, start in enumerate(
            range(0, len(routes), TOPIC_REGIME_TOKEN_COUNT)
        ):
            if request_id:
                audit.write(",")
            audit.write(f'{{"request_id":{request_id},"tokens":[')
            end = min(start + TOPIC_REGIME_TOKEN_COUNT, len(routes))
            for trace_id in range(start, end):
                if trace_id > start:
                    audit.write(",")
                token = {
                    "token_id": trace_id - start,
                    "trace_id": trace_id,
                    "trace": routes[trace_id].tolist(),
                }
                audit.write(json.dumps(token, separators=(",", ":")))
            audit.write("]}")
        audit.write("]}\n")


def _topic_sequence(
    rng: random.Random,
    topic_count: int,
    route_count: int,
) -> list[int]:
    topics = []
    while len(topics) < route_count:
        dominant_topics = list(range(topic_count))
        rng.shuffle(dominant_topics)
        for dominant in dominant_topics:
            alternatives = [topic for topic in range(topic_count) if topic != dominant]
            regime_count = min(
                TOPIC_REGIME_TOKEN_COUNT,
                route_count - len(topics),
            )
            topics.extend(
                dominant
                if rng.random() < DOMINANT_TOPIC_PROBABILITY
                else rng.choice(alternatives)
                for _ in range(regime_count)
            )
            if len(topics) == route_count:
                break
    return topics


def _topic_clusters(expert_count: int, topic_count: int) -> list[tuple[int, ...]]:
    experts = list(range(expert_count))
    random.Random(TOPIC_LAYOUT_SEED).shuffle(experts)
    return [tuple(experts[topic::topic_count]) for topic in range(topic_count)]


def _zipf_weights(expert_count: int, alpha: float) -> list[float]:
    return [1.0 / ((rank + 1) ** alpha) for rank in range(expert_count)]


def _weighted_unique_sample(
    rng: random.Random,
    cumulative_weights: list[float],
    count: int,
    excluded: Collection[int],
) -> list[int]:
    selected: set[int] = set()
    population = range(len(cumulative_weights))
    while len(selected) < count:
        expert = rng.choices(population, cum_weights=cumulative_weights, k=1)[0]
        if expert not in excluded:
            selected.add(expert)
    return sorted(selected)
