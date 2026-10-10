"""Evaluate the teammate's two illustrative rules using the agreed contract.

This starter evaluates independent rules once. Chained inference and an external
knowledge base remain part of the teammate's unfinished project scope.
"""

from copy import deepcopy


OBSERVATION_VALUES = {
    "motor_temperature": frozenset({"normal", "high"}),
    "movement_status": frozenset({"moving", "idle", "stalled"}),
    "sensor_lidar": frozenset({"clear", "blocked"}),
}

RULES = [
    {
        "id": "R01",
        "validation": "illustrative",
        "premises": {"motor_temperature": "high", "movement_status": "stalled"},
        "conclusion": {"condition": "suspected_motor_overheating", "pause_robot": True},
        "recommendation": "Pause the robot and inspect motor temperature and drive load.",
        "reason": (
            "Illustrative rule: a high motor temperature and stalled movement "
            "support suspected motor overheating; they do not establish the cause."
        ),
    },
    {
        "id": "R02",
        "validation": "illustrative",
        "premises": {"sensor_lidar": "blocked"},
        "conclusion": {"condition": "lidar_obstruction", "pause_robot": True},
        "recommendation": "Pause the robot and inspect the lidar sensor for an obstruction.",
        "reason": (
            "Illustrative rule: a reported lidar obstruction supports inspecting "
            "the sensor before resuming simulated movement."
        ),
    },
]


def _empty_result(status: str) -> dict:
    return {
        "status": status,
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": [],
    }


def diagnose(facts: dict[str, object]) -> dict:
    """Return fresh findings; missing/None observations remain unknown.

Only the documented categorical observations are supported. Unsupported names,
types, or values return invalid_input without firing any rule.
"""
    if type(facts) is not dict:
        return _empty_result("invalid_input")
    for key, value in facts.items():
        if type(key) is not str or key not in OBSERVATION_VALUES:
            return _empty_result("invalid_input")
        if value is not None and (
            type(value) is not str or value not in OBSERVATION_VALUES[key]
        ):
            return _empty_result("invalid_input")

    result = _empty_result("ok")
    known_facts = {key: value for key, value in facts.items() if value is not None}
    result["missing_facts"] = [
        key for key in OBSERVATION_VALUES if key not in known_facts
    ]
    if result["missing_facts"]:
        result["status"] = "insufficient_evidence"

    for rule in RULES:
        if not all(
            known_facts.get(key) == expected
            for key, expected in rule["premises"].items()
        ):
            continue
        result["findings"].append({
            "condition": rule["conclusion"]["condition"],
            "rule_ids": [rule["id"]],
        })
        result["recommendations"].append({
            "action": "pause_robot",
            "reason": rule["recommendation"],
        })
        result["rule_trace"].append({
            "rule_id": rule["id"],
            "premises": deepcopy(rule["premises"]),
            "conclusion": deepcopy(rule["conclusion"]),
            "reason": rule["reason"],
        })
    return result
