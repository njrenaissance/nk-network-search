# nk-network-search

A simulation of **networked search on an NK fitness landscape**, reimplementing
Lazer & Friedman (2007): `A` agents, wired together by a configurable network
topology, all search one shared, static [NK
landscape](https://en.wikipedia.org/wiki/NK_model) (Kauffman) under an
exploit-or-explore rule. The goal is to observe how network connectivity trades
short-run collective performance against long-run performance.

It is a small, fully typed Python package (`nkmodel`) built on
[`networkx`](https://networkx.org/) and managed with
[uv](https://docs.astral.sh/uv/).

## What's in the model

| Module | Responsibility |
| --- | --- |
| `nkmodel/landscape.py` | `NKLandscape` — per-locus contribution tables and the NK fitness function |
| `nkmodel/agent.py` | `Agent` — holds a candidate string; the exploit/explore turn decision |
| `nkmodel/network.py` | Topology builders (`ring`, `watts_strogatz`, `random_regular`, `complete`) + `build_network()` |
| `nkmodel/config.py` | `NKConfig` (`pydantic-settings`) + the cached `get_config()` accessor |

The experiment's design and acceptance criteria live in [`spec/`](spec/)
(`spec.md`, `build-spec.md`, `build-order.md`, and per-issue plans under
`spec/issues/`). The spec also describes runner scripts (`run.py`, `analysis.py`)
and `model`/`metrics` modules that tie the pieces into a full simulation loop;
those are planned but **not yet implemented** — today the package provides the
building blocks the unit tests assert against.

## Structure

```text
├── src/
│   └── nkmodel/
│       ├── __init__.py
│       ├── config.py      # NKConfig + get_config()
│       ├── landscape.py   # NKLandscape (NK fitness model)
│       ├── network.py     # topology builders + build_network()
│       └── agent.py       # Agent (exploit/explore decision)
├── tests/                 # unit tests mirroring nkmodel/ (plus conftest.py)
├── spec/                  # design notes + acceptance criteria
├── Makefile
└── pyproject.toml
```

## Requirements

- Python **>= 3.14**
- [uv](https://docs.astral.sh/uv/) for dependency management

Runtime dependencies (see `pyproject.toml`): `networkx`, `pydantic-settings`,
`python-dotenv`.

## Setup

This project uses `uv` for package management, linting, and formatting. After
cloning, run setup once — it installs dependencies and the local Git hooks:

```bash
make setup
```

(Equivalent to `uv sync && uv run pre-commit install && uv run pre-commit install --hook-type pre-push`.)

## Configuration

Every simulation knob lives in one settings class, `NKConfig`
(`src/nkmodel/config.py`), built on `pydantic-settings`. Import the cached
`get_config()` accessor rather than instantiating `NKConfig` directly:

```python
from nkmodel.config import get_config

config = get_config()
```

Each value has a default (see `DEFAULTS` in `config.py`) and can be overridden by
an `NK_*` environment variable or a local `.env` file. Real environment variables
(CI, prod) always take precedence over `.env`. Copy the checked-in example to get
started:

```bash
cp .env.example .env
```

| Variable | Meaning | Default |
| --- | --- | --- |
| `NK_N` | string length / number of loci | `20` |
| `NK_K` | interacting partners per locus (landscape ruggedness) | `5` |
| `NK_B` | values per locus (`2` = binary; binary is the built target) | `2` |
| `NK_SCHEME` | which `K` partners each locus reads: `adjacent` or `random` | `adjacent` |
| `NK_A` | number of agents (network nodes) | `100` |
| `NK_TOPOLOGY` | `ring`, `ws`, `random_regular`, or `complete` | `complete` |
| `NK_WS_K` | Watts–Strogatz base degree | `4` |
| `NK_WS_P` | Watts–Strogatz rewiring probability | `0.1` |
| `NK_DEGREE` | degree for the `random_regular` topology | `4` |
| `NK_STEPS` | synchronous turns per run | `300` |
| `NK_REPLICATIONS` | runs to average over | `50` |
| `NK_SEED` | master RNG seed (a run is fully determined by `(config, seed)`) | `0` |

## Usage

There is no top-level runner yet (see the `spec/` note above), so the package is
used as a library. The building blocks compose like this:

```python
import random

from nkmodel.agent import Agent
from nkmodel.config import get_config
from nkmodel.landscape import NKLandscape
from nkmodel.network import build_network

config = get_config()                       # NK_* env vars / .env, else defaults
rng = random.Random(config.seed)            # a run is reproducible from (config, seed)

landscape = NKLandscape(config.N, config.K, config.scheme, rng)
network = build_network(config, rng)        # an A-node graph for config.topology

# One agent per node, each seeded with a random binary string. Drive the
# synchronous exploit/explore turns across the network from here — see spec/
# for the full turn loop and metrics.
agents = {
    node: Agent(node, [rng.randint(0, config.B - 1) for _ in range(config.N)])
    for node in network.nodes
}
```

## Development

Common tasks are wrapped as `make` targets (see the `Makefile`); the raw `uv`
commands they run are shown alongside.

```bash
make test        # uv run pytest
make lint        # uv run ruff check .
make format      # uv run ruff format .
make typecheck   # uv run mypy src
make check       # lint + typecheck + test (all local quality gates)
```

Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy src` before
considering a change done.

## Git hooks

Local quality gates run through the [`pre-commit`](https://pre-commit.com/)
framework (config in `.pre-commit-config.yaml`): `git commit` runs
`ruff format --check`, `ruff check`, and `mypy src`, and `git push` runs
`pytest`. `make setup` (above) installs them. Git can't auto-install hooks on
clone, so this one-time step is how they get wired up — but CI
(`.github/workflows/`) runs the same checks regardless, so it stays the real gate
even when the local hooks aren't installed.

## Staying in sync with the template

This project was generated from the `basic` cookiecutter template and linked to it
with [`cruft`](https://cruft.github.io/cruft/). The link lives in `.cruft.json`
(template URL, the exact template commit, and the answers given at generation) — it
is what lets template improvements be pulled in later instead of the scaffold going
stale. Check whether the template has moved ahead:

```bash
uvx cruft check    # exit 0 = up to date; non-zero = behind
```

The **Template Sync** GitHub Actions workflow runs this check on demand (Actions tab
→ *Template Sync* → *Run workflow*); it is intentionally not part of the PR gate and
never blocks a merge. When the project is behind, run the `update-from-template`
skill (or `uvx cruft update` by hand) to apply the delta, resolve any `*.rej`
conflicts, and re-run the checks. See `.claude/standards/` and
`.claude/skills/update-from-template/` for the agent-run procedure.

## Wiki

Per `.claude/standards/wiki.md`, this project is meant to keep an `openwiki/` folder
of generated codebase documentation (produced by
[OpenWiki](https://www.npmjs.com/package/openwiki)). That folder has **not been
generated yet** — when it is, treat it as generated output (**never hand-edit it**);
regenerate it and commit the result alongside the code change that prompted it, so
the wiki stays in step with `main`.

OpenWiki is a per-machine global CLI, **not** a project dependency (it is never
added to `pyproject.toml`). Install and authenticate it once, then generate:

```bash
npm install -g openwiki    # one-time, per machine
openwiki auth <provider>   # one-time: sets up the LLM provider + API key
openwiki code --init       # first run in a fresh repo
openwiki code --update     # regenerate before committing a change
```

Regenerating calls a paid LLM provider. See `.claude/standards/wiki.md` for the
regenerate-before-commit rule agents follow.
