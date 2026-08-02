"""Model — the synchronous turn loop over landscape + agents + network + metrics.

Owns an `NKLandscape` (#7), a list of `Agent`s (#9), a `networkx` graph (#8),
and a `MetricsSeries` (#10); a run is fully determined by `(config, seed)`. See
`spec/issues/11-plan.md` for the design this module satisfies.

Reproducibility rests on the constructor deriving one child RNG per source of
randomness (landscape, network, initial strings, explore flips) from a single
master `random.Random(seed)`, so the whole run is a pure function of
`(config, seed)` while each stream stays independent of the others. Each turn is
a synchronous snapshot -> decide -> commit: every agent decides against the
start-of-turn snapshot, and no agent sees another's mid-turn move until the next
step.
"""

from __future__ import annotations

import random

from nkmodel.agent import Agent
from nkmodel.config import NKConfig
from nkmodel.landscape import NKLandscape
from nkmodel.metrics import MetricsRow, MetricsSeries
from nkmodel.network import build_network


class Model:
    """Owns the landscape, agents, graph, and metrics; runs synchronous turns.

    A run is fully determined by `(config, seed)`. See `spec/issues/11-plan.md`
    for the construction, turn-loop, and reproducibility design.
    """

    def __init__(self, config: NKConfig, seed: int) -> None:
        """Build the landscape, agents (uids ``0..A-1``), network, and metrics
        series deterministically from ``(config, seed)``.

        A single master `random.Random(seed)` seeds one independent child RNG per
        source of randomness so that, e.g., changing ``N`` does not shift the
        network draw — this per-concern seeding is what makes a run reproducible
        from ``(config, seed)`` alone.
        """
        self.config = config
        self.seed = seed

        master = random.Random(seed)
        self.landscape = NKLandscape(config.N, config.K, config.scheme, rng=random.Random(master.getrandbits(64)))
        self.graph = build_network(config, rng=random.Random(master.getrandbits(64)))
        initial_string_rng = random.Random(master.getrandbits(64))
        self.agents = [
            Agent(uid=uid, string=[initial_string_rng.randrange(config.B) for _ in range(config.N)])
            for uid in range(config.A)
        ]
        self.rng = random.Random(master.getrandbits(64))  # shared explore RNG
        self.metrics = MetricsSeries()

    def _neighbor_states(self, uid: int, snapshot: dict[int, list[int]]) -> list[list[int]]:
        """Start-of-turn strings of ``uid``'s graph neighbors, in ascending-uid
        order — the contract #9's `Agent.decide` relies on so its stable `max`
        copies the lowest-uid neighbor among several tied for best.
        """
        return [snapshot[neighbor_uid] for neighbor_uid in sorted(self.graph.neighbors(uid))]

    def step(self) -> MetricsRow:
        """Advance one synchronous turn: snapshot every agent's string, decide
        each against the snapshot of its graph neighbors, commit all moves
        simultaneously, then record and return exactly one metrics row.

        Decisions read only the start-of-turn ``snapshot``; commits happen after
        every agent has decided, so a move made this turn is invisible to the
        other agents until the next one (synchronous, not sequential).
        """
        snapshot = {agent.uid: list(agent.string) for agent in self.agents}
        next_strings = {
            agent.uid: agent.decide(self._neighbor_states(agent.uid, snapshot), self.landscape, self.rng)
            for agent in self.agents
        }
        for agent in self.agents:
            agent.string = next_strings[agent.uid]
        return self.metrics.record([agent.string for agent in self.agents], self.landscape)

    def run(self) -> MetricsSeries:
        """Run ``config.steps`` synchronous turns and return the metrics series."""
        for _ in range(self.config.steps):
            self.step()
        return self.metrics
