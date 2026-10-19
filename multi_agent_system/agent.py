"""Independent goal-based robot state and proposal behavior."""

from __future__ import annotations

import math

from search_algorithm.dstar_lite import DStarLitePlanner
from search_algorithm.models import Position


class RobotAgent:
    """A robot with its own persistent planner and fractional movement clock."""

    def __init__(self, robot_id: str, goal: Position, planner: DStarLitePlanner):
        self.id = robot_id
        self.goal = goal
        self.planner = planner
        self.position = planner.start
        self.path: list[Position] = []
        self.cost: int | None = None
        self.steps = 0
        self.waiting_ticks = 0
        self.speed_factor = 1.0
        self.movement_credit = 0.0
        self.status = "ready"
        self._refresh_plan()

    def _refresh_plan(self) -> None:
        result = self.planner.plan()
        self.path = list(result.path)
        self.cost = result.cost
        if result.status == "unreachable":
            self.status = "unreachable"
        elif self.position == self.goal:
            self.status = "arrived"
        elif self.status == "unreachable":
            self.status = "ready"

    def begin_tick(self, requested_speed: float, paused: bool) -> None:
        """Apply a prevalidated tick control and accrue at most one move."""
        self.speed_factor = 0.0 if paused else requested_speed
        if self.status == "arrived":
            return
        if paused:
            self.status = "paused"
            return

        if self.status in {"paused", "waiting"}:
            self.status = "ready" if self.path else "unreachable"
        if self.status == "unreachable" or self.speed_factor == 0.0:
            return
        self.movement_credit += self.speed_factor
        if math.isclose(
            self.movement_credit,
            round(self.movement_credit),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            self.movement_credit = float(round(self.movement_credit))

    def propose_next_cell(self) -> Position | None:
        """Return this robot's next cardinal route cell when it has a move."""
        if self.status in {"arrived", "paused", "unreachable"}:
            return None
        if self.speed_factor == 0.0:
            return None
        if self.movement_credit < 1.0 or len(self.path) < 2:
            return None
        if self.path[0] != self.position:
            raise RuntimeError("The current route does not begin at the robot position.")
        return self.path[1]

    def receive_denial(self) -> None:
        """React to a coordinator denial while retaining earned movement credit."""
        self.movement_credit = min(1.0, self.movement_credit)
        self.status = "waiting"
        self.waiting_ticks += 1

    def receive_grant(self, target: Position) -> Position:
        """React to an approved move and repair this robot's persistent route."""
        self.planner.move_start(target)
        self.position = target
        self.steps += 1
        self.movement_credit = max(0.0, self.movement_credit - 1.0)
        if self.movement_credit < 1e-12:
            self.movement_credit = 0.0
        self.status = "ready"
        self._refresh_plan()
        return self.position

    def snapshot(self) -> dict:
        """Return a JSON-shaped robot record with no shared mutable objects."""
        return {
            "id": self.id,
            "position": list(self.position),
            "goal": list(self.goal),
            "status": self.status,
            "path": [list(cell) for cell in self.path],
            "cost": self.cost,
            "steps": self.steps,
            "waiting_ticks": self.waiting_ticks,
            "speed_factor": self.speed_factor,
            "movement_credit": self.movement_credit,
            "initialization_count": self.planner.initialization_count,
        }
