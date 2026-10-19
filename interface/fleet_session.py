"""Integrate diagnosis, fuzzy cadence, and discrete multi-agent movement."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fuzzy_logic import configuration, evaluate_speed, evaluate_sugeno_speed
from interface.diagnostics import _is_json_value, evaluate_diagnostics
from multi_agent_system import crossing_scenario


HEALTHY_OBSERVATIONS = {
    "motor_temperature": "normal",
    "movement_status": "moving",
    "sensor_lidar": "clear",
}


class FleetControlSession:
    """Keep all four coursework methods connected without hardware claims."""

    def __init__(self) -> None:
        self.simulation = crossing_scenario()
        self.batteries = {robot_id: 85.0 for robot_id in self.simulation.agents}
        self.observations = {
            robot_id: deepcopy(HEALTHY_OBSERVATIONS)
            for robot_id in self.simulation.agents
        }
        self.history: list[dict[str, Any]] = []
        self.last_step_controls: dict[str, Any] | None = None
        self.method = "mamdani"

    def set_method(self, method: str) -> None:
        if type(method) is not str or method not in {"mamdani", "sugeno"}:
            raise ValueError("Fuzzy method must be mamdani or sugeno.")
        self.method = method

    def _check_robot(self, robot_id: str) -> None:
        if type(robot_id) is not str or robot_id not in self.simulation.agents:
            raise ValueError(f"Unknown robot ID: {robot_id!r}.")

    def set_battery(self, robot_id: str, battery_percent: float) -> None:
        self._check_robot(robot_id)
        # Use the controller's public validation before changing stored readings.
        result = evaluate_speed(self.simulation.clearance_cells(robot_id), battery_percent)
        self.batteries[robot_id] = result["inputs"]["battery_percent"]

    def set_observations(self, robot_id: str, facts: dict[str, Any]) -> None:
        self._check_robot(robot_id)
        if type(facts) is not dict or not _is_json_value(facts):
            raise ValueError("Robot observations must be a finite JSON object with string keys.")
        # Invalid or unknown observations are legitimate fail-closed demo cases.
        evaluate_diagnostics(facts)
        self.observations[robot_id] = deepcopy(facts)

    def preview_controls(self) -> dict[str, Any]:
        """Calculate proposed and permitted speeds without advancing any agent."""
        controls = {}
        for robot_id in self.simulation.agents:
            evaluator = evaluate_speed if self.method == "mamdani" else evaluate_sugeno_speed
            fuzzy = evaluator(
                self.simulation.clearance_cells(robot_id), self.batteries[robot_id]
            )
            diagnosis = evaluate_diagnostics(deepcopy(self.observations[robot_id]))
            can_move = diagnosis.can_move and self.batteries[robot_id] > 0
            reason = "Diagnosis permits a reservation request."
            if not diagnosis.can_move:
                reason = "Diagnostic evidence does not permit movement."
            elif self.batteries[robot_id] == 0:
                reason = "The simulated battery reading is zero."
            controls[robot_id] = {
                "fuzzy": fuzzy,
                "diagnostics": {
                    "adapter_status": diagnosis.status,
                    "result": deepcopy(diagnosis.result),
                    "raw_observations": deepcopy(self.observations[robot_id]),
                },
                "movement_allowed": can_move,
                "proposed_factor": fuzzy["output"]["speed_factor"],
                "applied_factor": fuzzy["output"]["speed_factor"] if can_move else 0.0,
                "reason": reason,
            }
        return controls

    def step(self) -> dict[str, Any]:
        """Evaluate fresh evidence, apply stop priority, then request reservations."""
        controls = self.preview_controls()
        snapshot = self.simulation.tick(
            speed_factors={key: value["applied_factor"] for key, value in controls.items()},
            paused_ids=[key for key, value in controls.items() if not value["movement_allowed"]],
        )
        self.last_step_controls = deepcopy(controls)
        compact_controls = deepcopy(controls)
        for control in compact_controls.values():
            # The last full aggregation is exported separately; each tick keeps its proof.
            control["fuzzy"].pop("aggregation", None)
        self.history.append({
            "tick": snapshot["tick"],
            "map_revision": snapshot["map_revision"],
            "controls": compact_controls,
            "robots": deepcopy(snapshot["robots"]),
        })
        return snapshot

    def run(self, ticks: int) -> dict[str, Any]:
        if type(ticks) is not int or not 1 <= ticks <= 200:
            raise ValueError("A run must contain between 1 and 200 simulation ticks.")
        for _ in range(ticks):
            self.step()
            if all(robot["status"] == "arrived" for robot in self.simulation.snapshot()["robots"]):
                break
        return self.simulation.snapshot()

    def to_dict(self) -> dict[str, Any]:
        return deepcopy({
            "schema_version": 1,
            "scope": "four-method warehouse simulation",
            "fuzzy_method": self.method,
            "units": {
                "distance": "Manhattan grid cells, capped at five for fuzzy input",
                "speed": "fractional grid moves per discrete simulation tick",
                "battery": "independent illustrative percentage input, not measured telemetry",
            },
            "stop_priority": "diagnosis and zero battery > fuzzy proposal > traffic reservation",
            "fleet": self.simulation.snapshot(),
            "fuzzy_configuration": configuration(),
            "next_step_controls": self.preview_controls(),
            "last_step_controls": self.last_step_controls,
            "history": self.history,
            "limitations": [
                "Illustrative memberships and rules are not calibrated to physical robots.",
                "Battery percentages and categorical diagnostic observations are separate inputs.",
                "One-tick reservations prevent the checked discrete conflicts, not all deadlocks.",
                "A simulation tick has no conversion to physical time or braking distance.",
            ],
        })
