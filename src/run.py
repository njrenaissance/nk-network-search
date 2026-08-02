"""Runner — single run, replication averaging, topology×K sweep, and disk
persistence, composed from `nkmodel/`.

Thin script per `spec/build-order.md`'s resolved ambiguity: the package lives
at `src/nkmodel/`, and this module sits beside it as the driver `build-spec.md`
§3 sketches, just rooted under `src/`. No production simulation logic lives
here — `Model` (`nkmodel.model`) owns the turn loop, `metrics.py` owns the
per-step numbers; this module composes them into the driver functions and
CSV persistence `spec/issues/12-plan.md` describes.

Signatures only — see `spec/issues/12-plan.md`. `tests/test_results.py` is
locked (`spec/issues/12-tests.lock`); implementing this module to satisfy it
is Build's job once the plan is approved.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from nkmodel.config import NKConfig
from nkmodel.metrics import MetricsRow


def run_single(config: NKConfig, seed: int) -> list[MetricsRow]:
    """Build a `Model` from `(config, seed)`, run `config.steps` turns, and
    return its recorded per-step rows."""
    raise NotImplementedError


def run_replications(config: NKConfig, seed: int) -> list[MetricsRow]:
    """Average `config.replications` independent `run_single` runs (seeds
    `seed, seed+1, ..., seed+config.replications-1`) into one per-step row of
    averaged `mean_fitness`/`best_fitness`/`diversity`."""
    raise NotImplementedError


def run_sweep(
    base_config: NKConfig,
    topologies: Sequence[str],
    k_values: Sequence[int],
    seed: int,
) -> dict[tuple[str, int], list[MetricsRow]]:
    """Run `run_replications` for every `(topology, K)` cell in the cartesian
    product of `topologies` × `k_values`, each cell built from `base_config`
    with that topology/K substituted."""
    raise NotImplementedError


def save_results_csv(rows: Sequence[MetricsRow], path: Path | str) -> None:
    """Write `rows` to `path` as CSV: header `mean_fitness,best_fitness,diversity`,
    one data row per step."""
    raise NotImplementedError


def load_results_csv(path: Path | str) -> list[MetricsRow]:
    """Read a CSV file written by `save_results_csv` back into `MetricsRow`s."""
    raise NotImplementedError


def write_sweep_results(
    results: dict[tuple[str, int], Sequence[MetricsRow]], output_dir: Path | str
) -> dict[tuple[str, int], Path]:
    """Write each `run_sweep` cell to `output_dir/{topology}_K{k}.csv` via
    `save_results_csv`; return the path each cell was written to."""
    raise NotImplementedError
