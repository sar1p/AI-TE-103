"""Verify the new Streamlit workspaces with their actual algorithm modules."""

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "app.py"


def _run(app):
    app.run(timeout=40)
    assert not app.exception, [error.message for error in app.exception]
    return app


def _submit(app, label):
    next(button for button in app.button if button.label == label).click()
    return _run(app)


def test_fleet_persists_on_unrelated_reruns_and_fuzzy_inputs_change_real_output():
    app = _run(AppTest.from_file(APP_PATH))
    assert [tab.label for tab in app.tabs] == [
        "Route planner", "Diagnostics", "Evidence & methods", "Fleet coordination", "Fuzzy speed control"
    ]
    session = app.session_state["fleet_control"]
    before = deepcopy(session.to_dict())
    initial_speed = app.session_state["fuzzy_comparison"]["mamdani"]["output"]["speed_percent"]
    app.slider(key="fuzzy_battery").set_value(5.0)
    app = _run(app)
    assert app.session_state["fleet_control"] is session
    assert session.to_dict() == before
    assert app.session_state["fuzzy_comparison"]["mamdani"]["output"]["speed_percent"] < initial_speed
    app.button(key="fleet_run").click()
    app = _run(app)
    assert session.simulation.tick_count == 12
    assert len(session.history) == 12
    assert any(agent.steps for agent in session.simulation.agents.values())
    after = deepcopy(session.to_dict())
    app = _run(app)
    assert session.to_dict() == after


def test_fleet_diagnostic_form_pauses_one_robot_then_corrected_form_resumes_it():
    app = _run(AppTest.from_file(APP_PATH))
    session = app.session_state["fleet_control"]
    original = session.simulation.agents["R01"].position
    app.selectbox(key="fleet_case_R01").set_value("battery-multi-hop")
    app = _submit(app, "Apply R01 readings")
    assert session.preview_controls()["R01"]["applied_factor"] == 0
    app.button(key="fleet_run").click()
    app = _run(app)
    assert session.simulation.agents["R01"].position == original
    assert session.simulation.agents["R02"].steps > 0
    assert any("R01" in warning.value and "overridden" in warning.value for warning in app.warning)
    app.selectbox(key="fleet_case_R01").set_value("corrected-observations")
    app = _submit(app, "Apply R01 readings")
    app.button(key="fleet_run").click()
    app = _run(app)
    assert session.simulation.agents["R01"].position != original
    app.button(key="fleet_reset").click()
    app = _run(app)
    assert app.session_state["fleet_control"] is not session
    assert app.session_state["fleet_control"].simulation.tick_count == 0
