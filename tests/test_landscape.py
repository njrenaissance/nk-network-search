import itertools
import random

import pytest

from nkmodel.landscape import NKLandscape

# ---------------------------------------------------------------------------
# Helpers (not tests themselves)
# ---------------------------------------------------------------------------


def _hill_climb(landscape: NKLandscape, start: tuple[int, ...]) -> list[int]:
    """Greedy one-bit hill-climb: repeatedly accept the first strictly-improving
    single-bit flip until none remains."""
    current = list(start)
    improved = True
    while improved:
        improved = False
        current_fitness = landscape.fitness(current)
        for i in range(len(current)):
            candidate = list(current)
            candidate[i] ^= 1
            if landscape.fitness(candidate) > current_fitness:
                current = candidate
                current_fitness = landscape.fitness(candidate)
                improved = True
                break
    return current


def _all_strings(n: int) -> list[tuple[int, ...]]:
    return list(itertools.product((0, 1), repeat=n))


# ---------------------------------------------------------------------------
# AC1 — fitness(string) is the mean of the N per-locus contributions, in [0, 1)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fitness_equals_mean_of_locus_contributions():
    n, k = 5, 2
    landscape = NKLandscape(n, k, "adjacent", random.Random(7))
    string = [1, 0, 1, 1, 0]

    expected = sum(landscape.contribution(i, string) for i in range(n)) / n

    assert landscape.fitness(string) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "string",
    [
        pytest.param([0, 0, 0, 0, 0], id="all_zeros"),
        pytest.param([1, 1, 1, 1, 1], id="all_ones"),
        pytest.param([1, 0, 1, 0, 1], id="alternating"),
    ],
)
def test_fitness_in_unit_interval(string):
    landscape = NKLandscape(5, 2, "adjacent", random.Random(7))

    assert 0.0 <= landscape.fitness(string) < 1.0


# ---------------------------------------------------------------------------
# AC2 — contribution(locus, string) depends only on locus's own bit + its K
# partners' bits
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("scheme", ["adjacent", "random"])
def test_contribution_depends_only_on_own_and_partner_bits(scheme):
    n, k, locus = 6, 2, 2
    landscape = NKLandscape(n, k, scheme, random.Random(1))
    relevant = {locus, *landscape.partners[locus]}
    base = [0, 1, 0, 1, 1, 0]
    other = [bit ^ (0 if i in relevant else 1) for i, bit in enumerate(base)]

    assert other != base  # sanity: the two strings genuinely differ outside the window
    assert landscape.contribution(locus, base) == landscape.contribution(locus, other)


@pytest.mark.unit
@pytest.mark.parametrize("scheme", ["adjacent", "random"])
def test_flipping_bit_outside_window_leaves_contribution_unchanged(scheme):
    n, k, locus = 6, 2, 2
    landscape = NKLandscape(n, k, scheme, random.Random(1))
    relevant = {locus, *landscape.partners[locus]}
    base = [0, 1, 0, 1, 1, 0]
    baseline = landscape.contribution(locus, base)

    for i in range(n):
        if i in relevant:
            continue
        flipped = list(base)
        flipped[i] ^= 1
        assert landscape.contribution(locus, flipped) == baseline


# ---------------------------------------------------------------------------
# AC3 — reproducibility: same seed => identical fitness; lazy-cache and
# pre-filled constructions agree value-for-value
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_same_seed_yields_identical_fitness():
    n, k, scheme = 8, 3, "adjacent"
    string = [1, 0, 1, 1, 0, 0, 1, 0]
    landscape_a = NKLandscape(n, k, scheme, random.Random(42))
    landscape_b = NKLandscape(n, k, scheme, random.Random(42))

    assert landscape_a.fitness(string) == landscape_b.fitness(string)


@pytest.mark.unit
def test_lazy_and_prefilled_constructions_agree():
    n, k, scheme, seed = 4, 2, "adjacent", 123
    lazy = NKLandscape(n, k, scheme, random.Random(seed))
    prefilled = NKLandscape(n, k, scheme, random.Random(seed))
    for bits in _all_strings(n):
        prefilled.fitness(list(bits))  # exhaustively visit every (locus, key) cell

    target = [1, 0, 1, 1]

    assert lazy.fitness(target) == prefilled.fitness(target)
    for locus in range(n):
        assert lazy.contribution(locus, target) == prefilled.contribution(locus, target)


# ---------------------------------------------------------------------------
# AC4 — K=0 is single-peaked: exactly one global optimum; greedy one-bit
# hill-climbing from any starting string reaches it
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_k_zero_has_exactly_one_global_optimum():
    n = 4
    landscape = NKLandscape(n, 0, "adjacent", random.Random(99))
    fitnesses = {bits: landscape.fitness(list(bits)) for bits in _all_strings(n)}
    best = max(fitnesses.values())

    winners = [bits for bits, value in fitnesses.items() if value == best]

    assert len(winners) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "start",
    _all_strings(4),
    ids=["".join(map(str, s)) for s in _all_strings(4)],
)
def test_k_zero_greedy_hill_climbing_reaches_global_optimum(start):
    n = 4
    landscape = NKLandscape(n, 0, "adjacent", random.Random(99))
    fitnesses = {bits: landscape.fitness(list(bits)) for bits in _all_strings(n)}
    optimum = list(max(fitnesses, key=lambda bits: fitnesses[bits]))

    climbed = _hill_climb(landscape, start)

    assert climbed == optimum
