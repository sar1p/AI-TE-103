"""Strict loader for named, illustrative diagnostic input scenarios."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .engine import _is_json_value, _reject_json_constant, _unique_object_pairs


class DiagnosticScenarioError(ValueError):
    """Raised when a named scenario is missing or malformed."""


_SCENARIO_DIRECTORY = Path(__file__).resolve().parents[1] / "data" / "diagnostic_scenarios"
_SCENARIO_KEYS = {
    "id",
    "title",
    "description",
    "provenance",
    "facts",
    "expected_status",
    "expected_conditions",
}
_VALID_STATUSES = {"ok", "insufficient_evidence", "invalid_input"}


def _read_scenario(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as source:
            payload = json.load(
                source,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_unique_object_pairs,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise DiagnosticScenarioError(
            f"Could not load diagnostic scenario {path}: {error}"
        ) from error
    if type(payload) is not dict or set(payload) != _SCENARIO_KEYS:
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {path} must contain exactly {sorted(_SCENARIO_KEYS)}."
        )
    scenario_id = payload["id"]
    if type(scenario_id) is not str or not scenario_id or scenario_id != path.stem:
        raise DiagnosticScenarioError(
            f"Diagnostic scenario ID in {path} must match its file name."
        )
    for key in ("title", "description", "provenance"):
        if type(payload[key]) is not str or not payload[key].strip():
            raise DiagnosticScenarioError(
                f"Diagnostic scenario {scenario_id!r} needs nonempty {key}."
            )
    if "illustrative" not in payload["provenance"].lower():
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {scenario_id!r} provenance must say illustrative."
        )
    if type(payload["facts"]) is not dict or not _is_json_value(payload["facts"]):
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {scenario_id!r} facts must be a finite JSON object."
        )
    if (
        type(payload["expected_status"]) is not str
        or payload["expected_status"] not in _VALID_STATUSES
    ):
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {scenario_id!r} has an unsupported expected_status."
        )
    conditions = payload["expected_conditions"]
    if type(conditions) is not list or any(
        type(condition) is not str or not condition.strip()
        for condition in conditions
    ):
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {scenario_id!r} expected_conditions must be a list of strings."
        )
    if len(set(conditions)) != len(conditions):
        raise DiagnosticScenarioError(
            f"Diagnostic scenario {scenario_id!r} repeats an expected condition."
        )
    return copy.deepcopy(payload)


def load_scenarios(directory: str | Path | None = None) -> list[dict[str, Any]]:
    """Load every scenario in filename order for CLI or UI preset lists."""
    source_directory = Path(directory) if directory is not None else _SCENARIO_DIRECTORY
    try:
        paths = sorted(source_directory.glob("*.json"), key=lambda path: path.stem)
    except OSError as error:
        raise DiagnosticScenarioError(
            f"Could not list diagnostic scenarios in {source_directory}: {error}"
        ) from error
    if not paths:
        raise DiagnosticScenarioError(
            f"No diagnostic scenario JSON files found in {source_directory}."
        )
    scenarios = [_read_scenario(path) for path in paths]
    ids = [scenario["id"] for scenario in scenarios]
    if len(set(ids)) != len(ids):
        raise DiagnosticScenarioError("Diagnostic scenario IDs must be unique.")
    return scenarios


def load_scenario(scenario_id: str, directory: str | Path | None = None) -> dict[str, Any]:
    """Load one named scenario by its stable filename ID."""
    if type(scenario_id) is not str or not scenario_id:
        raise DiagnosticScenarioError("Scenario ID must be a nonempty string.")
    for scenario in load_scenarios(directory):
        if scenario["id"] == scenario_id:
            return scenario
    raise DiagnosticScenarioError(f"Unknown diagnostic scenario {scenario_id!r}.")
