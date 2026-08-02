"""Tests for `run.py` — single run, replication averaging, topology×K sweep,
and the headline findings from Lazer & Friedman (2007).

See `spec/issues/12-plan.md` for the design and the parameter choices below.
All cases are deterministic: a fixed `seed` plus enough `replications` per
`.claude/standards/testing.md` / `spec.md`'s "Stochastic criteria run with a
fixed seed and enough replications to be deterministic under test."
"""

from __future__ import annotations

import pytest

from nkmodel import metrics
from nkmodel.config import DEFAULTS, NKConfig
from run import (
    load_results_csv,
    run_replications,
    run_single,
    run_sweep,
    write_sweep_results,
)

# ---------------------------------------------------------------------------
# Helpers (not tests themselves)
# ---------------------------------------------------------------------------


def _config(**overrides: object) -> NKConfig:
    """An `NKConfig` from `DEFAULTS` with the given per-test overrides."""
    return NKConfig(**{**DEFAULTS, **overrides})


def _high_k_ring_and_complete_rows() -> dict[str, list[metrics.MetricsRow]]:
    """One `run_replications` series per topology, called directly (not a
    fixture, so a `NotImplementedError` from the stub surfaces as a normal
    test failure rather than a fixture-setup error) by both the crossover and
    diversity-collapse tests below, which share these same two cells.
    """
    base = _config(N=10, K=6, A=16, replications=20, steps=20, B=2)
    return {
        "ring": run_replications(base.model_copy(update={"topology": "ring"}), seed=0),
        "complete": run_replications(base.model_copy(update={"topology": "complete"}), seed=0),
    }


# ---------------------------------------------------------------------------
# Foundational shape/contract tests for the three driver functions — not
# headline findings, but the "single-run function" / "sweep function" scope
# each headline test below relies on.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_run_single_returns_one_row_per_step():
    config = _config(N=6, K=2, A=8, topology="ring", steps=5, B=2)

    rows = run_single(config, seed=0)

    assert len(rows) == 5
    assert all(0 <= row.mean_fitness < 1 for row in rows)


@pytest.mark.unit
def test_run_replications_averages_across_independent_runs():
    config = _config(N=6, K=2, A=8, topology="ring", steps=4, replications=3, B=2)

    averaged = run_replications(config, seed=0)
    individual = [run_single(config, seed=0 + i) for i in range(3)]

    assert len(averaged) == 4
    for t, row in enumerate(averaged):
        assert row.mean_fitness == pytest.approx(sum(r[t].mean_fitness for r in individual) / 3)
        assert row.best_fitness == pytest.approx(sum(r[t].best_fitness for r in individual) / 3)
        assert row.diversity == pytest.approx(sum(r[t].diversity for r in individual) / 3)


@pytest.mark.unit
def test_run_sweep_returns_one_cell_per_topology_times_k_combination():
    base = _config(N=5, A=6, replications=2, steps=3, B=2)

    results = run_sweep(base, topologies=["ring", "complete"], k_values=[0, 2], seed=0)

    assert set(results.keys()) == {("ring", 0), ("ring", 2), ("complete", 0), ("complete", 2)}
    for (topology, k), rows in results.items():
        expected = run_replications(base.model_copy(update={"topology": topology, "K": k}), seed=0)
        assert rows == expected


# ---------------------------------------------------------------------------
# AC1 — K=0 invariance: with K=0, mean fitness converges to the same optimum
# for `ring` and `complete` (topology is irrelevant on a smooth landscape).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_k0_invariance_ring_and_complete_converge_to_same_optimum():
    config = _config(N=8, K=0, A=10, steps=15, B=2)

    ring_rows = run_single(config.model_copy(update={"topology": "ring"}), seed=0)
    complete_rows = run_single(config.model_copy(update={"topology": "complete"}), seed=0)

    assert ring_rows[-1].mean_fitness == pytest.approx(complete_rows[-1].mean_fitness, abs=1e-9)


# ---------------------------------------------------------------------------
# AC2 — crossover at high K: `complete` has strictly higher mean fitness than
# `ring` early, but strictly lower mean fitness at the final step (both
# averaged over replications).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_high_k_crossover_complete_wins_early_but_loses_by_the_end():
    rows = _high_k_ring_and_complete_rows()
    ring_rows, complete_rows = rows["ring"], rows["complete"]

    assert complete_rows[2].mean_fitness > ring_rows[2].mean_fitness
    assert complete_rows[-1].mean_fitness < ring_rows[-1].mean_fitness


# ---------------------------------------------------------------------------
# AC3 — diversity collapse: `complete` reaches ~0 diversity (convergence) in
# strictly fewer steps than `ring`.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_high_k_diversity_collapse_complete_converges_faster_than_ring():
    rows = _high_k_ring_and_complete_rows()
    ring_rows, complete_rows = rows["ring"], rows["complete"]

    ring_convergence = metrics.convergence_time([row.diversity for row in ring_rows])
    complete_convergence = metrics.convergence_time([row.diversity for row in complete_rows])

    assert complete_convergence is not None
    assert ring_convergence is not None
    assert complete_convergence < ring_convergence


# ---------------------------------------------------------------------------
# AC4 — inverted-U: at an intermediate horizon, sweeping connectivity from
# sparse to dense yields non-monotone mean fitness — an interior connectivity
# level outperforms both the sparsest and the densest.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_inverted_u_interior_connectivity_outperforms_sparse_and_dense():
    base = _config(N=10, K=6, A=16, replications=40, steps=10, B=2)
    intermediate_step = 6

    sparse = run_replications(base.model_copy(update={"topology": "random_regular", "degree": 2}), seed=0)
    interior = run_replications(base.model_copy(update={"topology": "random_regular", "degree": 6}), seed=0)
    dense = run_replications(base.model_copy(update={"topology": "random_regular", "degree": 15}), seed=0)

    interior_fitness = interior[intermediate_step].mean_fitness
    assert interior_fitness > sparse[intermediate_step].mean_fitness
    assert interior_fitness > dense[intermediate_step].mean_fitness


# ---------------------------------------------------------------------------
# AC5 — sweep results are persisted to disk (one file per cell) so a later
# process (`analysis.py`, issue #13) can read them back without rerunning the
# simulation.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_sweep_results_round_trips_through_disk(tmp_path):
    results = {
        ("ring", 0): [metrics.MetricsRow(0.1, 0.2, 0.3), metrics.MetricsRow(0.4, 0.5, 0.0)],
        ("complete", 2): [metrics.MetricsRow(0.6, 0.7, 0.1)],
    }

    written_paths = write_sweep_results(results, tmp_path)

    assert set(written_paths.keys()) == set(results.keys())
    for cell, path in written_paths.items():
        assert path.exists()
        assert load_results_csv(path) == results[cell]
