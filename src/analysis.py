"""Analysis — render the on-disk metric series `run.py` writes into figures.

Thin script (like `run.py`) rooted under `src/` per `spec/build-order.md`'s
resolved ambiguity. Consumes the `{topology}_K{k}.csv` sweep files
`run.write_sweep_results` produces (issue #12) and renders the three figures
`spec.md`'s "Inputs / Outputs" and `build-spec.md` §12 call for:

* **fitness curves** — mean (solid) and best (dashed) fitness vs step, one pair
  of lines per `(topology, K)` cell;
* **diversity curves** — diversity vs step, one line per cell;
* **the inverted-U** — mean fitness at a fixed intermediate horizon vs
  connectivity level, swept sparse -> dense.

Figures are always written to disk (`spec.md`'s "Where we persist"), never
shown, so this module renders through Matplotlib's non-interactive ``Agg``
backend and never needs a display — CI stays headless. See
`spec/issues/13-plan.md` for the design.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from nkmodel.metrics import MetricsRow
from run import load_results_csv

# Figures are saved to disk and never displayed, so the backend can be the
# non-interactive `Agg` one; switching here (after the import above) keeps
# rendering headless regardless of the ambient Matplotlib configuration.
plt.switch_backend("Agg")

# Built-in topologies ordered from sparsest to densest connectivity — the axis
# the inverted-U figure walks. Mirrors `spec.md`'s ring -> ws -> random_regular
# -> complete progression.
CONNECTIVITY_ORDER: tuple[str, ...] = ("ring", "ws", "random_regular", "complete")

# Default directory figures are written to; git-ignored (see `.gitignore`).
DEFAULT_OUTPUT_DIR = Path("figures")

Cell = tuple[str, int]
Series = Sequence[MetricsRow]


def load_sweep_results(input_dir: Path | str) -> dict[Cell, list[MetricsRow]]:
    """Load every `{topology}_K{k}.csv` under `input_dir` back into a sweep
    dict — the inverse of `run.write_sweep_results`.

    The keys round-trip through the filename convention issue #12 established,
    so `analysis.py` reads a completed sweep without rerunning the simulation.
    """
    return {cell: load_results_csv(path) for cell, path in sorted(_cell_files(Path(input_dir)))}


def _cell_files(input_dir: Path) -> list[tuple[Cell, Path]]:
    """The `((topology, k), path)` pairs for every sweep-cell CSV in `input_dir`."""
    return [(_parse_cell_filename(path), path) for path in input_dir.glob("*_K*.csv")]


def _parse_cell_filename(path: Path) -> Cell:
    """Split a `{topology}_K{k}.csv` name into `(topology, k)`.

    `topology` may itself contain underscores (e.g. `random_regular`), so the
    split is on the last `_K`, not the first underscore.
    """
    topology, separator, k_text = path.stem.rpartition("_K")
    if not separator or not topology or not k_text.isdigit():
        raise ValueError(f"not a sweep-cell filename: {path.name!r}")
    return topology, int(k_text)


def plot_fitness_curves(cells: Mapping[Cell, Series], output_path: Path | str) -> Path:
    """Plot mean (solid) and best (dashed, same colour) fitness vs step for
    every cell, and write the figure to `output_path`; return that path."""
    figure, axes = plt.subplots()
    for (topology, k), rows in sorted(cells.items()):
        steps = range(len(rows))
        mean_line = axes.plot(steps, [row.mean_fitness for row in rows], label=f"{topology} K={k} (mean)")[0]
        axes.plot(
            steps,
            [row.best_fitness for row in rows],
            linestyle="--",
            color=mean_line.get_color(),
            label=f"{topology} K={k} (best)",
        )
    axes.set_xlabel("step")
    axes.set_ylabel("fitness")
    axes.set_title("Fitness vs step")
    axes.legend(fontsize="small")
    return _save(figure, output_path)


def plot_diversity_curves(cells: Mapping[Cell, Series], output_path: Path | str) -> Path:
    """Plot diversity vs step, one line per cell, and write the figure to
    `output_path`; return that path."""
    figure, axes = plt.subplots()
    for (topology, k), rows in sorted(cells.items()):
        axes.plot(range(len(rows)), [row.diversity for row in rows], label=f"{topology} K={k}")
    axes.set_xlabel("step")
    axes.set_ylabel("diversity")
    axes.set_title("Diversity vs step")
    axes.legend(fontsize="small")
    return _save(figure, output_path)


def plot_inverted_u(connectivity_series: Sequence[tuple[str, Series]], horizon: int, output_path: Path | str) -> Path:
    """Plot mean fitness at step `horizon` against connectivity level.

    `connectivity_series` is an ordered (sparse -> dense) sequence of
    `(label, series)`; the label names each connectivity level on the x axis.
    The interior peak between the sparsest and densest levels is the inverted-U.
    """
    labels = [label for label, _ in connectivity_series]
    fitness_at_horizon = [series[horizon].mean_fitness for _, series in connectivity_series]
    figure, axes = plt.subplots()
    axes.plot(range(len(labels)), fitness_at_horizon, marker="o")
    axes.set_xticks(range(len(labels)))
    axes.set_xticklabels(labels)
    axes.set_xlabel("connectivity (sparse → dense)")
    axes.set_ylabel(f"mean fitness at step {horizon}")
    axes.set_title("Inverted-U: connectivity vs mean fitness")
    return _save(figure, output_path)


def connectivity_series_from_sweep(
    cells: Mapping[Cell, Series], k: int, order: Sequence[str] = CONNECTIVITY_ORDER
) -> list[tuple[str, Series]]:
    """The `(topology, series)` pairs at a fixed `k`, ordered sparse -> dense
    per `order` — ready to hand to `plot_inverted_u`.

    Topologies in `order` that the sweep did not cover are skipped, so a sweep
    over a subset of `CONNECTIVITY_ORDER` still yields a well-ordered axis.
    """
    return [(topology, cells[(topology, k)]) for topology in order if (topology, k) in cells]


def generate_figures(
    input_dir: Path | str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    *,
    inverted_u_k: int | None = None,
    horizon: int | None = None,
) -> dict[str, Path]:
    """Read the sweep directory `input_dir` and render all three figures into
    `output_dir`; return a `name -> path` map of what was written.

    `horizon` defaults to the midpoint step (an intermediate horizon) and
    `inverted_u_k` to the largest `K` in the sweep (where the connectivity
    trade-off is sharpest).
    """
    cells = load_sweep_results(input_dir)
    if not cells:
        raise ValueError(f"no sweep-cell CSVs (`*_K*.csv`) found under {str(input_dir)!r}")
    output_dir = Path(output_dir)

    steps = len(next(iter(cells.values())))
    horizon = steps // 2 if horizon is None else horizon
    inverted_u_k = max(k for _, k in cells) if inverted_u_k is None else inverted_u_k

    figures = {
        "fitness": plot_fitness_curves(cells, output_dir / "fitness_curves.png"),
        "diversity": plot_diversity_curves(cells, output_dir / "diversity_curves.png"),
    }
    connectivity = connectivity_series_from_sweep(cells, inverted_u_k)
    if connectivity:
        figures["inverted_u"] = plot_inverted_u(connectivity, horizon, output_dir / "inverted_u.png")
    return figures


def _save(figure: Figure, output_path: Path | str) -> Path:
    """Tidy layout, write `figure` to `output_path` (creating parent dirs),
    close it to free memory, and return the path written."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)
    return output_path
