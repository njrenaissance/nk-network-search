# Plan — Issue #13: `analysis.py` — fitness/diversity curves and inverted-U figure

**Status:** approved

**Status of this document.** Planning record for the change that lands
`src/analysis.py`. Per `.claude/standards/testing.md`, the test list below is
agreed first and `tests/test_analysis.py` is what "done" means; the
implementation is written to satisfy it. `spec/issues/13-tests.lock` pins the
test file's blob SHA so the Build step cannot weaken it.

Refs #13. Group 6 of 6 (`spec/build-order.md`), the last group — depends on #12
(`run.py`'s on-disk series format, merged). `analysis.py` only ever *consumes*
the `{topology}_K{k}.csv` files `run.write_sweep_results` writes; it runs no
simulation of its own.

## Acceptance criteria (from the issue)

- Given a fixture series (small, deterministic, the same shape #12 produces),
  each figure function runs without error and writes a file to the expected
  path.
- Figure generation is exercised by tests using a non-interactive Matplotlib
  backend (`Agg`) so CI has no display dependency.
- Tests at `tests/test_analysis.py`, marked `unit`.

## What the three figures are

Per `spec.md`'s "Inputs / Outputs" and `build-spec.md` §12:

- **Fitness curves** — mean (solid) and best (dashed) fitness vs step, one pair
  of lines per `(topology, K)` cell.
- **Diversity curves** — diversity vs step, one line per cell.
- **The inverted-U** — mean fitness at a fixed intermediate horizon vs
  connectivity level, swept sparse → dense; the interior peak is the result.

## Test list — `tests/test_analysis.py` (all `@pytest.mark.unit`, 10 cases)

| # | Test | Covers |
|---|---|---|
| 1 | `test_analysis_forces_non_interactive_agg_backend` | AC: figures render under `Agg`, no display needed |
| 2 | `test_curve_figure_writes_a_nonempty_file[fitness_curves]` | fitness-curve figure runs and writes a file |
| 3 | `test_curve_figure_writes_a_nonempty_file[diversity_curves]` | diversity-curve figure runs and writes a file |
| 4 | `test_inverted_u_figure_writes_a_nonempty_file` | inverted-U figure runs and writes a file |
| 5 | `test_figure_function_creates_missing_parent_directories` | a figure path under a not-yet-existing dir is created |
| 6 | `test_connectivity_series_from_sweep_orders_sparse_to_dense` | the inverted-U axis is ordered sparse → dense |
| 7 | `test_load_sweep_results_round_trips_run_output` | reads back exactly what `run.write_sweep_results` wrote |
| 8 | `test_generate_figures_writes_all_three_from_a_sweep_directory` | the orchestrator renders all three from a sweep dir |
| 9 | `test_load_sweep_results_rejects_a_malformed_cell_filename` | a non-`{topology}_K{k}` CSV fails loudly |
| 10 | `test_generate_figures_rejects_an_empty_directory` | an empty input dir fails loudly, not silently |

The fixture is a tiny hand-built sweep dict (three cells, three steps) of the
exact `dict[(topology, K), list[MetricsRow]]` shape `run.run_sweep` produces —
no `Model` is run, so the suite stays fast and fully deterministic. Its step-1
mean fitness is `ring 0.55 < random_regular 0.60 > complete 0.57`, a genuine
interior peak, so the inverted-U it feeds is non-monotone. Test 7 writes that
fixture through `run.write_sweep_results` and reads it back through
`analysis.load_sweep_results`, exercising the #12 → #13 on-disk contract
end-to-end.

---

## Below the fold: design detail

### Signatures (`src/analysis.py`)

```python
CONNECTIVITY_ORDER: tuple[str, ...] = ("ring", "ws", "random_regular", "complete")
DEFAULT_OUTPUT_DIR = Path("figures")

Cell = tuple[str, int]
Series = Sequence[MetricsRow]

def load_sweep_results(input_dir: Path | str) -> dict[Cell, list[MetricsRow]]: ...
def plot_fitness_curves(cells: Mapping[Cell, Series], output_path: Path | str) -> Path: ...
def plot_diversity_curves(cells: Mapping[Cell, Series], output_path: Path | str) -> Path: ...
def plot_inverted_u(
    connectivity_series: Sequence[tuple[str, Series]], horizon: int, output_path: Path | str
) -> Path: ...
def connectivity_series_from_sweep(
    cells: Mapping[Cell, Series], k: int, order: Sequence[str] = CONNECTIVITY_ORDER
) -> list[tuple[str, Series]]: ...
def generate_figures(
    input_dir: Path | str, output_dir: Path | str = DEFAULT_OUTPUT_DIR, *,
    inverted_u_k: int | None = None, horizon: int | None = None,
) -> dict[str, Path]: ...
```

Every plot function returns the `Path` it wrote, so a caller (and the tests)
can assert on the destination without recomputing it.

### The non-interactive backend

Figures are always written to disk (`spec.md`'s "Where we persist") and never
shown, so `analysis.py` calls `matplotlib.pyplot.switch_backend("Agg")` once at
import — after importing `pyplot`, so no import follows the statement and the
module stays free of the `matplotlib.use()`-before-import ordering wart (E402).
CI is thereby headless with no per-test setup; test 1 asserts the active
backend is `Agg` to lock this in.

### Consuming #12's on-disk format

`run.write_sweep_results` writes one `{topology}_K{k}.csv` per cell (header
`mean_fitness,best_fitness,diversity`, one row per step). `load_sweep_results`
is its inverse: it globs `*_K*.csv`, parses each name back into `(topology, k)`
— splitting on the **last** `_K` so multi-underscore topologies like
`random_regular` round-trip — and delegates the row parsing to
`run.load_results_csv` rather than re-implementing CSV reading (DRY; one owner
of the format). A CSV whose name doesn't fit the convention raises `ValueError`
(test 9) instead of being silently skipped or mis-keyed.

### The inverted-U axis

`plot_inverted_u` takes an already-ordered `(label, series)` sequence and plots
each series' `mean_fitness` at `horizon` against its rank, labelling the ticks —
so the caller owns what "connectivity level" means (topologies for a sweep,
degrees for a `random_regular` degree-sweep). `connectivity_series_from_sweep`
builds that sequence from a sweep dict at a fixed `K`, ordering topologies by
`CONNECTIVITY_ORDER` (sparse → dense) and skipping any the sweep didn't cover
(test 6). `generate_figures` defaults the horizon to the midpoint step (an
intermediate horizon) and the inverted-U's `K` to the largest in the sweep,
where the connectivity trade-off is sharpest.

### `matplotlib` dependency

Added to `[project].dependencies` in `pyproject.toml` (with the lockfile
updated), per the issue's Scope. It is a runtime dependency because
`analysis.py` is a shipped script that imports it — not a dev-only tool.

### Where figures go

`figures/` (the `DEFAULT_OUTPUT_DIR`) and `output/` (a conventional sweep-CSV
dir) are added to `.gitignore` — figures and run output are regenerated
artifacts, not source. `_save` creates the output directory if missing, so a
first run needs no manual `mkdir`.

### Out of scope

- A CLI `__main__` entrypoint — the issue asks for the figure *functions* (and
  the `generate_figures` orchestrator over them); wiring them to a command line
  is untested here and adds nothing the locked tests need.
- Asserting on figure *pixels/content* — the AC is "runs without error and
  writes a file"; the tests assert a non-empty file at the expected path, not
  the rendered image, keeping them fast and non-brittle.
- Any change to `run.py`'s format — `analysis.py` reads the convention #12
  settled; it does not alter it.
