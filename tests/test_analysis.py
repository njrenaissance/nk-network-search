"""Tests for `analysis.py` — fitness/diversity curves and the inverted-U
figure.

See `spec/issues/13-plan.md` for the design. Each fixture series below is a
small, hand-built `list[MetricsRow]` — the same shape `run.py` (#12) produces
and persists — rather than a real simulation run, since only the plotting
contract (runs without error, writes a file to the expected path) is under
test here, not simulation behavior. `matplotlib.use("Agg")` is forced before
`analysis` (and therefore `pyplot`) is imported, so figure generation never
needs a display — issue #13's second acceptance criterion.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import pytest

from analysis import plot_diversity_curve, plot_fitness_curve, plot_inverted_u
from nkmodel.metrics import MetricsRow

_ROWS = [
    MetricsRow(mean_fitness=0.3, best_fitness=0.5, diversity=0.9),
    MetricsRow(mean_fitness=0.5, best_fitness=0.6, diversity=0.4),
    MetricsRow(mean_fitness=0.6, best_fitness=0.65, diversity=0.0),
]


@pytest.mark.unit
def test_plot_fitness_curve_writes_file_to_expected_path(tmp_path):
    path = tmp_path / "fitness.png"

    result = plot_fitness_curve(_ROWS, path)

    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0


@pytest.mark.unit
def test_plot_diversity_curve_writes_file_to_expected_path(tmp_path):
    path = tmp_path / "diversity.png"

    result = plot_diversity_curve(_ROWS, path)

    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0


@pytest.mark.unit
def test_plot_inverted_u_writes_file_to_expected_path(tmp_path):
    cells = {
        2: [MetricsRow(0.40, 0.50, 0.8), MetricsRow(0.50, 0.55, 0.3)],
        6: [MetricsRow(0.50, 0.60, 0.7), MetricsRow(0.70, 0.75, 0.2)],
        15: [MetricsRow(0.45, 0.50, 0.6), MetricsRow(0.60, 0.62, 0.1)],
    }
    path = tmp_path / "inverted_u.png"

    result = plot_inverted_u(cells, horizon=1, path=path)

    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0
