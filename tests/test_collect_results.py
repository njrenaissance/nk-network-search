"""Tests for `collect_results.py` — the default-config results-collection
runner that drives `run.run_replications` and renders the collected series to
disk.

Batches use a tiny, cheap `NKConfig` (small `N`/`A`/`steps`/`replications`) so
the real `Model` runs stay fast and deterministic — no mocking of the internal
`run_replications` collaborator, per `.claude/standards/testing.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import collect_results
from collect_results import build_summary, collect
from nkmodel.config import DEFAULTS, NKConfig
from nkmodel.metrics import MetricsRow
from run import load_results_csv, run_replications


def _config(**overrides: object) -> NKConfig:
    """An `NKConfig` from `DEFAULTS` with the given per-test overrides."""
    return NKConfig(**{**DEFAULTS, **overrides})


def _tiny_config() -> NKConfig:
    """A cheap batch that runs a real `Model` in well under a second."""
    return _config(N=4, K=0, A=4, topology="ring", steps=3, replications=2)


def _rows(diversities: list[float]) -> list[MetricsRow]:
    """Synthetic per-step series carrying the given diversity values."""
    return [
        MetricsRow(mean_fitness=0.5 + i * 0.01, best_fitness=0.5 + i * 0.02, diversity=diversity)
        for i, diversity in enumerate(diversities)
    ]


@pytest.mark.unit
def test_collect_writes_averaged_series_and_summary(tmp_path):
    config = _tiny_config()

    csv_path = collect(config, tmp_path)

    assert csv_path == tmp_path / "averaged_replications2.csv"
    assert load_results_csv(csv_path) == run_replications(config, config.seed)
    assert (tmp_path / "SUMMARY.md").exists()
    assert "2 replications of the defaults" in (tmp_path / "SUMMARY.md").read_text()


@pytest.mark.unit
def test_collect_creates_missing_results_directory(tmp_path):
    nested = tmp_path / "does" / "not" / "exist"

    csv_path = collect(_tiny_config(), nested)

    assert csv_path.parent == nested
    assert csv_path.exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("diversities", "expected_convergence"),
    [
        pytest.param([0.9, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], "step 2", id="converges"),
        pytest.param([0.9, 0.4, 0.3, 0.2, 0.2, 0.1, 0.1, 0.1], "did not fully converge", id="never_converges"),
    ],
)
def test_build_summary_reports_metrics_and_trajectory(diversities, expected_convergence):
    config = _config(N=6, K=2, A=8, topology="ring", steps=len(diversities), replications=4)

    summary = build_summary(config, _rows(diversities), Path("averaged_replications4.csv"))

    assert "# Simulation results — 4 replications of the defaults" in summary
    assert "| `topology` | `ring` |" in summary
    assert "| Step | Mean fitness | Best fitness | Diversity |" in summary
    assert f"**Diversity collapse (convergence):** {expected_convergence}" in summary
    assert "[`averaged_replications4.csv`](averaged_replications4.csv)" in summary


@pytest.mark.unit
def test_main_writes_results_into_current_directory(tmp_path, monkeypatch, mocker):
    monkeypatch.chdir(tmp_path)
    mocker.patch("collect_results.get_config", return_value=_tiny_config())

    collect_results.main()

    assert (tmp_path / "results" / "averaged_replications2.csv").exists()
    assert (tmp_path / "results" / "SUMMARY.md").exists()
