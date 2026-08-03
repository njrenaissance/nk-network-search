# Plan — Issue #13: `analysis.py` — fitness/diversity curves and inverted-U figure

**Status:** approved

Refs #13. Group 6 of 6 (`spec/build-order.md`), depends on #12 (`run.py`'s
on-disk `MetricsRow` series format, merged).

## Acceptance criteria

- Given a fixture series (small, deterministic, same shape #12 produces),
  each figure function runs without error and writes a file to the expected
  path.
- Figure generation is exercised by tests using a non-interactive Matplotlib
  backend (`Agg`) so CI has no display dependency.
- Tests at `tests/test_analysis.py`, marked `unit`.

## Test list — `tests/test_analysis.py` (all `@pytest.mark.unit`, 3 cases)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_plot_fitness_curve_writes_file_to_expected_path` | fitness curve (mean/best fitness vs step) runs without error, writes a file |
| 2 | `test_plot_diversity_curve_writes_file_to_expected_path` | diversity curve vs step runs without error, writes a file |
| 3 | `test_plot_inverted_u_writes_file_to_expected_path` | inverted-U figure (mean fitness at a fixed horizon vs connectivity, sparse→dense) runs without error, writes a file |

(3 figure functions named in the issue's Scope ⇒ 3 cases, one per function.
Each fixture series is a small hand-built `list[MetricsRow]` — the same shape
`run.py` (#12) produces/persists — not a real simulation run, since only the
plotting contract is under test here. The "Agg backend" criterion isn't a
separate assertion: `tests/test_analysis.py` calls `matplotlib.use("Agg")`
before importing `analysis`/`pyplot`, so all 3 cases above already exercise
figure generation headlessly — that's what the test-file docstring records.)

All 3 cases currently fail against the committed stub with a genuine
`NotImplementedError` (functionality not yet written) — confirmed failing for
the right reason, not an import/collection error.
`spec/issues/13-tests.lock` pins the test file's blob SHA for Build's pre-push
test-integrity guard.

---

## Below the fold: design detail

### Signatures (`src/analysis.py`)

Per `spec/build-order.md`'s resolved ambiguity, `analysis.py` sits beside
`nkmodel/` and `run.py`, rooted under `src/` — so `src/analysis.py`, not
`src/nkmodel/analysis.py`.

```python
def plot_fitness_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path: ...
def plot_diversity_curve(rows: Sequence[MetricsRow], path: Path | str) -> Path: ...
def plot_inverted_u(
    cells: Mapping[float, Sequence[MetricsRow]], horizon: int, path: Path | str
) -> Path: ...
```

(Illustrative — Build may implement however it likes as long as the locked
tests pass.)

### Why one cell per call, not a multi-cell overlay

The issue's Scope says "per topology/K cell" for the fitness/diversity
curves — read as: one figure per cell, not one figure overlaying every cell.
`plot_fitness_curve`/`plot_diversity_curve` each take a single cell's
`list[MetricsRow]` (the same shape `run.py.load_results_csv` returns for one
`{topology}_K{k}.csv` file) and write one figure. A caller wanting a figure
per sweep cell loops over `run_sweep`'s (or `load_results_csv`'s) results and
calls the function once per cell — no new multi-series plotting contract to
design or lock here.

### `plot_inverted_u` — connectivity is a third axis, not `(topology, K)`

Issue #12's own inverted-U test sweeps `random_regular`'s `degree` (not `K`)
at fixed `topology`/`K` — connectivity level there is degree, sparse→dense.
`plot_inverted_u` mirrors that: `cells` maps *connectivity level* (whatever
numeric knob the caller swept — typically `degree`) to that level's series,
mirroring `run_sweep`'s `dict[key, list[MetricsRow]]` shape but keyed by a
single level instead of a `(topology, K)` tuple, since the inverted-U isn't a
`run_sweep` cell. The function reads `cells[level][horizon].mean_fitness` for
each level, sorts by level ascending (sparse→dense) before plotting — so
callers may pass `cells` in any order — and writes one figure.

### Matplotlib usage

`src/analysis.py` uses `matplotlib.pyplot` to draw each figure and
`Figure.savefig(path)` (or `plt.savefig`) to write it, then returns the
`Path`. Whether `analysis.py` itself also calls `matplotlib.use("Agg")` at
import time (defensive, in case a caller runs it somewhere with a display) is
Build's implementation choice — not locked by a test, since
`tests/test_analysis.py` already forces `Agg` before importing `analysis`,
which is what makes cases 1–3 deterministic in CI regardless.

### Dependency: `matplotlib`

Added to `pyproject.toml`'s `[project].dependencies` (`matplotlib>=3.11.1`,
the version resolved into `uv.lock` alongside this plan) — no documented
alternative needed; `matplotlib` is the standard choice and the issue names
it directly.

### Where we persist

Per `spec.md`'s "the runner scripts write the metric series and figures to
disk. No database." Figures are written wherever the caller's `path`
argument points; a gitignored `figures/`/`output/` directory (added to
`.gitignore` in this PR) is the suggested convention for a real analysis run,
matching `run.py`'s own on-disk (not committed) sweep output.

### Out of scope for this issue

- A CLI entrypoint / `__main__` block wiring `run.py`'s persisted sweep
  output to these three functions end-to-end — the issue's Scope asks for
  the figure-producing *functions*; a script invocation can be added later
  without touching the locked tests.
- Any real production logic beyond the signatures-only stub — Build's job
  once this plan is approved.
