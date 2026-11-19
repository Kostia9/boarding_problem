"""python -m boarding  ->  boarding time of every registered strategy."""

from . import STRATEGIES, Aircraft, Simulation

if __name__ == "__main__":
    aircraft = Aircraft()
    print(f"Boarding simulation: {aircraft.n_rows} rows x {len(aircraft.seats)} seats, "
          f"{aircraft.n_passengers} passengers, fixed times")
    for name, cls in STRATEGIES.items():
        note = "  (one fixed order, seed 0)" if cls.uses_randomness else ""
        print(f"  {name:<14} T = {Simulation(cls(), aircraft).run()} s{note}")
