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
def test_builder_returns_graph_with_a_nodes(builder, kwargs):
    graph = builder(A, **kwargs)

    assert graph.number_of_nodes() == A


@pytest.mark.unit
def test_ring_is_connected_two_regular_cycle():
    graph = ring(A)

    assert nx.is_connected(graph)
    assert all(degree == 2 for _, degree in graph.degree())


@pytest.mark.unit
def test_ring_lattice_is_connected_k_regular():
    k = 4
    graph = ring_lattice(A, k)

    assert nx.is_connected(graph)
    assert all(degree == k for _, degree in graph.degree())


@pytest.mark.unit
def test_complete_has_full_edge_count():
    graph = complete(A)

    assert graph.number_of_edges() == A * (A - 1) // 2


@pytest.mark.unit
def test_random_regular_is_degree_regular():
    degree = 4
    graph = random_regular(A, degree, rng=random.Random(0))

    assert all(node_degree == degree for _, node_degree in graph.degree())


@pytest.mark.unit
@pytest.mark.parametrize("p", [0, 0.1, 0.5, 1.0])
def test_watts_strogatz_preserves_base_edge_count_across_p(p):
    k = 4
    graph = watts_strogatz(A, k, p, rng=random.Random(0))

    assert graph.number_of_nodes() == A
    assert graph.number_of_edges() == A * k // 2


def _config_for(topology: str) -> NKConfig:
    return NKConfig(A=A, topology=topology, ws_k=4, ws_p=0.3, degree=4)


@pytest.mark.unit
@pytest.mark.parametrize("topology", ["ring", "ws", "random_regular", "complete"])
def test_build_network_reproducible(topology):
    config = _config_for(topology)

    graph_1 = build_network(config, rng=random.Random(42))
    graph_2 = build_network(config, rng=random.Random(42))

    assert sorted(graph_1.edges()) == sorted(graph_2.edges())


@pytest.mark.unit
@pytest.mark.parametrize(
    ("topology", "expected_direct_graph"),
    [
        pytest.param("ring", lambda: ring(A), id="ring"),
        pytest.param("ws", lambda: watts_strogatz(A, 4, 0.3, rng=random.Random(7)), id="ws"),
        pytest.param("random_regular", lambda: random_regular(A, 4, rng=random.Random(7)), id="random_regular"),
        pytest.param("complete", lambda: complete(A), id="complete"),
    ],
)
def test_build_network_dispatches_to_matching_builder(topology, expected_direct_graph):
    config = _config_for(topology)

    dispatched = build_network(config, rng=random.Random(7))
    direct = expected_direct_graph()

    assert sorted(dispatched.edges()) == sorted(direct.edges())
    assert dispatched.number_of_nodes() == A
