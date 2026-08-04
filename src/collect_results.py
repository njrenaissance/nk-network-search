"""Collect results from a default-configuration simulation batch.

Runs the NK networked-search model `config.replications` times (independent
seeds `config.seed, config.seed+1, ...`) under the current `NKConfig` and
collects the replication-averaged per-step metric series via
`run.run_replications`, writing it to `results/` alongside a human-readable
`SUMMARY.md`.

Configure via `NK_*` env vars / `.env` (see `nkmodel.config`); e.g. run ten
simulations of the defaults with::

    NK_REPLICATIONS=10 uv run python src/collect_results.py

No new simulation logic lives here: `run.run_replications` owns the batch, this
module only drives it with the configured settings and renders the collected
series to disk.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from nkmodel.config import NKConfig, get_config
from nkmodel.metrics import MetricsRow, convergence_time
from run import run_replications, save_results_csv

RESULTS_DIR = Path("results")

# Steps to tabulate in the summary trajectory (clamped to the run length).
_SUMMARY_STEPS = (0, 1, 5, 10, 25, 50, 100, 200)


def _config_table(config: NKConfig) -> str:
    """Render the settings that shaped this batch as a Markdown table."""
    rows = "\n".join(f"| `{name}` | `{value}` |" for name, value in config.model_dump().items())
    return f"| Setting | Value |\n| --- | --- |\n{rows}"


def _trajectory_table(averaged: Sequence[MetricsRow]) -> str:
    """Render mean/best fitness and diversity at sampled steps as a table."""
    last_step = len(averaged) - 1
    sampled = sorted({step for step in (*_SUMMARY_STEPS, last_step) if step <= last_step})
    header = "| Step | Mean fitness | Best fitness | Diversity |\n| ---: | ---: | ---: | ---: |"
    body = "\n".join(
        f"| {step} | {averaged[step].mean_fitness:.6f} | "
        f"{averaged[step].best_fitness:.6f} | {averaged[step].diversity:.6f} |"
        for step in sampled
    )
    return f"{header}\n{body}"


def _headline_metrics(averaged: Sequence[MetricsRow]) -> str:
    """Render the batch's headline numbers as a Markdown bullet list."""
    final = averaged[-1]
    peak_best_step = max(range(len(averaged)), key=lambda step: averaged[step].best_fitness)
    converged_at = convergence_time([row.diversity for row in averaged])
    converged = f"step {converged_at}" if converged_at is not None else "did not fully converge"
    return (
        f"- **Final mean fitness:** {final.mean_fitness:.6f}\n"
        f"- **Final best fitness:** {final.best_fitness:.6f}\n"
        f"- **Peak best fitness:** {averaged[peak_best_step].best_fitness:.6f} (step {peak_best_step})\n"
        f"- **Final diversity:** {final.diversity:.6f}\n"
        f"- **Diversity collapse (convergence):** {converged}"
    )


def build_summary(config: NKConfig, averaged: Sequence[MetricsRow], csv_path: Path) -> str:
    """Render a Markdown summary of one replication-averaged batch."""
    return (
        f"# Simulation results — {config.replications} replications of the defaults\n\n"
        f"Replication-averaged over {config.replications} independent runs "
        f"(seeds {config.seed}..{config.seed + config.replications - 1}), "
        f"{config.steps} synchronous steps each. Full per-step series: "
        f"[`{csv_path.name}`]({csv_path.name}).\n\n"
        f"## Configuration\n\n{_config_table(config)}\n\n"
        f"## Headline metrics\n\n{_headline_metrics(averaged)}\n\n"
        f"## Trajectory\n\n{_trajectory_table(averaged)}\n"
    )


def collect(config: NKConfig, results_dir: Path = RESULTS_DIR) -> Path:
    """Run the replication batch for `config` and write results to disk.

    Returns the path of the averaged per-step CSV written.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    averaged = run_replications(config, config.seed)
    csv_path = results_dir / f"averaged_replications{config.replications}.csv"
    save_results_csv(averaged, csv_path)
    (results_dir / "SUMMARY.md").write_text(build_summary(config, averaged, csv_path))
    return csv_path


def main() -> None:
    """Collect results for the configured batch and report where they landed."""
    config = get_config()
    csv_path = collect(config)
    print(
        f"Collected {config.replications} replications of the defaults "
        f"({config.steps} steps each) into {csv_path.parent}/:\n"
        f"  - {csv_path}\n"
        f"  - {csv_path.parent / 'SUMMARY.md'}"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
