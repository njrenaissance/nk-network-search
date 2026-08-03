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

import matplotlib

# Defensive: force a non-interactive backend at import time in case a caller
# runs this somewhere without a display. `tests/test_analysis.py` already
# forces `Agg` before importing this module, so this is belt-and-suspenders,
# not what makes the tests deterministic.
matplotlib.use("Agg", force=False)

import matplotlib.pyplot as plt  # noqa: E402 (must follow matplotlib.use())

from nkmodel.metrics import MetricsRow


def _save_and_close(fig: plt.Figure, path: Path | str) -> Path:
    """Write `fig` to `path`, close it to free resources, and return `path`."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def plot_fitness_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path:
    """Mean and best fitness vs step for one topology/K cell's series.

    Writes a figure to `path` and returns the path written.
    """
    steps = range(len(rows))
    mean_values = [row.mean_fitness for row in rows]
    best_values = [row.best_fitness for row in rows]

    fig, ax = plt.subplots()
    ax.plot(steps, mean_values, label="mean fitness")
    ax.plot(steps, best_values, label="best fitness")
    ax.set_xlabel("step")
    ax.set_ylabel("fitness")
    ax.set_title("Fitness vs step")
    ax.legend()

    return _save_and_close(fig, path)


def plot_diversity_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path:
    """Diversity vs step for one topology/K cell's series.

    Writes a figure to `path` and returns the path written.
    """
    steps = range(len(rows))
    diversity_values = [row.diversity for row in rows]

    fig, ax = plt.subplots()
    ax.plot(steps, diversity_values, label="diversity")
    ax.set_xlabel("step")
    ax.set_ylabel("diversity")
    ax.set_title("Diversity vs step")
    ax.legend()

    return _save_and_close(fig, path)


def plot_inverted_u(cells: Mapping[float, Sequence[MetricsRow]], horizon: int, path: Path | str) -> Path:
    """Mean fitness at step `horizon` vs connectivity level, sparse to dense.

    `cells` maps a connectivity level (e.g. `degree`) to that level's
    `MetricsRow` series; levels are plotted in ascending (sparse to dense)
    order regardless of `cells`' iteration order. Writes a figure to `path`
    and returns the path written.
    """
    levels = sorted(cells)
    mean_fitness_at_horizon = [cells[level][horizon].mean_fitness for level in levels]

    fig, ax = plt.subplots()
    ax.plot(levels, mean_fitness_at_horizon, marker="o")
    ax.set_xlabel("connectivity level")
    ax.set_ylabel(f"mean fitness at step {horizon}")
    ax.set_title("Mean fitness vs connectivity (inverted-U)")

    return _save_and_close(fig, path)
