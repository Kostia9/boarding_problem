# Airplane boarding

Discrete-time simulation of boarding a single-aisle aircraft (default 10 rows × 6 seats,
60 passengers) with a Streamlit + Plotly visualization. Cabin size, empty seats and
random stow times are configurable. The sidebar also controls the fraction of passengers who ignore the strategy.

## Run

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

streamlit run app.py      # visualization
python -m boarding        # cabin size study (mean T of every strategy, ~10 s)
python generate_plots.py  # regenerate the comparison PNGs in plots/
pytest                    # tests
```

```text
boarding/
├── model.py         State, Passenger, Aircraft
├── strategies.py    one function per strategy + STRATEGIES dict
└── simulation.py    Simulation: step(), run(); monte_carlo()
app.py               UI only, no model logic
test_simulation.py
```

```python
from boarding import Aircraft, Simulation, STRATEGIES, monte_carlo
Simulation(STRATEGIES["Back-to-front"], seed=0).run()   # -> 404 (T in seconds)

# 20 × 4 cabin, 80% full, stow time ~ geometric(mean 5 s); T of seeds 0..99
monte_carlo(STRATEGIES["Random"], 100, aircraft=Aircraft(20, "ABCD"),
            load_factor=0.8, stow_time=5, noncompliance=0.25).mean()
```

## Model

1 step = 1 s. One passenger per aisle cell, no overtaking, walking 1 row/s.
At their row a passenger blocks the aisle while stowing luggage (mean 5 s) and sitting down (2 s).
The next passenger enters when cell 1 is free. No seat interference.
Values are assumptions, not measured data.

- **Geometric stow time** draws a whole number of seconds starting
  at one. Each second, the probability of finishing is `1 / stow_time`. For a mean
  of 5 seconds this probability is 20%. Sitting adds a separate fixed delay.
- **Empty seats** (`load_factor < 1`): a random `round(load_factor · seats)` seats are taken.
- Both are drawn before the strategy runs, so for a given seed every strategy boards the
  same passengers with the same luggage (common random numbers → fair comparison).

Each passenger independently ignores the strategy with probability `noncompliance` and
joins a random queue position. Other passengers keep their relative order.

## Results

With the default full cabin and seed 0, boarding takes 142 s for Row-cycling,
196 s for Steffen, 266 s for Random, 287 s for Outside-in, 404 s for
Back-to-front, and 453 s for Front-to-back.

### Cabin size

`python -m boarding`: mean T (s) over 100 seeds, geometric stow time (mean 5 s), full cabin.

| rows × seats | Front-to-back | Back-to-front | Random | Row-cycling | Outside-in | Steffen |
|---|---|---|---|---|---|---|
| 10 × 2 | 146 | 86 | 84 | 46 | 86 | 62 |
| 40 × 2 | 592 | 327 | 246 | 111 | 327 | 142 |
| 10 × 4 | 284 | 222 | 156 | 87 | 171 | 117 |
| 40 × 4 | 1154 | 882 | 450 | 215 | 646 | 268 |
| 10 × 6 | 422 | 360 | 229 | 128 | 258 | 172 |
| 40 × 6 | 1718 | 1442 | 651 | 317 | 977 | 393 |
| 10 × 8 | 562 | 500 | 301 | 170 | 342 | 228 |
| 40 × 8 | 2282 | 2008 | 858 | 418 | 1304 | 518 |

(20 and 30 rows in the script output lie in between.)

- **The ranking does not change** with size: Row-cycling < Steffen < Random < Outside-in ≤
  Back-to-front < Front-to-back in every configuration.
- **Front-to-back and Back-to-front scale linearly** with the number of passengers
  for each fixed seat layout. Front-to-back boards serially, while Back-to-front overlaps at row boundaries.
- **Random, Row-cycling and Steffen scale sub-linearly with rows**: more rows means more passengers
  can stow at the same time. Best T per passenger drops from 2.12–2.31 s (10 rows) to 1.31–1.39 s
  (40 rows), almost independent of seats per row.
- **Back-to-front gains little over Front-to-back in wide cabins** (1.7× faster with 2
  seats, 1.1× with 8): more passengers per row means longer serial blocks.
- With 2 seats per row both seats are aisle seats, so Outside-in = Back-to-front.

## Mathematical description

After sampling the queue and individual stow times, the updates follow $X(t+1) = F(X(t))$ with state

$$X(t) = \big(p_i(t),\ s_i(t),\ \tau_i(t)\big)_{i=1}^{60},$$

where $p_i \in \{0,\dots,10\}$ is the position (0 = outside), $s_i$ the state
(WAITING, WALKING, BLOCKED, STOWING, SEATED), $\tau_i$ the remaining time at the row.
The boarding order $\pi$ is a parameter of $F$.

**Initial state:** $p_i = 0$, $s_i = \text{WAITING}$, $\tau_i = 0$.

**Transition $F$:** cells $k = 10, \dots, 1$ (back to front), then the door:

1. STOWING: $\tau_i \leftarrow \tau_i - 1$; at 0 → SEATED, cell freed.
2. Cell $k+1$ free → move, WALKING; if $p_i = r_i$ → STOWING, $\tau_i = L_i + 2$, where $L_i$ is passenger $i$’s sampled luggage time in seconds and the sitting time is $2$.
3. Cell $k+1$ occupied → BLOCKED.
4. Cell 1 free → next passenger in $\pi$ enters.

Back-to-front processing lets a line advance together in one step and makes $F$
independent of iteration order.

**Termination:** $T = \min\{t : s_i(t) = \text{SEATED}\ \forall i\}$. Always finite:
the passenger furthest down the aisle is never blocked.

**Blocking:** a STOWING passenger holds their cell for the sampled luggage time plus the sitting time, and the stop propagates
backwards through everyone behind them heading further back.

## Tests

For every strategy, in the default cabin, with random stow times + empty seats, and in a
15 × 4 cabin: everyone ends in their seat; one passenger per aisle cell, no overtaking, at
most one cell per step. Plus: same seed → same T, the known T values above, stow time
distribution, same passengers for every strategy, empty seats, input validation.

## Extending

All randomness must come from `sim.rng` (seeded by `Simulation(seed=...)`), so
every run is reproducible.

| To add | Do |
|---|---|
| Strategy | write `order(passengers, rng) -> list`, add it to `STRATEGIES` |
| Mean luggage time and fixed sitting time | `Simulation(..., stow_time=..., seat_time=...)` |
| Empty seats | `Simulation(..., load_factor=0.8)` |
| Other time models (e.g. seat interference) | subclass `Simulation`, override `time_at_row(passenger)` |
| Cabin size | `Aircraft(n_rows=..., seats=...)` |
| Monte Carlo | `monte_carlo(strategy, N, **simulation_kwargs)` |

Next steps: seat interference.
