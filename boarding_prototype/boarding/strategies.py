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
    seats_per_row = sum(p.target_row == 1 for p in passengers)
    return sorted(passengers, key=lambda p: (p.id % seats_per_row, -p.target_row))


def outside_in(passengers, rng):
    """Window seats first, then middle, then aisle; back to front within each group."""
    return sorted(passengers, key=lambda p: (-p.aisle_distance, -p.target_row))


STRATEGIES = {
    "Front-to-back": front_to_back,
    "Back-to-front": back_to_front,
    "Random": random_order,
    "Row-cycling": row_cycling,
    "Outside-in": outside_in,
}
