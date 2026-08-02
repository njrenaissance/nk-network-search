"""Runner — single run, replication averaging, topology×K sweep, and disk
persistence, composed from `nkmodel/`.

Thin script per `spec/build-order.md`'s resolved ambiguity: the package lives
at `src/nkmodel/`, and this module sits beside it as the driver `build-spec.md`
§3 sketches, just rooted under `src/`. No production simulation logic lives
here — `Model` (`nkmodel.model`) owns the turn loop, `metrics.py` owns the
per-step numbers; this module composes them into the driver functions and
CSV persistence `spec/issues/12-plan.md` describes.

See `spec/issues/12-plan.md` for the design and parameter choices;
`tests/test_results.py` is locked (`spec/issues/12-tests.lock`).
"""

from __future__ import annotations

import csv
import itertools
from collections.abc import Sequence
from pathlib import Path
from statistics import mean

from nkmodel.config import NKConfig
from nkmodel.metrics import MetricsRow
from nkmodel.model import Model


def run_single(config: NKConfig, seed: int) -> list[MetricsRow]:
    """Build a `Model` from `(config, seed)`, run `config.steps` turns, and
    return its recorded per-step rows."""
    return Model(config, seed).run().rows


def run_replications(config: NKConfig, seed: int) -> list[MetricsRow]:
    """Average `config.replications` independent `run_single` runs (seeds
    `seed, seed+1, ..., seed+config.replications-1`) into one per-step row of
    averaged `mean_fitness`/`best_fitness`/`diversity`."""
    runs = [run_single(config, seed + i) for i in range(config.replications)]
    steps = len(runs[0])
    return [
        MetricsRow(
            mean_fitness=mean(run[step].mean_fitness for run in runs),
            best_fitness=mean(run[step].best_fitness for run in runs),
            diversity=mean(run[step].diversity for run in runs),
        )
        for step in range(steps)
    ]


def run_sweep(
    base_config: NKConfig,
    topologies: Sequence[str],
    k_values: Sequence[int],
    seed: int,
) -> dict[tuple[str, int], list[MetricsRow]]:
    """Run `run_replications` for every `(topology, K)` cell in the cartesian
    product of `topologies` × `k_values`, each cell built from `base_config`
    with that topology/K substituted."""
    return {
        (topology, k): run_replications(base_config.model_copy(update={"topology": topology, "K": k}), seed)
        for topology, k in itertools.product(topologies, k_values)
    }


def save_results_csv(rows: Sequence[MetricsRow], path: Path | str) -> None:
    """Write `rows` to `path` as CSV: header `mean_fitness,best_fitness,diversity`,
    one data row per step."""
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["mean_fitness", "best_fitness", "diversity"])
        writer.writerows(rows)


def load_results_csv(path: Path | str) -> list[MetricsRow]:
    """Read a CSV file written by `save_results_csv` back into `MetricsRow`s."""
    with Path(path).open(newline="") as f:
        return [MetricsRow(*(float(value) for value in row.values())) for row in csv.DictReader(f)]


def write_sweep_results(
    results: dict[tuple[str, int], Sequence[MetricsRow]], output_dir: Path | str
) -> dict[tuple[str, int], Path]:
    """Write each `run_sweep` cell to `output_dir/{topology}_K{k}.csv` via
    `save_results_csv`; return the path each cell was written to."""
    output_dir = Path(output_dir)
    written_paths: dict[tuple[str, int], Path] = {}
    for (topology, k), rows in results.items():
        path = output_dir / f"{topology}_K{k}.csv"
        save_results_csv(rows, path)
        written_paths[(topology, k)] = path
    return written_paths
