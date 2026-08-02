# Plan — Issue #6: NKConfig settings (`config.py`)

**Status of this document.** Planning-only. No production code in this PR — per
`.claude/standards/testing.md`, tests are written and agreed *before*
implementation; this plan proposes the test list first, then the implementation
approach that satisfies it. Comment `/approve` on this PR to begin the Build
stage (Build writes `tests/test_config.py` + `src/nkmodel/config.py` to satisfy
the acceptance criteria below).

Refs #6. Scope, acceptance criteria: `spec/spec.md` → "Inputs / Outputs" and "Done
criteria → Config"; `spec/build-spec.md` §10; house convention:
`.claude/standards/configuration.md`.

## 1. Fields, types, defaults

One `DEFAULTS: dict[str, Any]` dict is the single source of truth (per
`.claude/standards/configuration.md`); every `NKConfig` field references it as its
default, so `NKConfig()` with no overrides equals `DEFAULTS`.

| Field | Type | Default (from `DEFAULTS`) | Notes |
|---|---|---|---|
| `N` | `int` | `20` | string length / loci |
| `K` | `int` | `5` | interacting partners per locus, `0 … N-1` |
| `B` | `int` | `2` | values per locus; binary is the built target |
| `scheme` | `Literal["adjacent", "random"]` | `"adjacent"` | which K partners each locus reads |
| `A` | `int` | `100` | number of agents |
| `topology` | `Literal["ring", "ws", "random_regular", "complete"]` | `"complete"` | network topology |
| `ws_k` | `int` | `4` | Watts–Strogatz base degree |
| `ws_p` | `float` | `0.1` | Watts–Strogatz rewiring probability |
| `degree` | `int` | `4` | degree for `random_regular` |
| `steps` | `int` | `300` | synchronous turns per run |
| `replications` | `int` | `50` | runs to average over |
| `seed` | `int` | `0` | master RNG seed |

`scheme` and `topology` are `Literal`-typed (not plain `str`) so an out-of-set
value fails loudly at load time via `pydantic.ValidationError`, per
`configuration.md`'s guidance on enumerated knobs.

```python
class NKConfig(BaseSettings):
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
```

No secrets here (no `SecretStr` fields needed) — this is all non-sensitive
simulation config.

## 2. `get_config()` singleton

```python
from functools import lru_cache


@lru_cache
def get_config() -> NKConfig:
    """The one cached config instance — import this, don't re-instantiate."""
    return NKConfig()
```

Matches `configuration.md`'s "instantiate `Settings` exactly once" guidance.
Sweeps (later issues) build explicit per-cell configs directly via
`NKConfig(**{**DEFAULTS, "K": 10, "topology": "ring"})`, bypassing the cached
singleton — that call path is out of scope for this issue, just noting it's not
blocked by this design.

## 3. `.env.example`

A new file at repo root listing every `NK_*` variable with its placeholder
(default) value, per `configuration.md`:

```dotenv
NK_N=20
NK_K=5
NK_B=2
NK_SCHEME=adjacent
NK_A=100
NK_TOPOLOGY=complete
NK_WS_K=4
NK_WS_P=0.1
NK_DEGREE=4
NK_STEPS=300
NK_REPLICATIONS=50
NK_SEED=0
```

`.env` itself is already git-ignored per the scaffold; no change needed there.

## 4. Test plan — `tests/test_config.py` (all `@pytest.mark.unit`)

Each test maps to one acceptance criterion in issue #6 / `spec.md`'s Config Done
criteria:

| Test | Acceptance criterion covered |
|---|---|
| `test_defaults_populate_every_field` — `NKConfig()` field-by-field equals `DEFAULTS` | "`NKConfig()` populates every field from `DEFAULTS`" |
| `test_get_config_returns_cached_singleton` — `get_config() is get_config()` | "`get_config()` returns the same cached object on repeated calls" |
| `test_invalid_k_raises` (parametrized: non-numeric string, `None`) — constructing `NKConfig(K=...)` raises `pydantic.ValidationError` | "non-numeric `K` … raises `pydantic.ValidationError`" |
| `test_invalid_scheme_raises` — `NKConfig(scheme="bogus")` raises `pydantic.ValidationError` | "`scheme` … outside its allowed set, raises `pydantic.ValidationError`" |
| `test_invalid_topology_raises` — `NKConfig(topology="bogus")` raises `pydantic.ValidationError` | "`topology` outside its allowed set, raises `pydantic.ValidationError`" |
| `test_env_var_overrides_default` — with `monkeypatch.setenv("NK_SEED", "7")`, `get_config.cache_clear()` then `get_config().seed == 7` | "With `NK_SEED=7` in the environment, `get_config().seed == 7`" |
| `test_real_env_var_takes_precedence_over_dotenv` — write a temporary `.env` with `NK_SEED=3`, set real env `NK_SEED=7` (via `monkeypatch.setenv`), assert resulting `seed == 7` | "a real env var takes precedence over the same key in `.env`" |

Use `pytest-mock`'s `mocker`/pytest's built-in `monkeypatch` fixture for env var
manipulation (no manual `os.environ` mutation), per `.claude/standards/testing.md`
and `.claude/rules/pytest-rules.md`. `get_config` being `lru_cache`d means tests
that vary the environment must call `get_config.cache_clear()` before/after to
avoid cross-test leakage — call this out explicitly in a fixture (e.g. an
autouse fixture in `test_config.py` that clears the cache before each test).

## 5. Out of scope for this issue

- Building `NKLandscape`/`network`/sweep logic that *consumes* `NKConfig` — later
  issues (#7, #8, #12).
- Nested `BaseSettings` sections — `configuration.md` recommends nesting for
  large configs, but `build-spec.md` §10 and this flat 12-field knob set are
  small enough to stay a single flat class (matches `build-spec.md`'s explicit
  note: "kept flat … revisit nesting if the knob count grows").
