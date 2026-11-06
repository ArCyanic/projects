"""Physical Pareto refinement of one fixed-count Stage 2 Deployment."""

from dataclasses import asdict, dataclass
from time import perf_counter

import numpy as np
from deployment import Deployment
from deployment.residency import (
    Residency,
    moe_nodes_from_residency,
    replace_moe_residents,
)
from mapping.workload import MappingProblem
from numba import njit
from simulation import ExecutionWorkload, evaluate_deployments
from simulation.decode import (
    DecodeExecutor,
    compile_decode_executor,
)
from simulation.decode.execution import evaluate_decode_moe_layer_causal_routes
from simulation.decode.model import resident_range
from simulation.workload import PREFILL_TOKEN_COUNTS, fixed_prefill_windows
from simulation.statistics import latency_summary

_PREFILL_PROPOSAL_COUNT = 8


@dataclass(slots=True)
class RefinementCandidate:
    name: str
    source: str
    decode_mean_ns: float
    decode_p95_ns: float
    prefill_mean_ns: dict[str, int]
    maximum_prefill_regret: float
    pareto: bool
    selected: bool

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class RefinementResult:
    deployment: Deployment
    candidates: tuple[RefinementCandidate, ...]
    maximum_prefill_regret: float
    host_seconds: float

    def to_payload(self) -> dict[str, object]:
        selected = next(item.name for item in self.candidates if item.selected)
        return {
            "method": "fixed-count-physical-pareto",
            "config": {"maximum_prefill_regret": self.maximum_prefill_regret},
            "selected_candidate": selected,
            "host_seconds": self.host_seconds,
            "candidates": [item.to_payload() for item in self.candidates],
        }


def refine_deployment(
    problem: MappingProblem,
    initial_residency,
    maximum_prefill_regret: float = 0.02,
) -> RefinementResult:
    """Select Decode/Prefill proposals through one batched Physical gate."""
    started = perf_counter()
    model = problem.model
    anchor = model.deploy(initial_residency)
    decode = _decode_pair_prefixes(
        problem,
        initial_residency,
    )
    prefill_residencies = _prefill_pair_residencies(problem, initial_residency)
    prefill = tuple(model.deploy(residency) for residency in prefill_residencies)
    deployments = (anchor, *decode, *prefill)
    names = (
        "stage2-anchor",
        *(f"decode-prefix-{index}" for index in range(1, len(decode) + 1)),
        *(f"prefill-swap-{index}" for index in range(1, len(prefill) + 1)),
    )
    sources = (
        "anchor",
        *("decode" for _ in decode),
        *("prefill" for _ in prefill),
    )
    metrics = _physical_metrics(deployments, problem)
    selected, regrets, pareto = select_refinement_candidate(
        metrics,
        maximum_prefill_regret,
    )
    candidates = tuple(
        RefinementCandidate(
            name,
            source,
            decode_mean,
            decode_p95,
            prefill_values,
            regrets[index],
            pareto[index],
            index == selected,
        )
        for index, (
            name,
            source,
            (decode_mean, decode_p95, prefill_values),
        ) in enumerate(zip(names, sources, metrics, strict=True))
    )
    return RefinementResult(
        deployments[selected],
        candidates,
        maximum_prefill_regret,
        perf_counter() - started,
    )


def select_refinement_candidate(metrics, maximum_prefill_regret):
    """Apply the configured Prefill boundary, then select Decode mean."""
    anchor_prefill = metrics[0][2]
    regrets = tuple(
        max(
            prefill_values[token_count] / anchor_prefill[token_count] - 1
            for token_count in anchor_prefill
        )
        for _, _, prefill_values in metrics
    )
    pareto = _pareto_flags(metrics)
    eligible = tuple(
        index
        for index, regret in enumerate(regrets)
        if regret <= maximum_prefill_regret
    )
    selected = min(eligible, key=lambda index: (metrics[index][0], index))
    return selected, regrets, pareto


def _physical_metrics(deployments, problem):
    executions = evaluate_deployments(
        deployments,
        ExecutionWorkload(
            problem.decode_routes, problem.prefill_routes, fixed_prefill_windows(1)
        ),
    )
    metrics = []
    for execution in executions:
        summary = latency_summary(execution.decode.latency_ns)
        prefill = {
            str(len(row.token_latency_ns)): row.makespan_ns for row in execution.prefill
        }
        metrics.append((summary["mean_ns"], summary["p95_ns"], prefill))
    return tuple(metrics)


def _pareto_flags(metrics):
    vectors = np.asarray(
        [
            (decode_mean, *(prefill[str(count)] for count in PREFILL_TOKEN_COUNTS))
            for decode_mean, _, prefill in metrics
        ]
    )
    return tuple(
        not any(
            np.all(vectors[other] <= vectors[index])
            and np.any(vectors[other] < vectors[index])
            for other in range(len(vectors))
            if other != index
        )
        for index in range(len(vectors))
    )


def _prefill_pair_residencies(problem, initial_residency):
    model = problem.model
    workload = problem.workload
    moe = moe_nodes_from_residency(
        initial_residency,
        model.block_table,
        model.hardware_profile.mesh_node_count,
    )
    counts = moe.sum(axis=2).astype(np.int16)
    shares = (
        workload.demand.astype(np.float64)
        * workload.expert_service_ns[None, :, :]
        / counts[None, :, :]
    )
    node_work = workload.dense_node_work.copy()
    for layer in range(moe.shape[0]):
        for expert in range(moe.shape[1]):
            node_work[:, moe[layer, expert]] += shares[:, layer, expert, None]
    scale = 1 / workload.window_token_count.astype(np.float64)
    peaks, untouched = _pair_peak_bounds(node_work)
    moves = []
    for layer in range(moe.shape[0]):
        move = _best_prefill_swap(
            moe[layer],
            shares[:, layer],
            node_work,
            scale,
            peaks,
            untouched,
        )
        if move[0] >= 0 and move[4] > 0:
            moves.append((float(move[4]), layer, *move[:4]))
    moves.sort(reverse=True)
    residencies = []
    for _, layer, left_expert, left_node, right_expert, right_node in moves[
        :_PREFILL_PROPOSAL_COUNT
    ]:
        candidate = moe.copy()
        candidate[layer, left_expert, left_node] = False
        candidate[layer, left_expert, right_node] = True
        candidate[layer, right_expert, right_node] = False
        candidate[layer, right_expert, left_node] = True
        residencies.append(
            replace_moe_residents(
                initial_residency,
                model.block_table,
                candidate,
            )
        )
    return tuple(residencies)


@njit(cache=True)
def _pair_peak_bounds(node_work):
    scenarios, nodes = node_work.shape
    peaks = np.zeros(scenarios, dtype=np.float64)
    untouched = np.zeros((scenarios, nodes, nodes), dtype=np.float64)
    for scenario in range(scenarios):
        for node in range(nodes):
            peaks[scenario] = max(peaks[scenario], node_work[scenario, node])
        for left in range(nodes):
            for right in range(nodes):
                for node in range(nodes):
                    if node != left and node != right:
                        untouched[scenario, left, right] = max(
                            untouched[scenario, left, right], node_work[scenario, node]
                        )
    return peaks, untouched


@njit(cache=True)
def _best_prefill_swap(moe, shares, node_work, scale, peaks, untouched):
    best = (-1, -1, -1, -1, 0.0)
    scenarios, nodes = node_work.shape
    for left_expert in range(moe.shape[0]):
        for right_expert in range(left_expert + 1, moe.shape[0]):
            for left in range(nodes):
                if not moe[left_expert, left] or moe[right_expert, left]:
                    continue
                for right in range(nodes):
                    if (
                        left == right
                        or not moe[right_expert, right]
                        or moe[left_expert, right]
                    ):
                        continue
                    gain = 0.0
                    for scenario in range(scenarios):
                        left_share = shares[scenario, left_expert]
                        right_share = shares[scenario, right_expert]
                        new_peak = max(
                            untouched[scenario, left, right],
                            node_work[scenario, left] + (right_share - left_share),
                            node_work[scenario, right] + (left_share - right_share),
                        )
                        gain += scale[scenario] * (peaks[scenario] - new_peak)
                    if gain > best[4]:
                        best = (left_expert, left, right_expert, right, gain)
    return best


_PROPOSALS_PER_LAYER = 400


_PREFIX_COUNT = 4


_PROPOSAL_SEED = 20_260_731


def _decode_pair_prefixes(
    problem: MappingProblem,
    initial_residency: Residency,
) -> tuple[Deployment, ...]:
    """Return evenly spaced prefixes from one Decode pair-exchange pass."""
    model = problem.model
    working = Residency(
        initial_residency.resident_ptr, initial_residency.resident_node.copy()
    )
    placement = _DecodePairPlacement(compile_decode_executor(model.deploy(working)))
    checkpoints = tuple(
        int(np.ceil(placement.layer_count * index / _PREFIX_COUNT))
        for index in range(1, _PREFIX_COUNT + 1)
    )
    prefixes = _run_pair_exchange(
        model.block_table,
        placement,
        problem.decode_routes,
        _AffectedRoutes(
            problem.decode_routes,
            model.block_table.shared_experts,
            model.block_table.routed_experts,
        ),
        np.random.default_rng(_PROPOSAL_SEED),
        checkpoints,
    )
    return tuple(
        model.deploy(
            replace_moe_residents(
                initial_residency,
                model.block_table,
                prefix,
            )
        )
        for prefix in prefixes
    )


class _DecodePairPlacement:
    """Maintain the resident-node index during one fixed-count exchange pass."""

    __slots__ = ("_executor", "_resident_id")

    def __init__(self, executor: DecodeExecutor) -> None:
        self._executor = executor
        table = executor.residents
        layers = table.model_layers - table.dense_layers
        self._resident_id = np.full(
            (layers, table.expert_columns, table.node_count), -1, dtype=np.int32
        )
        for layer in range(layers):
            for expert in range(table.expert_columns):
                slot = (table.dense_layers + layer) * table.expert_columns + expert
                start, end = resident_range(table, slot)
                self._resident_id[layer, expert, table.resident_node[start:end]] = (
                    np.arange(start, end)
                )

    @property
    def layer_count(self) -> int:
        return len(self._resident_id)

    def selected(self, layer: int) -> np.ndarray:
        return np.argwhere(self._resident_id[layer] >= 0)

    def has(self, layer: int, expert: int, node: int) -> bool:
        return bool(self._resident_id[layer, expert, node] >= 0)

    def materialize(self) -> np.ndarray:
        return self._resident_id >= 0

    def move(self, layer: int, expert: int, source: int, destination: int) -> None:
        identifier = self._resident_id[layer, expert, source]
        self._executor.residents.resident_node[identifier] = destination
        self._resident_id[layer, expert, source] = -1
        self._resident_id[layer, expert, destination] = identifier

    @property
    def initial_input_node(self) -> int:
        residents = self._executor.residents
        if residents.dense_layers == 0:
            return 0
        slot = (residents.dense_layers - 1) * residents.expert_columns
        return int(residents.resident_node[residents.resident_ptr[slot]])

    def layer_causal_durations(
        self,
        layer: int,
        active_experts: np.ndarray,
        input_nodes: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        return evaluate_decode_moe_layer_causal_routes(
            self._executor.residents,
            self._executor.collective,
            layer,
            active_experts,
            input_nodes,
        )


class _AffectedRoutes:
    __slots__ = ("_incidence", "_mask")

    def __init__(
        self,
        routes: np.ndarray,
        shared_experts: int,
        routed_experts: int,
    ) -> None:
        self._incidence = _compile_route_incidence(
            routes,
            shared_experts,
            routed_experts,
        )
        self._mask = np.empty(len(routes), dtype=np.bool_)

    def between(
        self,
        left_layer: int,
        left_expert: int,
        right_layer: int,
        right_expert: int,
    ) -> np.ndarray:
        np.logical_or(
            self._incidence[left_layer, left_expert],
            self._incidence[right_layer, right_expert],
            out=self._mask,
        )
        return np.flatnonzero(self._mask)


def _run_pair_exchange(
    block_table,
    placement,
    routes,
    affected_routes,
    random,
    checkpoint_layers,
):
    prefixes = []
    input_node = np.full(len(routes), placement.initial_input_node, dtype=np.int16)
    for moe_layer in range(placement.layer_count):
        model_layer = block_table.dense_layers + moe_layer
        active_expert = routes[:, moe_layer]
        current_duration, _ = placement.layer_causal_durations(
            model_layer,
            active_expert,
            input_node,
        )
        current_total = int(current_duration.sum())
        for _ in range(_PROPOSALS_PER_LAYER):
            selected = placement.selected(moe_layer)
            left, right = random.choice(len(selected), 2, replace=False)
            left_expert, left_node = selected[left]
            right_expert, right_node = selected[right]
            if (
                left_node == right_node
                or placement.has(moe_layer, int(left_expert), int(right_node))
                or placement.has(moe_layer, int(right_expert), int(left_node))
            ):
                continue
            placement.move(
                moe_layer,
                int(left_expert),
                int(left_node),
                int(right_node),
            )
            placement.move(
                moe_layer,
                int(right_expert),
                int(right_node),
                int(left_node),
            )
            affected = affected_routes.between(
                moe_layer,
                int(left_expert),
                moe_layer,
                int(right_expert),
            )
            candidate_duration, _ = placement.layer_causal_durations(
                model_layer,
                active_expert[affected],
                input_node[affected],
            )
            current_total, accepted_candidate = _accept_candidate(
                current_duration,
                current_total,
                affected,
                candidate_duration,
            )
            if not accepted_candidate:
                placement.move(
                    moe_layer,
                    int(left_expert),
                    int(right_node),
                    int(left_node),
                )
                placement.move(
                    moe_layer,
                    int(right_expert),
                    int(left_node),
                    int(right_node),
                )
        _, input_node = placement.layer_causal_durations(
            model_layer,
            routes[:, moe_layer],
            input_node,
        )
        if moe_layer + 1 in checkpoint_layers:
            prefixes.append(placement.materialize())
    return tuple(prefixes)


def _accept_candidate(
    current: np.ndarray,
    current_total: int,
    affected: np.ndarray,
    candidate: np.ndarray,
) -> tuple[int, bool]:
    candidate_total = (
        current_total - int(current[affected].sum()) + int(candidate.sum())
    )
    if candidate_total >= current_total:
        return current_total, False
    current[affected] = candidate
    return candidate_total, True


def _compile_route_incidence(
    routes: np.ndarray,
    shared_experts: int,
    routed_experts: int,
) -> np.ndarray:
    incidence = np.zeros(
        (routes.shape[1], shared_experts + routed_experts, len(routes)),
        dtype=np.bool_,
    )
    route_id = np.arange(len(routes))
    incidence[:, :shared_experts] = True
    for layer in range(routes.shape[1]):
        for rank in range(routes.shape[2]):
            incidence[
                layer,
                routes[:, layer, rank].astype(np.int16) + shared_experts,
                route_id,
            ] = True
    return incidence
