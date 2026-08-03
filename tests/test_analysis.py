"""Tests for `analysis.py` — rendering the on-disk metric series `run.py`
writes (issue #12) into fitness/diversity curves and the inverted-U figure.

Figures render through Matplotlib's non-interactive `Agg` backend (forced by
`analysis` on import, asserted below), so CI needs no display. Every case uses
a small, deterministic, hand-built sweep of the same shape `run.run_sweep`
produces — no simulation is run here. See `spec/issues/13-plan.md`.
"""

from __future__ import annotations

import matplotlib
import pytest

from analysis import (
    connectivity_series_from_sweep,
    generate_figures,
    load_sweep_results,
    plot_diversity_curves,
    plot_fitness_curves,
    plot_inverted_u,
)
from nkmodel.metrics import MetricsRow
from run import write_sweep_results


def _sweep_cells() -> dict[tuple[str, int], list[MetricsRow]]:
    """A tiny deterministic sweep — the shape `run.run_sweep` produces — with
    an interior-connectivity fitness bump at step 1 (ring 0.55 < random_regular
    0.60 > complete 0.57) so the inverted-U it feeds is genuinely non-monotone.
    """
    return {
        ("ring", 6): [MetricsRow(0.50, 0.60, 1.0), MetricsRow(0.55, 0.65, 0.5), MetricsRow(0.58, 0.70, 0.25)],
        ("random_regular", 6): [MetricsRow(0.52, 0.62, 1.0), MetricsRow(0.60, 0.72, 0.4), MetricsRow(0.64, 0.75, 0.1)],
        ("complete", 6): [MetricsRow(0.53, 0.63, 1.0), MetricsRow(0.57, 0.67, 0.1), MetricsRow(0.59, 0.70, 0.0)],
    }


@pytest.mark.unit
def test_analysis_forces_non_interactive_agg_backend():
    assert matplotlib.get_backend().lower() == "agg"


@pytest.mark.unit
@pytest.mark.parametrize(
    "plot_curves",
    [
        pytest.param(plot_fitness_curves, id="fitness_curves"),
        pytest.param(plot_diversity_curves, id="diversity_curves"),
    ],
)
def test_curve_figure_writes_a_nonempty_file(plot_curves, tmp_path):
    output_path = tmp_path / "curve.png"

    written = plot_curves(_sweep_cells(), output_path)

    assert written == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.unit
def test_inverted_u_figure_writes_a_nonempty_file(tmp_path):
    output_path = tmp_path / "inverted_u.png"
    connectivity = connectivity_series_from_sweep(_sweep_cells(), k=6)

    written = plot_inverted_u(connectivity, horizon=1, output_path=output_path)

    assert written == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 0


@pytest.mark.unit
def test_figure_function_creates_missing_parent_directories(tmp_path):
    output_path = tmp_path / "nested" / "figures" / "fitness.png"

    plot_fitness_curves(_sweep_cells(), output_path)

    assert output_path.exists()


@pytest.mark.unit
def test_connectivity_series_from_sweep_orders_sparse_to_dense():
    series = connectivity_series_from_sweep(_sweep_cells(), k=6)

    assert [label for label, _ in series] == ["ring", "random_regular", "complete"]


@pytest.mark.unit
def test_load_sweep_results_round_trips_run_output(tmp_path):
    cells = _sweep_cells()

    write_sweep_results(cells, tmp_path)  # the `{topology}_K{k}.csv` format issue #12 produces
    loaded = load_sweep_results(tmp_path)

    assert loaded == cells


@pytest.mark.unit
def test_generate_figures_writes_all_three_from_a_sweep_directory(tmp_path):
    input_dir = tmp_path / "sweep"
    input_dir.mkdir()
    output_dir = tmp_path / "figures"
    write_sweep_results(_sweep_cells(), input_dir)

    figures = generate_figures(input_dir, output_dir)

    assert set(figures) == {"fitness", "diversity", "inverted_u"}
    for path in figures.values():
        assert path.exists()
        assert path.parent == output_dir


@pytest.mark.unit
def test_load_sweep_results_rejects_a_malformed_cell_filename(tmp_path):
    (tmp_path / "ring_Kx.csv").write_text("mean_fitness,best_fitness,diversity\n")

    with pytest.raises(ValueError, match="not a sweep-cell filename"):
        load_sweep_results(tmp_path)


@pytest.mark.unit
def test_generate_figures_rejects_an_empty_directory(tmp_path):
    with pytest.raises(ValueError, match="no sweep-cell CSVs"):
        generate_figures(tmp_path, tmp_path / "out")
