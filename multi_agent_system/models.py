"""Public value objects for the cooperative fleet simulation."""

from dataclasses import dataclass

from search_algorithm.models import Position


@dataclass(frozen=True)
class RobotSpec:
    """Immutable initial configuration for one goal-based warehouse robot."""

    id: str
    start: tuple[int, int]
    goal: tuple[int, int]


@dataclass(frozen=True)
class TrafficDecision:
    """Coordinator response for one movement proposal."""

    granted: bool
    target: Position
    reason: str
    details: dict
