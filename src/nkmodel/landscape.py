"""NKLandscape — per-locus contribution tables and the NK fitness function.

Stub for issue #7: signatures only, so `tests/test_landscape.py` can import and
run (red) before the Build stage implements the real logic. See
`spec/issues/7-plan.md` for the design this will satisfy.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import Literal


class NKLandscape:
    """NK fitness landscape: N loci, each with a K+1-bit contribution table."""

    def __init__(
        self,
        n: int,
        k: int,
        scheme: Literal["adjacent", "random"] = "adjacent",
        rng: random.Random | None = None,
    ) -> None:
        self.N = n
        self.K = k
        self.scheme = scheme
        self.rng = rng if rng is not None else random.Random()

    def contribution(self, locus: int, string: Sequence[int]) -> float:
        raise NotImplementedError

    def fitness(self, string: Sequence[int]) -> float:
        raise NotImplementedError
