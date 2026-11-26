"""Streamlit + Plotly front end for the boarding simulation.

Run with:  streamlit run app.py
All model logic lives in the `boarding` package; this file only draws its state.
"""

import time

import plotly.graph_objects as go
import streamlit as st

from boarding import STRATEGIES, Aircraft, Simulation, State

AIRCRAFT = Aircraft()
STATE_COLORS = {State.WALKING: "#2a78d6", State.BLOCKED: "#eb6834",
                State.STOWING: "#1baf7a", State.SEATED: "#eda100"}
EMPTY_COLOR = "#e1e0d9"


@st.cache_data
def boarding_times(seed: int) -> dict[str, int]:
    """Total boarding time T of every strategy (reproducible for a given seed, so cached)."""
    return {name: Simulation(strategy, AIRCRAFT, seed=seed).run()
            for name, strategy in STRATEGIES.items()}


def reset():
    strategy = STRATEGIES[st.session_state.strategy]
    st.session_state.sim = Simulation(strategy, AIRCRAFT, seed=int(st.session_state.seed))
    st.session_state.running = False


def draw_cabin(sim: Simulation) -> go.Figure:
    """Top-down view: aisle at y = 0, seats at their signed offset from it."""
    aircraft = sim.aircraft
    seat_y = aircraft.seat_offset
    rows = range(1, aircraft.n_rows + 1)
    fig = go.Figure()
    # Background: every seat and every aisle cell as an empty square.
    fig.add_trace(go.Scatter(
        x=[r for r in rows for _ in aircraft.seats],
        y=[seat_y(s) for _ in rows for s in aircraft.seats],
        mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square", size=30, color=EMPTY_COLOR),
    ))
    fig.add_trace(go.Scatter(
        x=list(rows), y=[0] * aircraft.n_rows, mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(symbol="square-open", size=30, color="#c3c2b7"),
    ))
    # One trace per state, always present so the legend never changes.
    for state, color in STATE_COLORS.items():
        ps = [p for p in sim.passengers if p.state is state]
        seated = state is State.SEATED
        fig.add_trace(go.Scatter(
            x=[p.target_row if seated else p.current_position for p in ps],
            y=[seat_y(p.target_seat) if seated else 0 for p in ps],
            mode="markers+text", name=state.value.capitalize(),
            marker=dict(symbol="square" if seated else "circle", size=28, color=color),
            text=[p.seat_label for p in ps],
            textfont=dict(size=10, color="#0b0b0b" if seated else "#ffffff"),
            customdata=[state.value.lower() for p in ps],
            hovertemplate="Passenger %{text}: %{customdata}<extra></extra>",
        ))
    half = max(map(abs, map(seat_y, aircraft.seats)))
    fig.update_layout(
        height=380, margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08, x=0, itemsizing="constant"),
        xaxis=dict(title="Row (door at the left)", tickvals=list(rows),
                   range=[0.3, aircraft.n_rows + 0.7], showgrid=False, zeroline=False, fixedrange=True),
        yaxis=dict(tickvals=[seat_y(s) for s in aircraft.seats] + [0],
                   ticktext=list(aircraft.seats) + ["aisle"],
                   range=[-half - 0.7, half + 0.7], showgrid=False, zeroline=False, fixedrange=True),
    )
    return fig


st.set_page_config(page_title="Airplane boarding prototype", layout="wide")
st.title("Airplane boarding")
st.caption(f"{AIRCRAFT.n_rows} rows x {len(AIRCRAFT.seats)} seats, one aisle, 1 step = 1 second. "
           "At their row a passenger sits down with probability 1/7 per second (7 s on average). "
           "Labels show each passenger's assigned seat.")

if "sim" not in st.session_state:
    st.session_state.strategy = "Random"
    st.session_state.seed = 0
    reset()

STRATEGY_NAMES = ["Random"] + [name for name in STRATEGIES if name != "Random"]
s1, s2 = st.columns([4, 1])
s1.selectbox("Boarding strategy", STRATEGY_NAMES, key="strategy", on_change=reset)
s2.number_input("Seed", min_value=0, step=1, key="seed", on_change=reset,
                help="All randomness (the random order and the time each passenger needs "
                     "at their row) comes from a generator with this fixed seed, "
                     "so every run is reproducible.")
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
times = boarding_times(int(st.session_state.seed))
st.table({"Strategy": list(times), "Total boarding time T (s)": list(times.values())})
st.caption(f"Every row is a single run with seed {st.session_state.seed}, not an average over many runs.")

if st.session_state.running:
    time.sleep(1 / speed)
    sim.step()
    st.rerun()
