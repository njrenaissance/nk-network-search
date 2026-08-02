# Plan — Issue #10: fitness/diversity metrics (`metrics.py`)

**Status:** proposed

**Status of this document.** Planning-only. No production code in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the implementation
approach that satisfies it. Comment `/approve` on this PR to begin the Build
stage (Build writes `src/nkmodel/metrics.py` to satisfy the acceptance criteria
below; `tests/test_metrics.py` is locked and Build may not weaken it).

Refs #10. Group 3 of 6 (`spec/build-order.md`), parallel with #9 (Agent). Depends
only on #7 (`NKLandscape`, merged) — `metrics.py` calls `landscape.fitness(string)`
and takes no dependency on `Agent`/`Model`.

## Acceptance criteria

- `mean_fitness`/`best_fitness` are in `[0, 1)` and match direct computation
  over the given strings.
- `diversity` correctly counts distinct strings for a known fixture set
  (all-identical → minimal diversity; all-distinct → maximal diversity).
- `convergence_time` returns the first step index where diversity reaches
  (≈) 0 for a synthetic series, or the documented sentinel `None` if it never
  converges.

## Test list — `tests/test_metrics.py` (all `@pytest.mark.unit`, 12 cases)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_fitness_metric_matches_direct_computation_and_is_in_unit_interval` (× `mean_fitness`/`best_fitness`) | `mean_fitness`/`best_fitness` match direct computation and lie in `[0, 1)` |
| 2 | `test_diversity_counts_distinct_strings` (× all-identical / all-distinct / partial-duplicates / single-agent) | `diversity` counts distinct strings correctly; all-identical is minimal, all-distinct is maximal |
| 3 | `test_convergence_time_returns_first_step_reaching_zero_or_sentinel` (× converges-mid-series / already-converged / within-tolerance / never-converges) | `convergence_time` returns the first (≈)0 step, or `None` if it never converges |
| 4 | `test_metrics_series_record_appends_one_row_per_call` | `MetricsSeries.record` appends one row per call, matching the standalone metric functions |
| 5 | `test_metrics_series_convergence_time_delegates_to_recorded_diversities` | `MetricsSeries.convergence_time()` reads its own recorded series |

All 12 cases currently fail against the stub in this PR with a genuine
`NotImplementedError` (functionality not yet written) — confirmed failing for
the right reason, and confirmed passing 12/12 against a throwaway reference
implementation used only to validate the suite before committing it (that
reference code is not part of this PR).

---

## Below the fold: design detail

### Signatures (`src/nkmodel/metrics.py`)

```python
class _Landscape(Protocol):
    def fitness(self, string: Sequence[int]) -> float: ...


def mean_fitness(strings: Sequence[Sequence[int]], landscape: _Landscape) -> float: ...
def best_fitness(strings: Sequence[Sequence[int]], landscape: _Landscape) -> float: ...
def diversity(strings: Sequence[Sequence[int]]) -> float: ...
def convergence_time(diversities: Sequence[float], tolerance: float = 1e-9) -> int | None: ...


class MetricsRow(NamedTuple):
    mean_fitness: float
    best_fitness: float
    diversity: float


class MetricsSeries:
    def __init__(self) -> None: ...
    def record(self, strings: Sequence[Sequence[int]], landscape: _Landscape) -> MetricsRow: ...
    def convergence_time(self, tolerance: float = 1e-9) -> int | None: ...
```

`strings` is a plain `Sequence[Sequence[int]]` — one bit-string per agent at a
step, no `Agent` object involved (this issue's whole point, so it builds in
parallel with #9). `landscape` is typed as a small structural `Protocol`
(`_Landscape`, one method: `fitness`) rather than importing `NKLandscape`
directly — this module only ever *calls* `.fitness(string)`, so the narrower
structural type is what Clean Code's "depend on the smallest interface you
use" calls for, and it keeps this file honest about not needing anything else
`NKLandscape` exposes (`partners`, `contribution`, ...). Tests still construct
a real `NKLandscape` (issue #7) to exercise it end-to-end.

### `mean_fitness` / `best_fitness`

Direct reductions over `landscape.fitness(s) for s in strings` — mean and max,
respectively. Both inherit `fitness`'s `[0, 1)` range from `NKLandscape`
(issue #7) directly; no separate clamping needed.

### `diversity` — pinned design decision

The issue text allows either "count of distinct strings" or "mean pairwise
Hamming distance." This plan pins **normalized distinct-string count**:

```python
def diversity(strings: Sequence[Sequence[int]]) -> float:
    n = len(strings)
    if n <= 1:
        return 0.0
    distinct = len({tuple(s) for s in strings})
    return (distinct - 1) / (n - 1)
```

Rationale — this is the one formulation that satisfies *both* halves of
`spec.md`'s contract at once:

- The acceptance criteria's "all-identical → minimal, all-distinct → maximal"
  fixture, exactly: `0.0` when every string collapses to one distinct value,
  `1.0` when every string is pairwise distinct.
- `spec.md`'s `convergence_time`: "first step at which diversity reaches (≈)
  0" — a plain distinct-string *count* bottoms out at `1` (one agent, or all
  agents sharing one string), never `0`, so "reaches 0" would be unsatisfiable.
  Normalizing so full convergence (one shared string) *is* `0.0` makes that
  sentence literally true.

A single agent (or empty collection edge case guarded the same way) is
trivially non-diverse: `0.0`.

### `convergence_time` — standalone helper + series delegate

Takes a plain `Sequence[float]` of already-computed diversity values (a
"synthetic series," per the acceptance criteria — tests build one directly,
with no landscape needed) and returns the first index `<= tolerance`, else
`None`:

```python
def convergence_time(diversities: Sequence[float], tolerance: float = 1e-9) -> int | None:
    for step, d in enumerate(diversities):
        if d <= tolerance:
            return step
    return None
```

`tolerance` (default `1e-9`) is the "(≈)" in "reaches (≈) 0" — `diversity`'s
normalized formula lands on exact rationals for these tests, but a tolerance
keeps the check robust once Build wires it into a real accumulated series.
`None` is the documented sentinel for "never converges" (no magic `-1`).

`MetricsSeries.convergence_time()` is a thin delegate over its own
`[row.diversity for row in self.rows]`, so a caller can ask an in-progress or
completed series directly without re-deriving the list itself.

### `MetricsRow` / `MetricsSeries`

`MetricsRow` is a `NamedTuple` (three named floats) — an immutable, structural
record with no behavior, appropriate for "one row per step." `MetricsSeries`
owns `self.rows: list[MetricsRow]` and `record(strings, landscape)`:

```python
def record(self, strings, landscape) -> MetricsRow:
    row = MetricsRow(
        mean_fitness=mean_fitness(strings, landscape),
        best_fitness=best_fitness(strings, landscape),
        diversity=diversity(strings),
    )
    self.rows.append(row)
    return row
```

Matches `build-spec.md` §6's `self.metrics.record(self)` call site in
`Model.step` (issue #11, later) — signature here is `record(strings,
landscape)` instead of `record(model)` since this module takes no `Model`
dependency (issue #10's scope), so `Model.step` will pass
`[a.string for a in self.agents]` and `self.landscape` through at that call
site.

### Where we persist

In-memory only, per `spec.md`'s "Where we persist" — a `MetricsSeries` lives
for the lifetime of one run; the runner script (`run.py`, later) is what
writes it to disk.

### Out of scope for this issue

- `Agent`, `Model`, the turn loop (#9, #11) — this issue is `mean_fitness` /
  `best_fitness` / `diversity` / `MetricsSeries` / `convergence_time` alone,
  operating on plain string collections.
- Mean pairwise Hamming distance as a *separate* metric — considered and
  folded into the normalized distinct-count `diversity` above instead of
  shipping two competing diversity numbers (see "pinned design decision").
- Plotting/rendering the series (`analysis.py`, issue #13).
