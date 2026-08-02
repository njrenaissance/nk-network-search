"""Network topology builders — thin wrappers over `networkx` graph generators.

Each builder returns a plain `networkx.Graph` for a given topology; `build_network`
dispatches on `NKConfig.topology` (issue #6) to the matching builder. Seeding is
caller-driven: pass a `random.Random` instance through `rng` for reproducible
results — `networkx` accepts it directly as its `seed=` argument.
"""

import random
from typing import cast

import networkx as nx

from nkmodel.config import NKConfig


def ring(a: int) -> nx.Graph:
    """A degree-2 cycle over `a` nodes."""
    return cast("nx.Graph", nx.watts_strogatz_graph(a, 2, 0))


def ring_lattice(a: int, k: int) -> nx.Graph:
    """The base `k`-regular ring lattice over `a` nodes, no rewiring."""
    return cast("nx.Graph", nx.watts_strogatz_graph(a, k, 0))


def watts_strogatz(a: int, k: int, p: float, rng: random.Random | None = None) -> nx.Graph:
    """A Watts-Strogatz small-world graph: `k`-regular lattice rewired with probability `p`."""
    return cast("nx.Graph", nx.watts_strogatz_graph(a, k, p, seed=rng))


def random_regular(a: int, degree: int, rng: random.Random | None = None) -> nx.Graph:
    """A random `degree`-regular graph over `a` nodes."""
    return cast("nx.Graph", nx.random_regular_graph(degree, a, seed=rng))


def complete(a: int) -> nx.Graph:
    """The complete graph over `a` nodes."""
    return cast("nx.Graph", nx.complete_graph(a))


def build_network(config: NKConfig, rng: random.Random | None = None) -> nx.Graph:
    """Build the network described by `config.topology`, seeded by `rng`."""
    if config.topology == "ring":
        return ring(config.A)
    if config.topology == "ws":
        return watts_strogatz(config.A, config.ws_k, config.ws_p, rng)
    if config.topology == "random_regular":
        return random_regular(config.A, config.degree, rng)
    return complete(config.A)  # config.topology == "complete"
