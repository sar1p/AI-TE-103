"""Warehouse route planning and observation-based diagnostic demonstration."""

import json
import math
from uuid import uuid4

import streamlit as st

from interface.diagnostics import DiagnosticState, evaluate_diagnostics
from interface.evidence import environment_metadata
from interface.fleet_view import render_fleet_tab
from interface.fuzzy_view import render_fuzzy_tab
from interface.presentation import render_diagnostic_result, route_status_strip
from interface.rendering import grid_html
from interface.session import SimulationSession
from interface.theme import apply_page_styles
from search_algorithm.grid import GridError
from search_algorithm.scenarios import available_scenarios


st.set_page_config(
    page_title="Warehouse Operations | AI-TE-103",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_page_styles()


def reset_session(scenario):
    st.session_state.simulation = SimulationSession(scenario)


def apply_action(event, movement_allowed):
    try:
        st.session_state.simulation.apply_event(event, movement_allowed=movement_allowed)
    except GridError as error:
        st.error(str(error))
    else:
        st.rerun()


def _load_observation_schema():
    """Read the engine's UI schema when it exists without breaking search-only use."""
    try:
        from expert_system.engine import get_observation_schema

        schema = get_observation_schema()
    except Exception as error:
        return None, f"Guided observations are unavailable: {type(error).__name__}: {error}"
    if type(schema) is not dict:
        return None, "Guided observations are unavailable because the schema is malformed."
    observations = schema.get("observations")
    required = schema.get("required_observations")
    groups = schema.get("groups")
    if type(observations) is not dict or type(required) is not list or type(groups) is not list:
        return None, "Guided observations are unavailable because the schema is incomplete."
    if any(
        type(name) is not str
        or type(definition) is not dict
        or type(definition.get("allowed_values")) is not list
        or not all(type(value) is str for value in definition["allowed_values"])
        for name, definition in observations.items()
    ):
        return None, "Guided observations are unavailable because the schema is invalid."
    return schema, ""


def _load_diagnostic_scenarios():
    """Use the expert-system scenario loader so presets follow its validation rules."""
    try:
        from expert_system.scenarios import load_scenarios

        return load_scenarios(), ""
    except Exception as error:
        return None, f"Diagnostic presets are unavailable: {type(error).__name__}: {error}"


def _observation_title(name):
    return name.replace("_", " ").capitalize()


def _reject_json_constant(value):
    raise ValueError(f"Non-finite JSON number {value!r} is not allowed.")


def _finite_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite JSON number {value!r} is not allowed.")
    return number


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key {key!r}.")
        result[key] = value
    return result


def _parse_strict_json(text):
    return json.loads(
        text,
        parse_constant=_reject_json_constant,
        parse_float=_finite_json_float,
        object_pairs_hook=_unique_json_object,
    )


def _sync_guided_values(schema, facts):
    """Load supported values into the draft form without changing raw JSON."""
    if type(facts) is not dict:
        raise ValueError("The current input must be a JSON object to load into the guided form.")
    observations = schema["observations"]
    unsupported = []
    for name, definition in observations.items():
        value = facts.get(name)
        if value is not None and not any(
            type(value) is type(allowed) and value == allowed
            for allowed in definition["allowed_values"]
        ):
            unsupported.append(name)
            value = None
        st.session_state[f"guided_observation_{name}"] = value
    return unsupported


def _render_guided_observation_form(schema):
    """Submit only explicit choices; the Unknown option is retained as JSON null."""
    observations = schema["observations"]
    required = schema["required_observations"]
    groups = schema["groups"]
    submitted_facts = {}

    with st.form("guided_observation_form", border=True):
        with st.container(key="guided_observation_fields"):
            st.markdown("**Required observations**")
            required_columns = st.columns(max(1, min(3, len(required))))
            for index, name in enumerate(required):
                definition = observations[name]
                with required_columns[index % len(required_columns)]:
                    submitted_facts[name] = st.selectbox(
                        _observation_title(name),
                        options=[None, *definition["allowed_values"]],
                        format_func=lambda value: "Unknown" if value is None else value,
                        placeholder="Unknown",
                        key=f"guided_observation_{name}",
                    )

            for group in groups:
                group_id = group["id"]
                names = group["observations"]
                st.markdown(f"**{_observation_title(group_id)}**")
                columns = st.columns(max(1, min(3, len(names))))
                for index, name in enumerate(names):
                    definition = observations[name]
                    with columns[index % len(columns)]:
                        submitted_facts[name] = st.selectbox(
                            _observation_title(name),
                            options=[None, *definition["allowed_values"]],
                            format_func=lambda value: "Unknown" if value is None else value,
                            placeholder="Unknown",
                            key=f"guided_observation_{name}",
                        )

        submitted = st.form_submit_button("Apply observations and evaluate", type="primary")

    if submitted:
        # Assign before constructing the keyed text area below. Arbitrary reruns never rewrite it.
        st.session_state["raw_facts"] = json.dumps(
            submitted_facts, indent=2, ensure_ascii=False, allow_nan=False
        )
    return submitted


choices = available_scenarios()
if not choices:
    st.error("No search scenarios are available. Check data/search_scenarios.")
    st.stop()
by_id = {scenario.id: scenario for _, scenario in choices}

st.caption("AI-TE-103 / SIMULATION")
st.title("Warehouse Operations")
st.caption("Dynamic routes, robot diagnostics, cooperative agents, and fuzzy speed control.")

route_tab, diagnosis_tab, evidence_tab, fleet_tab, fuzzy_tab = st.tabs(
    ["Route planner", "Diagnostics", "Evidence & methods", "Fleet coordination", "Fuzzy speed control"]
)

with route_tab, st.container(key="scenario_toolbar", border=True):
    scenario_column, reset_column, gate_column = st.columns([3.2, 1, 1.65], vertical_alignment="bottom")
    with scenario_column:
        selected = st.selectbox(
            "Scenario",
            list(by_id),
            format_func=lambda key: by_id[key].title,
            key="scenario_choice",
        )
    scenario = by_id[selected]
    with reset_column:
        reset_clicked = st.button("Reset simulation", key="reset_simulation", width="stretch")
    with gate_column:
        use_gate = st.toggle(
            "Apply diagnostic safety gate",
            value=False,
            key="diagnostic_gate",
        )
    st.caption(scenario.description)

if "simulation" not in st.session_state or st.session_state.simulation.scenario.id != selected:
    reset_session(scenario)
elif reset_clicked:
    reset_session(scenario)

if "simulation_error" in st.session_state:
    st.error(st.session_state.pop("simulation_error"))

with diagnosis_tab:
    st.subheader("Robot observations")
    st.caption(
        "Choose only readings you have. Unknown values remain null and each evaluation starts "
        "from these raw observations."
    )

    schema, schema_message = _load_observation_schema()
    preset_facts = None
    scenarios, scenarios_message = _load_diagnostic_scenarios()
    if scenarios is None:
        st.info(scenarios_message)
    else:
        scenarios_by_id = {item["id"]: item for item in scenarios}
        with st.container(key="diagnostic_preset_toolbar", border=True):
            preset_column, load_column = st.columns([3, 1], vertical_alignment="bottom")
            with preset_column:
                selected_preset = st.selectbox(
                    "Diagnostic scenario preset",
                    list(scenarios_by_id),
                    format_func=lambda key: scenarios_by_id[key]["title"],
                    key="diagnostic_preset_choice",
                )
            with load_column:
                load_preset = st.button(
                    "Load preset",
                    key="diagnostic_preset_load",
                    width="stretch",
                )
            selected_details = scenarios_by_id[selected_preset]
            st.caption(selected_details["description"])
            st.caption(f"Provenance: {selected_details['provenance']}")
        if load_preset:
            try:
                from expert_system.scenarios import load_scenario

                loaded = load_scenario(selected_preset)
                preset_facts = loaded["facts"]
            except Exception as error:
                st.error(f"Could not load the selected diagnostic preset: {type(error).__name__}: {error}")
            else:
                st.session_state["raw_facts"] = json.dumps(
                    preset_facts, indent=2, ensure_ascii=False, allow_nan=False
                )
                if schema is not None:
                    unsupported = _sync_guided_values(schema, preset_facts)
                    if unsupported:
                        st.warning(
                            "Preset values outside the guided choices remain visible in the JSON input: "
                            + ", ".join(unsupported)
                        )

    result_panel = st.container(key="diagnostic_result")
    st.subheader("Observation draft")
    if schema is None:
        st.info(schema_message)
    else:
        with st.container(key="guided_observation_load"):
            st.caption(
                "Guided observations are a separate draft. Use the load button to copy supported "
                "values from the active JSON input; only submitting the draft applies it."
            )
            if st.button(
                "Load current JSON into draft",
                key="load_json_into_guided_form",
            ):
                try:
                    current_facts = _parse_strict_json(st.session_state.get("raw_facts", "{}"))
                    unsupported = _sync_guided_values(schema, current_facts)
                except (ValueError, TypeError) as error:
                    st.error(f"Could not load the current JSON into the guided draft: {error}")
                else:
                    if unsupported:
                        st.warning(
                            "Unsupported values remain in the JSON input and show as Unknown in the draft: "
                            + ", ".join(unsupported)
                        )
                    else:
                        st.success("The guided draft now matches the supported active observations.")
        _render_guided_observation_form(schema)

    with st.expander("Advanced observations (JSON)", expanded=False):
        if "raw_facts" not in st.session_state:
            st.session_state["raw_facts"] = "{}"
        raw_text = st.text_area(
            "Raw observations",
            value=None,
            height=155,
            key="raw_facts",
            help="This is the exact raw input sent to a fresh diagnostic evaluation.",
        )
    try:
        facts = _parse_strict_json(raw_text)
    except (ValueError, TypeError) as error:
        diagnostic = DiagnosticState("error", f"Invalid observations JSON: {error}")
        facts = None
    else:
        diagnostic = evaluate_diagnostics(facts)

    with result_panel:
        if diagnostic.status == "pending":
            st.info("Expert system pending — no diagnosis is available yet.")
            st.caption("Search-only route planning remains available while this module is pending.")
        elif diagnostic.status == "error":
            st.error(diagnostic.message)
        else:
            render_diagnostic_result(diagnostic.result, facts)

movement_allowed = not use_gate or diagnostic.can_move

with route_tab:
    if use_gate and not movement_allowed:
        if diagnostic.status == "pending":
            st.info("Expert system pending — the diagnostic safety gate pauses robot movement.")
        st.warning(
            "The diagnostic safety gate pauses movement: robot movement is paused. "
            "Map edits and route planning remain available."
        )
    elif use_gate:
        st.success("The diagnostic safety gate allows movement. Simulated movement is available.")
    else:
        status_label = "Expert system pending" if diagnostic.status == "pending" else "diagnosis evaluated separately"
        st.info(f"Search-only demonstration · {status_label}.")

    session = st.session_state.simulation
    remaining_moves = session.dstar_result.cost
    route_status_strip([
        ("Route status", session.dstar_result.status.title()),
        ("Moves remaining", remaining_moves if remaining_moves is not None else "—"),
        ("Map revision", session.planner.grid.revision),
        ("Robot position", f"{session.planner.start[0]}, {session.planner.start[1]}"),
    ])

    map_panel, control_panel = st.container(key="mission_layout").columns([2.1, 1], gap="large")
    with map_panel:
        with st.container(border=True):
            with st.container(key="map_header"):
                map_heading, overlay_column = st.columns([1.25, 1])
                with map_heading:
                    st.subheader(scenario.title)
                    st.caption(f"Robot {session.planner.start} → fixed goal {session.planner.goal}")
                with overlay_column:
                    overlay = st.radio(
                        "Route overlay",
                        ["D* Lite", "A*"],
                        horizontal=True,
                        key="route_overlay",
                    )
            shown = session.dstar_result if overlay == "D* Lite" else session.astar_result
            st.html(grid_html(session.planner.grid, shown.path, session.planner.start, session.planner.goal))
            st.caption("Coordinates are row, column. Four-neighbor movement has unit cost. The goal is fixed.")
            if shown.status == "unreachable":
                st.warning("No route is available. Reopen a passage or reset the scenario.")

    with control_panel:
        with st.container(border=True):
            st.subheader("Mission controls")
            next_event = next(
                (event for event in scenario.events if event["id"] not in session.applied_events),
                None,
            )
            if next_event:
                st.caption(f"Next scenario event: {next_event.get('label', next_event['id'])}")
            else:
                st.caption("All scripted events are complete. Continue exploring or reset the simulation.")

            next_paused = next_event and next_event["type"] == "move" and not movement_allowed
            if st.button(
                "Apply next scenario event",
                type="primary",
                width="stretch",
                key="next_event",
                disabled=next_event is None or bool(next_paused),
            ):
                apply_action(next_event, movement_allowed)

            remaining = [event for event in scenario.events if event["id"] not in session.applied_events]
            run_paused = not movement_allowed and any(event["type"] == "move" for event in remaining)
            if st.button(
                "Run remaining scenario",
                width="stretch",
                key="run_remaining",
                disabled=not remaining or run_paused,
            ):
                try:
                    for event in remaining:
                        session.apply_event(event, movement_allowed=movement_allowed)
                except GridError as error:
                    st.session_state.simulation_error = (
                        f"Scenario stopped: {error} Reset before replaying after manual edits."
                    )
                    st.rerun()
                else:
                    st.rerun()

            if st.button(
                "Move robot one step",
                width="stretch",
                key="move_robot",
                disabled=not movement_allowed or len(session.dstar_result.path) < 2,
            ):
                apply_action(
                    {"id": f"manual-move-{uuid4()}", "type": "move", "label": "Manual robot step"},
                    movement_allowed,
                )

            st.divider()
            st.markdown("**Edit a map cell**")
            with st.form(f"edit_cell_{scenario.id}"):
                row = st.number_input("Row", min_value=0, max_value=session.planner.grid.height - 1, step=1)
                column = st.number_input(
                    "Column", min_value=0, max_value=session.planner.grid.width - 1, step=1
                )
                action = st.selectbox("Cell state", ["Blocked", "Open"])
                edit = st.form_submit_button("Apply cell change", width="stretch")
            if edit:
                apply_action(
                    {
                        "id": f"manual-map-{uuid4()}",
                        "type": "map",
                        "label": "Manual map edit",
                        "changes": [{"cell": [row, column], "blocked": action == "Blocked"}],
                    },
                    movement_allowed,
                )

    st.subheader("Planning work")
    comparison = []
    for name, attribute in [("D* Lite", "dstar_lite"), ("A*", "astar")]:
        current = session.records[-1][attribute]["metrics"]
        comparison.append({
            "Algorithm": name,
            "States processed (last call)": current["processed_states"],
            "Queue pops": current["queue_pops"],
            "Queue pushes": current["queue_pushes"],
            "Planning time (ms)": round(current["elapsed_ms"], 3),
            "States processed (session)": sum(
                record[attribute]["metrics"]["processed_states"] for record in session.records
            ),
        })
    st.dataframe(comparison, hide_index=True, width="stretch")
    st.caption(
        "Planning time covers search and route extraction, not interface rendering or map edits. "
        "The algorithms count different state operations; use the benchmark tool for full update-and-plan timings."
    )
    with st.expander("Event history and retained planner state"):
        st.caption(
            f"Planner initializations: {session.planner.initialization_count} · "
            f"Retained g values: {len(session.planner.g)} · "
            f"Retained rhs values: {len(session.planner.rhs)} · "
            f"kₘ: {session.planner.k_m}"
        )
        st.dataframe(
            [
                {key: record[key] for key in ("event_id", "label", "map_revision", "start", "k_m")}
                for record in session.records
            ],
            hide_index=True,
            width="stretch",
        )

with fleet_tab:
    fleet_session = render_fleet_tab()

with fuzzy_tab:
    fuzzy_comparison = render_fuzzy_tab()

with evidence_tab:
    session = st.session_state.simulation
    metadata = environment_metadata()
    if diagnostic.status == "ready":
        try:
            from expert_system.engine import knowledge_base_metadata, load_knowledge_base

            metadata["knowledge_base"] = knowledge_base_metadata(load_knowledge_base())
        except Exception:
            metadata["knowledge_base"] = None
    st.subheader("Operating data")
    st.write(
        "Download route results, diagnostic inputs and traces, fleet positions and "
        "messages, both fuzzy calculations, gate states, and source metadata."
    )
    payload = {
        "metadata": metadata,
        **session.to_dict(),
        "scope": "route planning, observation-based diagnostics, cooperative agents, and fuzzy control",
        "diagnostics": {
            "adapter_status": diagnostic.status,
            "result": diagnostic.result,
            "safety_gate_enabled": use_gate,
            "raw_observations_json": raw_text,
            "raw_observations": facts,
        },
        "fleet_simulation": fleet_session.to_dict(),
        "fuzzy_exploration": fuzzy_comparison,
    }
    st.download_button(
        "Download session evidence (JSON)",
        json.dumps(payload, indent=2, allow_nan=False),
        file_name=f"{scenario.id}-session.json",
        mime="application/json",
        key="download_evidence",
    )
    with st.expander("Source metadata"):
        st.json(metadata)

    st.subheader("Methods and limits")
    st.markdown(
        "**Navigation:** D* Lite retains search values and repairs the route after map changes or "
        "robot movement. A* provides a fresh static search for comparison. Both operate on this "
        "finite grid with unit movement cost."
    )
    st.markdown(
        "**Diagnostics:** the expert system evaluates the observations supplied above and exposes "
        "its findings, actions, and rule trace. It does not measure sensors or verify physical robot health."
    )
    st.markdown(
        "**Cooperative agents:** two robots keep independent goals and planners, exchange requests and "
        "decisions with a traffic coordinator, and reserve their next cells. This discrete baseline can deadlock."
    )
    st.markdown(
        "**Fuzzy control:** Mamdani and zero-order Sugeno use explicit illustrative memberships and rules. "
        "Their proposal changes fractional movement cadence; diagnostic stops and reservations retain priority."
    )
    st.caption("The four methods are independently runnable and meet in the fleet simulation; no physical robot is controlled.")
    with st.expander("Reproduction commands"):
        st.code(
            "python -m pytest -q\n"
            "python -m expert_system --all --output artifacts/diagnostic-scenarios.json\n"
            "python -m search_algorithm.main\n"
            "python tools/replay_demo.py --output artifacts/demo\n"
            "python tools/combined_demo.py --output artifacts/combined-demo.json\n"
            "python -m fuzzy_logic --clearance 3 --battery 85\n"
            "python -m multi_agent_system --ticks 12\n"
            "python tools/fleet_demo.py --output artifacts/fleet-demo.json\n"
            "python tools/benchmark_search.py --output artifacts/benchmark --repeats 5",
            language="bash",
        )
