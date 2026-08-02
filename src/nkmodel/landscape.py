"""NKLandscape — per-locus contribution tables and the NK fitness function.

Implements the NK fitness model (Kauffman & Levin): `N` loci, each contributing
a fitness component drawn from a `2^(K+1)`-entry table keyed by its own bit and
its `K` "partner" loci's bits. Overall `fitness` is the mean of the `N` per-locus
contributions. See `spec/issues/7-plan.md` for the design this satisfies.
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

        self.partners: list[list[int]] = self._build_partners()
        self._locus_seeds: list[int] = [self.rng.getrandbits(64) for _ in range(self.N)]
        self._tables: dict[int, list[float]] = {}

    def _build_partners(self) -> list[list[int]]:
        if self.scheme == "adjacent":
            return [[(i + d) % self.N for d in range(1, self.K + 1)] for i in range(self.N)]
        return [self.rng.sample([j for j in range(self.N) if j != i], self.K) for i in range(self.N)]

    def _row(self, locus: int) -> list[float]:
        if locus not in self._tables:
            row_rng = random.Random(self._locus_seeds[locus])
            self._tables[locus] = [row_rng.random() for _ in range(2 ** (self.K + 1))]
        return self._tables[locus]

    def _key(self, locus: int, string: Sequence[int]) -> int:
        bits = [string[locus], *(string[p] for p in self.partners[locus])]
        key = 0
        for bit in bits:
            key = (key << 1) | bit
        return key

    def contribution(self, locus: int, string: Sequence[int]) -> float:
        return self._row(locus)[self._key(locus, string)]

    def fitness(self, string: Sequence[int]) -> float:
        return sum(self.contribution(i, string) for i in range(self.N)) / self.N
