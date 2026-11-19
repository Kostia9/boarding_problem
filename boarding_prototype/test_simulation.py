"""Run with `pytest`."""

from copy import copy

import numpy as np
import pytest

from boarding import Aircraft, STRATEGIES, Simulation, State

IN_AISLE = (State.WALKING, State.BLOCKED, State.STOWING)


def steps(sim):
    """Yield after every step until boarding is finished."""
    while not sim.finished:
        sim.step()
        yield


@pytest.mark.parametrize("name", STRATEGIES)
def test_everyone_reaches_their_seat(name):
    sim = Simulation(STRATEGIES[name])
    sim.run()
    for p in sim.passengers:
        assert p.state is State.SEATED and p.current_position == p.target_row


@pytest.mark.parametrize("name", STRATEGIES)
def test_aisle_rules(name):
    sim = Simulation(STRATEGIES[name])
    entry_rank = {p.id: i for i, p in enumerate(sim.entry_order)}
    previous = {p.id: 0 for p in sim.passengers}
    for _ in steps(sim):
        # one passenger per cell, and whoever entered earlier is further down the aisle
        line = sorted((p for p in sim.passengers if p.state in IN_AISLE), key=lambda p: entry_rank[p.id])
        positions = [p.current_position for p in line]
        assert positions == sorted(set(positions), reverse=True)
        # at most one cell forward per step, never past their own row
        for p in sim.passengers:
            assert 0 <= p.current_position - previous[p.id] <= 1
            assert p.current_position <= p.target_row
            previous[p.id] = p.current_position


def test_same_seed_same_result():
    random = STRATEGIES["Random"]
    assert Simulation(random, seed=7).run() == Simulation(random, seed=7).run()


def test_known_boarding_times():
    times = {name: Simulation(strategy).run() for name, strategy in STRATEGIES.items()}
    assert times == {"Front-to-back": 430, "Back-to-front": 367, "Random": 209,
                     "Row-cycling": 97, "Outside-in": 259}


@pytest.mark.parametrize("order", [lambda ps: ps[:-1], lambda ps: [ps[0]] * len(ps),
                                   lambda ps: list(map(copy, ps))])
def test_invalid_order(order):
    with pytest.raises(ValueError):
        Simulation(lambda ps, rng: order(ps))


def test_in_place_strategy():
    def reverse(ps, rng):
        ps.reverse()
        return ps

    sim = Simulation(reverse, Aircraft(1, "AB"))
    assert [p.id for p in sim.passengers] == [0, 1]
    assert [p.id for p in sim.entry_order] == [1, 0]


@pytest.mark.parametrize("stow, seat", [(1.5, 0), (0, 0), (-1, 2)])
def test_invalid_fixed_times(stow, seat):
    with pytest.raises(ValueError):
        Simulation(STRATEGIES["Front-to-back"], Aircraft(1, "A"),
                   stow_time=stow, seat_time=seat).step()


def test_custom_time_must_be_whole():
    class FractionalTime(Simulation):
        def time_at_row(self, passenger):
            return 1.5

    with pytest.raises(ValueError):
        FractionalTime(STRATEGIES["Front-to-back"], Aircraft(1, "A")).step()


def test_numpy_times():
    sim = Simulation(STRATEGIES["Front-to-back"], Aircraft(1, "A"),
                     stow_time=np.uint8(200), seat_time=np.uint8(100))
    assert sim.run() == 301


def test_row_cycling_uses_cabin_order():
    sim = Simulation(STRATEGIES["Row-cycling"], Aircraft(2, "QXWZKJ"))
    assert [p.seat_label for p in sim.entry_order] == [
        f"{row}{seat}" for seat in "QXWZKJ" for row in (2, 1)]
