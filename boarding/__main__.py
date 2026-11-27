"""python -m boarding  ->  mean boarding time of every strategy for several cabin sizes."""

from . import STRATEGIES, Aircraft, monte_carlo

N_RUNS = 100
STOW_TIME, STOW_SD = 5, 2

print(f"Mean T in seconds over {N_RUNS} seeds; gamma stow time (mean {STOW_TIME} s, sd {STOW_SD} s)\n")
print(f"{'rows x seats':<13}" + "".join(f"{name:>15}" for name in STRATEGIES) + "   T / passenger (best)")
for n_seats in (2, 4, 6, 8):
    for n_rows in (10, 20, 30, 40):
        aircraft = Aircraft(n_rows, "ABCDEFGH"[:n_seats])
        means = {name: monte_carlo(strategy, N_RUNS, aircraft=aircraft, stow_time=STOW_TIME,
                                   stow_sd=STOW_SD).mean()
                 for name, strategy in STRATEGIES.items()}
        best = min(means, key=means.get)
        print(f"{n_rows:>4} x {n_seats:<6}" + "".join(f"{t:>15.0f}" for t in means.values())
              + f"   {means[best] / aircraft.n_passengers:.2f} s ({best})")
