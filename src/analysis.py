"""Analysis — fitness/diversity curves and the inverted-U figure, rendered
from the per-step series `run.py` (#12) writes to disk.

Thin script per `spec/build-order.md`'s resolved ambiguity: sits beside
`nkmodel/` and `run.py`, rooted under `src/`. No simulation logic lives here —
it only consumes `MetricsRow` series `run.py`'s `load_results_csv` /
`write_sweep_results` convention already produces and renders them with
`matplotlib`.

See `spec/issues/13-plan.md` for the design; `tests/test_analysis.py` is
locked (`spec/issues/13-tests.lock`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from nkmodel.metrics import MetricsRow


def plot_fitness_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path:
    """Mean and best fitness vs step for one topology/K cell's series.

    Writes a figure to `path` and returns the path written.
    """
    raise NotImplementedError


def plot_diversity_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path:
    """Diversity vs step for one topology/K cell's series.

    Writes a figure to `path` and returns the path written.
    """
    raise NotImplementedError


def plot_inverted_u(cells: Mapping[float, Sequence[MetricsRow]], horizon: int, path: Path | str) -> Path:
    """Mean fitness at step `horizon` vs connectivity level, sparse to dense.

    `cells` maps a connectivity level (e.g. `degree`) to that level's
    `MetricsRow` series; levels are plotted in ascending (sparse to dense)
    order regardless of `cells`' iteration order. Writes a figure to `path`
    and returns the path written.
    """
    raise NotImplementedError
