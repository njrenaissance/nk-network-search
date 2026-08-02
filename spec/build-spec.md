# Lazer–Friedman NK Experiment — Build Spec (design detail)

> **Status of this document.** This is the *design elaboration* — module layout,
> code sketches, and the reasoning behind each pinned decision. The canonical
> contract and the definition of "done" live in [`spec.md`](./spec.md); where the
> two ever disagree, `spec.md` wins. This file exists so the Scaffold and Build
> stages have the concrete structure to build against.

A small, self-contained reimplementation of Lazer, D., & Friedman, A. (2007),
*The Network Structure of Exploration and Exploitation* (ASQ 52(4):667–694).
Purpose is understanding how these models work, not the org research project.
Shares intuitions with `code-spec-v0.2.md` (hidden fitness lives in the
landscape; agents just hold positions) but essentially no code. Build this first.

## 1. What it is, in one paragraph

`A` agents search one shared, static NK landscape. Each agent holds a candidate
solution — a string of `N` bits. Each turn, an agent either **exploits** (if a
neighbor scores higher, copy that neighbor's string) or **explores** (otherwise,
flip one random bit and keep it only if it scores higher). The network wiring the
agents together is the independent variable. The headline result: well-connected
networks do better short-run but worse long-run, because connectivity destroys the
solution diversity that fuels long-run search — with an inverted-U between
connectedness and performance at intermediate horizons.

## 2. The three objects

- **The landscape (the problem).** Fixed at setup, identical for all agents, never
  changes.
- **The agents.** Each holds one string; fitness is read from the landscape, never
  owned or copied.
- **The network.** Who can see whom. The thing we vary.

## 3. Module layout

```text
nkmodel/
  landscape.py   # NKLandscape: tables, interaction scheme, fitness(string)
  agent.py       # Agent: holds a string; exploit/explore decision
  network.py     # topology builders (ring, complete, small-world, random-regular)
  model.py       # Model: owns landscape + agents + graph; runs synchronous turns
  metrics.py     # mean/best fitness, diversity, convergence time
  config.py      # NKConfig dataclass
run.py           # single run + topology×K sweep
analysis.py      # curves + figures
tests/
  test_landscape.py   # K=0 => single global optimum
  test_agent.py       # lone agent halts at a local optimum
  test_results.py     # connected loses long-run at high K; inverted-U
```

## 4. The landscape (`landscape.py`)

Facts locked in from our walkthrough:

- Each locus `i` has its own contribution, a function of `K+1` bits: itself plus
  `K` partners.
- Contribution values are independent random draws from `[0, 1)`.
- Total table size is `N · 2^(K+1)` entries (N loci × 2^(K+1) rows each). Each
  locus gets its own independent table — not one shared table.
- `fitness(string)` = mean of the N per-locus contributions.
- Interaction scheme sets which K partners each locus uses: `"adjacent"` (loci
  `i+1 … i+K`, cyclic) or `"random"` (K distinct loci drawn once at setup). Same
  table size either way, but with `"random"` you must store the partner list per
  locus to build the lookup key consistently.

```python
class NKLandscape:
    def __init__(self, N, K, scheme="adjacent", rng=...):
        self.N, self.K = N, K
        self.partners = self._build_partners(scheme)   # list[list[int]], length N
        self.tables = {}                                # lazy: (locus, key_bits) -> float

    def contribution(self, locus, string) -> float:
        key = tuple(string[j] for j in [locus, *self.partners[locus]])
        if (locus, key) not in self.tables:             # lazy fill — only visited configs
            self.tables[(locus, key)] = self.rng.random()
        return self.tables[(locus, key)]

    def fitness(self, string) -> float:
        return sum(self.contribution(i, string) for i in range(self.N)) / self.N
```

Lazy caching (draw-and-cache on first visit) is mathematically identical to
pre-filling the full `N · 2^(K+1)` table, but avoids materializing it when K is
large and agents only ever visit a tiny slice of the `2^N` strings. Fine to
pre-fill instead for small N if you prefer explicitness — do that for the K=0 test
so you can assert the whole surface.

## 5. The agent (`agent.py`)

State is just the string. Fitness is derived from the landscape on demand (cache
the number for speed if you want, but the string is the single source of truth —
never store-and-copy fitness independently).

```python
class Agent:
    def __init__(self, uid, string):
        self.uid = uid
        self.string = string          # list[int] length N

    def decide(self, neighbor_states, landscape, rng) -> list[int]:
        """Return this agent's NEXT string. Pure function of the start-of-turn snapshot."""
        my_fit = landscape.fitness(self.string)
        best = max(neighbor_states, key=lambda s: landscape.fitness(s), default=None)
        if best is not None and landscape.fitness(best) > my_fit:
            return list(best)                              # EXPLOIT: copy best neighbor's string
        # EXPLORE: one random bit-flip, keep only if strictly better
        cand = list(self.string); i = rng.randrange(len(cand)); cand[i] ^= 1
        return cand if landscape.fitness(cand) > my_fit else list(self.string)
```

## 6. The turn loop (`model.py`) — synchronous

Critical for reproducibility: snapshot every agent's string at the start of the
turn, then everyone decides against that snapshot, then commit. No agent sees
another's mid-turn move.

```python
def step(self):
    snapshot = {a.uid: list(a.string) for a in self.agents}          # freeze
    next_strings = {}
    for a in self.agents:
        neigh = [snapshot[n] for n in self.graph.neighbors(a.uid)]   # start-of-turn states
        next_strings[a.uid] = a.decide(neigh, self.landscape, self.rng)
    for a in self.agents:                                            # commit
        a.string = next_strings[a.uid]
    self.metrics.record(self)
```

## 7. Decisions to pin down (hidden degrees of freedom)

These aren't fully forced by the paper's prose; choose and document them, because
they change results:

- **Exploit comparison is strict `>`.** A neighbor merely tying you is not "better"
  → you explore instead. (Prevents pointless copying.)
- **Explore acceptance is strict `>`.** Reject flips that tie. (A one-step
  hill-climb, never neutral drift — matches the paper; you could relax later.)
- **Exploit tie-break.** If several neighbors tie for the best (and beat you), pick
  deterministically (lowest uid) or randomly — pin one.
- **One bit per explore step.** The classic rule. (A knob you can vary later.)
- **Update = synchronous.** As in §6. Sequential updating is a different model.

## 8. The network (`network.py`)

Connectivity is the independent variable. Build a family spanning sparse→dense so
you can trace the performance curve:

- `ring(A)` / `ring_lattice(A, k)` — sparse, high diameter (inefficient).
- `watts_strogatz(A, k, p)` — sweep rewiring `p` from lattice→random.
- `random_regular(A, degree)` — hold degree, vary it.
- `complete(A)` — everyone sees everyone (maximally efficient).

"Efficiency" ≈ how fast information spreads (short average path length / high
degree). NetworkX supplies all of these.

## 9. Metrics (`metrics.py`)

Record per step:

- **Mean fitness** across agents (the performance curve; watch short-run vs
  long-run).
- **Best fitness** in the population.
- **Diversity** — number of distinct strings, and/or mean pairwise Hamming
  distance. This is the mechanism: connected networks lose diversity fast.
- **Convergence time** — step at which diversity hits (or nears) zero.

## 10. Config (`config.py`)

```python
from functools import lru_cache
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Every non-secret default in ONE place (config standard: no scattered literals).
DEFAULTS: dict[str, Any] = {
    "N": 20,             # loci / string length
    "K": 5,              # 0 (smooth) … N-1 (max rugged)
    "B": 2,              # values per locus; start binary
    "scheme": "adjacent",
    "A": 100,            # agents
    "topology": "complete",
    "ws_k": 4,
    "ws_p": 0.1,
    "degree": 4,
    "steps": 300,        # synchronous turns per run
    "replications": 50,  # over landscapes × initial strings × network draws
    "seed": 0,
}


class NKConfig(BaseSettings):
    """Simulation config. A pydantic-settings BaseSettings so any knob can be
    overridden from the environment or .env (e.g. NK_K=10, NK_TOPOLOGY=ring)
    without editing code; real env vars take precedence over .env."""

    model_config = SettingsConfigDict(env_prefix="NK_", env_file=".env")

    N: int = DEFAULTS["N"]
    K: int = DEFAULTS["K"]
    B: int = DEFAULTS["B"]
    scheme: Literal["adjacent", "random"] = DEFAULTS["scheme"]
    A: int = DEFAULTS["A"]
    topology: Literal["ring", "ws", "random_regular", "complete"] = DEFAULTS["topology"]
    ws_k: int = DEFAULTS["ws_k"]
    ws_p: float = DEFAULTS["ws_p"]
    degree: int = DEFAULTS["degree"]
    steps: int = DEFAULTS["steps"]
    replications: int = DEFAULTS["replications"]
    seed: int = DEFAULTS["seed"]


@lru_cache
def get_config() -> NKConfig:
    """The one cached config instance — import this, don't re-instantiate."""
    return NKConfig()
```

> **Config framework.** Changed from the original `@dataclass` sketch to
> **`pydantic-settings`** per this project's configuration standard (Profile:
> *App config (pydantic-settings): enabled*) and the reviewer request on PR #5.
> `pydantic-settings` is already a project dependency, so no `pyproject.toml` change
> is needed. Notes:
>
> - Enumerated knobs (`scheme`, `topology`) are `Literal`-typed, so an invalid value
>   fails loudly at load time instead of deep inside a builder.
> - Every non-secret default lives once in `DEFAULTS`; the fields reference it, so
>   `NKConfig()` still picks up env / `.env` overrides (init kwargs > env > `.env` >
>   field default). There are no secrets here, so no `SecretStr` fields.
> - Sweeps build explicit per-cell configs — `NKConfig(**{**DEFAULTS, "K": 10,
>   "topology": "ring"})` — validated the same way; init kwargs win, so a sweep cell
>   is deterministic regardless of ambient environment.
> - Ship a `.env.example` listing every `NK_*` variable with its placeholder default.
> - Kept flat (not nested `BaseSettings` sections) because `run.py` varies individual
>   knobs per sweep cell and a single well-named block is the most ergonomic for that;
>   revisit nesting if the knob count grows.

Starting values for learning (not the paper's exact constants): N=20, K∈{0,5,10},
B=2, A=100, steps≈300, replications≥50. If you want to match the paper's figures,
lift N, K, A, steps, replications from a reimplementation (comses.net Boroomand &
Smaldino 2020, or NetLogo Modeling Commons model 5219) rather than these.

## 11. Milestones

1. **Landscape.** `NKLandscape` + `fitness`. ✅ when `test_landscape` passes: with
   K=0 the landscape is single-peaked — hill-climbing from anywhere reaches one
   global optimum.
2. **Single-agent explore.** One agent, no network, pure one-bit hill-climb. ✅
   when a lone agent climbs and halts at a local optimum (no neighbor, no improving
   flip).
3. **Network + exploit.** `A` agents, `ring` and `complete`, synchronous turn loop
   with the exploit/explore rule. ✅ when a full run executes and agents on
   `complete` visibly converge to a shared string.
4. **Metrics + sweep.** Fitness/diversity tracking; sweep topology × K. ✅ when you
   reproduce the short-run/long-run crossover (complete wins early, loses late at
   high K) and the inverted-U at an intermediate horizon.

## 12. What to look for (the paper in a few runs)

- **K=0, any topology:** everyone reaches the same global optimum; network
  structure irrelevant. (Ruggedness is required for the effect — confirms your
  landscape.)
- **High K, `complete` vs `ring`:** `complete` climbs faster early, then plateaus
  lower; `ring` lags early, keeps improving, ends higher. The crossover is the
  result.
- **Diversity trace:** `complete`'s diversity collapses to ~0 quickly; `ring`
  retains distinct strings far longer. That collapse is the explanation for the
  crossover — not a separate finding.

## 13. Bridge to the org sim (later)

This NK landscape is the clean prototype of the hidden-fitness `Problem` sets in
`code-spec-v0.2.md §9`: fitness lives in a fixed problem structure, agents hold
positions and can't see fitness directly, and premature convergence on a connected
network yields fast-but-worse collective outcomes. Same mechanic, dressed up with
teams, boundaries, and tacit/explicit contagion. Learn it here first.
