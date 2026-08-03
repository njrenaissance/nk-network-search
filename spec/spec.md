# spec.md

**Status:** deliver-ready

## Purpose

Reimplement Lazer & Friedman (2007)'s NK model of networked search — `A` agents
exploring one shared, static NK landscape under an exploit-or-explore rule — to
observe how network connectivity trades short-run collective performance against
long-run performance.

## Inputs / Outputs

**Input** — a single `NKConfig` value, a `pydantic-settings` `BaseSettings` (env
prefix `NK_`, `.env`-aware) so any knob can be overridden by an environment variable
or per sweep cell:

- `N: int` — string length / number of loci (default 20)
- `K: int` — interacting partners per locus, `0 … N-1` (landscape ruggedness)
- `B: int` — values per locus (2 = binary; binary is the built target)
- `scheme: str` — `"adjacent"` | `"random"` (which `K` partners each locus reads)
- `A: int` — number of agents
- `topology: str` — `"ring"` | `"ws"` | `"random_regular"` | `"complete"`
- `ws_k: int`, `ws_p: float` — Watts–Strogatz base degree and rewiring probability
- `degree: int` — degree for `random_regular`
- `steps: int` — synchronous turns per run
- `replications: int` — runs to average over (landscapes × initial strings ×
  network draws)
- `seed: int` — master RNG seed; a run is fully determined by `(config, seed)`

**Output** — per-step metric time-series, per run and aggregated over replications:

- `mean_fitness[t]: float` in `[0, 1)` — population mean fitness at step `t`
- `best_fitness[t]: float` in `[0, 1)` — best agent fitness at step `t`
- `diversity[t]` — `int` count of distinct strings and/or `float` mean pairwise
  Hamming distance
- `convergence_time: int` — first step at which `diversity` reaches (≈) 0
- A topology×K sweep yields these series per cell; `analysis.py` renders them as
  fitness/diversity curves and the inverted-U figure, written to disk.

Fitness is hidden in the landscape: an agent reads `landscape.fitness(string)` on
demand and never owns or copies a fitness number — the string is the single source
of truth.

## What we produce

**library** — a `nkmodel/` package (`landscape`, `agent`, `network`, `model`,
`metrics`, `config`) that the unit tests assert against, driven by thin `run.py`
(single run + sweep) and `analysis.py` (figures) scripts. See
[`build-spec.md`](./build-spec.md) for the module layout and code sketches.

## Where we persist

**file** — a run holds the landscape, agents, and metrics in memory and is fully
reproducible from `(config, seed)`; the runner scripts write the metric series and
figures to disk. No database.

## Method

**rules** — a deterministic, rule-based agent simulation; no ML and no learned
parameters. The algorithm, with its hidden degrees of freedom pinned (each of these
changes results, so each is fixed and documented):

- **Landscape.** Each locus `i` has its own independent contribution table keyed by
  its own bit plus its `K` partners' bits — `K+1` bits, `2^(K+1)` rows per locus,
  `N · 2^(K+1)` entries total. Contributions are iid draws from `[0, 1)`.
  `fitness(string)` is the mean of the `N` per-locus contributions. Partners are
  fixed at setup by `scheme` (`"adjacent"` = loci `i+1 … i+K` cyclic; `"random"` =
  `K` distinct loci drawn once, stored per locus). Draw-and-cache on first visit is
  used (identical in distribution to pre-filling the full table); small-N tests may
  pre-fill to assert the whole surface.
- **Agent turn.** Compare against neighbors' start-of-turn strings. If some neighbor
  scores **strictly** higher, copy the best such neighbor's string (*exploit*).
  Otherwise flip one random bit and keep it only if it scores **strictly** higher
  (*explore*); a tying flip is rejected.
- **Pinned degrees of freedom.**
  - Exploit comparison is strict `>` — a tie is not "better", so the agent explores.
  - Explore acceptance is strict `>` — reject flips that only tie (one-step
    hill-climb, no neutral drift).
  - Exploit tie-break — when several neighbors tie for best and all beat the agent,
    copy the **lowest-uid** one (deterministic).
  - One bit flipped per explore step.
  - Update is **synchronous** — snapshot every string at the start of the turn,
    every agent decides against the snapshot, then commit; no agent sees another's
    mid-turn move.
- **Network** is the independent variable, built with NetworkX and spanning
  sparse→dense: `ring` / `ring_lattice`, `watts_strogatz(A, k, p)`,
  `random_regular(A, degree)`, `complete`.

## Done criteria

Stochastic criteria run with a fixed `seed` and enough `replications` to be
deterministic under test.

**Config**

- `NKConfig()` populates every field from the single `DEFAULTS` dict, and
  `get_config()` returns a cached singleton (the same object on repeated calls).
- Fields are validated at load: a non-numeric `K`, or a `scheme` / `topology` outside
  its allowed set, raises `pydantic.ValidationError`.
- Environment overrides apply: with `NK_SEED=7` in the environment,
  `get_config().seed == 7`, and a real env var takes precedence over the same key in
  `.env`.

**Landscape** *(test_landscape)*

- `fitness(string)` returns the mean of the `N` per-locus contributions and lies in
  `[0, 1)`.
- `contribution(locus, string)` depends only on the bits at `locus` and its `K`
  partners: two strings that agree on those `K+1` positions give an identical
  contribution, and flipping any bit outside them leaves it unchanged.
- Reproducibility: two landscapes built with the same `seed` return identical
  `fitness` for the same string, and the lazy-cache and pre-filled constructions
  agree value-for-value.
- K=0 is single-peaked: with `K=0` each contribution depends only on its own locus,
  so exactly one global optimum exists (each locus set to its higher-scoring bit),
  and greedy one-bit hill-climbing from any starting string reaches that same
  optimum.

**Agent** *(test_agent)*

- Given a neighbor scoring strictly higher, `decide` returns a copy of that
  neighbor's string (equal value, distinct object).
- Given no strictly-better neighbor, `decide` returns a string at Hamming distance
  ≤ 1 from the current one (a single flip or no change).
- A one-bit flip that only ties current fitness is rejected — `decide` returns the
  current string unchanged.
- A neighbor that only ties the agent's fitness does not trigger a copy.
- With several neighbors tied for best and all beating the agent, the copied string
  is the deterministic tie-break winner (lowest uid).
- `decide` is pure: it mutates neither `self.string` nor any argument.
- Lone agent halts: an agent with no neighbors climbs by single-bit flips and, once
  no improving flip exists (a local optimum), returns its own string unchanged on
  every later step.

**Model**

- One `step` decides every agent against the start-of-turn snapshot and then
  commits: in a two-agent case, an agent's committed move within a step is not
  visible to the other until the next step (synchronous, not sequential).
- Each `step` appends exactly one record (mean fitness, best fitness, diversity) to
  the metrics series.
- Same `(config, seed)` produces an identical metric time-series across two runs.

**Results — the headline** *(test_results)*

- K=0 invariance: with `K=0`, mean fitness converges to the same optimum for `ring`
  and `complete` (within tolerance) — topology is irrelevant on a smooth landscape.
- Crossover at high K: at high `K`, `complete` has strictly higher mean fitness than
  `ring` at an early step but strictly lower mean fitness at the final step
  (averaged over replications).
- Diversity collapse: `complete` reaches ~0 diversity (convergence) in strictly
  fewer steps than `ring`.
- Inverted-U: at an intermediate horizon, sweeping connectivity from sparse to dense
  yields non-monotone mean fitness — an interior connectivity level outperforms both
  the sparsest and the densest.
