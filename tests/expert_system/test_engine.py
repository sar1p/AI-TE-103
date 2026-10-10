"""Expected outcomes for the teammate's two illustrative diagnostic rules."""

from copy import deepcopy
import json

import pytest

from expert_system.engine import diagnose
from interface.diagnostics import evaluate_diagnostics


HEALTHY = {
    "motor_temperature": "normal",
    "movement_status": "moving",
    "sensor_lidar": "clear",
}


def test_empty_observations_use_the_agreed_incomplete_status():
    result = diagnose({})

    assert result == {
        "status": "insufficient_evidence",
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": ["motor_temperature", "movement_status", "sensor_lidar"],
    }


@pytest.mark.parametrize(
    ("changes", "expected_findings", "rule_ids"),
    [
        (
            {"motor_temperature": "high", "movement_status": "stalled"},
            ["suspected_motor_overheating"],
            ["R01"],
        ),
        ({"sensor_lidar": "blocked"}, ["lidar_obstruction"], ["R02"]),
        (
            {
                "motor_temperature": "high",
                "movement_status": "stalled",
                "sensor_lidar": "blocked",
            },
            ["suspected_motor_overheating", "lidar_obstruction"],
            ["R01", "R02"],
        ),
    ],
)
def test_supported_faults_follow_the_contract_and_pause_movement(
    changes, expected_findings, rule_ids
):
    facts = HEALTHY | changes
    result = diagnose(facts)

    assert result["status"] == "ok"
    assert result["findings"] == [
        {"condition": condition, "rule_ids": [rule_id]}
        for condition, rule_id in zip(expected_findings, rule_ids)
    ]
    assert [entry["rule_id"] for entry in result["rule_trace"]] == rule_ids
    for entry, condition in zip(result["rule_trace"], expected_findings):
        assert set(entry) == {"rule_id", "premises", "conclusion", "reason"}
        assert entry["conclusion"]["condition"] == condition
        assert entry["premises"]
        assert all(facts[key] == value for key, value in entry["premises"].items())
        assert "illustrative" in entry["reason"].lower()
    assert result["recommendations"]
    assert all(
        set(item) == {"action", "reason"} and item["action"] == "pause_robot"
        for item in result["recommendations"]
    )
    assert result["missing_facts"] == []
    assert json.loads(json.dumps(result, allow_nan=False)) == result
    state = evaluate_diagnostics(facts)
    assert state.status == "ready", state.message
    assert state.result == result
    assert not state.can_move


@pytest.mark.parametrize(
    ("temperature", "movement"),
    [("normal", "moving"), ("normal", "idle"), ("high", "moving"), ("normal", "stalled")],
)
def test_complete_observations_without_a_matching_rule_allow_simulated_movement(
    temperature, movement
):
    facts = HEALTHY | {"motor_temperature": temperature, "movement_status": movement}
    result = diagnose(facts)

    assert result["status"] == "ok"
    assert result["findings"] == result["rule_trace"] == result["recommendations"] == []
    assert result["missing_facts"] == []
    state = evaluate_diagnostics(facts)
    assert state.status == "ready"
    assert state.can_move


def test_missing_and_null_observations_are_unknown():
    assert diagnose(dict.fromkeys(HEALTHY)) == diagnose({})
    facts = {"motor_temperature": "high", "sensor_lidar": "clear"}
    result = diagnose(facts)

    assert result["status"] == "insufficient_evidence"
    assert result["missing_facts"] == ["movement_status"]
    assert result["findings"] == result["rule_trace"] == []
    assert not evaluate_diagnostics(facts).can_move


@pytest.mark.parametrize(
    ("facts", "condition", "rule_id", "missing"),
    [
        (
            {"sensor_lidar": "blocked"},
            "lidar_obstruction",
            "R02",
            ["motor_temperature", "movement_status"],
        ),
        (
            {"motor_temperature": "high", "movement_status": "stalled"},
            "suspected_motor_overheating",
            "R01",
            ["sensor_lidar"],
        ),
    ],
)
def test_partial_evidence_retains_a_supported_finding_but_stays_incomplete(
    facts, condition, rule_id, missing
):
    result = diagnose(facts)

    assert result["status"] == "insufficient_evidence"
    assert result["findings"] == [{"condition": condition, "rule_ids": [rule_id]}]
    assert result["missing_facts"] == missing
    state = evaluate_diagnostics(facts)
    assert state.status == "ready", state.message
    assert not state.can_move


@pytest.mark.parametrize(
    "facts",
    [
        None,
        [],
        {1: "normal"},
        {"unexpected_observation": "low"},
        HEALTHY | {"unexpected_observation": "normal"},
        HEALTHY | {"motor_temperature": "warm"},
        HEALTHY | {"motor_temperature": 42},
        HEALTHY | {"motor_temperature": []},
        HEALTHY | {"motor_temperature": float("nan")},
        HEALTHY | {"movement_status": 17},
        HEALTHY | {"movement_status": "unknown"},
        HEALTHY | {"sensor_lidar": True},
        HEALTHY | {"sensor_lidar": {}},
        HEALTHY | {"sensor_lidar": ("clear",)},
    ],
)
def test_unsupported_inputs_return_invalid_without_inventing_findings(facts):
    result = diagnose(facts)

    assert result == {
        "status": "invalid_input",
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": [],
    }
    state = evaluate_diagnostics(facts)
    assert not state.can_move
    if state.status == "ready":
        assert state.result["status"] == "invalid_input"


def test_corrections_recompute_from_raw_observations_without_mutating_them():
    faulty = HEALTHY | {
        "motor_temperature": "high",
        "movement_status": "stalled",
        "sensor_lidar": "blocked",
    }
    original = deepcopy(faulty)
    first = diagnose(faulty)
    corrected = diagnose(HEALTHY)

    assert len(first["findings"]) == 2
    assert faulty == original
    assert corrected["findings"] == corrected["rule_trace"] == corrected["recommendations"] == []
    assert diagnose(faulty) == first
    assert evaluate_diagnostics(HEALTHY).can_move


def test_returned_trace_cannot_mutate_rules_or_later_results():
    facts = HEALTHY | {"sensor_lidar": "blocked"}
    expected = diagnose(facts)
    modified = diagnose(facts)
    modified["rule_trace"][0]["premises"]["sensor_lidar"] = "clear"
    modified["rule_trace"][0]["conclusion"]["condition"] = "invented_condition"
    modified["findings"][0]["rule_ids"].append("invented_rule")

    assert diagnose(facts) == expected


def test_newly_supported_battery_observations_retain_the_full_chain():
    facts = HEALTHY | {
        "movement_status": "stalled",
        "battery_voltage": "low",
        "battery_connection": "disconnected",
    }

    result = diagnose(facts)

    assert result["status"] == "ok"
    assert result["findings"] == [
        {
            "condition": "battery_power_path_issue",
            "rule_ids": ["R03", "R04", "R05"],
        },
        {
            "condition": "battery_related_stall",
            "rule_ids": ["R03", "R04", "R05", "R06"],
        },
    ]
    assert [entry["rule_id"] for entry in result["rule_trace"]] == [
        "R03", "R04", "R05", "R06"
    ]
    assert {item["action"] for item in result["recommendations"]} == {
        "pause_robot",
        "check_power",
        "check_drive",
    }
    assert result["missing_facts"] == []
