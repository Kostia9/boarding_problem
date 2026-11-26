"""Streamlit + Plotly front end for the boarding simulation.

Run with:  streamlit run app.py
All model logic lives in the `boarding` package; this file only draws its state.
"""

import time

import plotly.graph_objects as go
import streamlit as st

from boarding import DELAYS, STRATEGIES, Aircraft, Simulation, State

SEAT_LAYOUTS = {"6 per row (ABC | DEF)": "ABCDEF", "4 per row (AB | CD)": "ABCD",
                "2 per row (A | B)": "AB"}
STATE_COLORS = {State.WALKING: "#2a78d6", State.BLOCKED: "#eb6834",
                State.STOWING: "#1baf7a", State.SEATED: "#eda100"}
EMPTY_COLOR = "#e1e0d9"


@st.cache_data
def boarding_times(seed: int, noncompliance: float, delay_name: str, phases: int,
                   sigma: float, n_rows: int, seats: str, stow_time: int,
                   seat_time: int) -> dict[str, int]:
    """Total boarding time T of every strategy (reproducible for given settings, so cached)."""
    delay = DELAYS[delay_name](phases=phases, sigma=sigma)
    return {name: Simulation(strategy, Aircraft(n_rows, seats), seed=seed,
                             noncompliance=noncompliance, delay=delay,
                             stow_time=stow_time, seat_time=seat_time).run()
            for name, strategy in STRATEGIES.items()}


def max_phases():
    """Erlang needs phases <= mean time at the row."""
    return max(1, int(st.session_state.stow_time) + int(st.session_state.seat_time))


def current_phases():
    return min(int(st.session_state.phases), max_phases())


def current_delay():
    return DELAYS[st.session_state.delay](phases=current_phases(),
                                          sigma=float(st.session_state.sigma))


def current_aircraft():
    return Aircraft(int(st.session_state.n_rows), SEAT_LAYOUTS[st.session_state.layout])


def reset():
    strategy = STRATEGIES[st.session_state.strategy]
    st.session_state.sim = Simulation(strategy, current_aircraft(), seed=int(st.session_state.seed),
                                      noncompliance=st.session_state.noncompliance,
                                      delay=current_delay(),
                                      stow_time=int(st.session_state.stow_time),
                                      seat_time=int(st.session_state.seat_time))
    st.session_state.running = False


def draw_cabin(sim: Simulation) -> go.Figure:
    """Top-down view: aisle at y = 0, seats at their signed offset from it."""
    aircraft = sim.aircraft
    seat_y = aircraft.seat_offset
    rows = range(1, aircraft.n_rows + 1)
    # Shrink the squares for long cabins; drop the seat labels once they no longer fit.
    size = max(6, min(30, int(1000 / aircraft.n_rows * 0.75)))
    show_labels = size >= 22
    fig = go.Figure()
    # Background: every seat and every aisle cell as an empty square.
    fig.add_trace(go.Scatter(
        x=[r for r in rows for _ in aircraft.seats],
        y=[seat_y(s) for _ in rows for s in aircraft.seats],
        mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square", size=size, color=EMPTY_COLOR),
    ))
    fig.add_trace(go.Scatter(
        x=list(rows), y=[0] * aircraft.n_rows, mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square-open", size=size, color="#c3c2b7"),
    ))
    # One trace per state, always present so the legend never changes.
    for state, color in STATE_COLORS.items():
        ps = [p for p in sim.passengers if p.state is state]
        seated = state is State.SEATED
        fig.add_trace(go.Scatter(
            x=[p.target_row if seated else p.current_position for p in ps],
            y=[seat_y(p.target_seat) if seated else 0 for p in ps],
            mode="markers+text" if show_labels else "markers", name=state.value.capitalize(),
            marker=dict(symbol="square" if seated else "circle", size=size - 2, color=color),
            text=[p.seat_label for p in ps],
            textfont=dict(size=10, color="#0b0b0b" if seated else "#ffffff"),
            customdata=[state.value.lower() for p in ps],
            hovertemplate="Passenger %{text}: %{customdata}<extra></extra>",
        ))
    half = max(map(abs, map(seat_y, aircraft.seats)))
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08, x=0, itemsizing="constant"),
        xaxis=dict(title="Row (door at the left)",
                   tickvals=list(rows) if aircraft.n_rows <= 20 else list(range(5, aircraft.n_rows + 1, 5)),
                   range=[0.3, aircraft.n_rows + 0.7], showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(tickvals=[seat_y(s) for s in aircraft.seats] + [0],
                   ticktext=list(aircraft.seats) + ["aisle"],
                   range=[-half - 0.7, half + 0.7], showgrid=False, zeroline=False, fixedrange=True),
    )
    return fig


st.set_page_config(page_title="Airplane boarding prototype", layout="wide")
st.title("Airplane boarding")
if "sim" not in st.session_state:
    st.session_state.n_rows = Aircraft.n_rows
    st.session_state.layout = next(iter(SEAT_LAYOUTS))
    st.session_state.stow_time = 5
    st.session_state.seat_time = 2

with st.sidebar:
    st.header("Cabin")
    st.number_input("Rows", min_value=1, max_value=60, step=1, key="n_rows", on_change=reset)
    st.selectbox("Seats", list(SEAT_LAYOUTS), key="layout", on_change=reset)
    st.number_input("Luggage time (mean s)", min_value=0, max_value=60, step=1, key="stow_time",
                    on_change=reset)
    st.number_input("Sitting-down time (mean s)", min_value=0, max_value=60, step=1,
                    key="seat_time", on_change=reset)
    if st.session_state.stow_time + st.session_state.seat_time < 1:
        st.error("Luggage + sitting-down time must be at least 1 s.")
        st.stop()

aircraft_now = current_aircraft()
mean_time = st.session_state.stow_time + st.session_state.seat_time
st.caption(f"{aircraft_now.n_rows} rows x {len(aircraft_now.seats)} seats "
           f"({aircraft_now.n_passengers} passengers), one aisle, 1 step = 1 second. "
           f"At their row a passenger blocks the aisle for a random time, {mean_time} s on average. "
           "Labels show each passenger's assigned seat.")

if "sim" not in st.session_state:
    st.session_state.strategy = "Random"
    st.session_state.seed = 0
    st.session_state.noncompliance = 0.0
    st.session_state.delay = "geometric"
    st.session_state.phases = 3
    st.session_state.sigma = 0.5
    reset()

STRATEGY_NAMES = ["Random"] + [name for name in STRATEGIES if name != "Random"]
s1, s2, s3 = st.columns([3, 2, 1])
s1.selectbox("Boarding strategy", STRATEGY_NAMES, key="strategy", on_change=reset)
s2.slider("Passengers ignoring the strategy", 0.0, 1.0, step=0.05, key="noncompliance",
          on_change=reset, format="%.2f",
          help="Each passenger ignores the strategy with this probability and joins the queue "
               "at a random place. 0 = everyone follows it, 1 = random boarding.")
s3.number_input("Seed", min_value=0, step=1, key="seed", on_change=reset,
                help="All randomness (the random order and the time each passenger needs "
                     "at their row) comes from a generator with this fixed seed, "
                     "so every run is reproducible.")
d1, d2 = st.columns([3, 3])
d1.selectbox(f"Time at the row (mean {mean_time} s)", list(DELAYS), key="delay", on_change=reset,
             help="geometric: memoryless, std ≈ mean; erlang: k geometric phases, less spread; "
                  "lognormal: skewed with a few very slow passengers; fixed: always the mean.")
if st.session_state.delay == "erlang":
    st.session_state.phases = current_phases()
    d2.number_input("Phases k", min_value=1, max_value=max_phases(), step=1, key="phases",
                    on_change=reset)
elif st.session_state.delay == "lognormal":
    d2.number_input("Sigma", min_value=0.05, max_value=2.0, step=0.05, key="sigma", on_change=reset)
sim: Simulation = st.session_state.sim
finished = sim.finished
if finished:
    st.session_state.running = False

c1, c2, c3, c4 = st.columns([1, 1, 1, 3])
if c1.button("Pause" if st.session_state.running else "Start", disabled=finished, width="stretch"):
    st.session_state.running = not st.session_state.running
    st.rerun()
if c2.button("Step", disabled=finished or st.session_state.running, width="stretch"):
    sim.step()
    st.rerun()
c3.button("Reset", on_click=reset, width="stretch")
speed = c4.slider("Playback speed (simulated seconds per real second)", 1, 30, 10)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Simulation time", f"{sim.t} s")
m2.metric("Seated", f"{sim.n_seated} / {len(sim.passengers)}")
m3.metric("Waiting outside", sim.count(State.WAITING))
m4.metric("Blocked in aisle", sim.count(State.BLOCKED))
m5.metric("Total boarding time T", f"{sim.t} s" if finished else "-")

st.plotly_chart(draw_cabin(sim), width="stretch", key="cabin", config={"displayModeBar": False})

st.subheader("Strategy comparison")
times = boarding_times(int(st.session_state.seed), st.session_state.noncompliance,
                       st.session_state.delay, current_phases(),
                       float(st.session_state.sigma), aircraft_now.n_rows, aircraft_now.seats,
                       int(st.session_state.stow_time), int(st.session_state.seat_time))
st.table({"Strategy": list(times), "Total boarding time T (s)": list(times.values())})
st.caption(f"Every row is a single run with seed {st.session_state.seed}, not an average over many runs.")

if st.session_state.running:
    time.sleep(1 / speed)
    sim.step()
    st.rerun()
