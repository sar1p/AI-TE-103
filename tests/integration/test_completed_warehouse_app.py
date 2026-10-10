"""Exercise the completed warehouse UI with its real diagnostic engine."""

from copy import deepcopy
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "app.py"
FORM_SUBMIT_LABEL = "Apply observations and evaluate"


def _run(app):
    app.run(timeout=30)
    assert not app.exception, [entry.message for entry in app.exception]
    return app


def _app():
    return _run(AppTest.from_file(APP_PATH))


def _load_preset(app, scenario_id):
    app.selectbox(key="diagnostic_preset_choice").set_value(scenario_id)
    app.button(key="diagnostic_preset_load").click()
    return _run(app)


def _simulation(app):
    return app.session_state["simulation"]


def _submit_observations(app):
    next(button for button in app.button if button.label == FORM_SUBMIT_LABEL).click()
    return _run(app)


def _snapshot(session):
    return {
        "revision": session.planner.grid.revision,
        "rows": session.planner.grid.to_rows(),
        "start": session.planner.start,
        "goal": session.planner.goal,
        "records": deepcopy(session.records),
        "applied_events": deepcopy(session.applied_events),
        "initialization_count": session.planner.initialization_count,
    }


def _visible_diagnosis(app):
    return "\n".join(
        [
            *(entry.value for entry in app.markdown),
            *(entry.value for entry in app.info),
            *(entry.value for entry in app.warning),
            *(entry.value for entry in app.success),
            *(entry.value for entry in app.caption),
        ]
    )


def test_battery_preset_shows_multihop_chain_and_pauses_movement_atomically():
    app = _app()
    app.toggle(key="diagnostic_gate").set_value(True)
    app = _load_preset(app, "battery-multi-hop")

    session = _simulation(app)
    planner = session.planner
    initial_start = planner.start
    initial_records = len(session.records)
    visible = _visible_diagnosis(app)
    assert all(rule_id in visible for rule_id in ("R03", "R04", "R05", "R06"))
    assert "Battery power path issue" in visible
    assert "Battery related stall" in visible
    assert any("pauses movement" in entry.value.lower() for entry in app.warning)
    assert app.button(key="move_robot").disabled

    # A map event remains available while gated; the following movement does not.
    assert not app.button(key="next_event").disabled
    app.button(key="next_event").click()
    app = _run(app)
    assert session.planner is planner
    assert planner.grid.revision == 1
    assert planner.start == initial_start
    assert len(session.records) == initial_records + 1
    assert app.button(key="next_event").disabled
    assert app.button(key="run_remaining").disabled
    assert app.button(key="move_robot").disabled

    paused_state = _snapshot(session)
    app.radio(key="route_overlay").set_value("A*")
    app = _run(app)
    assert _snapshot(session) == paused_state
    assert session.planner.initialization_count == 1


def test_guided_correction_clears_old_findings_and_resumes_same_planner():
    app = _app()
    app.toggle(key="diagnostic_gate").set_value(True)
    app = _load_preset(app, "battery-multi-hop")
    session = _simulation(app)
    planner = session.planner
    initial_start = planner.start
    initial_records = len(session.records)
    assert app.button(key="move_robot").disabled

    app.selectbox(key="guided_observation_movement_status").set_value("moving")
    app.selectbox(key="guided_observation_battery_voltage").set_value("normal")
    app.selectbox(key="guided_observation_battery_connection").set_value("connected")
    app = _submit_observations(app)

    applied = json.loads(app.text_area(key="raw_facts").value)
    assert applied["movement_status"] == "moving"
    assert applied["battery_voltage"] == "normal"
    assert applied["battery_connection"] == "connected"
    visible = _visible_diagnosis(app)
    assert "**Diagnosis status:** `ok`" in visible
    assert "No rule returned a finding" in visible
    assert not any(rule_id in visible for rule_id in ("R03", "R04", "R05", "R06"))
    assert any("allows movement" in entry.value.lower() for entry in app.success)
    assert not app.button(key="move_robot").disabled

    app.button(key="move_robot").click()
    app = _run(app)
    assert _simulation(app) is session
    assert session.planner is planner
    assert session.planner.initialization_count == 1
    assert abs(planner.start[0] - initial_start[0]) + abs(
        planner.start[1] - initial_start[1]
    ) == 1
    assert len(session.records) == initial_records + 1


def test_incomplete_group_preset_reports_missing_observation_and_blocks_gate():
    app = _load_preset(_app(), "partial-power")
    session = _simulation(app)
    app.toggle(key="diagnostic_gate").set_value(True)
    app = _run(app)

    visible = _visible_diagnosis(app)
    assert "**Diagnosis status:** `insufficient_evidence`" in visible
    assert "Battery connection" in visible
    assert app.button(key="move_robot").disabled
    assert session.planner.start == tuple(session.scenario.start)
    assert len(session.records) == 1


def test_preset_and_json_draft_sync_only_apply_when_guided_form_is_submitted():
    app = _load_preset(_app(), "battery-multi-hop")
    preset_facts = json.loads(app.text_area(key="raw_facts").value)
    assert preset_facts["battery_voltage"] == "low"
    assert app.selectbox(key="guided_observation_movement_status").value == "stalled"
    assert app.selectbox(key="guided_observation_battery_connection").value == "disconnected"

    changed_raw = json.dumps({
        "motor_temperature": "high",
        "movement_status": "stalled",
        "sensor_lidar": "clear",
    })
    app.text_area(key="raw_facts").set_value(changed_raw)
    app = _run(app)

    # Editing the active JSON does not silently refresh the separate draft.
    assert app.text_area(key="raw_facts").value == changed_raw
    assert app.selectbox(key="guided_observation_battery_voltage").value == "low"

    app.button(key="load_json_into_guided_form").click()
    app = _run(app)
    assert app.text_area(key="raw_facts").value == changed_raw
    assert app.selectbox(key="guided_observation_motor_temperature").value == "high"
    assert app.selectbox(key="guided_observation_battery_voltage").value is None
    assert app.selectbox(key="guided_observation_battery_connection").value is None

    app.selectbox(key="guided_observation_movement_status").set_value("moving")
    assert app.text_area(key="raw_facts").value == changed_raw

    app = _submit_observations(app)
    applied = json.loads(app.text_area(key="raw_facts").value)
    assert applied["motor_temperature"] == "high"
    assert applied["movement_status"] == "moving"
    assert applied["battery_voltage"] is None
    assert applied["battery_connection"] is None


def test_duplicate_json_keys_fail_closed_when_gate_is_enabled():
    app = _app()
    session = _simulation(app)
    before = _snapshot(session)

    app.text_area(key="raw_facts").set_value(
        '{"motor_temperature":"normal","motor_temperature":"high",'
        '"movement_status":"moving","sensor_lidar":"clear"}'
    )
    app.toggle(key="diagnostic_gate").set_value(True)
    app = _run(app)

    assert any("Duplicate JSON object key" in entry.value for entry in app.error)
    assert app.button(key="move_robot").disabled
    assert _snapshot(session) == before
