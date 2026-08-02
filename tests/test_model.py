"""Tests for `nkmodel.model.Model` — the synchronous turn loop.

See `spec/issues/11-plan.md` for the design these assert against.

A local `_FixedFitnessLandscape` fake gives exact, caller-controlled fitness
values so the tie / strict-beat scenarios (synchronous commit, lowest-uid
tie-break) are deterministic — the real `NKLandscape`'s per-locus contributions
are continuous draws, so two distinct strings landing on an *exact* fitness tie
has probability zero in practice (same rationale as `tests/test_agent.py`'s
fake). Tests that only need genuine hill-climbing convergence use the real
`NKLandscape`.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from nkmodel import metrics
from nkmodel.config import DEFAULTS, NKConfig
from nkmodel.model import Model

# ---------------------------------------------------------------------------
# Helpers / fakes (not tests themselves)
# ---------------------------------------------------------------------------


class _FixedFitnessLandscape:
    """Test double for the `fitness(string) -> float` protocol `Model` relies on.

    Returns a caller-specified fitness for listed strings and `default` for any
    other (e.g. explore candidates we deliberately don't enumerate). See the
    module docstring for why a fake is needed to engineer exact ties.
    """

    def __init__(self, fitness_by_string: dict[tuple[int, ...], float], default: float = 0.0) -> None:
        self._fitness_by_string = fitness_by_string
        self._default = default

    def fitness(self, string: Sequence[int]) -> float:
        return self._fitness_by_string.get(tuple(string), self._default)


def _config(**overrides: object) -> NKConfig:
    """An `NKConfig` from `DEFAULTS` with the given per-test overrides."""
    return NKConfig(**{**DEFAULTS, **overrides})


# ---------------------------------------------------------------------------
# Constructor — a run is fully determined by (config, seed); the Model wires up
# a landscape, agents (uids 0..A-1), a graph, and an empty metrics series.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_model_constructed_from_config_and_seed_wires_all_collaborators():
    config = _config(N=6, K=2, A=5, topology="complete", B=2)

    model = Model(config, seed=0)

    assert model.config is config
    assert model.seed == 0
    assert [agent.uid for agent in model.agents] == [0, 1, 2, 3, 4]
    assert all(len(agent.string) == 6 for agent in model.agents)
    assert all(bit in (0, 1) for agent in model.agents for bit in agent.string)
    assert model.landscape.N == 6
    assert model.landscape.K == 2
    assert model.graph.number_of_nodes() == 5
    assert model.metrics.rows == []


# ---------------------------------------------------------------------------
# AC1 — synchronous, not sequential: an agent's committed move within a step is
# not visible to another until the next step.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_step_updates_synchronously_not_sequentially():
    n = 4
    seed = 0
    config = _config(N=n, A=2, topology="complete", B=2)
    model = Model(config, seed=seed)

    a0 = [0, 0, 0, 0]  # agent 0 — worst, will exploit
    b0 = [1, 1, 1, 1]  # agent 1 — start-of-turn string
    # Agent 0 exploits first (no rng draw), so agent 1's explore is the first
    # consumer of the shared rng: its flip index is the first draw.
    flip_index = random.Random(seed).randrange(n)
    b1 = list(b0)
    b1[flip_index] ^= 1  # agent 1's strictly-better explore result, same step

    model.landscape = _FixedFitnessLandscape({tuple(a0): 0.1, tuple(b0): 0.5, tuple(b1): 0.9})
    model.agents[0].string = a0
    model.agents[1].string = b0
    model.rng = random.Random(seed)

    model.step()

    # Agent 0 copied agent 1's START-of-turn string (b0), NOT the string agent 1
    # moved to within the same step (b1) — proving synchronous, not sequential.
    assert model.agents[0].string == b0
    assert model.agents[0].string != b1
    assert model.agents[1].string == b1


# ---------------------------------------------------------------------------
# Integration with #9's tie-break contract: Model must pass neighbor_states in
# ascending-uid order so decide's stable `max` copies the lowest-uid neighbor
# among several tied for best.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_step_passes_neighbors_in_ascending_uid_order_for_tie_break():
    config = _config(N=4, A=3, topology="complete", B=2)
    model = Model(config, seed=0)

    s0 = [0, 0, 0, 0]  # agent 0 — worst; will exploit a tied-best neighbor
    s1 = [1, 1, 1, 1]  # agent 1 — tied for best, lowest uid
    s2 = [1, 1, 1, 0]  # agent 2 — tied for best, higher uid
    # default=0.0 makes agents 1 & 2's explore flips (unlisted strings) rejected,
    # so they hold their strings and only agent 0's copy is under test.
    model.landscape = _FixedFitnessLandscape({tuple(s0): 0.1, tuple(s1): 0.9, tuple(s2): 0.9}, default=0.0)
    model.agents[0].string = s0
    model.agents[1].string = s1
    model.agents[2].string = s2
    model.rng = random.Random(0)

    model.step()

    # Both neighbors tie for best and beat agent 0; the lowest uid (agent 1) wins.
    assert model.agents[0].string == s1
    assert model.agents[0].string != s2


# ---------------------------------------------------------------------------
# AC2 — each step appends exactly one metrics row (mean, best, diversity), and
# step() returns the row it appended.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_step_appends_exactly_one_metrics_row_per_call():
    config = _config(N=6, K=2, A=8, topology="ring", scheme="adjacent", B=2)
    model = Model(config, seed=3)

    returned_rows = [model.step() for _ in range(4)]

    assert len(model.metrics.rows) == 4
    assert returned_rows == model.metrics.rows  # step() returns the appended row
    current = [agent.string for agent in model.agents]
    last = model.metrics.rows[-1]
    assert last.mean_fitness == pytest.approx(metrics.mean_fitness(current, model.landscape))
    assert last.best_fitness == pytest.approx(metrics.best_fitness(current, model.landscape))
    assert last.diversity == pytest.approx(metrics.diversity(current))
    assert all(0 <= row.mean_fitness < 1 for row in model.metrics.rows)


# ---------------------------------------------------------------------------
# AC3 — the same (config, seed) produces an identical metric time-series across
# two separate Model runs (landscape, network, initial strings, and explore
# flips are all reproducible). topology="ws" exercises the network RNG too.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_same_config_and_seed_produce_identical_series():
    config = _config(N=6, K=3, A=8, topology="ws", ws_k=4, ws_p=0.3, steps=12, B=2)

    first = Model(config, seed=7)
    second = Model(config, seed=7)
    first.run()
    second.run()

    assert first.metrics.rows == second.metrics.rows
    assert len(first.metrics.rows) == 12


@pytest.mark.unit
def test_different_seed_produces_different_series():
    config = _config(N=6, K=3, A=8, topology="ws", ws_k=4, ws_p=0.3, steps=12, B=2)

    first = Model(config, seed=1)
    second = Model(config, seed=2)
    first.run()
    second.run()

    assert first.metrics.rows != second.metrics.rows


# ---------------------------------------------------------------------------
# AC4 — a full run on `complete` topology visibly converges agents to a shared
# string (build-spec.md milestone 3).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_complete_topology_run_converges_to_shared_string():
    config = _config(N=6, K=2, A=12, topology="complete", steps=100, B=2)
    model = Model(config, seed=0)

    model.run()

    assert len(model.metrics.rows) == 100
    assert model.metrics.rows[-1].diversity == pytest.approx(0.0)
    assert model.metrics.convergence_time() is not None
    assert len({tuple(agent.string) for agent in model.agents}) == 1
