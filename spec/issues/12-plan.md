# Plan — Issue #12: `run.py` — single run + topology×K sweep, headline results

**Status:** proposed

**Status of this document.** Planning-only. No production logic in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the implementation
approach that satisfies it. Comment `/approve` on this PR to begin the Build
stage (Build writes `src/run.py` to satisfy the acceptance criteria below;
`tests/test_results.py` is locked and Build may not weaken it).

Refs #12. Group 5 of 6 (`spec/build-order.md`), depends on #11 (`Model`, merged).
`run.py` composes `Model` + `nkmodel.metrics` into a single-run driver, a
replication-averaging driver, a topology×K sweep, and CSV persistence for
`analysis.py` (issue #13, later) to consume.

## Acceptance criteria

- **K=0 invariance.** With `K=0`, mean fitness converges to the same optimum
  for `ring` and `complete` (topology is irrelevant on a smooth landscape).
- **Crossover at high K.** `complete` has strictly higher mean fitness than
  `ring` at an early step, but strictly lower mean fitness at the final step
  (both averaged over replications).
- **Diversity collapse.** `complete` reaches (≈)0 diversity (convergence) in
  strictly fewer steps than `ring`.
- **Inverted-U.** At an intermediate horizon, sweeping connectivity from
  sparse to dense yields non-monotone mean fitness — an interior connectivity
  level outperforms both the sparsest and the densest.
- **Persistence.** A sweep's per-cell series round-trip through disk
  byte-for-byte (write, then read back, reproduces the same rows) so
  `analysis.py` can consume them without rerunning the simulation.

## Test list — `tests/test_results.py` (all `@pytest.mark.unit`, 8 cases)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_run_single_returns_one_row_per_step` | foundational: `run_single` — one row per configured step |
| 2 | `test_run_replications_averages_across_independent_runs` | foundational: `run_replications` — averages `config.replications` independent seeds |
| 3 | `test_run_sweep_returns_one_cell_per_topology_times_k_combination` | foundational: `run_sweep` — one cell per `topology × K` pair |
| 4 | `test_k0_invariance_ring_and_complete_converge_to_same_optimum` | K=0 invariance |
| 5 | `test_high_k_crossover_complete_wins_early_but_loses_by_the_end` | crossover at high K |
| 6 | `test_high_k_diversity_collapse_complete_converges_faster_than_ring` | diversity collapse |
| 7 | `test_inverted_u_interior_connectivity_outperforms_sparse_and_dense` | inverted-U |
| 8 | `test_write_sweep_results_round_trips_through_disk` | persistence |

(5 acceptance criteria ⇒ 8 cases: the three foundational driver-function
contracts each earn a dedicated case before the four headline/persistence
criteria are layered on top of them — tests 5 and 6 reuse the same two
`run_replications` cells via a plain helper, not a fixture, since a fixture
that raises `NotImplementedError` during setup shows up as a pytest *error*,
not a *failure*.)

All 8 cases currently fail against the committed stub with a genuine
`NotImplementedError` (functionality not yet written) — confirmed failing for
the right reason, not an import/collection error — and were validated 8/8
green against a throwaway reference implementation used only to validate the
suite before committing it (that reference code is not part of this PR).
`spec/issues/12-tests.lock` pins the test file's blob SHA for Build's pre-push
test-integrity guard.

---

## Below the fold: design detail

### Signatures (`src/run.py`)

Per `spec/build-order.md`'s resolved ambiguity, this project uses a `src/`
layout: the package lives at `src/nkmodel/`, and `run.py` sits beside it as a
thin script (`build-spec.md` §3's sketch, rooted under `src/`) — so
`src/run.py`, not `src/nkmodel/run.py` and not a repo-root script.

```python
def run_single(config: NKConfig, seed: int) -> list[MetricsRow]: ...
def run_replications(config: NKConfig, seed: int) -> list[MetricsRow]: ...
def run_sweep(
    base_config: NKConfig, topologies: Sequence[str], k_values: Sequence[int], seed: int
) -> dict[tuple[str, int], list[MetricsRow]]: ...
def save_results_csv(rows: Sequence[MetricsRow], path: Path | str) -> None: ...
def load_results_csv(path: Path | str) -> list[MetricsRow]: ...
def write_sweep_results(
    results: dict[tuple[str, int], Sequence[MetricsRow]], output_dir: Path | str
) -> dict[tuple[str, int], Path]: ...
```

(Illustrative below — matches the reference implementation used to validate
the test suite. Build may implement this however it likes as long as the
locked tests pass.)

### `run_single` / `run_replications` — the two drivers the issue's Scope names

```python
def run_single(config: NKConfig, seed: int) -> list[MetricsRow]:
    return Model(config, seed).run().rows


def run_replications(config: NKConfig, seed: int) -> list[MetricsRow]:
    runs = [run_single(config, seed + i) for i in range(config.replications)]
    steps = len(runs[0])
    return [
        MetricsRow(
            mean_fitness=mean(r[t].mean_fitness for r in runs),
            best_fitness=mean(r[t].best_fitness for r in runs),
            diversity=mean(r[t].diversity for r in runs),
        )
        for t in range(steps)
    ]
```

Every public function returns a plain `list[MetricsRow]` (not a `MetricsSeries`)
— `run.py` only ever *consumes* `Model`'s per-run series to average or persist
it, so the narrower, already-averaged shape is what the rest of this module
(and `analysis.py`, later) actually needs.

**Varying "landscape draw, initial strings, and network draw across
replications" (the issue's Scope wording)** falls out for free from `Model`'s
existing `(config, seed)` reproducibility contract (issue #11): each
replication is an independent `Model` run at `seed + i`, and because `Model`
derives its landscape/network/initial-string/explore RNG streams from that one
seed, incrementing it varies all three simultaneously without `run.py` needing
any seeding logic of its own.

### `run_sweep` — topology × K grid

```python
def run_sweep(base_config, topologies, k_values, seed):
    return {
        (topology, k): run_replications(base_config.model_copy(update={"topology": topology, "K": k}), seed)
        for topology, k in itertools.product(topologies, k_values)
    }
```

`NKConfig.model_copy(update=...)` (a `pydantic` `BaseModel` method) builds each
cell's config from `base_config` with only `topology`/`K` substituted — the
same "sweeps build explicit per-cell configs" approach `build-spec.md` §10
already establishes for `NKConfig(**{**DEFAULTS, ...})`, just starting from a
caller-supplied base instead of `DEFAULTS` directly, since a sweep's other
knobs (`N`, `A`, `steps`, `replications`, ...) come from the caller, not from
the global defaults.

### Persistence — CSV, one file per cell

**Format decision: CSV**, via the stdlib `csv` module — no new dependency
(`pyproject.toml` has no `pandas`), and the data is exactly the tabular shape
CSV is for: one row per step, three float columns (`mean_fitness`,
`best_fitness`, `diversity`). JSON was considered and rejected — it would add
a nesting level (list-of-objects) for what is, structurally, a flat table.

```python
def save_results_csv(rows, path):
    with Path(path).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["mean_fitness", "best_fitness", "diversity"])
        writer.writerows(rows)


def load_results_csv(path):
    with Path(path).open(newline="") as f:
        return [MetricsRow(*(float(v) for v in row.values())) for row in csv.DictReader(f)]


def write_sweep_results(results, output_dir):
    return {
        cell: save_results_csv(rows, Path(output_dir) / f"{cell[0]}_K{cell[1]}.csv") or Path(output_dir) / f"{cell[0]}_K{cell[1]}.csv"
        for cell, rows in results.items()
    }
```

(The illustrative `write_sweep_results` one-liner above is deliberately dense
for exposition; Build is free to write it as a plain loop — see the reference
implementation's straightforward loop form, which is what was actually
validated.) Filename convention: `{topology}_K{k}.csv` — a later issue
(`analysis.py`, #13) reads this same convention back; changing it is that
issue's call to make if needed, not a constraint this plan locks in beyond the
round-trip contract test 8 asserts.

### Test doubles: none needed

Unlike `test_model.py`/`test_agent.py`, no fixed-fitness fake landscape is
needed here — every case either asserts on the aggregate/statistical shape of
real `NKLandscape` runs (headline criteria) or exercises `run.py`'s own logic
directly with synthetic `MetricsRow`s that need no landscape at all
(persistence, test 8's `results` dict is built by hand).

### Picking parameters that make stochastic criteria deterministic

Per `spec.md`'s "Stochastic criteria run with a fixed `seed` and enough
`replications` to be deterministic under test," every headline case pins a
specific `seed=0` and a small-but-sufficient `N`/`A`/`replications`/`steps`
found by direct experimentation against the real `NKLandscape`/`Model`
(not tuned against a mocked shortcut):

- **K=0 invariance** (test 4): `N=8, K=0, A=10, steps=15` — a single run per
  topology (no averaging needed; K=0 hill-climbing to the one global optimum
  is already exact). Both `ring` and `complete` reach the identical
  `mean_fitness` (`0.7091085483091748`) by step 15.
- **Crossover + diversity collapse** (tests 5, 6): `N=10, K=6, A=16,
  replications=20, steps=20`. At step 2, `complete` leads `ring` by ~0.05
  mean fitness; by the final step (19), `ring` leads `complete` by ~0.015 —
  and `complete`'s aggregated diversity hits 0 at step 5 versus `ring`'s
  step 15.
- **Inverted-U** (test 7): `N=10, K=6, A=16, replications=40, steps=10`,
  `random_regular` topology at `degree ∈ {2, 6, 15}` (sparse/interior/dense
  connectivity, holding `topology`/`K` fixed — a third sweep axis
  `run_sweep`'s topology×K grid doesn't cover, so this case calls
  `run_replications` directly per degree rather than through `run_sweep`). At
  step 6, `degree=6`'s mean fitness (~0.706) exceeds both `degree=2` (~0.692)
  and `degree=15` (~0.703) — confirmed stable across steps 4–9 in
  experimentation, not a single lucky step.

These are the exact figures the reference implementation produced; Build's
real implementation will reproduce them because it drives the same `Model`
these numbers were measured against — the numbers themselves are not asserted
directly (the tests assert the qualitative `>`/`<` relationships), so
Build's implementation is not pinned to matching them exactly.

### Where we persist

**File** — per `spec.md`'s "Where we persist," `run.py` is the runner script
that writes the metric series to disk (CSV, one file per sweep cell); no
database. In-process, results are plain `list[MetricsRow]`, matching `Model`
(#11) and `metrics.py` (#10)'s in-memory-only scope.

### Out of scope for this issue

- Rendering the persisted series into figures (`analysis.py`) — issue #13,
  which consumes the `{topology}_K{k}.csv` convention this issue establishes.
- A CLI entrypoint / `__main__` block for running sweeps from the command
  line — the issue's Scope asks for the driver *functions*; wiring them to a
  script invocation is not tested here and can be added without touching the
  locked tests.
- Any real production logic beyond the signatures-only stub — Build's job
  once this plan is approved.
