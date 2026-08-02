"""Agent — holds a candidate string; the exploit/explore turn decision.

Implements the per-agent half of the NK networked-search turn: an agent holds
only a candidate solution string, and reads its fitness from the landscape on
demand rather than owning or caching a fitness value independently. See
`spec/issues/9-plan.md` for the design and full acceptance criteria this
module satisfies.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

from nkmodel.landscape import NKLandscape


class Agent:
    """Holds one candidate string; fitness is read from the landscape on
    demand and never owned or copied independently."""

    def __init__(self, uid: int, string: list[int]) -> None:
        self.uid = uid
        self.string = string

    def decide(
        self,
        neighbor_states: Sequence[Sequence[int]],
        landscape: NKLandscape,
        rng: random.Random,
    ) -> list[int]:
        """Return this agent's NEXT string -- a pure function of the
        start-of-turn snapshot (`self.string`, `neighbor_states`). See
        `spec/issues/9-plan.md` for the exploit/explore rule and the
        tie-break convention `neighbor_states` ordering relies on.
        """
        my_fitness = landscape.fitness(self.string)

        best_neighbor = max(neighbor_states, key=landscape.fitness, default=None)
        if best_neighbor is not None and landscape.fitness(best_neighbor) > my_fitness:
            return list(best_neighbor)  # EXPLOIT

        candidate = list(self.string)
        flip_index = rng.randrange(len(candidate))
        candidate[flip_index] ^= 1
        if landscape.fitness(candidate) > my_fitness:
            return candidate  # EXPLORE: accepted
        return list(self.string)  # EXPLORE: rejected
