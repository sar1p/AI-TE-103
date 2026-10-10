"""Exercise the real diagnostic engine through the Streamlit safety gate."""

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


def _run(app):
    app.run(timeout=20)
    assert not app.exception, [entry.message for entry in app.exception]
    return app


def test_real_diagnosis_pauses_then_corrected_observations_restore_movement():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = _run(AppTest.from_file(app_path))
    session = app.session_state["simulation"]
    start = session.planner.start
    record_count = len(session.records)
    app.toggle(key="diagnostic_gate").set_value(True)
    app.text_area(key="raw_facts").set_value(json.dumps({
        "motor_temperature": "high",
        "movement_status": "stalled",
        "sensor_lidar": "clear",
    }))
    app = _run(app)

    assert not app.error, [entry.value for entry in app.error]
    assert app.button(key="move_robot").disabled
    assert app.session_state["simulation"] is session
    assert session.planner.start == start
    assert len(session.records) == record_count
    assert any("pauses movement" in entry.value.lower() for entry in app.warning)

    app.text_area(key="raw_facts").set_value(json.dumps({
        "motor_temperature": "normal",
        "movement_status": "moving",
        "sensor_lidar": "clear",
    }))
    app = _run(app)
    assert not app.error
    assert not app.button(key="move_robot").disabled
    assert any("allows movement" in entry.value.lower() for entry in app.success)
    app.button(key="move_robot").click()
    app = _run(app)

    assert app.session_state["simulation"] is session
    assert session.planner.start != start
    assert len(session.records) == record_count + 1
    assert session.planner.initialization_count == 1


def test_real_engine_rejects_bad_values_and_keeps_robot_still():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    app = _run(AppTest.from_file(app_path))
    session = app.session_state["simulation"]
    start = session.planner.start
    record_count = len(session.records)
    app.toggle(key="diagnostic_gate").set_value(True)
    app.text_area(key="raw_facts").set_value(json.dumps({
        "motor_temperature": [],
        "movement_status": 17,
        "sensor_lidar": True,
    }))
    app = _run(app)

    assert not app.error
    assert app.button(key="move_robot").disabled
    assert any("invalid_input" in entry.value for entry in app.markdown)
    assert session.planner.start == start
    assert len(session.records) == record_count
