"""Exercise all four methods together and independently check fleet transitions."""

from copy import deepcopy
import json

import pytest

from expert_system.scenarios import load_scenario
from interface.fleet_session import FleetControlSession, HEALTHY_OBSERVATIONS
from tools.fleet_demo import run_demo


@pytest.mark.parametrize("method", ["mamdani", "sugeno"])
def test_four_methods_finish_crossing_without_vertex_conflict_or_swap(method):
    session = FleetControlSession()
    session.set_method(method)
    planners = {key: agent.planner for key, agent in session.simulation.agents.items()}
    prior = {key: agent.position for key, agent in session.simulation.agents.items()}
    for _ in range(100):
        snapshot = session.step()
        positions = {robot["id"]: tuple(robot["position"]) for robot in snapshot["robots"]}
        assert len(set(positions.values())) == len(positions)
        for robot_id, position in positions.items():
            assert sum(abs(a - b) for a, b in zip(prior[robot_id], position)) <= 1
            assert position not in session.simulation.grid.blocked
            for other_id in positions:
                if robot_id != other_id:
                    assert not (position == prior[other_id] and prior[robot_id] == positions[other_id])
        prior = positions
        if all(robot["status"] == "arrived" for robot in snapshot["robots"]):
            break
    assert all(robot["status"] == "arrived" for robot in snapshot["robots"])
    assert any(message["kind"] == "denial" for message in snapshot["messages"])
    assert any(message["kind"] == "grant" for message in snapshot["messages"])
    for robot_id, agent in session.simulation.agents.items():
        assert agent.planner is planners[robot_id]
        assert agent.planner.initialization_count == 1
    exported = session.to_dict()
    assert exported["fuzzy_method"] == method
    assert len(exported["history"]) == snapshot["tick"]
    assert exported["last_step_controls"]["R01"]["fuzzy"]["provenance"]
    json.dumps(exported, allow_nan=False)


@pytest.mark.parametrize("method", ["mamdani", "sugeno"])
def test_diagnosis_overrides_positive_fuzzy_proposal_and_correction_resumes(method):
    session = FleetControlSession()
    session.set_method(method)
    session.set_observations("R01", load_scenario("battery-multi-hop")["facts"])
    start = session.simulation.agents["R01"].position
    session.run(10)
    control = session.last_step_controls["R01"]
    assert control["proposed_factor"] > 0
    assert control["applied_factor"] == 0
    assert not control["movement_allowed"]
    assert session.simulation.agents["R01"].position == start
    assert session.simulation.agents["R02"].steps > 0
    session.set_observations("R01", deepcopy(HEALTHY_OBSERVATIONS))
    session.run(100)
    assert all(robot["status"] == "arrived" for robot in session.simulation.snapshot()["robots"])
    assert session.last_step_controls["R01"]["diagnostics"]["result"]["findings"] == []


@pytest.mark.parametrize("facts", [{}, {"motor_temperature": "invalid"}])
def test_unknown_or_invalid_diagnostic_observations_fail_closed(facts):
    session = FleetControlSession()
    session.set_observations("R01", facts)
    start = session.simulation.agents["R01"].position
    session.run(5)
    assert session.simulation.agents["R01"].position == start
    assert session.preview_controls()["R01"]["applied_factor"] == 0


def test_zero_battery_overrides_controller_without_inventing_a_diagnostic_finding():
    session = FleetControlSession()
    session.set_battery("R01", 0)
    control = session.preview_controls()["R01"]
    assert control["diagnostics"]["result"]["status"] == "ok"
    assert control["diagnostics"]["result"]["findings"] == []
    assert control["proposed_factor"] > 0
    assert control["applied_factor"] == 0
    session.run(5)
    assert session.simulation.agents["R01"].steps == 0


def test_previews_exports_and_rejected_settings_do_not_advance_or_mutate_state():
    session = FleetControlSession()
    before = session.to_dict()
    session.preview_controls()
    assert session.to_dict() == before
    invalid_observations = [{"x": float("nan")}, {1: "invalid key"}]
    cycle = {}
    cycle["cycle"] = cycle
    invalid_observations.append(cycle)
    for facts in invalid_observations:
        with pytest.raises(ValueError):
            session.set_observations("R01", facts)
        assert session.to_dict() == before
    for battery in [True, -1, 101, float("inf")]:
        with pytest.raises(ValueError):
            session.set_battery("R01", battery)
        assert session.to_dict() == before
    with pytest.raises(ValueError):
        session.set_method([])
    with pytest.raises(ValueError):
        session.set_observations("missing", {})
    assert session.to_dict() == before
    exported = session.to_dict()
    exported["fleet"]["robots"][0]["position"][0] = 999
    exported["next_step_controls"]["R01"]["fuzzy"]["output"]["speed_factor"] = 1
    assert session.to_dict() == before


@pytest.mark.parametrize("method", ["mamdani", "sugeno"])
def test_reproducible_cli_demo_checks_actual_results(method):
    document = run_demo(method)
    assert all(document["checks"].values())
    assert document["crossing"]["fleet"]["tick"] > 6
    assert document["diagnostic_pause"]["last_step_controls"]["R01"]["applied_factor"] == 0
    json.dumps(document, allow_nan=False)
