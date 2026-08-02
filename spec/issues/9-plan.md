# Plan — Issue #9: Agent exploit/explore decision (`agent.py`)

**Status:** approved

**Status of this document.** Planning-only. No production code in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the
implementation approach that satisfies it. Comment `/approve` on this PR to
begin the Build stage (Build writes `src/nkmodel/agent.py` to satisfy the
acceptance criteria below; `tests/test_agent.py` is locked and Build may not
weaken it).

Refs #9. Group 3 of 6 (`spec/build-order.md`), parallel with #10 (metrics).
Depends only on #7 (`NKLandscape`, merged) — `decide` calls
`landscape.fitness`.

## Acceptance criteria

- Given a neighbor scoring strictly higher, `decide` returns a copy of that
  neighbor's string (equal value, distinct object).
- Given no strictly-better neighbor, `decide` returns a string at Hamming
  distance ≤ 1 from the current one.
- A one-bit flip that only ties current fitness is rejected — current string
  returned unchanged.
- A neighbor that only ties the agent's fitness does not trigger a copy.
- With several neighbors tied for best and all beating the agent, the copied
  string is the lowest-uid tie-break winner.
- `decide` is pure — mutates neither `self.string` nor any argument.
- Lone agent (no neighbors) climbs by single-bit flips and, once at a local
  optimum, returns its own string unchanged on every later step.

## Test list — `tests/test_agent.py` (all `@pytest.mark.unit`, 8 cases)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_decide_exploits_strictly_better_neighbor_returns_copy` | strictly-better neighbor ⇒ copy (equal value, distinct object) |
| 2 | `test_decide_without_better_neighbor_stays_within_hamming_distance_one` (× accepted/rejected flip) | no strictly-better neighbor ⇒ result within Hamming distance ≤ 1 |
| 3 | `test_decide_rejects_flip_that_only_ties_current_fitness` | tying flip rejected — current string unchanged |
| 4 | `test_decide_does_not_exploit_neighbor_that_only_ties` | tying neighbor does not trigger a copy |
| 5 | `test_decide_tie_break_among_best_neighbors_picks_lowest_uid_by_order` | several tied best neighbors ⇒ lowest-uid winner copied |
| 6 | `test_decide_does_not_mutate_self_string_or_arguments` | `decide` is pure |
| 7 | `test_lone_agent_climbs_then_halts_at_local_optimum` | lone agent hill-climbs, then holds at local optimum |

(7 acceptance criteria ⇒ 8 test cases: criterion 2 is parametrized over the
accept/reject branch of the explore step.)

All 8 cases currently fail against the committed stub with a genuine
`NotImplementedError` (functionality not yet written) — confirmed, not an
import/collection error — and were validated 8/8 green against a throwaway
reference implementation used only to validate the suite before committing it
(that reference code is not part of this PR).
`spec/issues/9-tests.lock` pins the test file's blob SHA for Build's pre-push
test-integrity guard.

---

## Below the fold: design detail

### Signature

```python
class Agent:
    def __init__(self, uid: int, string: list[int]) -> None: ...

    def decide(
        self,
        neighbor_states: Sequence[Sequence[int]],
        landscape: NKLandscape,
        rng: random.Random,
    ) -> list[int]: ...
```

`string` is `list[int]` of `0`/`1` bits, length `N` (binary `B=2`, matching
`NKLandscape`). `Agent` holds only `uid` and `string` — no cached fitness
field; `spec.md`'s "Fitness is hidden in the landscape" rule means any
fitness value is recomputed from `landscape.fitness(self.string)` on demand,
never stored on the agent. `rng` is a required `random.Random` passed in by
the caller (the later `Model`, issue #11) — no hidden global randomness, same
convention as `NKLandscape` (#7) and `network.py` (#8).

### The exploit/explore rule

```python
def decide(self, neighbor_states, landscape, rng) -> list[int]:
    my_fitness = landscape.fitness(self.string)
    best = max(neighbor_states, key=landscape.fitness, default=None)
    if best is not None and landscape.fitness(best) > my_fitness:
        return list(best)  # EXPLOIT
    candidate = list(self.string)
    candidate[rng.randrange(len(candidate))] ^= 1
    return candidate if landscape.fitness(candidate) > my_fitness else list(self.string)  # EXPLORE
```

(Illustrative — matches `build-spec.md` §5's sketch. Build may implement this
however it likes as long as the tests pass; this is not binding code, just the
design this plan is reasoned against.)

### `neighbor_states` and the lowest-uid tie-break — the one real design choice here

`decide` takes `neighbor_states: Sequence[Sequence[int]]` — **raw strings,
not `(uid, string)` pairs** — matching `build-spec.md` §5's signature exactly.
That leaves one question: how does `decide` implement "copy the **lowest-uid**
neighbor's string among ties" without ever seeing a uid?

**Convention (pinned here, binding on the caller):** `neighbor_states` is
passed to `decide` in ascending order of neighbor `uid`. Python's
`max(..., key=...)` is stable — on a tie it returns the *first* maximal
element encountered — so with the caller's ascending-uid ordering, "first
among the tied-best" and "lowest uid among the tied-best" are the same
element. `decide` needs no uid bookkeeping at all; the tie-break falls out of
list order plus `max`'s documented stability.

This is a real, worth-flagging design decision (it makes the ordering
contract part of `decide`'s implicit interface), but it is not
architecture-level or hard to reverse — a later issue could switch to
`(uid, string)` pairs with one function signature change — so it's recorded
here rather than as an ADR. The later `Model` (issue #11), which owns
`graph.neighbors(uid)`, is responsible for sorting by uid before calling
`decide`; this issue only needs `decide` to honor that order, which
`test_decide_tie_break_among_best_neighbors_picks_lowest_uid_by_order`
exercises directly by constructing `neighbor_states` in ascending-uid order
and asserting the first of several tied-best entries wins.

### Test doubles: why `tests/test_agent.py` fakes the landscape for 6 of 7 cases

`NKLandscape`'s per-locus contributions are continuous draws
(`random.Random.random()`, issue #7). Two distinct strings landing on an
*exact* tie in fitness has probability zero in practice. But several
acceptance criteria here are specifically about tie-handling (`==`, not just
`>`) — "a tying flip is rejected," "a tying neighbor is not copied." Those
can only be exercised deterministically by controlling the exact fitness
value assigned to specific strings.

`tests/test_agent.py` defines a small fake, `_FixedFitnessLandscape`, wrapping
a `dict[tuple[int, ...], float]` and implementing only `fitness(string)`. This
is not standing in for a landscape that's hard to construct — `NKLandscape` is
one line to build — it exists solely to make exact ties and exact
strictly-greater/lesser relationships assertable. `.claude/standards/testing.md`
already carves out mocking of true external boundaries; the same reasoning
extends to a hand-written fake here, since the real `NKLandscape`'s randomness
is fundamentally unable to produce a reliable exact tie for a test to assert
against.

The one exception is the lone-agent test (criterion 7,
`test_lone_agent_climbs_then_halts_at_local_optimum`), which uses the real
`NKLandscape` with `K=0` — same single-peaked guarantee `test_landscape.py`
(#7) already established — because that test only needs genuine, monotonic
one-bit-flip improvement toward one global optimum, not an exact tie. It
seeds both the landscape's RNG and the agent's decision RNG so the run is
reproducible, then drives `decide` in a loop (no neighbors) until the agent's
string reaches the exhaustively-computed optimum, and confirms a few further
steps return that same string unchanged.

### Where we persist

In-memory only, per `spec.md`'s "Where we persist" — an `Agent` lives for the
lifetime of one run; nothing here is written to disk.

### Out of scope for this issue

- `Model`'s turn loop, synchronous snapshot/commit semantics, and building
  `neighbor_states` from a real graph — issue #11. This issue is `Agent`
  alone; `decide` is tested by constructing `neighbor_states` directly, not
  via a graph.
- `metrics.py` (#10) — parallel, no dependency either way.
- Any real production logic beyond the signatures-only stub — Build's job
  once this plan is approved.
