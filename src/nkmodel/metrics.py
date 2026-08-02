"""Fitness/diversity metrics over plain string collections.

Computes `mean_fitness`, `best_fitness`, and `diversity` for a collection of
agent strings at one step against a shared `NKLandscape`, plus a
`MetricsSeries` accumulator and a `convergence_time` helper. Operates on plain
`Sequence[Sequence[int]]` string collections only — no dependency on
`Agent`/`Model` (see `spec/issues/10-plan.md`).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple, Protocol


class _Landscape(Protocol):
    """Structural type for the one method metrics.py depends on."""

    def fitness(self, string: Sequence[int]) -> float: ...


def mean_fitness(strings: Sequence[Sequence[int]], landscape: _Landscape) -> float:
    """Mean of `landscape.fitness(s)` over all `strings`. In `[0, 1)`."""
    return sum(landscape.fitness(s) for s in strings) / len(strings)


def best_fitness(strings: Sequence[Sequence[int]], landscape: _Landscape) -> float:
    """Max of `landscape.fitness(s)` over all `strings`. In `[0, 1)`."""
    return max(landscape.fitness(s) for s in strings)


def diversity(strings: Sequence[Sequence[int]]) -> float:
    """Distinct-string diversity, normalized to `[0, 1]`.

    `0.0` when every string is identical (or there's at most one string);
    `1.0` when every string is pairwise distinct.
    """
    n = len(strings)
    if n <= 1:
        return 0.0
    distinct = len({tuple(s) for s in strings})
    return (distinct - 1) / (n - 1)


def convergence_time(diversities: Sequence[float], tolerance: float = 1e-9) -> int | None:
    """First index in `diversities` at which the value is `<= tolerance` of 0.

    Returns `None` (the documented sentinel) if it never does.
    """
    for step, value in enumerate(diversities):
        if value <= tolerance:
            return step
    return None


class MetricsRow(NamedTuple):
    """One recorded step: `mean_fitness`, `best_fitness`, `diversity`."""

    mean_fitness: float
    best_fitness: float
    diversity: float


class MetricsSeries:
    """Accumulates one `MetricsRow` per `record()` call."""

    def __init__(self) -> None:
        self.rows: list[MetricsRow] = []

    def record(self, strings: Sequence[Sequence[int]], landscape: _Landscape) -> MetricsRow:
        """Compute this step's metrics, append the row, and return it."""
        row = MetricsRow(
            mean_fitness=mean_fitness(strings, landscape),
            best_fitness=best_fitness(strings, landscape),
            diversity=diversity(strings),
        )
        self.rows.append(row)
        return row

    def convergence_time(self, tolerance: float = 1e-9) -> int | None:
        """`convergence_time` over this series' recorded `diversity` values so far."""
        return convergence_time([row.diversity for row in self.rows], tolerance=tolerance)
