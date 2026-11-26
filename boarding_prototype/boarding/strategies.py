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


# --- Zone policies ------------------------------------------------------------
# Airlines call groups (zones) one after another; inside a zone the order is random.
# This is the book's model of a policy (Bachmat, Def. 3.4.1): it fixes which zone a
# passenger is in, not their exact place in the queue.

def _n_rows(passengers):
    return max(p.target_row for p in passengers)


def _section_from_back(row, n_rows, n_sections):
    """0 for the last rows of the cabin, n_sections - 1 for the first rows."""
    return (n_rows - row) * n_sections // n_rows


def zone_policy(zone):
    """Strategy from `zone(passenger, passengers) -> sortable key`; lower zones board first.

    The queue is shuffled first and then sorted by zone. Python's sort is stable,
    so the order inside each zone stays random.
    """
    def order(passengers, rng):
        queue = list(passengers)
        rng.shuffle(queue)
        return sorted(queue, key=lambda p: zone(p, passengers))
    return order


def back_to_front_zones(n_zones=3):
    """Rows split into n_zones equal sections, called from the back of the cabin to the front."""
    return zone_policy(lambda p, ps: _section_from_back(p.target_row, _n_rows(ps), n_zones))


def block(section_order=(0, 2, 1)):
    """Three row sections called in a fixed order; default: back, front, middle.

    Section 0 is the back of the cabin, 1 the middle, 2 the front.
    """
    rank = {section: i for i, section in enumerate(section_order)}
    return zone_policy(lambda p, ps: rank[_section_from_back(p.target_row, _n_rows(ps), 3)])


def outside_in_random(passengers, rng):
    """Window seats first, then middle, then aisle; random order inside each group (WilMA)."""
    return zone_policy(lambda p, ps: -p.aisle_distance)(passengers, rng)


def reverse_pyramid(passengers, rng):
    """Diagonal zones: back window seats first, front aisle seats last.

    zone = (row section counted from the back, 3 sections) + (seat distance from the window),
    so zone 0 is the back third's window seats and the last zone the front third's aisle seats.
    """
    max_distance = max(p.aisle_distance for p in passengers)
    return zone_policy(lambda p, ps: _section_from_back(p.target_row, _n_rows(ps), 3)
                       + max_distance - p.aisle_distance)(passengers, rng)


STRATEGIES = {
    "Front-to-back": front_to_back,
    "Back-to-front": back_to_front,
    "Random": random_order,
    "Row-cycling": row_cycling,
    "Outside-in": outside_in,
    "Back-to-front (3 zones)": back_to_front_zones(3),
    "Block (back, front, middle)": block(),
    "Outside-in (random)": outside_in_random,
    "Reverse pyramid": reverse_pyramid,
}
