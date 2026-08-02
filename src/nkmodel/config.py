"""NKConfig — the single source of app configuration for the NK experiment.

Every configurable knob for the simulation (landscape shape, network topology,
run length, RNG seed, ...) is read through `NKConfig`, sourced from `DEFAULTS`
and overridable via `NK_*` environment variables or a `.env` file. Import
`get_config()` rather than instantiating `NKConfig` directly, per
`.claude/standards/configuration.md`.
"""

from functools import lru_cache
from typing import Any, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULTS: dict[str, Any] = {
    "N": 20,
    "K": 5,
    "B": 2,
    "scheme": "adjacent",
    "A": 100,
    "topology": "complete",
    "ws_k": 4,
    "ws_p": 0.1,
    "degree": 4,
    "steps": 300,
    "replications": 50,
    "seed": 0,
}


class NKConfig(BaseSettings):
    """Simulation configuration, overridable via `NK_*` env vars or `.env`."""

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
