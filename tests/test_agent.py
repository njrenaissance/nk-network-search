"""Tests for `nkmodel.agent.Agent` — see `spec/issues/9-plan.md`.

`Agent.decide` is compared against fitness with both `>` (exploit/explore
acceptance) and implicitly `==` (tie rejection). `NKLandscape`'s real
per-locus contributions are continuous draws (`random.Random.random()`), so
two distinct strings landing on an exact tie has probability zero in
practice — several acceptance criteria here are specifically about
tie-handling, which can only be exercised deterministically by controlling
the exact fitness value per string. `_FixedFitnessLandscape` below is a
lightweight fake satisfying the `fitness(string) -> float` protocol
`Agent.decide` depends on; it is not standing in for a landscape that's hard
to construct (`NKLandscape` itself is one line to build) — it's the only way
to engineer an exact tie. The lone-agent hill-climb test (AC7) instead uses
the real `NKLandscape` with `K=0`, since that test only needs genuine
monotonic improvement, not an exact tie.
"""

import itertools
import random
from collections.abc import Sequence

import pytest

from nkmodel.agent import Agent
from nkmodel.landscape import NKLandscape

# ---------------------------------------------------------------------------
# Helpers / fakes (not tests themselves)
# ---------------------------------------------------------------------------


class _FixedFitnessLandscape:
    """Test double for the `landscape.fitness(string) -> float` protocol,
    giving exact, caller-controlled fitness values so tie/strict-beat
    scenarios are deterministic. See module docstring for why a fake is
    needed here instead of the real `NKLandscape`."""

    def __init__(self, fitness_by_string: dict[tuple[int, ...], float]) -> None:
        self._fitness_by_string = fitness_by_string

    def fitness(self, string: Sequence[int]) -> float:
        return self._fitness_by_string[tuple(string)]


def _hamming(a: Sequence[int], b: Sequence[int]) -> int:
    return sum(1 for x, y in zip(a, b, strict=True) if x != y)


def _all_strings(n: int) -> list[tuple[int, ...]]:
    return list(itertools.product((0, 1), repeat=n))


# ---------------------------------------------------------------------------
# AC1 — exploit: a strictly-better neighbor is copied (equal value, distinct
# object)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decide_exploits_strictly_better_neighbor_returns_copy():
    my_string = [0, 0, 0, 0]
    neighbor_string = [1, 1, 1, 1]
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.3,
            tuple(neighbor_string): 0.9,
        }
    )
    agent = Agent(uid=0, string=my_string)

    result = agent.decide([neighbor_string], landscape, random.Random(0))

    assert result == neighbor_string
    assert result is not neighbor_string


# ---------------------------------------------------------------------------
# AC2 — no strictly-better neighbor: decide returns a string at Hamming
# distance <= 1 from the current one (accept or reject the one-bit flip)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    ("flip_fitness", "expected_distance"),
    [
        pytest.param(0.9, 1, id="flip_accepted_strictly_better"),
        pytest.param(0.1, 0, id="flip_rejected_worse"),
    ],
)
def test_decide_without_better_neighbor_stays_within_hamming_distance_one(flip_fitness, expected_distance):
    my_string = [0, 0, 0, 0]
    seed = 0
    flip_index = random.Random(seed).randrange(len(my_string))
    candidate = list(my_string)
    candidate[flip_index] ^= 1
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.5,
            tuple(candidate): flip_fitness,
        }
    )
    agent = Agent(uid=0, string=my_string)

    result = agent.decide([], landscape, random.Random(seed))

    assert _hamming(result, my_string) <= 1
    assert _hamming(result, my_string) == expected_distance


# ---------------------------------------------------------------------------
# AC3 — a one-bit flip that only ties current fitness is rejected: decide
# returns the current string unchanged
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decide_rejects_flip_that_only_ties_current_fitness():
    my_string = [0, 0, 0, 0]
    seed = 0
    flip_index = random.Random(seed).randrange(len(my_string))
    candidate = list(my_string)
    candidate[flip_index] ^= 1
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.5,
            tuple(candidate): 0.5,  # exact tie, not an improvement
        }
    )
    agent = Agent(uid=0, string=my_string)

    result = agent.decide([], landscape, random.Random(seed))

    assert result == my_string


# ---------------------------------------------------------------------------
# AC4 — a neighbor that only ties the agent's fitness does not trigger a copy
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decide_does_not_exploit_neighbor_that_only_ties():
    my_string = [0, 0, 0, 0]
    neighbor_string = [1, 1, 1, 1]
    seed = 0
    flip_index = random.Random(seed).randrange(len(my_string))
    candidate = list(my_string)
    candidate[flip_index] ^= 1
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.5,
            tuple(neighbor_string): 0.5,  # ties -- not "strictly higher"
            tuple(candidate): 0.1,  # explore branch's flip is rejected too
        }
    )
    agent = Agent(uid=0, string=my_string)

    result = agent.decide([neighbor_string], landscape, random.Random(seed))

    assert result != neighbor_string
    assert result == my_string


# ---------------------------------------------------------------------------
# AC5 — several neighbors tied for best, all beating the agent: the copied
# string is the lowest-uid tie-break winner.
#
# `decide` itself only receives raw neighbor strings, not (uid, string)
# pairs -- per spec/issues/9-plan.md, the caller (Model, a later issue) is
# responsible for passing `neighbor_states` in ascending-neighbor-uid order.
# Because Python's `max(..., key=...)` is stable and returns the *first*
# maximal element on ties, passing candidates in ascending-uid order makes
# "first among ties" and "lowest uid among ties" the same thing -- no
# explicit uid bookkeeping needed inside `decide`. This test constructs
# `neighbor_states` in that documented order to exercise exactly that.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decide_tie_break_among_best_neighbors_picks_lowest_uid_by_order():
    my_string = [0, 0, 0, 0]
    lowest_uid_winner = [1, 1, 1, 1]  # uid=1, first among the tied-best
    other_tied_winner = [1, 1, 1, 0]  # uid=2, ties for best but listed later
    non_winner = [1, 0, 0, 0]  # uid=3, beats the agent but not tied for best
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.1,
            tuple(lowest_uid_winner): 0.9,
            tuple(other_tied_winner): 0.9,
            tuple(non_winner): 0.5,
        }
    )
    agent = Agent(uid=0, string=my_string)
    # Ascending-uid order: uid 1, then uid 2, then uid 3.
    neighbor_states = [lowest_uid_winner, other_tied_winner, non_winner]

    result = agent.decide(neighbor_states, landscape, random.Random(0))

    assert result == lowest_uid_winner
    assert result is not lowest_uid_winner


# ---------------------------------------------------------------------------
# AC6 — decide is pure: mutates neither self.string nor any argument
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decide_does_not_mutate_self_string_or_arguments():
    my_string = [0, 0, 0, 0]
    neighbor_string = [1, 1, 0, 0]
    seed = 0
    flip_index = random.Random(seed).randrange(len(my_string))
    candidate = list(my_string)
    candidate[flip_index] ^= 1
    landscape = _FixedFitnessLandscape(
        {
            tuple(my_string): 0.5,
            tuple(neighbor_string): 0.2,  # below my fitness -- no exploit
            tuple(candidate): 0.9,  # explore branch accepts this flip
        }
    )
    agent = Agent(uid=0, string=my_string)
    my_string_before = list(my_string)
    neighbor_string_before = list(neighbor_string)
    neighbor_states = [neighbor_string]

    agent.decide(neighbor_states, landscape, random.Random(seed))

    assert agent.string == my_string_before
    assert agent.string is my_string  # same object, never reassigned
    assert neighbor_states[0] == neighbor_string_before
    assert neighbor_states[0] is neighbor_string


# ---------------------------------------------------------------------------
# AC7 — lone agent (no neighbors) climbs by single-bit flips and, once at a
# local optimum, returns its own string unchanged on every later step
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_lone_agent_climbs_then_halts_at_local_optimum():
    n = 4
    landscape = NKLandscape(n, 0, "adjacent", random.Random(99))
    fitnesses = {bits: landscape.fitness(list(bits)) for bits in _all_strings(n)}
    optimum = list(max(fitnesses, key=lambda bits: fitnesses[bits]))
    agent = Agent(uid=0, string=[1, 1, 0, 0])
    rng = random.Random(7)

    for _ in range(200):
        agent.string = agent.decide([], landscape, rng)

    assert agent.string == optimum

    # Steady state: once at the optimum, every later step is a no-op.
    for _ in range(5):
        next_string = agent.decide([], landscape, rng)
        assert next_string == agent.string
        agent.string = next_string
