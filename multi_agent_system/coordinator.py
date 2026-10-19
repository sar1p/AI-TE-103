"""Conservative one-tick reservations for simultaneous robot proposals."""

from __future__ import annotations

from collections import defaultdict

from search_algorithm.models import Position

from .models import TrafficDecision


class TrafficCoordinator:
    """Resolve one set of proposals against a snapshot of starting positions.

    A robot may enter only a cell that was unoccupied at the start of the tick.
    This intentionally rejects swaps and following moves into a just-vacated
    cell. Requests for the same free cell use rotating deterministic priority.
    """

    def __init__(self, robot_ids: list[str]):
        self._robot_ids = tuple(robot_ids)
        self._cursor = 0

    def resolve(
        self,
        proposals: dict[str, Position],
        starting_positions: dict[str, Position],
    ) -> dict[str, TrafficDecision]:
        """Return a grant or denial for every submitted proposal."""
        if not self._robot_ids:
            return {}

        rotation = self._robot_ids[self._cursor :] + self._robot_ids[: self._cursor]
        rank = {robot_id: index for index, robot_id in enumerate(rotation)}
        occupants: dict[Position, list[str]] = defaultdict(list)
        for robot_id in self._robot_ids:
            occupants[starting_positions[robot_id]].append(robot_id)

        decisions: dict[str, TrafficDecision] = {}
        eligible: dict[Position, list[str]] = defaultdict(list)
        for robot_id in self._robot_ids:
            target = proposals.get(robot_id)
            if target is None:
                continue
            blockers = occupants.get(target, [])
            if blockers:
                decisions[robot_id] = TrafficDecision(
                    granted=False,
                    target=target,
                    reason="occupied_start",
                    details={"blocking_robots": list(blockers)},
                )
            else:
                eligible[target].append(robot_id)

        for target, requesters in eligible.items():
            winner = min(requesters, key=rank.__getitem__)
            decisions[winner] = TrafficDecision(
                granted=True,
                target=target,
                reason="cell_available" if len(requesters) == 1 else "round_robin",
                details={
                    "requesters": list(requesters),
                    "priority_order": list(rotation),
                },
            )
            for robot_id in requesters:
                if robot_id == winner:
                    continue
                decisions[robot_id] = TrafficDecision(
                    granted=False,
                    target=target,
                    reason="cell_conflict",
                    details={"winner": winner, "requesters": list(requesters)},
                )

        # Rotate the tie-break order each simulation tick, including quiet ticks.
        self._cursor = (self._cursor + 1) % len(self._robot_ids)
        return decisions
