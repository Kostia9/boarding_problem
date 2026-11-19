"""Validation tests. Run with `pytest`."""

import pytest

from boarding import STRATEGIES, Aircraft, BoardingStrategy, FixedTiming, Simulation, State

ALL = [cls() for cls in STRATEGIES.values()]
ids = [s.name for s in ALL]


def trace(sim):
    """Yield the simulation after every step until completion."""
    while not sim.finished:
        sim.step()
        assert sim.t < 100_000, "simulation did not terminate"
        yield sim


# ---- the five required checks -------------------------------------------------

@pytest.mark.parametrize("strategy", ALL, ids=ids)
def test_everyone_reaches_assigned_seat(strategy):
    sim = Simulation(strategy)
    sim.run()
    n = sim.aircraft.n_passengers
    assert len(sim.passengers) == n
    assert len({p.seat_label for p in sim.passengers}) == n
    for p in sim.passengers:
        assert p.state is State.SEATED and p.current_position == p.target_row
    assert not sim.queue and all(c is None for c in sim.aisle)


@pytest.mark.parametrize("strategy", ALL, ids=ids)
def test_one_passenger_per_aisle_cell(strategy):
    sim = Simulation(strategy)
    for _ in trace(sim):
        in_aisle = [p for p in sim.passengers if p.in_aisle]
        cells = [p.current_position for p in in_aisle]
        assert len(cells) == len(set(cells))
        assert all(1 <= c <= sim.aircraft.n_rows for c in cells)
        assert all(sim.aisle[p.current_position] is p for p in in_aisle)


@pytest.mark.parametrize("strategy", ALL, ids=ids)
def test_no_overtaking(strategy):
    sim = Simulation(strategy)
    rank = {p.id: i for i, p in enumerate(sim.entry_order)}
    previous = {p.id: 0 for p in sim.passengers}
    for _ in trace(sim):
        # whoever entered earlier is always strictly further down the aisle
        line = sorted((p for p in sim.passengers if p.in_aisle), key=lambda p: rank[p.id])
        positions = [p.current_position for p in line]
        assert positions == sorted(positions, reverse=True)
        # nobody jumps: at most one cell forward per step, never backward or past their row
        for p in sim.passengers:
            assert 0 <= p.current_position - previous[p.id] <= 1
            assert p.current_position <= p.target_row
            previous[p.id] = p.current_position


@pytest.mark.parametrize("strategy", ALL, ids=ids)
def test_deterministic(strategy):
    assert Simulation(strategy, seed=7).run() == Simulation(strategy, seed=7).run()


# ---- known results of the fixed model ---------------------------------------

def test_known_boarding_times():
    # Row-cycling meets the lower bound: cell 1 admits one passenger per second, and a
    # row-1 passenger holds it for 7 s. Best case: the last passenger is from row 1
    # -> 1 + 5*7 + 54*1 = 90 to enter, +7 to sit = 97.
    times = {name: Simulation(cls()).run() for name, cls in STRATEGIES.items()}
    assert times == {"Front-to-back": 430, "Back-to-front": 367, "Random": 209,
                     "Row-cycling": 97, "Outside-in": 259}


def test_random_order_is_a_seeded_permutation():
    def order(seed):
        return [p.id for p in Simulation(STRATEGIES["Random"](), seed=seed).entry_order]
    first = order(1)
    assert sorted(first) == list(range(Aircraft().n_passengers))
    assert first == order(1) and first != order(2)


# ---- extension points work --------------------------------------------------

class SeatInterference(FixedTiming):
    """Example constraint: +2 s per row-mate already seated between the aisle and my seat."""
    def seat_time(self, p, sim):
        blocking = {q.target_seat for q in sim.passengers
                    if q.target_row == p.target_row and q.state is State.SEATED}
        return self.seat + 2 * len(blocking & set(sim.aircraft.seats_between_aisle_and(p.target_seat)))


def test_custom_constraint_only_slows_boarding():
    strategy = STRATEGIES["Back-to-front"]()
    assert Simulation(strategy, timing=SeatInterference()).run() > Simulation(strategy).run()


def test_other_aircraft_size():
    sim = Simulation(STRATEGIES["Front-to-back"](), aircraft=Aircraft(n_rows=4, seats="ABCD"))
    assert sim.run() > 0 and len(sim.passengers) == 16


def test_outside_in_uses_cabin_layout():
    aircraft = Aircraft(n_rows=2, seats="QXWZKJ")
    sim = Simulation(STRATEGIES["Outside-in"](), aircraft=aircraft)
    assert [p.seat_label for p in sim.entry_order] == [
        "2Q", "2J", "1Q", "1J",
        "2X", "2K", "1X", "1K",
        "2W", "2Z", "1W", "1Z",
    ]


def test_seat_offset():
    assert [Aircraft().seat_offset(s) for s in "ABCDEF"] == [3, 2, 1, -1, -2, -3]


def test_seats_between_aisle():
    a = Aircraft()
    assert a.seats_between_aisle_and("A") == ["C", "B"]
    assert a.seats_between_aisle_and("C") == [] == a.seats_between_aisle_and("D")
    assert a.seats_between_aisle_and("F") == ["D", "E"]


def test_invalid_strategy_rejected():
    class Broken(BoardingStrategy):
        def order(self, passengers, rng):
            return passengers[:-1]
    with pytest.raises(ValueError):
        Simulation(Broken())
