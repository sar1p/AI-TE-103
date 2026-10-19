"""Illustrative Mamdani fuzzy speed controller for the warehouse simulation.

The controller is a standalone coursework example. Its thresholds are
illustrative and are not calibrated to a physical warehouse or robot.
"""

from __future__ import annotations

from copy import deepcopy
from math import isfinite
from typing import Any

__all__ = ["evaluate_speed", "evaluate_sugeno_speed", "FuzzyInputError", "configuration"]


class FuzzyInputError(ValueError):
    """Raised when a controller input has an unsupported type or range."""


_CLEARANCE_SETS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("near", (0.0, 0.0, 1.5)),
    ("medium", (0.5, 2.0, 3.5)),
    ("far", (2.5, 5.0, 5.0)),
)
_BATTERY_SETS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("low", (0.0, 0.0, 35.0)),
    ("medium", (20.0, 50.0, 80.0)),
    ("high", (65.0, 100.0, 100.0)),
)
_SPEED_SETS: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("slow", (0.0, 0.0, 40.0)),
    ("medium", (20.0, 50.0, 80.0)),
    ("fast", (60.0, 100.0, 100.0)),
)
_RULE_MATRIX: tuple[tuple[str, ...], ...] = (
    ("slow", "slow", "slow"),
    ("slow", "medium", "medium"),
    ("slow", "medium", "fast"),
)
_CLEARANCE_LABELS = tuple(label for label, _ in _CLEARANCE_SETS)
_BATTERY_LABELS = tuple(label for label, _ in _BATTERY_SETS)
_GRID_STEP = 0.5
_SPEED_GRID = tuple(index * _GRID_STEP for index in range(201))
_SUGENO_SINGLETONS = {
    "slow": 40.0 / 3.0,
    "medium": 50.0,
    "fast": 260.0 / 3.0,
}


def _triangular_membership(
    value: float, parameters: tuple[float, float, float]
) -> float:
    """Evaluate a triangle, including left/right shoulder triangles."""
    left, peak, right = parameters
    if value < left or value > right:
        return 0.0
    if value == peak:
        return 1.0
    if value < peak:
        # A repeated left endpoint is a vertical shoulder whose peak is 1.
        return (value - left) / (peak - left)
    # Here right > peak; a repeated right endpoint is handled by value==peak.
    return (right - value) / (right - peak)


def _validate_input(value: object, name: str, lower: float, upper: float) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FuzzyInputError(f"{name} must be a finite int or float (bool is not accepted)")
    if isinstance(value, float) and not isfinite(value):
        raise FuzzyInputError(f"{name} must be finite")
    if value < lower or value > upper:
        raise FuzzyInputError(f"{name} must be within [{lower:g}, {upper:g}]")
    # Normalize numeric subclasses to JSON-friendly built-in scalar types.
    return int(value) if isinstance(value, int) else float(value)


def _membership_values(
    value: float, sets: tuple[tuple[str, tuple[float, float, float]], ...]
) -> dict[str, float]:
    return {label: _triangular_membership(value, parameters) for label, parameters in sets}


def _rule_table() -> list[dict[str, str]]:
    return [
        {
            "id": f"F{row_index * len(_BATTERY_LABELS) + column_index + 1:02d}",
            "clearance": clearance_label,
            "battery": battery_label,
            "consequent": consequent,
        }
        for row_index, (clearance_label, row) in enumerate(
            zip(_CLEARANCE_LABELS, _RULE_MATRIX, strict=True)
        )
        for column_index, (battery_label, consequent) in enumerate(
            zip(_BATTERY_LABELS, row, strict=True)
        )
    ]


_CONFIGURATION: dict[str, Any] = {
    "universes": {
        "clearance_cells": {"minimum": 0.0, "maximum": 5.0, "unit": "cells"},
        "battery_percent": {"minimum": 0.0, "maximum": 100.0, "unit": "percent"},
        "speed_percent": {"minimum": 0.0, "maximum": 100.0, "unit": "percent", "step": _GRID_STEP},
    },
    "memberships": {
        "clearance_cells": {
            label: {"shape": "triangle", "parameters": list(parameters)}
            for label, parameters in _CLEARANCE_SETS
        },
        "battery_percent": {
            label: {"shape": "triangle", "parameters": list(parameters)}
            for label, parameters in _BATTERY_SETS
        },
        "speed_percent": {
            label: {"shape": "triangle", "parameters": list(parameters)}
            for label, parameters in _SPEED_SETS
        },
    },
    "rule_table": _rule_table(),
    "numerical_method": {
        "inference": "Mamdani",
        "and": "minimum of antecedent memberships",
        "implication": "clip each consequent membership at its rule activation",
        "aggregation": "maximum of clipped consequent memberships",
        "defuzzification": "centroid",
        "quadrature": "composite trapezoidal quadrature over the uniform speed grid",
        "sample_step": _GRID_STEP,
    },
    "sugeno": {
        "inference": "zero-order Sugeno",
        "and": "minimum of antecedent memberships",
        "consequents": "constant singleton outputs",
        "singletons_percent": dict(_SUGENO_SINGLETONS),
        "defuzzification": "activation-weighted average of rule singletons",
        "numerical_method": "finite weighted sum; no output-universe sampling",
        "sample_step": None,
        "provenance": {
            "model": "illustrative coursework values; not field-calibrated",
            "singletons": "analytic centroids of the corresponding speed triangles",
            "membership_values": "degrees of membership, not probabilities",
        },
    },
    "provenance": {
        "model": "illustrative coursework values; not field-calibrated",
        "thresholds": "illustrative coursework values; not field-calibrated",
        "membership_values": "degrees of membership, not probabilities",
    },
    "limitations": [
        "This output is an illustrative speed recommendation, not a physical robot command.",
        "The thresholds are not field-calibrated and membership degrees are not probabilities.",
        "This controller does not implement stop safety, collision avoidance, or reservation checks.",
        "The caller must override motion using diagnostics and reservations when required.",
        "Mamdani centroid integration is approximated with composite trapezoidal quadrature on a 0.5 percent grid.",
        "Mamdani and zero-order Sugeno can return different outputs because their inference and aggregation differ.",
    ],
}


def configuration() -> dict[str, Any]:
    """Return a JSON-shaped copy of the illustrative controller configuration."""
    return deepcopy(_CONFIGURATION)


def _trapezoidal_integral(values: tuple[float, ...]) -> float:
    return sum(
        (values[index] + values[index + 1]) * 0.5 * _GRID_STEP
        for index in range(len(values) - 1)
    )


def _prepare_evaluation(
    clearance_cells: object, battery_percent: object
) -> tuple[dict[str, int | float], dict[str, dict[str, dict[str, float]]], list[dict[str, str | float]]]:
    clearance_input = _validate_input(clearance_cells, "clearance_cells", 0.0, 5.0)
    battery_input = _validate_input(battery_percent, "battery_percent", 0.0, 100.0)
    clearance_value = float(clearance_input)
    battery_value = float(battery_input)

    clearance_memberships = _membership_values(clearance_value, _CLEARANCE_SETS)
    battery_memberships = _membership_values(battery_value, _BATTERY_SETS)

    rules: list[dict[str, str | float]] = []
    for rule in _rule_table():
        activation = min(
            clearance_memberships[rule["clearance"]],
            battery_memberships[rule["battery"]],
        )
        rules.append({**rule, "activation": activation})

    inputs = {
        "clearance_cells": clearance_input,
        "battery_percent": battery_input,
    }
    memberships = {
        "clearance": clearance_memberships,
        "battery": battery_memberships,
    }
    return inputs, memberships, rules


def _result_provenance(method: str) -> dict[str, str]:
    return {
        "model": "illustrative",
        "method": method,
        "thresholds": "illustrative coursework values; not field-calibrated",
        "membership_values": "degrees of membership, not probabilities",
    }


def evaluate_speed(clearance_cells: object, battery_percent: object) -> dict[str, Any]:
    """Evaluate the default Mamdani controller and return a JSON-shaped result.

    Inputs must be finite built-in ``int`` or ``float`` values (excluding
    ``bool``), with clearance in [0, 5] and battery in [0, 100].
    """
    inputs, memberships, rules = _prepare_evaluation(clearance_cells, battery_percent)
    activations = [(rule["consequent"], rule["activation"]) for rule in rules]

    speed_parameters = dict(_SPEED_SETS)
    aggregation: list[dict[str, float]] = []
    for speed_percent in _SPEED_GRID:
        membership = max(
            min(_triangular_membership(speed_percent, speed_parameters[consequent]), activation)
            for consequent, activation in activations
        )
        aggregation.append({"speed_percent": speed_percent, "membership": membership})

    output_memberships = tuple(point["membership"] for point in aggregation)
    weighted_memberships = tuple(
        point["speed_percent"] * point["membership"] for point in aggregation
    )
    numerator = _trapezoidal_integral(weighted_memberships)
    denominator = _trapezoidal_integral(output_memberships)
    if denominator <= 0.0:  # The complete rule table and covered inputs should prevent this.
        raise RuntimeError("The fuzzy rule base produced an empty output set")
    speed_percent = numerator / denominator

    return {
        "inputs": inputs,
        "memberships": memberships,
        "rules": rules,
        "output": {
            "speed_percent": speed_percent,
            "speed_factor": speed_percent / 100.0,
        },
        "aggregation": aggregation,
        "defuzzification": {
            "method": "centroid",
            "numerator": numerator,
            "denominator": denominator,
            "sample_step": _GRID_STEP,
        },
        "provenance": _result_provenance("Mamdani"),
    }


def evaluate_sugeno_speed(clearance_cells: object, battery_percent: object) -> dict[str, Any]:
    """Evaluate the zero-order Sugeno alternative with shared fuzzy inputs.

    The rule consequents are fixed singleton speeds. Their output is the
    activation-weighted average; it is not a centroid of an aggregated fuzzy
    output set.
    """
    inputs, memberships, base_rules = _prepare_evaluation(clearance_cells, battery_percent)
    rules = [
        {
            **rule,
            "singleton_percent": _SUGENO_SINGLETONS[rule["consequent"]],
        }
        for rule in base_rules
    ]
    numerator = sum(
        rule["activation"] * rule["singleton_percent"]
        for rule in rules
    )
    denominator = sum(rule["activation"] for rule in rules)
    if denominator <= 0.0:  # Complete sets and the rule table should prevent this.
        raise RuntimeError("The fuzzy rule base produced no active Sugeno singleton")
    speed_percent = numerator / denominator

    return {
        "inputs": inputs,
        "memberships": memberships,
        "rules": rules,
        "output": {
            "speed_percent": speed_percent,
            "speed_factor": speed_percent / 100.0,
        },
        "aggregation": [],
        "defuzzification": {
            "method": "Sugeno weighted average",
            "numerator": numerator,
            "denominator": denominator,
            "sample_step": None,
        },
        "provenance": _result_provenance("zero-order Sugeno"),
    }
