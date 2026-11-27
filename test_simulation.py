"""Run with `pytest`."""

from copy import copy

import numpy as np
import pytest

from boarding import Aircraft, STRATEGIES, Simulation, State, monte_carlo

IN_AISLE = (State.WALKING, State.BLOCKED, State.STOWING)
CONFIGS = {"default": {},
           "random stow, 70% full": dict(load_factor=0.7, seed=3),
           "15 x 4 cabin": dict(aircraft=Aircraft(15, "ABCD"))}


def steps(sim):
    """Yield after every step until boarding is finished."""
    while not sim.finished:
        sim.step()
        yield


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", STRATEGIES)
def test_everyone_reaches_their_seat(name, config):
    sim = Simulation(STRATEGIES[name], **CONFIGS[config])
    sim.run()
    for p in sim.passengers:
        assert p.state is State.SEATED and p.current_position == p.target_row


@pytest.mark.parametrize("config", CONFIGS)
@pytest.mark.parametrize("name", STRATEGIES)
def test_aisle_rules(name, config):
    sim = Simulation(STRATEGIES[name], **CONFIGS[config])
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
    assert times == {"Front-to-back": 453, "Back-to-front": 404, "Random": 266,
                     "Row-cycling": 142, "Outside-in": 287, "Steffen": 196}


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


@pytest.mark.parametrize("stow, seat", [(1.5, 0), (0, 2), (-1, 2), (5, -1)])
def test_invalid_times(stow, seat):
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
    assert sim.run() == 1 + int(np.random.default_rng(0).geometric(1 / 200)) + 100


def test_row_cycling_uses_cabin_order():
    sim = Simulation(STRATEGIES["Row-cycling"], Aircraft(2, "QXWZKJ"))
    assert [p.seat_label for p in sim.entry_order] == [
        f"{row}{seat}" for seat in "QXWZKJ" for row in (2, 1)]


def test_random_stow_times():
    sim = Simulation(STRATEGIES["Front-to-back"], Aircraft(100, "ABCDEF"), stow_time=5)
    times = np.array([p.stow_time for p in sim.passengers])
    assert times.min() >= 1 and len(set(times)) > 1
    np.testing.assert_array_equal(times, np.random.default_rng(0).geometric(0.2, size=len(times)))


def test_same_seed_same_passengers_for_every_strategy():
    def passengers(name):
        sim = Simulation(STRATEGIES[name], seed=5, load_factor=0.8)
        return [(p.id, p.stow_time) for p in sim.passengers]

    assert all(passengers(name) == passengers("Random") for name in STRATEGIES)


def test_empty_seats():
    sim = Simulation(STRATEGIES["Random"], load_factor=0.5)
    labels = [p.seat_label for p in sim.passengers]
    assert len(labels) == len(set(labels)) == 30
    assert sim.run() > 0


@pytest.mark.parametrize("load_factor", [0, -0.5, 1.5, 0.001])
def test_invalid_load_factor(load_factor):
    with pytest.raises(ValueError):
        Simulation(STRATEGIES["Random"], load_factor=load_factor)


def test_row_cycling_with_empty_seats():
    sim = Simulation(STRATEGIES["Row-cycling"], load_factor=0.6)
    keys = [(p.seat_index, -p.target_row) for p in sim.entry_order]
    assert keys == sorted(keys)


def test_monte_carlo():
    times = monte_carlo(STRATEGIES["Random"], 5)
    assert len(times) == 5 and len(set(times)) > 1
    assert list(times) == list(monte_carlo(STRATEGIES["Random"], 5))


def test_steffen_order():
    sim = Simulation(STRATEGIES["Steffen"], Aircraft(4, "ABCD"))
    assert " ".join(p.seat_label for p in sim.entry_order) == (
        "4A 2A 4D 2D 3A 1A 3D 1D 4B 2B 4C 2C 3B 1B 3C 1C")


@pytest.mark.parametrize("fraction", [0, 0.5, 1])
def test_noncompliance_changes_only_queue_order(fraction):
    strategy = STRATEGIES["Steffen"]
    settings = dict(seed=42, load_factor=0.75)
    baseline = Simulation(strategy, **settings)
    sim = Simulation(strategy, noncompliance=fraction, **settings)
    assert [(p.seat_label, p.stow_time) for p in sim.passengers] == [
        (p.seat_label, p.stow_time) for p in baseline.passengers]
    order = [p.id for p in sim.entry_order]
    original = [p.id for p in baseline.entry_order]
    assert sorted(order) == sorted(original)
    assert (order == original) == (fraction == 0)
    assert sim.run() > 0


@pytest.mark.parametrize("fraction", [-0.1, 1.1, float("nan"), True])
def test_invalid_noncompliance(fraction):
    with pytest.raises(ValueError):
        Simulation(STRATEGIES["Random"], noncompliance=fraction)


@pytest.mark.parametrize("row", [2, 3])
def test_row_behind_reopens_when_stowing_ends(row):
    sim = Simulation(STRATEGIES["Back-to-front"], Aircraft(row, "A"),
                     stow_time=1, seat_time=2, block_probability=1)
    for _ in range(row):
        sim.step()
    assert sim.aisle[row].state is State.STOWING
    assert sim.aisle[row - 1] is None
    sim.step()
    assert sim.aisle[row].remaining_time == 2
    assert sim.aisle[row - 1] is not None
    assert sim.run() > row


def test_blocking_probability_preserves_seeded_flight():
    settings = dict(seed=7, load_factor=0.8, noncompliance=0.25)
    baseline = Simulation(STRATEGIES["Random"], **settings)
    sim = Simulation(STRATEGIES["Random"], **settings, block_probability=0.5)
    assert [(p.id, p.stow_time) for p in sim.entry_order] == [
        (p.id, p.stow_time) for p in baseline.entry_order]
    assert 0 < sum(p.blocks_behind for p in sim.passengers) < len(sim.passengers)
