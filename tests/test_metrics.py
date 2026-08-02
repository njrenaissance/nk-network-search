"""Tests for nkmodel.metrics — fitness/diversity metrics over plain string
collections. See spec/issues/10-plan.md for the design these assert against.

Operates on plain `Sequence[Sequence[int]]` string collections and
`NKLandscape` only — no `Agent`/`Model` dependency (issue #10).
"""

from __future__ import annotations

import random

import pytest

from nkmodel import metrics
from nkmodel.landscape import NKLandscape

N = 4


@pytest.fixture
def landscape() -> NKLandscape:
    """A small, deterministic landscape shared by the fitness-metric tests."""
    return NKLandscape(n=N, k=1, scheme="adjacent", rng=random.Random(0))


@pytest.fixture
def strings() -> list[list[int]]:
    """Three distinct length-N strings — enough to make mean != best."""
    return [[0, 0, 0, 0], [1, 1, 1, 1], [0, 1, 0, 1]]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("metric_fn", "expected_fn"),
    [
        pytest.param(metrics.mean_fitness, lambda fits: sum(fits) / len(fits), id="mean_fitness"),
        pytest.param(metrics.best_fitness, max, id="best_fitness"),
    ],
)
def test_fitness_metric_matches_direct_computation_and_is_in_unit_interval(metric_fn, expected_fn, landscape, strings):
    direct_fits = [landscape.fitness(s) for s in strings]

    result = metric_fn(strings, landscape)

    assert result == pytest.approx(expected_fn(direct_fits))
    assert 0 <= result < 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("string_set", "expected_diversity"),
    [
        pytest.param([[0, 0], [0, 0], [0, 0]], 0.0, id="all_identical_is_minimal"),
        pytest.param([[0, 0], [0, 1], [1, 0]], 1.0, id="all_distinct_is_maximal"),
        pytest.param([[0, 0], [0, 0], [1, 1]], 0.5, id="partial_duplicates_is_between"),
        pytest.param([[0, 0]], 0.0, id="single_agent_is_trivially_zero"),
    ],
)
def test_diversity_counts_distinct_strings(string_set, expected_diversity):
    assert metrics.diversity(string_set) == pytest.approx(expected_diversity)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("diversities", "expected_step"),
    [
        pytest.param([1.0, 0.5, 0.0, 0.0], 2, id="converges_at_first_zero_step"),
        pytest.param([0.0, 0.5, 1.0], 0, id="already_converged_at_step_zero"),
        pytest.param([1.0, 0.8, 1e-10], 2, id="converges_within_tolerance_of_zero"),
        pytest.param([1.0, 0.5, 0.2], None, id="never_converges_returns_sentinel"),
    ],
)
def test_convergence_time_returns_first_step_reaching_zero_or_sentinel(diversities, expected_step):
    assert metrics.convergence_time(diversities) == expected_step


@pytest.mark.unit
def test_metrics_series_record_appends_one_row_per_call(landscape, strings):
    series = metrics.MetricsSeries()
    identical_strings = [[0, 0, 0, 0], [0, 0, 0, 0]]

    series.record(strings, landscape)
    series.record(identical_strings, landscape)

    assert len(series.rows) == 2
    assert series.rows[0].mean_fitness == pytest.approx(metrics.mean_fitness(strings, landscape))
    assert series.rows[0].best_fitness == pytest.approx(metrics.best_fitness(strings, landscape))
    assert series.rows[0].diversity == pytest.approx(metrics.diversity(strings))
    assert series.rows[1].diversity == pytest.approx(0.0)


@pytest.mark.unit
def test_metrics_series_convergence_time_delegates_to_recorded_diversities(landscape):
    series = metrics.MetricsSeries()
    diverse_strings = [[0, 0, 0, 0], [1, 1, 1, 1]]
    identical_strings = [[0, 0, 0, 0], [0, 0, 0, 0]]

    series.record(diverse_strings, landscape)
    series.record(identical_strings, landscape)

    assert series.convergence_time() == 1
