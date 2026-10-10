#!/usr/bin/env python3
"""Run real chained diagnosis, movement gating, and incremental route repair."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from expert_system.engine import load_knowledge_base
from interface.diagnostics import evaluate_diagnostics
from interface.evidence import environment_metadata
from interface.session import SimulationSession
from search_algorithm.grid import GridError
from search_algorithm.scenarios import available_scenarios


FAULT_OBSERVATIONS = {
    "motor_temperature": "normal",
    "movement_status": "stalled",
    "sensor_lidar": "clear",
    "battery_voltage": "low",
    "battery_connection": "disconnected",
}
CORRECTED_OBSERVATIONS = {
    "motor_temperature": "normal",
    "movement_status": "moving",
    "sensor_lidar": "clear",
    "battery_voltage": "normal",
    "battery_connection": "connected",
}


def run_demo() -> dict:
    """Return actual outputs; reject a run that violates this demonstration's checks."""
    knowledge_base = load_knowledge_base()
    scenario = next(
        (scenario for _, scenario in available_scenarios() if scenario.id == "corridor-changes"),
        None,
    )
    if scenario is None:
        raise RuntimeError("The corridor-changes search scenario is unavailable.")
    session = SimulationSession(scenario)
    fault = evaluate_diagnostics(copy.deepcopy(FAULT_OBSERVATIONS))
    if fault.status != "ready" or fault.result["status"] != "ok" or fault.can_move:
        raise RuntimeError("The chained power-path case did not produce a valid pause result.")
    fault_conditions = {finding["condition"] for finding in fault.result["findings"]}
    if fault_conditions != {"battery_power_path_issue", "battery_related_stall"}:
        raise RuntimeError("The chained power-path case returned unexpected findings.")
    if {step["rule_id"] for step in fault.result["rule_trace"]} != {"R03", "R04", "R05", "R06"}:
        raise RuntimeError("The power-path case did not demonstrate the documented chain.")

    # Map edits are allowed while the movement gate is paused.
    session.apply_event(scenario.events[0], movement_allowed=fault.can_move)
    before_rejected_move = copy.deepcopy(session.to_dict())
    original_start = session.planner.start
    original_planner = session.planner
    try:
        session.apply_event(scenario.events[1], movement_allowed=fault.can_move)
    except GridError as error:
        rejection = str(error)
    else:
        raise RuntimeError("The diagnostic gate unexpectedly permitted movement.")
    if session.to_dict() != before_rejected_move or session.planner.start != original_start:
        raise RuntimeError("A rejected movement changed the simulation.")

    corrected = evaluate_diagnostics(copy.deepcopy(CORRECTED_OBSERVATIONS))
    if corrected.status != "ready" or not corrected.can_move:
        raise RuntimeError("Corrected raw observations did not restore simulated movement.")
    if any(corrected.result[name] for name in ("findings", "rule_trace", "recommendations", "missing_facts")):
        raise RuntimeError("Corrected observations retained unsupported diagnostic conclusions.")
    session.apply_event(scenario.events[1], movement_allowed=corrected.can_move)
    if session.planner is not original_planner or session.planner.initialization_count != 1:
        raise RuntimeError("The demonstration discarded incremental planner state.")
    if abs(session.planner.start[0] - original_start[0]) + abs(session.planner.start[1] - original_start[1]) != 1:
        raise RuntimeError("The resumed robot did not make exactly one legal step.")
    if [record["dstar_lite"]["cost"] for record in session.records] != [10, 12, 11]:
        raise RuntimeError("The corridor demonstration returned unexpected route costs.")
    for record in session.records:
        if record["dstar_lite"]["cost"] != record["astar"]["cost"]:
            raise RuntimeError("The two planners disagree on the recorded route cost.")

    canonical_knowledge = json.dumps(
        knowledge_base.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "scope": "combined diagnostic inference and simulated route planning",
        "diagnostic_inference_included": True,
        "metadata": environment_metadata(),
        "knowledge_base": {
            "canonical_json_sha256": hashlib.sha256(canonical_knowledge).hexdigest(),
            "rule_count": len(knowledge_base.rules),
            "observation_count": len(knowledge_base.observations),
            "provenance": knowledge_base.provenance,
        },
        "diagnostic_sequence": [
            {"event": "fault_observations", "facts": FAULT_OBSERVATIONS,
             "result": fault.result, "movement_allowed": fault.can_move},
            {"event": "corrected_observations", "facts": CORRECTED_OBSERVATIONS,
             "result": corrected.result, "movement_allowed": corrected.can_move},
        ],
        "rejected_movement": {
            "event_id": scenario.events[1]["id"], "reason": rejection,
            "session_unchanged": True, "position": list(original_start),
        },
        "search_session": session.to_dict(),
        "checks": {
            "chained_diagnosis_pauses_movement": True,
            "map_edit_allowed_while_paused": True,
            "rejected_move_is_atomic": True,
            "correction_removes_dependent_findings": True,
            "corrected_observations_allow_one_step": True,
            "incremental_planner_retained": True,
            "route_costs_agree_with_astar": True,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/combined-demo.json"))
    args = parser.parse_args(argv)
    try:
        document = run_demo()
        serialized = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(f"Combined demonstration failed: {error}", file=sys.stderr)
        return 2
    print(f"Combined evidence: {args.output.resolve()}")
    print("Actual rule chain: R03/R04 -> R05 -> R06; movement paused, corrected, and resumed.")
    print("Actual route costs: 10 -> 12 -> 11; retained planner initializations: 1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
