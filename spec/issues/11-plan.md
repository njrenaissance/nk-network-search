# Plan — Issue #11: synchronous turn-loop `Model` (`model.py`)

**Status:** proposed

**Status of this document.** Planning-only. No production logic in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the implementation
approach that satisfies it. Comment `/approve` on this PR to begin the Build
stage (Build writes `src/nkmodel/model.py` to satisfy the acceptance criteria
below; `tests/test_model.py` is locked and Build may not weaken it).

Refs #11. Group 4 of 6 (`spec/build-order.md`) — the first issue that needs all
of Group 2 and Group 3. Depends on #7 (`NKLandscape`), #8 (`network.py`), #9
(`Agent`), and #10 (`metrics.py`), all merged. `Model` composes them: it builds
the landscape and network, constructs the agents, drives `Agent.decide` each
turn, and records one `MetricsSeries` row per step.

## Acceptance criteria

- In a two-agent case, an agent's committed move within a step is not visible to
  the other until the next step (synchronous, not sequential).
- Each `step()` appends exactly one record (mean fitness, best fitness,
  diversity) to the metrics series.
- The same `(config, seed)` produces an identical metric time-series across two
  separate `Model` runs.
- A full run on `complete` topology visibly converges agents to a shared string
  (`build-spec.md` milestone 3).

## Test list — `tests/test_model.py` (all `@pytest.mark.unit`, 7 cases)

| # | Test | Acceptance criterion |
|---|---|---|
| 1 | `test_model_constructed_from_config_and_seed_wires_all_collaborators` | constructed from `(config, seed)` — wires landscape, agents (uids `0..A-1`), graph, empty metrics |
| 2 | `test_step_updates_synchronously_not_sequentially` | synchronous, not sequential — a committed move is invisible within the same step |
| 3 | `test_step_passes_neighbors_in_ascending_uid_order_for_tie_break` | integration of #9's tie-break: `Model` passes `neighbor_states` in ascending-uid order |
| 4 | `test_step_appends_exactly_one_metrics_row_per_call` | each `step()` appends exactly one row and returns it |
| 5 | `test_same_config_and_seed_produce_identical_series` | same `(config, seed)` ⇒ identical time-series across two runs |
| 6 | `test_different_seed_produces_different_series` | a different seed drives a different run (reproducibility is not vacuous) |
| 7 | `test_complete_topology_run_converges_to_shared_string` | full `complete`-topology run converges to one shared string |

(4 acceptance criteria ⇒ 7 cases: the constructor contract and the tie-break
integration each earn a dedicated test, and AC3 is split into a positive
"same seed ⇒ identical" case and its complement "different seed ⇒ differs" so
the reproducibility assertion is not passing vacuously.)

All 7 cases currently fail against the committed stub with a genuine
`NotImplementedError` (functionality not yet written) — confirmed failing for
the right reason, not an import/collection error — and were validated 7/7 green
against a throwaway reference implementation used only to validate the suite
before committing it (that reference code is not part of this PR).
`spec/issues/11-tests.lock` pins the test file's blob SHA for Build's pre-push
test-integrity guard.

---

## Below the fold: design detail

### Signatures (`src/nkmodel/model.py`)

```python
class Model:
    def __init__(self, config: NKConfig, seed: int) -> None: ...
    def step(self) -> MetricsRow: ...
    def run(self) -> MetricsSeries: ...
```

Public attributes established by the constructor and asserted by the tests:
`.config`, `.seed`, `.landscape` (`NKLandscape`), `.graph` (`networkx.Graph`),
`.agents` (`list[Agent]`, uids `0..A-1`), `.rng` (`random.Random`, the shared
explore RNG), `.metrics` (`MetricsSeries`).

(Illustrative below — matches `build-spec.md` §6's sketch. Build may implement
this however it likes as long as the locked tests pass; the code here is the
design this plan is reasoned against, not binding code.)

### Construction and the reproducibility seeding — the main design decision

"A run is fully determined by `(config, seed)`" is the crux. Randomness enters
in four independent places — the landscape's contribution draws (#7), the
network draws for `ws`/`random_regular` (#8), each agent's initial string, and
every explore-step bit-flip (#9). To make the whole run a pure function of
`(config, seed)` **and** keep those streams independent (so, e.g., changing `N`
doesn't shift the network draw), the constructor derives one child RNG per
concern from a single master `random.Random(seed)` — the same `getrandbits(64)`
idiom `NKLandscape` already uses internally for its per-locus seeds:

```python
def __init__(self, config: NKConfig, seed: int) -> None:
    self.config = config
    self.seed = seed
    master = random.Random(seed)
    self.landscape = NKLandscape(
        config.N, config.K, config.scheme, rng=random.Random(master.getrandbits(64))
    )
    self.graph = build_network(config, rng=random.Random(master.getrandbits(64)))
    init_rng = random.Random(master.getrandbits(64))
    self.agents = [
        Agent(uid=uid, string=[init_rng.randrange(config.B) for _ in range(config.N)])
        for uid in range(config.A)
    ]
    self.rng = random.Random(master.getrandbits(64))  # shared explore RNG
    self.metrics = MetricsSeries()
```

Binary is the built target (`B=2`), so initial strings are drawn with
`randrange(config.B)` — `{0, 1}` bits matching `Agent`/`NKLandscape`. This is a
real, worth-flagging design decision (the seeding discipline is what AC3 rests
on) but it is not architecture-level or hard to reverse — a later issue could
reorder or re-derive the streams with a localized change — so it is recorded
here rather than as an ADR.

### `step()` — synchronous snapshot / commit, with the ascending-uid contract

```python
def step(self) -> MetricsRow:
    snapshot = {agent.uid: list(agent.string) for agent in self.agents}
    next_strings: dict[int, list[int]] = {}
    for agent in self.agents:
        neighbor_states = [snapshot[uid] for uid in sorted(self.graph.neighbors(agent.uid))]
        next_strings[agent.uid] = agent.decide(neighbor_states, self.landscape, self.rng)
    for agent in self.agents:  # commit only after every agent has decided
        agent.string = next_strings[agent.uid]
    return self.metrics.record([agent.string for agent in self.agents], self.landscape)
```

Two integration points worth calling out:

- **Snapshot before decide, commit after.** Every agent decides against the
  start-of-turn `snapshot`, never a neighbor's mid-turn move — this is the
  synchronous semantics AC1 pins. `sorted(...)` also makes iteration
  order-independent of `networkx`'s neighbor iteration order.
- **Ascending-uid `neighbor_states`.** #9's plan made `Model` responsible for
  passing neighbors to `decide` in ascending-uid order, so that `decide`'s
  stable `max` copies the lowest-uid neighbor among ties without any uid
  bookkeeping. `sorted(self.graph.neighbors(agent.uid))` honors that contract
  (networkx labels nodes `0..A-1`, matching agent uids). Test 3 exercises this
  end-to-end.

`metrics.record` is called as `record(strings, landscape)` — the signature #10
settled on — passing `[agent.string for agent in self.agents]` and
`self.landscape`, since `metrics.py` takes no `Model`/`Agent` dependency.

### `run()`

```python
def run(self) -> MetricsSeries:
    for _ in range(self.config.steps):
        self.step()
    return self.metrics
```

A thin driver over `config.steps` turns; returns the accumulated series. Test 7
drives a full `complete`-topology run through it and asserts convergence.

### Test doubles: why `tests/test_model.py` fakes the landscape for 2 of 7 cases

Tests 2 and 3 assert tie/strict-beat behavior (`>` vs `==`) — "the copy is the
start-of-turn string," "the lowest-uid tied-best neighbor wins." As in
`test_agent.py`, the real `NKLandscape`'s continuous per-locus draws make an
*exact* fitness tie a probability-zero event, so these can only be exercised
deterministically by controlling exact fitness per string. `test_model.py`
defines a small `_FixedFitnessLandscape` fake (a `dict[tuple[int, ...], float]`
with a `default` for unlisted explore candidates) implementing only
`fitness(string)`. These two tests construct a real `Model`, then swap in the
fake landscape and controlled strings/rng to drive the real `step()` against a
known fitness surface — the unit under test (`step`) is real; only the fitness
oracle is faked, exactly the boundary `.claude/standards/testing.md` allows.

The other five tests use the real `NKLandscape`: construction (1), one-row-per-
step and range checks (4), reproducibility (5, 6), and `complete`-topology
convergence (7) all need genuine behavior, not an engineered tie.

### Where we persist

In-memory only, per `spec.md`'s "Where we persist" — a `Model` holds the
landscape, agents, and metrics for the lifetime of one run; writing the series
to disk is the runner's job (`run.py`, issue #12).

### Out of scope for this issue

- `run.py`'s single-run + topology×K sweep driver and the headline
  `test_results.py` assertions (K=0 invariance, high-K crossover, diversity
  collapse, inverted-U) — issue #12.
- Plotting/rendering the series (`analysis.py`) — issue #13.
- Any real production logic beyond the signatures-only stub — Build's job once
  this plan is approved.
