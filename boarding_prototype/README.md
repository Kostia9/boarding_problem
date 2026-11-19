# Airplane boarding prototype

Discrete-time simulation of boarding a single-aisle aircraft (10 rows × 6 seats,
60 passengers) with a Streamlit + Plotly visualization.

## Run

```bash
uv venv .venv && source .venv/bin/activate
uv pip install -r requirements.txt

streamlit run app.py      # visualization
python -m boarding        # boarding time of every strategy
pytest                    # tests
```

```text
boarding/
├── model.py         State, Passenger, Aircraft
├── strategies.py    one function per strategy + STRATEGIES dict
└── simulation.py    Simulation: step(), run()
app.py               UI only, no model logic
test_simulation.py
```

```python
from boarding import Simulation, STRATEGIES
Simulation(STRATEGIES["Back-to-front"], seed=0).run()   # -> 367 (T in seconds)
```

## Model

1 step = 1 s. One passenger per aisle cell, no overtaking, walking 1 row/s.
At their row a passenger blocks the aisle for 5 s (luggage) + 2 s (sitting).
The next passenger enters when cell 1 is free. No seat interference.
Values are assumptions, not measured data.

## Results

| Strategy | T |
|---|---|
| Front-to-back | 430 s |
| Back-to-front | 367 s |
| Outside-in (window → middle → aisle, back to front) | 259 s |
| Random (seed 0; seeds 0–199: 186–242 s, mean 213 s) | 209 s |
| Row-cycling (rows 10, 9, …, 1, 10, 9, …) | **97 s, optimal** |

Only passengers at different rows can stow in parallel, so T depends on how far
consecutive passengers are spread over rows:

- **Front-to-back** is fully serial: row 1 stows at the door and blocks entry: 60 × 7 + 10.
- **Back-to-front** overlaps only at row boundaries.
- **Outside-in** enters A and F of the same row back to back, so every second passenger waits.
- **Row-cycling**: each wave of 10 reaches all rows at t = 10 and sits at t = 17;
  later waves take 16 s: T = 17 + 5 · 16 = 97.

**Lower bound.** Each passenger enters cell 1 at a distinct second; a row-1 passenger
holds it 7 s, others ≥ 1 s. If the last to enter is from row 1, they enter at
≥ 1 + 5·7 + 54 = 90 and sit at ≥ 97; otherwise they enter at ≥ 96 and sit at ≥ 104.
So T ≥ 97 for every order.

## Mathematical description

Deterministic system $X(t+1) = F(X(t))$ with state

$$X(t) = \big(p_i(t),\ s_i(t),\ \tau_i(t)\big)_{i=1}^{60},$$

where $p_i \in \{0,\dots,10\}$ is the position (0 = outside), $s_i$ the state
(WAITING, WALKING, BLOCKED, STOWING, SEATED), $\tau_i$ the remaining stow time.
The boarding order $\pi$ is a parameter of $F$.

**Initial state:** $p_i = 0$, $s_i = \text{WAITING}$, $\tau_i = 0$.

**Transition $F$:** cells $k = 10, \dots, 1$ (back to front), then the door:

1. STOWING: $\tau_i \leftarrow \tau_i - 1$; at 0 → SEATED, cell freed.
2. Cell $k+1$ free → move, WALKING; if $p_i = r_i$ → STOWING, $\tau_i = 7$.
3. Cell $k+1$ occupied → BLOCKED.
4. Cell 1 free → next passenger in $\pi$ enters.

Back-to-front processing lets a line advance together in one step and makes $F$
independent of iteration order.

**Termination:** $T = \min\{t : s_i(t) = \text{SEATED}\ \forall i\}$. Always finite:
the passenger furthest down the aisle is never blocked.

**Blocking:** a STOWING passenger holds their cell for 7 s, and the stop propagates
backwards through everyone behind them heading further back.

## Tests

For every strategy: everyone ends in their seat; one passenger per aisle cell,
no overtaking, at most one cell per step. Plus: same seed → same T, and the known
T values above.

## Extending

All randomness must come from `sim.rng` (seeded by `Simulation(seed=...)`), so
every run is reproducible.

| To add | Do |
|---|---|
| Strategy | write `order(passengers, rng) -> list`, add it to `STRATEGIES` |
| Other fixed times | `Simulation(..., stow_time=..., seat_time=...)` |
| Random or state-dependent times (e.g. seat interference) | subclass `Simulation`, override `time_at_row(passenger)` |
| Cabin size | `Aircraft(n_rows=..., seats=...)` |
| Monte Carlo | `[Simulation(strategy, seed=k).run() for k in range(N)]` |

Next steps: stochastic times, Monte Carlo, seat interference.
