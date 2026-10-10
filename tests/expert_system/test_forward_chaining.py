"""Behavioral tests for the external-rule forward-chaining engine."""

from copy import deepcopy

import pytest

from expert_system.engine import diagnose, infer, load_knowledge_base, validate_knowledge_base


CORE_HEALTHY = {
    "motor_temperature": "normal",
    "movement_status": "moving",
    "sensor_lidar": "clear",
}


def _rule(
    rule_id,
    premises,
    condition,
    *,
    expose_finding=False,
    pause_robot=False,
    recommendations=None,
):
    conclusion = {"condition": condition}
    if pause_robot:
        conclusion["pause_robot"] = True
    return {
        "id": rule_id,
        "validation": "illustrative",
        "premises": premises,
        "conclusion": conclusion,
        "reason": f"Illustrative test rule {rule_id}.",
        "expose_finding": expose_finding,
        "recommendations": recommendations or [],
    }


def _single_seed_knowledge_base(rules):
    return {
        "schema_version": 1,
        "provenance": "Illustrative fixture rules for engine behavior tests.",
        "required_observations": ["seed"],
        "observations": {
            "seed": {"type": "string", "allowed_values": ["on", "off"]}
        },
        "groups": [],
        "rules": rules,
    }


def _assert_grounded_chronological_trace(raw_facts, trace):
    available = {key: value for key, value in raw_facts.items() if value is not None}
    for step in trace:
        for key, expected in step["premises"].items():
            assert key in available
            assert available[key] == expected
        conclusion = step["conclusion"]
        available[conclusion["condition"]] = conclusion.get("value", True)


def test_consumer_before_producer_requires_multiple_forward_chaining_passes():
    pause = [{"action": "pause_robot", "reason": "Illustrative test pause."}]
    knowledge_base = _single_seed_knowledge_base(
        [
            _rule(
                "consumer",
                {"derived_middle": True},
                "final_condition",
                expose_finding=True,
                pause_robot=True,
                recommendations=pause,
            ),
            _rule("producer", {"seed": "on"}, "derived_middle"),
        ]
    )

    result = infer({"seed": "on"}, knowledge_base)

    assert result["status"] == "ok"
    assert result["rule_trace"] == [
        {
            "rule_id": "producer",
            "premises": {"seed": "on"},
            "conclusion": {"condition": "derived_middle"},
            "reason": "Illustrative test rule producer.",
        },
        {
            "rule_id": "consumer",
            "premises": {"derived_middle": True},
            "conclusion": {
                "condition": "final_condition",
                "pause_robot": True,
            },
            "reason": "Illustrative test rule consumer.",
        },
    ]
    assert result["findings"] == [
        {"condition": "final_condition", "rule_ids": ["producer", "consumer"]}
    ]
    assert result["recommendations"] == pause
    assert result["missing_facts"] == []


def test_grounded_cycle_terminates_once_and_cannot_self_start():
    knowledge_base = _single_seed_knowledge_base(
        [
            _rule("cycle_to_a", {"derived_b": True}, "derived_a"),
            _rule("cycle_to_b", {"derived_a": True}, "derived_b"),
            _rule("seed_a", {"seed": "on"}, "derived_a"),
        ]
    )

    unsupported = infer({}, knowledge_base)
    assert unsupported["status"] == "insufficient_evidence"
    assert unsupported["missing_facts"] == ["seed"]
    assert unsupported["rule_trace"] == []
    assert unsupported["findings"] == []

    grounded = infer({"seed": "on"}, knowledge_base)
    fired_ids = [step["rule_id"] for step in grounded["rule_trace"]]
    assert grounded["status"] == "ok"
    assert fired_ids == ["seed_a", "cycle_to_b", "cycle_to_a"]
    assert len(fired_ids) == len(set(fired_ids))
    assert grounded["findings"] == []
    _assert_grounded_chronological_trace({"seed": "on"}, grounded["rule_trace"])


@pytest.mark.parametrize(
    ("facts", "rule_ids", "conditions", "finding_rule_ids"),
    [
        (
            CORE_HEALTHY
            | {
                "movement_status": "stalled",
                "battery_voltage": "low",
                "battery_connection": "disconnected",
            },
            ["R03", "R04", "R05", "R06"],
            ["battery_power_path_issue", "battery_related_stall"],
            [
                ["R03", "R04", "R05"],
                ["R03", "R04", "R05", "R06"],
            ],
        ),
        (
            CORE_HEALTHY
            | {"drive_status": "fault", "encoder_feedback": "absent"},
            ["R07", "R08", "R09"],
            ["drive_encoder_fault"],
            [["R07", "R08", "R09"]],
        ),
        (
            CORE_HEALTHY
            | {"motor_connection": "disconnected", "motor_enable": "enabled"},
            ["R10", "R11"],
            ["motor_connection_fault"],
            [["R10", "R11"]],
        ),
    ],
)
def test_supported_multi_hop_chains_have_literal_expected_provenance(
    facts, rule_ids, conditions, finding_rule_ids
):
    result = diagnose(facts)

    assert result["status"] == "ok"
    assert [step["rule_id"] for step in result["rule_trace"]] == rule_ids
    assert result["findings"] == [
        {"condition": condition, "rule_ids": chain_ids}
        for condition, chain_ids in zip(conditions, finding_rule_ids)
    ]
    assert result["missing_facts"] == []
    _assert_grounded_chronological_trace(facts, result["rule_trace"])
    assert all("illustrative" in step["reason"].lower() for step in result["rule_trace"])


@pytest.mark.parametrize(
    ("known_observation", "missing_observation"),
    [
        ("battery_voltage", "battery_connection"),
        ("drive_status", "encoder_feedback"),
        ("motor_connection", "motor_enable"),
    ],
)
def test_partial_optional_group_requests_only_its_missing_member(
    known_observation, missing_observation
):
    known_values = {
        "battery_voltage": "normal",
        "drive_status": "normal",
        "motor_connection": "connected",
    }
    facts = CORE_HEALTHY | {known_observation: known_values[known_observation]}

    result = diagnose(facts)

    assert result["status"] == "insufficient_evidence"
    assert result["missing_facts"] == [missing_observation]
    assert result["findings"] == []


def test_optional_groups_are_inactive_when_absent_or_null():
    complete_core = diagnose(CORE_HEALTHY)
    null_group_member = diagnose(CORE_HEALTHY | {"battery_voltage": None})

    assert complete_core["status"] == null_group_member["status"] == "ok"
    assert complete_core["missing_facts"] == []
    assert null_group_member["missing_facts"] == []
    assert complete_core["findings"] == null_group_member["findings"] == []


def test_known_negative_values_are_complete_evidence_and_do_not_fire_fault_rules():
    facts = CORE_HEALTHY | {
        "battery_voltage": "normal",
        "battery_connection": "connected",
        "drive_status": "normal",
        "encoder_feedback": "present",
        "motor_connection": "connected",
        "motor_enable": "disabled",
    }

    result = diagnose(facts)

    assert result["status"] == "ok"
    assert result["missing_facts"] == []
    assert result["findings"] == []
    assert result["rule_trace"] == []


def test_correction_removes_only_the_dependent_upstream_and_downstream_findings():
    faulty = CORE_HEALTHY | {
        "movement_status": "stalled",
        "battery_voltage": "low",
        "battery_connection": "disconnected",
        "drive_status": "fault",
        "encoder_feedback": "absent",
    }
    corrected = faulty | {"battery_voltage": "normal"}

    first = diagnose(faulty)
    second = diagnose(corrected)

    assert first["findings"] == [
        {
            "condition": "battery_power_path_issue",
            "rule_ids": ["R03", "R04", "R05"],
        },
        {
            "condition": "battery_related_stall",
            "rule_ids": ["R03", "R04", "R05", "R06"],
        },
        {"condition": "drive_encoder_fault", "rule_ids": ["R07", "R08", "R09"]},
    ]
    assert second["findings"] == [
        {"condition": "drive_encoder_fault", "rule_ids": ["R07", "R08", "R09"]}
    ]
    assert [step["rule_id"] for step in second["rule_trace"]] == ["R04", "R07", "R08", "R09"]


@pytest.mark.parametrize(
    "facts",
    [
        CORE_HEALTHY | {"unexpected_observation": "normal"},
        CORE_HEALTHY | {"battery_voltage_low": True},
        CORE_HEALTHY | {"battery_power_path_issue": True},
        CORE_HEALTHY | {"drive_encoder_fault": True},
    ],
)
def test_unknown_or_derived_fact_injection_is_invalid(facts):
    result = diagnose(facts)

    assert result == {
        "status": "invalid_input",
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": [],
    }


def test_input_and_returned_results_are_isolated_and_deterministic():
    facts = CORE_HEALTHY | {
        "movement_status": "stalled",
        "battery_voltage": "low",
        "battery_connection": "disconnected",
    }
    original = deepcopy(facts)

    first = diagnose(facts)
    expected = deepcopy(first)
    assert facts == original
    assert diagnose(facts) == expected

    first["rule_trace"][0]["premises"]["battery_voltage"] = "normal"
    first["rule_trace"][0]["conclusion"]["condition"] = "invented"
    first["findings"][0]["rule_ids"].append("invented_rule")
    first["recommendations"].clear()

    assert facts == original
    assert diagnose(facts) == expected


def test_loaded_knowledge_base_isolated_from_the_source_payload():
    payload = load_knowledge_base().as_dict()
    knowledge_base = validate_knowledge_base(payload)
    payload["rules"][2]["premises"]["battery_voltage"] = "normal"

    result = infer(
        CORE_HEALTHY
        | {
            "movement_status": "stalled",
            "battery_voltage": "low",
            "battery_connection": "disconnected",
        },
        knowledge_base,
    )

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
