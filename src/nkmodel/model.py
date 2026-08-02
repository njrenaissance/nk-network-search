"""Model — the synchronous turn loop over landscape + agents + network + metrics.

Owns an `NKLandscape` (#7), a list of `Agent`s (#9), a `networkx` graph (#8),
and a `MetricsSeries` (#10); a run is fully determined by `(config, seed)`. See
`spec/issues/11-plan.md` for the design this module satisfies.

Status of this file: signatures-only stub, committed alongside the approved
plan and the locked `tests/test_model.py` red test suite (issue #11). Every
method currently raises `NotImplementedError` so the suite collects but fails
for the right reason -- Build fills in the real logic after human approval of
the plan.
"""

from __future__ import annotations

from nkmodel.config import NKConfig
from nkmodel.metrics import MetricsRow, MetricsSeries


class Model:
    """Owns the landscape, agents, graph, and metrics; runs synchronous turns.

    A run is fully determined by `(config, seed)`. See `spec/issues/11-plan.md`
    for the construction, turn-loop, and reproducibility design.
    """

    def __init__(self, config: NKConfig, seed: int) -> None:
        """Build the landscape, agents (uids ``0..A-1``), network, and metrics
        series deterministically from ``(config, seed)``."""
        raise NotImplementedError

    def step(self) -> MetricsRow:
        """Advance one synchronous turn: snapshot every agent's string, decide
        each against the snapshot of its graph neighbors, commit all moves
        simultaneously, then record exactly one metrics row."""
        raise NotImplementedError

    def run(self) -> MetricsSeries:
        """Run ``config.steps`` synchronous turns and return the metrics series."""
        raise NotImplementedError
