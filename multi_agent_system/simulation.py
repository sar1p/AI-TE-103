"""Bounded, centralized traffic coordination for independent D* Lite robots."""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Iterable
from numbers import Real

from search_algorithm.dstar_lite import DStarLitePlanner
from search_algorithm.grid import Grid, GridError
from search_algorithm.models import Position

from .agent import RobotAgent
from .coordinator import TrafficCoordinator
from .models import RobotSpec

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}\Z")


class FleetSimulation:
    """Simulate independent goal-seeking robots on a shared static/dynamic grid.

    Traffic handling is a conservative one-tick reservation rule. It prevents
    vertex collisions and edge swaps in each accepted transition, but it does
    not search joint plans or guarantee deadlock resolution.
    """

    def __init__(self, rows: list[str], robots: list[RobotSpec]):
        self.grid = Grid.from_rows(rows)
        try:
            robot_specs = list(robots)
        except TypeError as error:
            raise ValueError("robots must be an iterable of RobotSpec values") from error
        if isinstance(robots, (str, bytes)):
            raise ValueError("robots must be an iterable of RobotSpec values")
        if len(robot_specs) < 2:
            raise ValueError("at least two robots are required")

        seen_ids: set[str] = set()
        starts: set[Position] = set()
        goals: set[Position] = set()
        normalized: list[tuple[str, Position, Position]] = []
        for index, spec in enumerate(robot_specs):
            if not isinstance(spec, RobotSpec):
                raise ValueError(f"robots[{index}] must be a RobotSpec")
            if not isinstance(spec.id, str) or not _SAFE_ID.fullmatch(spec.id):
                raise ValueError(
                    f"robots[{index}].id must be a safe 1-32 character ASCII identifier"
                )
            if spec.id in seen_ids:
                raise ValueError(f"robot id {spec.id!r} is duplicated")
            seen_ids.add(spec.id)

            start = self.grid.validate_position(
                spec.start, label=f"robots[{index}].start"
            )
            goal = self.grid.validate_position(
                spec.goal, label=f"robots[{index}].goal"
            )
            if start in starts:
                raise ValueError(f"starting cell {start} is duplicated")
            if goal in goals:
                raise ValueError(f"goal cell {goal} is duplicated")
            starts.add(start)
            goals.add(goal)
            normalized.append((spec.id, start, goal))

        self.agents: dict[str, RobotAgent] = {}
        for robot_id, start, goal in normalized:
            planner = DStarLitePlanner(self.grid, start, goal)
            self.agents[robot_id] = RobotAgent(robot_id, goal, planner)

        self.tick_count = 0
        self.messages: list[dict] = []
        self._coordinator = TrafficCoordinator(list(self.agents))

    def _log(
        self,
        tick: int,
        sender: str,
        receiver: str,
        kind: str,
        payload: dict,
    ) -> None:
        self.messages.append(
            {
                "tick": tick,
                "sender": sender,
                "receiver": receiver,
                "kind": kind,
                "payload": copy.deepcopy(payload),
            }
        )

    @staticmethod
    def _normalize_speed_factors(
        values: dict[str, float] | None, known_ids: set[str]
    ) -> dict[str, float]:
        if values is None:
            return {}
        if not isinstance(values, dict):
            raise ValueError("speed_factors must be a dictionary or None")
        normalized: dict[str, float] = {}
        for robot_id, value in values.items():
            if robot_id not in known_ids:
                raise ValueError(f"unknown robot id in speed_factors: {robot_id!r}")
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"speed factor for {robot_id!r} must be a finite number")
            try:
                factor = float(value)
            except (OverflowError, ValueError) as error:
                raise ValueError(
                    f"speed factor for {robot_id!r} must be a finite number"
                ) from error
            if not math.isfinite(factor) or not 0.0 <= factor <= 1.0:
                raise ValueError(
                    f"speed factor for {robot_id!r} must be finite and in [0, 1]"
                )
            normalized[robot_id] = factor
        return normalized

    @staticmethod
    def _normalize_paused_ids(
        values: Iterable[str], known_ids: set[str]
    ) -> set[str]:
        if isinstance(values, (str, bytes)):
            raise ValueError("paused_ids must be an iterable of robot ids")
        try:
            paused_values = list(values)
        except TypeError as error:
            raise ValueError("paused_ids must be an iterable of robot ids") from error
        paused: set[str] = set()
        for robot_id in paused_values:
            if not isinstance(robot_id, str) or robot_id not in known_ids:
                raise ValueError(f"unknown robot id in paused_ids: {robot_id!r}")
            paused.add(robot_id)
        return paused

    def tick(
        self,
        speed_factors: dict[str, float] | None = None,
        paused_ids: Iterable[str] = (),
    ) -> dict:
        """Advance one validated tick and return an isolated JSON snapshot.

        Unspecified speed factors default to one. A paused robot neither
        accrues credit nor proposes a move; earned credit is retained.
        """
        known_ids = set(self.agents)
        factors = self._normalize_speed_factors(speed_factors, known_ids)
        paused = self._normalize_paused_ids(paused_ids, known_ids)

        next_tick = self.tick_count + 1
        starting_positions = {
            robot_id: agent.position for robot_id, agent in self.agents.items()
        }
        proposals: dict[str, Position] = {}

        for robot_id, agent in self.agents.items():
            requested_speed = factors.get(robot_id, 1.0)
            is_paused = robot_id in paused
            agent.begin_tick(requested_speed, is_paused)
            self._log(
                next_tick,
                "controller",
                robot_id,
                "control",
                {
                    "requested_speed_factor": requested_speed,
                    "effective_speed_factor": agent.speed_factor,
                    "paused": is_paused,
                },
            )

            if agent.status == "arrived":
                continue
            if is_paused:
                self._log(
                    next_tick,
                    robot_id,
                    "traffic_coordinator",
                    "wait",
                    {"status": "paused", "reason": "paused", "position": list(agent.position)},
                )
                continue
            if agent.status == "unreachable":
                self._log(
                    next_tick,
                    robot_id,
                    "traffic_coordinator",
                    "wait",
                    {
                        "status": "unreachable",
                        "reason": "no_route",
                        "position": list(agent.position),
                    },
                )
                continue
            target = agent.propose_next_cell()
            if target is None:
                if agent.speed_factor == 0.0:
                    reason = "zero_speed"
                elif agent.movement_credit < 1.0:
                    reason = "movement_credit"
                else:
                    reason = "no_route"
                self._log(
                    next_tick,
                    robot_id,
                    "traffic_coordinator",
                    "wait",
                    {"status": "ready", "reason": reason, "position": list(agent.position)},
                )
                continue
            proposals[robot_id] = target
            self._log(
                next_tick,
                robot_id,
                "traffic_coordinator",
                "request",
                {
                    "from": list(agent.position),
                    "to": list(target),
                    "movement_credit": agent.movement_credit,
                },
            )

        decisions = self._coordinator.resolve(proposals, starting_positions)
        granted_ids: list[str] = []
        for robot_id in self.agents:
            decision = decisions.get(robot_id)
            if decision is None:
                continue
            if decision.granted:
                granted_ids.append(robot_id)
                self._log(
                    next_tick,
                    "traffic_coordinator",
                    robot_id,
                    "grant",
                    {
                        "to": list(decision.target),
                        "reason": decision.reason,
                        **copy.deepcopy(decision.details),
                    },
                )
                continue

            agent = self.agents[robot_id]
            agent.receive_denial()
            self._log(
                next_tick,
                "traffic_coordinator",
                robot_id,
                "denial",
                {
                    "to": list(decision.target),
                    "reason": decision.reason,
                    **copy.deepcopy(decision.details),
                },
            )
            self._log(
                next_tick,
                robot_id,
                "traffic_coordinator",
                "wait",
                {
                    "status": "waiting",
                    "reason": decision.reason,
                    "position": list(agent.position),
                    **copy.deepcopy(decision.details),
                },
            )

        # Robots update themselves only after receiving their coordinator grant.
        position_updates: list[tuple[str, Position, Position]] = []
        for robot_id in granted_ids:
            agent = self.agents[robot_id]
            previous = starting_positions[robot_id]
            current = agent.receive_grant(decisions[robot_id].target)
            position_updates.append((robot_id, previous, current))
        for robot_id, previous, current in position_updates:
            self._log(
                next_tick,
                robot_id,
                "fleet",
                "position_update",
                {
                    "from": list(previous),
                    "to": list(current),
                    "status": self.agents[robot_id].status,
                },
            )

        self.tick_count = next_tick
        return self.snapshot()

    def update_cells(self, changes: Iterable[dict]) -> set[Position]:
        """Atomically validate and propagate a batch to the shared map/planners."""
        try:
            batch = list(changes)
        except TypeError as error:
            raise GridError("changes must be an iterable of records") from error

        protected = {
            cell
            for agent in self.agents.values()
            for cell in (agent.position, agent.goal)
        }
        candidate = self.grid.clone()
        changed = candidate.apply_changes(batch, protected=protected)
        normalized_batch = [
            {
                "cell": candidate.validate_position(
                    record["cell"], label=f"changes[{index}].cell", require_open=False
                ),
                "blocked": record["blocked"],
            }
            for index, record in enumerate(batch)
        ]

        if not changed:
            return set()
        for agent in self.agents.values():
            agent.planner.update_cells(normalized_batch)
        self.grid.apply_changes(normalized_batch, protected=protected)
        for agent in self.agents.values():
            agent._refresh_plan()
        return set(changed)

    def clearance_cells(self, robot_id: str) -> float:
        """Return nearest blocked/other-robot Manhattan clearance, capped at 5."""
        if not isinstance(robot_id, str) or robot_id not in self.agents:
            raise ValueError(f"unknown robot id: {robot_id!r}")
        position = self.agents[robot_id].position
        distances = [
            abs(position[0] - row) + abs(position[1] - column)
            for row, column in self.grid.blocked
        ]
        distances.extend(
            abs(position[0] - agent.position[0])
            + abs(position[1] - agent.position[1])
            for other_id, agent in self.agents.items()
            if other_id != robot_id
        )
        return float(min(5, min(distances, default=5)))

    def snapshot(self) -> dict:
        """Return a JSON-compatible isolated copy of current simulation state."""
        return {
            "tick": self.tick_count,
            "map_revision": self.grid.revision,
            "rows": self.grid.to_rows(),
            "robots": [agent.snapshot() for agent in self.agents.values()],
            "messages": copy.deepcopy(self.messages),
        }
