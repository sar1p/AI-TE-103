from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from fuzzy_logic import FuzzyInputError, configuration, evaluate_speed, evaluate_sugeno_speed


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_input_membership_shoulders_and_triangle_endpoints() -> None:
    at_origin = evaluate_speed(0, 0)
    assert at_origin["memberships"]["clearance"] == {"near": 1.0, "medium": 0.0, "far": 0.0}
    assert at_origin["memberships"]["battery"] == {"low": 1.0, "medium": 0.0, "high": 0.0}

    at_maximum = evaluate_speed(5, 100)
    assert at_maximum["memberships"]["clearance"] == {"near": 0.0, "medium": 0.0, "far": 1.0}
    assert at_maximum["memberships"]["battery"] == {"low": 0.0, "medium": 0.0, "high": 1.0}

    at_peaks = evaluate_speed(2, 50)
    assert at_peaks["memberships"]["clearance"]["medium"] == 1.0
    assert at_peaks["memberships"]["battery"]["medium"] == 1.0
    assert evaluate_speed(1.5, 35)["memberships"]["clearance"]["near"] == 0.0
    assert evaluate_speed(1.5, 35)["memberships"]["clearance"]["medium"] == pytest.approx(2 / 3)
    assert evaluate_speed(3.5, 80)["memberships"]["clearance"]["far"] == pytest.approx(2 / 5)


def test_memberships_cover_both_complete_input_universes() -> None:
    for clearance_cells in (step / 4 for step in range(21)):
        result = evaluate_speed(clearance_cells, 50)
        assert max(result["memberships"]["clearance"].values()) > 0
    for battery_percent in range(0, 101, 5):
        result = evaluate_speed(2, battery_percent)
        assert max(result["memberships"]["battery"].values()) > 0


def test_rules_and_aggregation_match_the_complete_matrix() -> None:
    result = evaluate_speed(3, 80)
    assert [rule["id"] for rule in result["rules"]] == [f"F{index:02d}" for index in range(1, 10)]
    assert [(rule["clearance"], rule["battery"], rule["consequent"]) for rule in result["rules"]] == [
        (clearance, battery, consequent)
        for clearance, row in zip(("near", "medium", "far"), (("slow", "slow", "slow"), ("slow", "medium", "medium"), ("slow", "medium", "fast")), strict=True)
        for battery, consequent in zip(("low", "medium", "high"), row, strict=True)
    ]
    assert result["rules"][5]["activation"] == pytest.approx(1 / 3)
    assert result["rules"][8]["activation"] == pytest.approx(1 / 5)
    assert len(result["aggregation"]) == 201
    assert result["aggregation"][0] == {"speed_percent": 0.0, "membership": 0.0}
    assert result["aggregation"][-1]["speed_percent"] == 100.0
    assert all(0.0 <= point["membership"] <= 1.0 for point in result["aggregation"])
    assert all(
        result["aggregation"][index + 1]["speed_percent"] - point["speed_percent"] == 0.5
        for index, point in enumerate(result["aggregation"][:-1])
    )


def test_full_slow_triangle_centroid_matches_analytical_reference() -> None:
    result = evaluate_speed(0, 50)
    assert result["output"]["speed_percent"] == pytest.approx(40 / 3, abs=0.003)
    assert result["output"]["speed_factor"] == pytest.approx(result["output"]["speed_percent"] / 100)
    assert result["defuzzification"]["method"] == "centroid"
    assert result["defuzzification"]["sample_step"] == 0.5


def test_mixed_consequents_match_numeric_reference() -> None:
    result = evaluate_speed(3, 80)
    assert result["memberships"]["clearance"] == pytest.approx(
        {"near": 0.0, "medium": 1 / 3, "far": 1 / 5}
    )
    assert result["memberships"]["battery"] == pytest.approx(
        {"low": 0.0, "medium": 0.0, "high": 3 / 7}
    )
    # Reference centroid for the medium consequent clipped at 1/3 and the
    # fast shoulder clipped at 1/5, integrated on the specified 0.5 grid.
    assert result["defuzzification"]["denominator"] == pytest.approx(319 / 15, abs=1e-10)
    assert result["defuzzification"]["numerator"] == pytest.approx(148817 / 120, abs=1e-10)
    assert result["output"]["speed_percent"] == pytest.approx(148817 / 2552, abs=1e-10)


def test_sugeno_single_rule_uses_its_analytical_singleton() -> None:
    result = evaluate_sugeno_speed(0, 50)
    active_rules = [rule for rule in result["rules"] if rule["activation"] > 0]

    assert len(active_rules) == 1
    assert active_rules[0]["id"] == "F02"
    assert active_rules[0]["consequent"] == "slow"
    assert active_rules[0]["singleton_percent"] == pytest.approx(40 / 3)
    assert result["output"]["speed_percent"] == pytest.approx(40 / 3)
    assert result["aggregation"] == []
    assert result["defuzzification"] == {
        "method": "Sugeno weighted average",
        "numerator": pytest.approx(40 / 3),
        "denominator": 1.0,
        "sample_step": None,
    }
    assert result["provenance"]["model"] == "illustrative"
    assert result["provenance"]["method"] == "zero-order Sugeno"


def test_sugeno_blends_active_rules_by_their_firing_strengths() -> None:
    result = evaluate_sugeno_speed(3, 80)
    mamdani = evaluate_speed(3, 80)
    active_rules = [rule for rule in result["rules"] if rule["activation"] > 0]

    assert [(rule["id"], rule["consequent"], rule["activation"]) for rule in active_rules] == [
        ("F06", "medium", pytest.approx(1 / 3)),
        ("F09", "fast", pytest.approx(1 / 5)),
    ]
    # (1/3 * 50 + 1/5 * 260/3) / (1/3 + 1/5) = 63.75.
    assert result["defuzzification"]["numerator"] == pytest.approx(34)
    assert result["defuzzification"]["denominator"] == pytest.approx(8 / 15)
    assert result["output"]["speed_percent"] == pytest.approx(63.75)
    assert result["output"]["speed_factor"] == pytest.approx(0.6375)
    assert result["memberships"] == mamdani["memberships"]
    assert [
        {key: value for key, value in rule.items() if key != "singleton_percent"}
        for rule in result["rules"]
    ] == mamdani["rules"]
    assert result["provenance"]["model"] == "illustrative"
    assert result["provenance"]["method"] == "zero-order Sugeno"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize(
    ("clearance", "battery"),
    [
        (True, 50),
        (2, False),
        (None, 50),
        ("2", 50),
        (2, "50"),
        (2.0 + 1.0j, 50),
        (math.nan, 50),
        (2, math.nan),
        (math.inf, 50),
        (2, -math.inf),
        (-0.01, 50),
        (5.01, 50),
        (2, -0.01),
        (2, 100.01),
    ],
)
def test_invalid_inputs_raise_the_public_value_error(clearance: object, battery: object) -> None:
    with pytest.raises(FuzzyInputError):
        evaluate_speed(clearance, battery)
    with pytest.raises(FuzzyInputError):
        evaluate_sugeno_speed(clearance, battery)


def test_configuration_and_results_are_json_safe_isolated_and_deterministic() -> None:
    first_configuration = configuration()
    serialized_configuration = json.dumps(first_configuration, allow_nan=False, sort_keys=True)
    first_configuration["memberships"]["clearance_cells"]["near"]["parameters"][0] = -999
    first_configuration["rule_table"][0]["consequent"] = "changed"
    first_configuration["sugeno"]["singletons_percent"]["slow"] = -999
    assert json.dumps(configuration(), allow_nan=False, sort_keys=True) == serialized_configuration
    assert configuration()["sugeno"]["singletons_percent"] == pytest.approx(
        {"slow": 40 / 3, "medium": 50.0, "fast": 260 / 3}
    )
    assert configuration()["numerical_method"]["inference"] == "Mamdani"

    first_result = evaluate_speed(3, 80)
    serialized_result = json.dumps(first_result, allow_nan=False, sort_keys=True)
    second_result = evaluate_speed(3, 80)
    assert first_result == second_result
    assert json.dumps(second_result, allow_nan=False, sort_keys=True) == serialized_result
    assert first_result["inputs"] == {"clearance_cells": 3, "battery_percent": 80}
    assert first_result["provenance"] == {
        "model": "illustrative",
        "method": "Mamdani",
        "thresholds": "illustrative coursework values; not field-calibrated",
        "membership_values": "degrees of membership, not probabilities",
    }
    assert len(serialized_configuration) > 0


def test_cli_writes_strict_json_to_stdout_or_requested_file(tmp_path: Path) -> None:
    command = [sys.executable, "-m", "fuzzy_logic", "--clearance", "3", "--battery", "80"]
    stdout_result = subprocess.run(command, cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False)
    assert stdout_result.returncode == 0
    parsed = json.loads(stdout_result.stdout, parse_constant=lambda value: pytest.fail(f"invalid JSON constant: {value}"))
    assert parsed["inputs"] == {"clearance_cells": 3.0, "battery_percent": 80.0}
    assert parsed["provenance"]["method"] == "Mamdani"

    sugeno_result = subprocess.run(
        [*command, "--method", "sugeno"], cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False
    )
    assert sugeno_result.returncode == 0
    sugeno_parsed = json.loads(
        sugeno_result.stdout, parse_constant=lambda value: pytest.fail(f"invalid JSON constant: {value}")
    )
    assert sugeno_parsed["provenance"]["method"] == "zero-order Sugeno"
    assert sugeno_parsed["aggregation"] == []
    assert sugeno_parsed["defuzzification"]["sample_step"] is None

    output_path = tmp_path / "speed.json"
    file_result = subprocess.run(
        [*command, "--output", str(output_path)], cwd=REPOSITORY_ROOT, capture_output=True, text=True, check=False
    )
    assert file_result.returncode == 0
    assert file_result.stdout == ""
    assert json.loads(output_path.read_text(encoding="utf-8")) == parsed


def test_cli_invalid_input_exits_two_with_a_clear_error() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "fuzzy_logic", "--clearance", "nan", "--battery", "80"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "clearance_cells must be finite" in result.stderr
    assert "Traceback" not in result.stderr
