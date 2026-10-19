#!/usr/bin/env python3
"""Reproduce diagnosis, fuzzy cadence, retained planners, and cooperative traffic."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from expert_system.scenarios import load_scenario
from interface.evidence import environment_metadata
from interface.fleet_session import FleetControlSession, HEALTHY_OBSERVATIONS


def _assert_transition(before: list[dict], after: list[dict]) -> None:
    old = {robot["id"]: tuple(robot["position"]) for robot in before}
    new = {robot["id"]: tuple(robot["position"]) for robot in after}
    if len(set(new.values())) != len(new):
        raise RuntimeError("A fleet transition produced a vertex collision.")
    for robot_id, position in old.items():
        target = new[robot_id]
        if sum(abs(first - second) for first, second in zip(position, target)) > 1:
            raise RuntimeError("A fleet transition moved a robot more than one cardinal cell.")
        for other_id in old:
            if robot_id != other_id and position == new[other_id] and target == old[other_id]:
                raise RuntimeError("A fleet transition produced an edge swap.")


def run_demo(method: str = "mamdani") -> dict:
    # A symmetric replay exhibits contention under the real fuzzy controller.
    crossing = FleetControlSession()
    crossing.set_method(method)
    prior = crossing.simulation.snapshot()["robots"]
    for _ in range(100):
        current = crossing.step()["robots"]
        _assert_transition(prior, current)
        prior = current
        if all(robot["status"] == "arrived" for robot in current):
            break
    else:
        raise RuntimeError("The crossing replay did not finish within 100 ticks.")
    crossing_payload = crossing.to_dict()
    if not any(message["kind"] == "denial" for message in crossing_payload["fleet"]["messages"]):
        raise RuntimeError("The symmetric replay did not demonstrate a reservation denial.")
    if not all(robot["initialization_count"] == 1 for robot in current):
        raise RuntimeError("The replay discarded a robot's incremental planner.")

    # A second replay proves that fuzzy output cannot bypass diagnostic stops.
    recovery = FleetControlSession()
    recovery.set_method(method)
    recovery.set_observations("R01", load_scenario("battery-multi-hop")["facts"])
    original = tuple(recovery.simulation.agents["R01"].position)
    recovery.run(8)
    paused = recovery.to_dict()
    paused_control = paused["last_step_controls"]["R01"]
    if tuple(recovery.simulation.agents["R01"].position) != original:
        raise RuntimeError("The paused robot moved despite diagnostic evidence.")
    if paused_control["applied_factor"] != 0 or paused_control["proposed_factor"] <= 0:
        raise RuntimeError("The replay did not show a positive fuzzy proposal overridden to zero.")
    recovery.set_observations("R01", deepcopy(HEALTHY_OBSERVATIONS))
    recovery.run(100)
    recovered = recovery.to_dict()
    if not all(robot["status"] == "arrived" for robot in recovered["fleet"]["robots"]):
        raise RuntimeError("Corrected observations did not permit the fleet to finish.")
    positions = {robot["id"]: robot["position"] for robot in recovered["fleet"]["robots"]}
    if positions["R01"] == list(original):
        raise RuntimeError("The corrected robot did not resume movement.")
    return {
        "schema_version": 1,
        "metadata": environment_metadata(),
        "scope": "actual four-method warehouse simulation replay",
        "method": method,
        "crossing": crossing_payload,
        "diagnostic_pause": paused,
        "corrected_observations": recovered,
        "checks": {
            "both_robots_reach_distinct_goals": True,
            "reservation_contention_is_logged": True,
            "crossing_transitions_have_no_vertex_collision_or_edge_swap": True,
            "one_persistent_planner_per_robot": True,
            "positive_fuzzy_proposal_is_overridden_by_diagnosis": True,
            "corrected_observations_resume_movement": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=["mamdani", "sugeno"], default="mamdani")
    parser.add_argument("--output", type=Path, default=Path("artifacts/fleet-demo.json"))
    args = parser.parse_args(argv)
    try:
        result = run_demo(args.method)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Fleet demonstration failed: {error}", file=sys.stderr)
        return 2
    print(f"Fleet evidence: {args.output.resolve()}")
    print(f"Method: {args.method}; verified checks: {len(result['checks'])}; all passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
