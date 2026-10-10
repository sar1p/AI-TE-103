"""Exercise the standalone diagnostic CLI without launching the visual app."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import expert_system.main as diagnostic_cli
from expert_system.scenarios import load_scenarios


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _run_cli(*arguments, cwd=None, input_text=None):
    environment = os.environ.copy()
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        str(REPOSITORY_ROOT)
        if not inherited_pythonpath
        else str(REPOSITORY_ROOT) + os.pathsep + inherited_pythonpath
    )
    return subprocess.run(
        [sys.executable, "-m", "expert_system.main", *arguments],
        cwd=cwd or REPOSITORY_ROOT,
        env=environment,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _export(process):
    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    return json.loads(process.stdout)


def test_cli_lists_named_cases_and_runs_battery_case_from_another_directory(tmp_path):
    listing = _export(_run_cli("--list-scenarios", cwd=tmp_path))
    assert [item["id"] for item in listing["scenarios"]] == [
        "battery-multi-hop",
        "corrected-observations",
        "drive-encoder-multi-hop",
        "empty-input",
        "invalid-observation",
        "motor-connection-multi-hop",
        "partial-power",
        "simultaneous-faults",
    ]

    selected = _export(
        _run_cli("--scenario", "battery-multi-hop", cwd=tmp_path)
    )
    assert selected["input"]["kind"] == "scenario"
    assert selected["input"]["id"] == "battery-multi-hop"
    assert selected["input"]["facts"] == {
        "motor_temperature": "normal",
        "movement_status": "stalled",
        "sensor_lidar": "clear",
        "battery_voltage": "low",
        "battery_connection": "disconnected",
    }
    assert selected["diagnosis"]["status"] == "ok"
    assert selected["diagnosis"]["findings"] == [
        {
            "condition": "battery_power_path_issue",
            "rule_ids": ["R03", "R04", "R05"],
        },
        {
            "condition": "battery_related_stall",
            "rule_ids": ["R03", "R04", "R05", "R06"],
        },
    ]
    assert selected["expectation_match"] is True
    assert selected["metadata"]["knowledge_base"]["schema_version"] == 1
    assert selected["metadata"]["knowledge_base"]["source"] == (
        "expert_system/knowledge_base.json"
    )
    assert "illustrative" in selected["metadata"]["knowledge_base"]["provenance"].lower()


def test_cli_all_scenarios_match_literal_expected_conditions():
    exported = _export(_run_cli("--all"))
    expected = {
        "battery-multi-hop": (
            "ok",
            ["battery_power_path_issue", "battery_related_stall"],
        ),
        "corrected-observations": ("ok", []),
        "drive-encoder-multi-hop": ("ok", ["drive_encoder_fault"]),
        "empty-input": ("insufficient_evidence", []),
        "invalid-observation": ("invalid_input", []),
        "motor-connection-multi-hop": ("ok", ["motor_connection_fault"]),
        "partial-power": ("insufficient_evidence", []),
        "simultaneous-faults": (
            "ok",
            [
                "suspected_motor_overheating",
                "lidar_obstruction",
                "battery_power_path_issue",
                "battery_related_stall",
                "drive_encoder_fault",
                "motor_connection_fault",
            ],
        ),
    }

    assert exported["input"] == {"kind": "all_scenarios", "count": len(expected)}
    assert exported["scenario_validation"] == {"passed": True, "failed_ids": []}
    assert {
        case["input"]["id"]: (
            case["diagnosis"]["status"],
            [finding["condition"] for finding in case["diagnosis"]["findings"]],
            case["expectation_match"],
        )
        for case in exported["cases"]
    } == {scenario_id: (*outcome, True) for scenario_id, outcome in expected.items()}

    assert {
        case["input"]["id"]: case["input"]["facts"]
        for case in exported["cases"]
    } == {scenario["id"]: scenario["facts"] for scenario in load_scenarios()}


def test_facts_stdin_and_output_file_emit_the_same_json_export(tmp_path):
    facts = {
        "motor_temperature": "normal",
        "movement_status": "stalled",
        "sensor_lidar": "clear",
        "battery_voltage": "low",
        "battery_connection": "disconnected",
    }
    output_path = tmp_path / "nested" / "exports" / "diagnosis.json"
    process = _run_cli(
        "--facts",
        "-",
        "--output-file",
        str(output_path),
        cwd=tmp_path,
        input_text=json.dumps(facts),
    )

    exported = _export(process)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved == exported
    assert exported["input"] == {
        "kind": "facts",
        "source": "stdin",
        "facts": facts,
    }
    assert [item["condition"] for item in exported["diagnosis"]["findings"]] == [
        "battery_power_path_issue",
        "battery_related_stall",
    ]


def test_cli_all_reports_a_nonzero_result_when_a_fixture_expectation_is_wrong(
    monkeypatch, capsys
):
    scenarios = copy.deepcopy(load_scenarios())
    scenarios[0]["expected_conditions"].append("deliberately_wrong_condition")
    monkeypatch.setattr(diagnostic_cli, "load_scenarios", lambda: scenarios)

    exit_code = diagnostic_cli.main(["--all"])
    exported = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert exported["scenario_validation"] == {
        "passed": False,
        "failed_ids": ["battery-multi-hop"],
    }
    battery_case = next(
        case for case in exported["cases"] if case["input"]["id"] == "battery-multi-hop"
    )
    assert battery_case["expectation_match"] is False


@pytest.mark.parametrize(
    "json_text",
    [
        '{"motor_temperature":"normal","motor_temperature":"high"}',
        '{"motor_temperature":NaN}',
        '{"motor_temperature":Infinity}',
    ],
)
def test_cli_rejects_duplicate_keys_and_non_finite_json(tmp_path, json_text):
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(json_text, encoding="utf-8")

    process = _run_cli("--facts", str(facts_path), cwd=tmp_path)

    assert process.returncode == 2
    assert process.stdout == ""
    assert "error:" in process.stderr.lower()


def test_cli_rejects_a_json_list_as_invalid_observation_input(tmp_path):
    facts_path = tmp_path / "facts.json"
    facts_path.write_text("[]", encoding="utf-8")

    process = _run_cli("--facts", str(facts_path), cwd=tmp_path)

    assert process.returncode == 2
    exported = json.loads(process.stdout)
    assert exported["diagnosis"] == {
        "status": "invalid_input",
        "findings": [],
        "rule_trace": [],
        "recommendations": [],
        "missing_facts": [],
    }


def test_cli_requires_an_explicit_scenario_or_facts_source():
    process = _run_cli()

    assert process.returncode == 2
    assert process.stdout == ""
    assert "usage:" in process.stderr.lower()
    assert "required" in process.stderr.lower()
