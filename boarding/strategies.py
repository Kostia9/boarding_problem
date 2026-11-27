"""Boarding strategies: functions that take the passengers and return their entry order.

To add a strategy, write a function `(passengers, rng) -> list` and add it to STRATEGIES.
"""


def front_to_back(passengers, rng):
    return sorted(passengers, key=lambda p: (p.target_row, p.target_seat))


def back_to_front(passengers, rng):
    return sorted(passengers, key=lambda p: (-p.target_row, p.target_seat))


def random_order(passengers, rng):
    order = list(passengers)
    rng.shuffle(order)
    return order


def row_cycling(passengers, rng):
    """Waves of one passenger per row, back to front: seat A of rows 10..1, then B, ..."""
    return sorted(passengers, key=lambda p: (p.seat_index, -p.target_row))


def outside_in(passengers, rng):
    """Window seats first, then middle, then aisle; back to front within each group."""
    return sorted(passengers, key=lambda p: (-p.aisle_distance, -p.target_row))


def steffen(passengers, rng):
    """Steffen (2008): outside-in, and consecutive passengers sit two rows apart.

    Window seats of one side in every second row back to front (10A, 8A, ..., 2A), then the
    other side (10F, ..., 2F), then the remaining rows (9A, ..., 1A, 9F, ..., 1F); then
    middle seats, then aisle seats, in the same pattern.
    """
    last_row = max(p.target_row for p in passengers)
    return sorted(passengers, key=lambda p: (-p.aisle_distance, (last_row - p.target_row) % 2,
                                             p.seat_index, -p.target_row))


def with_noncompliance(order, fraction, rng):
    """Each passenger ignores the strategy with probability `fraction`.

    Passengers who follow it keep their relative order; the others join the queue
    at a uniformly random place. fraction = 0 leaves the order unchanged (and draws
    no random numbers), fraction = 1 gives random boarding.
    """
    if isinstance(fraction, bool) or not 0 <= fraction <= 1:
        raise ValueError(f"Expected a fraction between 0 and 1, got {fraction!r}")
    if fraction == 0:
        return list(order)
    ignores = rng.random(len(order)) < fraction
    queue = [p for p, ignored in zip(order, ignores) if not ignored]
    for p in [p for p, ignored in zip(order, ignores) if ignored]:
        queue.insert(int(rng.integers(len(queue) + 1)), p)
    return queue


STRATEGIES = {
    "Front-to-back": front_to_back,
    "Back-to-front": back_to_front,
    "Random": random_order,
    "Row-cycling": row_cycling,
    "Outside-in": outside_in,
    "Steffen": steffen,
}
