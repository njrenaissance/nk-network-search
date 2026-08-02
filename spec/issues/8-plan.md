# Plan — Issue #8: network topology builders (`network.py`)

**Status:** approved

**Status of this document.** Planning-only. No production code in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation. `tests/test_network.py` will fail to **collect** until Build
writes `src/nkmodel/network.py` — that's expected and is this PR's whole point.
Comment `/approve` to begin the Build stage.

Refs #8. Group 2 of 6 (parallel with #7), depends only on #6 (merged).

## Acceptance criteria → tests (read this, approve from this)

| # | Acceptance criterion | Test(s) in `tests/test_network.py` |
|---|---|---|
| 1 | Each builder returns a graph with exactly `A` nodes | `test_builder_returns_graph_with_a_nodes[ring]`, `[ring_lattice]`, `[watts_strogatz]`, `[random_regular]`, `[complete]` |
| 2a | `ring` / `ring_lattice` produce a **connected, ring-structured** graph | `test_ring_is_connected_two_regular_cycle`, `test_ring_lattice_is_connected_k_regular` |
| 2b | `complete` produces `A*(A-1)/2` edges | `test_complete_has_full_edge_count` |
| 2c | `random_regular` produces an (approximately) `degree`-regular graph | `test_random_regular_is_degree_regular` |
| 2d | `watts_strogatz` produces a graph with `A` nodes and base degree `ws_k` before rewiring | `test_watts_strogatz_preserves_base_edge_count_across_p` |
| 3 | `build_network` reproducible: same `(config, seed)` ⇒ isomorphic/identical graph across two calls | `test_build_network_reproducible[ring]`, `[ws]`, `[random_regular]`, `[complete]` |
| 3b | `build_network` dispatches to the matching builder for each `topology` value | `test_build_network_dispatches_to_matching_builder[ring]`, `[ws]`, `[random_regular]`, `[complete]` |
| 4 | Invalid `topology` rejected at config load, **not re-validated here** | *(no test — already covered by #6's `test_invalid_topology_raises`)* |
| 5 | Tests live at `tests/test_network.py`, marked `unit` | every test above carries `@pytest.mark.unit` |

21 test cases total (5 node-count + 4 structural + 4 watts-strogatz-`p` variants +
4 reproducibility + 4 dispatch, across 8 `def test_...` functions), all
`@pytest.mark.unit`, parametrized wherever the assertion shape repeats across
topologies (per `.claude/rules/pytest-rules.md`).

Approve this PR to have Build write `src/nkmodel/network.py` against the design
below.

---

## Below the fold: implementation design

### 1. Dependency

Add `networkx` to `pyproject.toml` `[project.dependencies]` (done in this PR via
`uv add networkx`, currently resolves to `networkx>=3.6.1`; `uv.lock` updated
alongside).

### 2. Function signatures (`src/nkmodel/network.py`)

```python
import random

import networkx as nx

from nkmodel.config import NKConfig


def ring(a: int) -> nx.Graph: ...
def ring_lattice(a: int, k: int) -> nx.Graph: ...
def watts_strogatz(a: int, k: int, p: float, rng: random.Random | None = None) -> nx.Graph: ...
def random_regular(a: int, degree: int, rng: random.Random | None = None) -> nx.Graph: ...
def complete(a: int) -> nx.Graph: ...


def build_network(config: NKConfig, rng: random.Random | None = None) -> nx.Graph: ...
```

Parameter names are lowercase (`a`, `k`, `p`) rather than `spec.md`'s `A`/`k`/`p`
notation, to satisfy `pep8-naming` (`N803`) already enforced in `pyproject.toml`'s
ruff config — same reasoning that keeps `NKConfig`'s fields uppercase (class
attributes, not function args) while function locals stay lowercase.

### 3. NetworkX API per builder

- `ring(a)` → `nx.watts_strogatz_graph(a, 2, 0)` — degree-2 cycle, i.e.
  `ring_lattice(a, 2)`. (Equivalent to `nx.cycle_graph(a)`; using
  `watts_strogatz_graph` with `p=0` keeps `ring` expressed in terms of
  `ring_lattice` per `build-spec.md` §8's grouping of the two.)
- `ring_lattice(a, k)` → `nx.watts_strogatz_graph(a, k, 0)` — the base lattice
  (each node wired to its `k` nearest neighbors), no rewiring.
- `watts_strogatz(a, k, p, rng)` → `nx.watts_strogatz_graph(a, k, p, seed=rng)`.
- `random_regular(a, degree, rng)` → `nx.random_regular_graph(degree, a,
  seed=rng)`.
- `complete(a)` → `nx.complete_graph(a)`.

NetworkX's `seed=` parameter accepts `None`, an `int`, or a `random.Random`
instance directly (`networkx.utils.decorators.py_random_state`) — so builders
just forward the caller's `rng` unchanged; no manual seed-to-Random conversion
needed.

### 4. `build_network` dispatch

```python
def build_network(config: NKConfig, rng: random.Random | None = None) -> nx.Graph:
    if config.topology == "ring":
        return ring(config.A)
    if config.topology == "ws":
        return watts_strogatz(config.A, config.ws_k, config.ws_p, rng)
    if config.topology == "random_regular":
        return random_regular(config.A, config.degree, rng)
    return complete(config.A)  # config.topology == "complete"
```

`config.topology` is a `Literal["ring", "ws", "random_regular", "complete"]`
(already enforced by `NKConfig`, issue #6), so the four branches are exhaustive —
no `else: raise` needed, and no re-validation of `topology` here (criterion 4).
`ring_lattice` has no matching `config.topology` value (config exposes no
"ring degree" knob beyond `ws_k`/`degree`, which belong to `ws`/`random_regular`)
— it stays a standalone builder for direct use/tests, not wired into the
dispatcher, matching how the issue lists it as a sibling of `ring` rather than a
dispatch target.

### 5. Reproducibility / seeding approach

`build_network(config, rng)` takes an already-constructed `rng` (a
`random.Random`, e.g. `random.Random(config.seed)` built by the caller — `Model`
in a later issue). Tests exercise this directly:

```python
rng1 = random.Random(seed)
rng2 = random.Random(seed)
g1 = build_network(config, rng1)
g2 = build_network(config, rng2)
assert sorted(g1.edges()) == sorted(g2.edges())
```

Two independent `random.Random(seed)` instances with the same seed drive
`nx.watts_strogatz_graph`/`nx.random_regular_graph` to identical edge sets
(verified against the installed `networkx==3.6.1` in this repo's `.venv`) — so
the test asserts exact edge-set equality, a strictly stronger and simpler check
than isomorphism. `ring`/`complete` are deterministic in `a` alone, so the same
assertion holds trivially for them too.

### 6. Structural assertions used per topology

- **`ring`**: `nx.is_connected(g)` and every node has degree 2 (a simple cycle).
- **`ring_lattice(a, k)`**: `nx.is_connected(g)` and every node has degree `k`
  (verified for `k=4` on `a=10`).
- **`complete`**: `g.number_of_edges() == a * (a - 1) // 2`.
- **`random_regular`**: every node has degree `== degree` (`nx.random_regular_graph`
  is exactly, not just approximately, regular by construction; test parameters
  are chosen so `a * degree` is even, since NetworkX raises otherwise — that
  parity constraint is a caller/config concern, not something this builder
  re-validates, consistent with criterion 4's scoping).
- **`watts_strogatz`**: `g.number_of_nodes() == a` and, for `p ∈ {0, 0.1, 0.5,
  1.0}`, `g.number_of_edges() == a * k // 2` — NetworkX's rewiring replaces
  edge endpoints but never changes the total edge count, so this count is the
  stable signature of "base degree `k` before rewiring" regardless of `p`.

### 7. Test file skeleton (`tests/test_network.py`)

All tests `@pytest.mark.unit`. No stub is written for `src/nkmodel/network.py` in
this PR — the whole module is absent until Build, so every test below fails at
**collection** (`ModuleNotFoundError: No module named 'nkmodel.network'`), the
same precedent issue #6 established (see its plan commit message). Build's job
is to make these pass.

```python
import random

import networkx as nx
import pytest

from nkmodel.config import NKConfig
from nkmodel.network import (
    build_network,
    complete,
    random_regular,
    ring,
    ring_lattice,
    watts_strogatz,
)

A = 10


@pytest.mark.unit
@pytest.mark.parametrize(
    ("builder", "kwargs"),
    [
        pytest.param(ring, {}, id="ring"),
        pytest.param(ring_lattice, {"k": 4}, id="ring_lattice"),
        pytest.param(watts_strogatz, {"k": 4, "p": 0.1}, id="watts_strogatz"),
        pytest.param(random_regular, {"degree": 4}, id="random_regular"),
        pytest.param(complete, {}, id="complete"),
    ],
)
def test_builder_returns_graph_with_a_nodes(builder, kwargs): ...


@pytest.mark.unit
def test_ring_is_connected_two_regular_cycle(): ...


@pytest.mark.unit
def test_ring_lattice_is_connected_k_regular(): ...


@pytest.mark.unit
def test_complete_has_full_edge_count(): ...


@pytest.mark.unit
def test_random_regular_is_degree_regular(): ...


@pytest.mark.unit
@pytest.mark.parametrize("p", [0, 0.1, 0.5, 1.0])
def test_watts_strogatz_preserves_base_edge_count_across_p(p): ...


@pytest.mark.unit
@pytest.mark.parametrize("topology", ["ring", "ws", "random_regular", "complete"])
def test_build_network_reproducible(topology): ...


@pytest.mark.unit
@pytest.mark.parametrize("topology", ["ring", "ws", "random_regular", "complete"])
def test_build_network_dispatches_to_matching_builder(topology): ...
```

(Actual file has full bodies — see the committed `tests/test_network.py`.)

### 8. Out of scope for this issue

- Re-validating `topology` (already `pydantic.ValidationError` at `NKConfig`
  load, issue #6).
- Anything consuming the returned `nx.Graph` (`Model`, issue #11) — this issue
  only builds the graph.
