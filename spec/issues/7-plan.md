# Plan — Issue #7: NKLandscape fitness model (`landscape.py`)

**Status:** proposed

**Status of this document.** Planning-only. No production code in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the implementation
approach that satisfies it. Comment `/approve` on this PR to begin the Build
stage (Build writes `src/nkmodel/landscape.py` to satisfy the acceptance criteria
below; `tests/test_landscape.py` is locked and Build may not weaken it).

Refs #7. Group 2 of 6 (`spec/build-order.md`), parallel with #8. Depends only on
#6 (merged) — for shared field-type conventions only; `NKLandscape` takes plain
constructor args, no import from `nkmodel.config`.

## Acceptance criteria

- `fitness(string)` returns the mean of the `N` per-locus contributions, in `[0, 1)`.
- `contribution(locus, string)` depends only on locus's own bit + its `K`
  partners' bits: two strings agreeing on those `K+1` positions give an
  identical contribution; flipping a bit outside them leaves it unchanged.
- Two landscapes built with the same seed return identical `fitness` for the
  same string; lazy-cache and pre-filled constructions agree value-for-value.
- `K=0` is single-peaked: exactly one global optimum; greedy one-bit
  hill-climbing from any starting string reaches it.

## Test list — `tests/test_landscape.py` (all `@pytest.mark.unit`)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_fitness_equals_mean_of_locus_contributions` | `fitness` = mean of per-locus `contribution` |
| 2 | `test_fitness_in_unit_interval` (3 strings) | `fitness` in `[0, 1)` |
| 3 | `test_contribution_depends_only_on_own_and_partner_bits` (× `adjacent`/`random`) | two strings agreeing on the `K+1` window ⇒ identical contribution |
| 4 | `test_flipping_bit_outside_window_leaves_contribution_unchanged` (× `adjacent`/`random`) | flipping a bit outside the window leaves contribution unchanged |
| 5 | `test_same_seed_yields_identical_fitness` | same seed ⇒ identical `fitness` |
| 6 | `test_lazy_and_prefilled_constructions_agree` | lazy-cache vs. pre-filled agree value-for-value |
| 7 | `test_k_zero_has_exactly_one_global_optimum` | `K=0` ⇒ exactly one global optimum |
| 8 | `test_k_zero_greedy_hill_climbing_reaches_global_optimum` (16 starting strings, `N=4`) | greedy hill-climb from any start reaches that optimum |

All 27 parametrized cases currently fail against the stub in this PR with a
genuine `NotImplementedError`/`AttributeError` (functionality not yet written) —
confirmed passing 27/27 against a throwaway reference implementation used only
to validate the suite before committing it (that reference code is not part of
this PR).

---

## Below the fold: design detail

### Signature

```python
class NKLandscape:
    def __init__(
        self,
        n: int,
        k: int,
        scheme: Literal["adjacent", "random"] = "adjacent",
        rng: random.Random | None = None,
    ) -> None: ...

    def contribution(self, locus: int, string: Sequence[int]) -> float: ...
    def fitness(self, string: Sequence[int]) -> float: ...
```

(Constructor parameters are lowercase `n`/`k` to satisfy ruff `N803`; the public
attributes are `self.N`/`self.K`, matching `NKConfig`'s field names and the
paper's vocabulary.) `string` is a `Sequence[int]` of `0`/`1` bits, length `N`
(binary `B=2`, this project's built target — `B` is not otherwise consumed
here). `rng` is a required-in-practice `random.Random` — no hidden global
randomness; a caller builds `random.Random(seed)` and passes it in, so a
landscape is fully reproducible from that seed alone.

### Partners (`scheme`)

`self.partners: list[list[int]]`, length `N`, each entry the `K` partner loci
for that locus, built once at construction:

- `"adjacent"` — `partners[i] = [(i + d) % N for d in range(1, K + 1)]` (cyclic
  successors, no RNG consumed).
- `"random"` — for each locus `i` in order `0..N-1`, `K` distinct loci sampled
  from `range(N) - {i}` via `rng.sample(...)`, stored once and never redrawn.

`partners` is a public attribute (mirrors `build-spec.md` §4's own sketch) so
tests can build "agrees on the K+1 window" strings without hardcoding an
internal bit-key encoding — the encoding itself is Build's choice.

### Per-locus contribution table: lazy vs. pre-filled, made to agree by construction

Each locus's table is `2^(K+1)` entries, keyed by `(own bit, *partner bits)`.
To satisfy "lazy-cache and pre-filled constructions agree value-for-value"
*regardless of visitation order* (a stronger, directly-testable property, not
just "identical in distribution" per `build-spec.md` §4's note), draw a
dedicated per-locus seed once at construction — `self._locus_seeds = [rng.getrandbits(64) for _ in range(N)]`,
consumed in fixed locus order `0..N-1` — and generate a locus's **entire** row
in one shot, in canonical key order, the first time *any* key for that locus is
touched:

```python
def _row(self, locus: int) -> list[float]:
    if locus not in self._tables:
        row_rng = random.Random(self._locus_seeds[locus])
        self._tables[locus] = [row_rng.random() for _ in range(2 ** (self.K + 1))]
    return self._tables[locus]
```

Because a locus's row is a pure function of `(seed, locus)` and is always
materialized whole (not entry-by-entry), a landscape queried sparsely (only the
cells one string touches) and one already driven exhaustively over every
possible string first necessarily land on the same values — there is no
separate "pre-fill mode" to build or maintain; `test_lazy_and_prefilled_constructions_agree`
exercises exactly this by exhaustively calling `fitness` over all `2^N` strings
on one instance before comparing against a freshly-lazy instance seeded
identically.

### `contribution` / `fitness`

```python
def contribution(self, locus, string) -> float:
    key = bits_to_int([string[locus], *(string[p] for p in self.partners[locus])])
    return self._row(locus)[key]

def fitness(self, string) -> float:
    return sum(self.contribution(i, string) for i in range(self.N)) / self.N
```

### Where we persist

In-memory only, per `spec.md`'s "Where we persist" — a landscape lives for the
lifetime of one run, fully reproducible from `(N, K, scheme, seed)`.

### Out of scope for this issue

- `Agent`, network topologies, the turn loop, metrics (#8–#11) — this issue is
  `NKLandscape` alone.
- A real hill-climbing implementation in `src/` — the greedy-climb used by
  test #8 is a test-local helper that exercises a structural property of the
  landscape (single-peakedness at `K=0`), not a production `Agent` API (that's
  #9's `decide`).
- Non-binary `B` — `NKConfig.B` exists for future extension; `NKLandscape`
  itself is binary-only per this issue's scope.
