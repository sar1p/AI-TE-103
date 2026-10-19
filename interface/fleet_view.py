"""Visible two-robot coordination, diagnostic control, and fuzzy movement."""

from __future__ import annotations

from html import escape
import json

import streamlit as st

from expert_system.scenarios import load_scenarios
from interface.fleet_session import FleetControlSession
from interface.presentation import route_status_strip


def fleet_grid_html(snapshot: dict) -> str:
    rows = snapshot["rows"]
    robots = snapshot["robots"]
    positions = {tuple(robot["position"]): index for index, robot in enumerate(robots)}
    goals = {tuple(robot["goal"]): index for index, robot in enumerate(robots)}
    routes = {tuple(cell) for robot in robots for cell in robot["path"]}
    cells = ['<div class="fleet-axis"></div>']
    cells.extend(f'<div class="fleet-axis">{column}</div>' for column in range(len(rows[0])))
    for row, line in enumerate(rows):
        cells.append(f'<div class="fleet-axis">{row}</div>')
        for column, character in enumerate(line):
            cell = (row, column)
            kind, label = "open", ""
            if character == "#":
                kind = "shelf"
            elif cell in routes:
                kind = "route"
            if cell in goals:
                kind, label = "goal", f"G{goals[cell] + 1}"
            if cell in positions:
                index = positions[cell]
                kind, label = f"robot-{index % 2}", f"R{index + 1}"
            description = escape(f"Row {row}, column {column}: {kind} {label}")
            cells.append(
                f'<div class="fleet-cell fleet-{kind}" title="{description}" '
                f'aria-label="{description}">{label}</div>'
            )
    return f"""<style>
    .fleet-map {{ overflow-x:auto; padding:8px 0; }}
    .fleet-grid {{ display:grid; grid-template-columns:26px repeat({len(rows[0])},minmax(30px,1fr));
        grid-auto-rows:36px; gap:3px; min-width:{len(rows[0])*33+26}px; }}
    .fleet-cell,.fleet-axis {{ display:flex; align-items:center; justify-content:center;
        font:600 12px ui-monospace,monospace; }}
    .fleet-cell {{ border:1px solid #c8d0d6; border-radius:2px; }}
    .fleet-axis {{ color:#596773; font-weight:400; }}
    .fleet-open {{ background:#fff; }} .fleet-route {{ background:#e7eff4; }}
    .fleet-shelf {{ background:#aeb8c0; border-color:#8e9ba5; }}
    .fleet-goal {{ background:#f8ecd2; color:#61440a; }}
    .fleet-robot-0 {{ background:#244c69; color:#fff; }}
    .fleet-robot-1 {{ background:#925321; color:#fff; }}
    </style><div class="fleet-map" role="img" aria-label="Two robots and their destinations in a shared warehouse">
    <div class="fleet-grid">{''.join(cells)}</div></div>"""


def _reset() -> None:
    st.session_state.fleet_control = FleetControlSession()
    for key in list(st.session_state):
        if key.startswith(("fleet_battery_", "fleet_case_")):
            del st.session_state[key]


def render_fleet_tab() -> FleetControlSession:
    if "fleet_control" not in st.session_state:
        st.session_state.fleet_control = FleetControlSession()
    session = st.session_state.fleet_control
    st.subheader("Shared warehouse, independent robots")
    st.caption(
        "Each robot keeps its own D* Lite planner and requests its next cell. "
        "The traffic coordinator grants one-tick reservations; fuzzy output controls move cadence."
    )
    controls = st.columns([1.35, 1, 1, 1])
    with controls[0]:
        method = st.selectbox(
            "Fleet fuzzy method", ["mamdani", "sugeno"],
            format_func=lambda name: "Mamdani / centroid" if name == "mamdani" else "Sugeno / weighted average",
            key="fleet_fuzzy_method",
        )
        session.set_method(method)
    with controls[1]:
        if st.button("Advance one tick", key="fleet_step", width="stretch"):
            session.step()
            st.rerun()
    with controls[2]:
        if st.button("Run 12 ticks", key="fleet_run", width="stretch"):
            session.run(12)
            st.rerun()
    with controls[3]:
        if st.button("Reset fleet", key="fleet_reset", width="stretch"):
            _reset()
            st.rerun()

    cases = load_scenarios()
    by_id = {case["id"]: case for case in cases}
    case_ids = list(by_id)
    st.markdown("**Robot readings**")
    st.caption(
        "Apply each robot's readings before advancing. Percentage battery readings are synthetic inputs; "
        "diagnostic presets remain separate categorical observations."
    )
    for column, robot_id in zip(st.columns(len(session.simulation.agents)), session.simulation.agents):
        with column, st.form(f"fleet_form_{robot_id}"):
            st.markdown(f"**{robot_id}**")
            battery = st.number_input(
                f"{robot_id} battery (%)", min_value=0.0, max_value=100.0,
                value=85.0, step=5.0, key=f"fleet_battery_{robot_id}",
            )
            case_id = st.selectbox(
                f"{robot_id} diagnostic case", case_ids,
                index=case_ids.index("corrected-observations"),
                format_func=lambda value: by_id[value]["title"], key=f"fleet_case_{robot_id}",
            )
            if st.form_submit_button(f"Apply {robot_id} readings"):
                session.set_battery(robot_id, battery)
                session.set_observations(robot_id, by_id[case_id]["facts"])

    snapshot = session.simulation.snapshot()
    proposed = session.preview_controls()
    route_status_strip([
        ("Simulation tick", snapshot["tick"]),
        ("Moves completed", sum(robot["steps"] for robot in snapshot["robots"])),
        ("Reservation denials", sum(message["kind"] == "denial" for message in snapshot["messages"])),
        ("Robots at goal", sum(robot["status"] == "arrived" for robot in snapshot["robots"])),
    ])
    st.html(fleet_grid_html(snapshot))
    st.caption("R1 / G1: R01 and its goal. R2 / G2: R02 and its goal. Pale cells show independent route proposals.")
    st.dataframe([
        {
            "Robot": robot["id"], "Position": str(tuple(robot["position"])),
            "Goal": str(tuple(robot["goal"])), "Last tick state": robot["status"],
            "Fuzzy proposal (%)": round(proposed[robot["id"]]["fuzzy"]["output"]["speed_percent"], 2),
            "Permitted factor": round(proposed[robot["id"]]["applied_factor"], 3),
            "Clearance (cells)": proposed[robot["id"]]["fuzzy"]["inputs"]["clearance_cells"],
            "Moves": robot["steps"], "Reservation waits": robot["waiting_ticks"],
            "Planner initializations": robot["initialization_count"],
        }
        for robot in snapshot["robots"]
    ], hide_index=True, width="stretch")
    for robot_id, control in proposed.items():
        if not control["movement_allowed"]:
            st.warning(f"{robot_id}: {control['reason']} The fuzzy proposal is overridden to zero.")
    st.markdown("**Agent communication**")
    if snapshot["messages"]:
        st.dataframe([
            {**message, "payload": json.dumps(message["payload"], sort_keys=True)}
            for message in snapshot["messages"][-30:]
        ], hide_index=True, width="stretch")
    else:
        st.info("Advance the simulation to see move requests, grants, denials, and position updates.")
    with st.expander("Per-robot inference and fuzzy proofs"):
        st.json(proposed)
    st.caption(
        "Discrete reservations reject occupied cells and position swaps. This baseline can wait indefinitely "
        "in a head-on deadlock. Speed percentages have no physical time or braking-distance calibration."
    )
    st.download_button(
        "Download fleet evidence (JSON)", json.dumps(session.to_dict(), indent=2, allow_nan=False),
        file_name="warehouse-fleet.json", mime="application/json", key="fleet_download",
    )
    return session
