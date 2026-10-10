"""Schema and strict-JSON tests for the external diagnostic knowledge base."""

import json

import pytest

from expert_system.engine import (
    KnowledgeBaseError,
    load_knowledge_base,
    validate_knowledge_base,
)


def _payload():
    return load_knowledge_base().as_dict()


def _invalid_payload(case):
    payload = _payload()
    if case == "empty_rule_id":
        payload["rules"][0]["id"] = ""
    elif case == "duplicate_rule_id":
        payload["rules"][1]["id"] = payload["rules"][0]["id"]
    elif case == "empty_condition":
        payload["rules"][0]["conclusion"]["condition"] = ""
    elif case == "raw_derived_collision":
        payload["rules"][2]["conclusion"]["condition"] = "battery_voltage"
    elif case == "undeclared_premise":
        payload["rules"][0]["premises"]["unlisted_fact"] = True
    elif case == "unlabeled_provenance":
        payload["provenance"] = "Rules reviewed by an engineer."
    elif case == "unlabeled_rule":
        payload["rules"][0]["validation"] = "validated"
    elif case == "conflicting_assignment":
        payload["rules"].append(
            {
                "id": "R_CONFLICT",
                "validation": "illustrative",
                "premises": {"battery_voltage": "normal"},
                "conclusion": {
                    "condition": "battery_voltage_low",
                    "value": False,
                },
                "reason": "Illustrative conflicting test assignment.",
                "expose_finding": False,
                "recommendations": [],
            }
        )
    return payload


@pytest.mark.parametrize(
    "case",
    [
        "empty_rule_id",
        "duplicate_rule_id",
        "empty_condition",
        "raw_derived_collision",
        "undeclared_premise",
        "unlabeled_provenance",
        "unlabeled_rule",
        "conflicting_assignment",
    ],
)
def test_inconsistent_rule_data_is_rejected_before_inference(case):
    with pytest.raises(KnowledgeBaseError):
        validate_knowledge_base(_invalid_payload(case))


def test_knowledge_base_declares_the_supported_raw_fields_and_optional_groups():
    knowledge_base = load_knowledge_base()

    assert knowledge_base.required_observations == (
        "motor_temperature",
        "movement_status",
        "sensor_lidar",
    )
    assert knowledge_base.observations == {
        "motor_temperature": {
            "type": "string",
            "allowed_values": ("normal", "high"),
        },
        "movement_status": {
            "type": "string",
            "allowed_values": ("moving", "idle", "stalled"),
        },
        "sensor_lidar": {
            "type": "string",
            "allowed_values": ("clear", "blocked"),
        },
        "battery_voltage": {
            "type": "string",
            "allowed_values": ("normal", "low"),
        },
        "battery_connection": {
            "type": "string",
            "allowed_values": ("connected", "disconnected"),
        },
        "drive_status": {
            "type": "string",
            "allowed_values": ("normal", "fault"),
        },
        "encoder_feedback": {
            "type": "string",
            "allowed_values": ("present", "absent"),
        },
        "motor_connection": {
            "type": "string",
            "allowed_values": ("connected", "disconnected"),
        },
        "motor_enable": {
            "type": "string",
            "allowed_values": ("enabled", "disabled"),
        },
    }
    assert [(group.id, group.observations) for group in knowledge_base.groups] == [
        ("power", ("battery_voltage", "battery_connection")),
        ("drive_feedback", ("drive_status", "encoder_feedback")),
        ("motor_path", ("motor_connection", "motor_enable")),
    ]
    assert all(rule.validation == "illustrative" for rule in knowledge_base.rules)
    assert all("illustrative" in rule.reason.lower() for rule in knowledge_base.rules)


def test_default_knowledge_base_path_does_not_depend_on_the_working_directory(
    tmp_path, monkeypatch
):
    original = load_knowledge_base().as_dict()
    monkeypatch.chdir(tmp_path)

    assert load_knowledge_base().as_dict() == original


def test_loader_accepts_a_valid_external_knowledge_base_file(tmp_path):
    payload = _payload()
    path = tmp_path / "external-rules.json"
    path.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")

    loaded = load_knowledge_base(path)

    assert loaded.as_dict() == payload


@pytest.mark.parametrize(
    "json_text",
    [
        '{"schema_version": 1, "schema_version": 1}',
        '{"schema_version": NaN}',
    ],
)
def test_loader_rejects_duplicate_keys_and_non_finite_json(tmp_path, json_text):
    path = tmp_path / "malformed-kb.json"
    path.write_text(json_text, encoding="utf-8")

    with pytest.raises(KnowledgeBaseError):
        load_knowledge_base(path)


def test_validator_rejects_non_object_knowledge_bases():
    with pytest.raises(KnowledgeBaseError):
        validate_knowledge_base([_payload()])


def test_validated_knowledge_base_returns_an_isolated_json_document():
    payload = _payload()
    knowledge_base = validate_knowledge_base(payload)
    exported = knowledge_base.as_dict()
    exported["rules"][0]["premises"]["motor_temperature"] = "normal"

    assert payload["rules"][0]["premises"]["motor_temperature"] == "high"
    assert knowledge_base.as_dict()["rules"][0]["premises"]["motor_temperature"] == "high"
    assert json.loads(json.dumps(knowledge_base.as_dict(), allow_nan=False)) == payload
