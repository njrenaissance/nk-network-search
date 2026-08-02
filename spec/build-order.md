# build-order.md

This is the durable **build order** for the NK networked-search experiment
(`spec/spec.md`, `spec/build-spec.md`). It records the static group structure and
issue numbers only — per-issue progress is *not* tracked here; it is derived from
live GitHub issue/PR state.

Issues within a group have no dependency on one another and may be planned/built in
parallel. Each group depends only on issues from strictly earlier groups.

## Resolved ambiguity

`build-spec.md` §3 sketches a top-level `nkmodel/` package, but this project's
scaffold (`CLAUDE.md`, `pyproject.toml`'s `pythonpath = ["src"]`) uses a `src/`
layout. Per `spec.md`'s authority over `build-spec.md`, the package lives at
`src/nkmodel/`, with `run.py` and `analysis.py` as thin root-level scripts that
import from it — same module layout `build-spec.md` §3 describes, just rooted
under `src/`.

## Groups

### Group 1 — Config (foundational)

| Issue | Title |
|---|---|
| [#6](https://github.com/njrenaissance/nk-network-search/issues/6) | feat: NKConfig settings (config.py) |

No dependencies. Every other module reads its knobs from `NKConfig`, so it is the
sole first-group issue.

### Group 2 — Landscape & Network (parallel, depend only on Group 1)

| Issue | Title |
|---|---|
| [#7](https://github.com/njrenaissance/nk-network-search/issues/7) | feat: NKLandscape fitness model (landscape.py) |
| [#8](https://github.com/njrenaissance/nk-network-search/issues/8) | feat: network topology builders (network.py) |

Both read config fields (`N`/`K`/`scheme` and `topology`/`ws_k`/`ws_p`/`degree`/`A`
respectively) but are otherwise independent of each other — neither imports the
other.

### Group 3 — Agent & Metrics (parallel, depend only on Group 2's Landscape)

| Issue | Title |
|---|---|
| [#9](https://github.com/njrenaissance/nk-network-search/issues/9) | feat: Agent exploit/explore decision (agent.py) |
| [#10](https://github.com/njrenaissance/nk-network-search/issues/10) | feat: fitness/diversity metrics (metrics.py) |

`Agent.decide` calls `landscape.fitness` directly. `metrics.py` operates on plain
string collections plus the landscape (not on `Agent` objects), so it has the same
dependency footprint as Agent and builds in parallel with it, not after it.

### Group 4 — Model (depends on all of Group 2 and Group 3)

| Issue | Title |
|---|---|
| [#11](https://github.com/njrenaissance/nk-network-search/issues/11) | feat: synchronous turn-loop Model (model.py) |

The turn loop ties together landscape, agents, network, and metrics recording —
it is the first issue that needs all four.

### Group 5 — Runner & headline results (depends on Group 4)

| Issue | Title |
|---|---|
| [#12](https://github.com/njrenaissance/nk-network-search/issues/12) | feat: run.py — single run + topology×K sweep, headline results |

Delivers the single-run + sweep driver and the `test_results.py` assertions on
the paper's headline findings (K=0 invariance, high-K crossover, diversity
collapse, inverted-U).

### Group 6 — Analysis / figures (depends on Group 5's on-disk series format)

| Issue | Title |
|---|---|
| [#13](https://github.com/njrenaissance/nk-network-search/issues/13) | feat: analysis.py — fitness/diversity curves and inverted-U figure |

Renders the series `run.py` writes to disk into the fitness/diversity curves and
the inverted-U figure. Kept separate from Group 5 because it depends on that
on-disk format being settled, not just on `Model`.
