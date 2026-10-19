"""Deterministic scenarios for demonstrations and tests."""

from .models import RobotSpec
from .simulation import FleetSimulation


def crossing_scenario() -> FleetSimulation:
    """Return two equal-speed robots that conflict at the central crossing."""
    return FleetSimulation(
        rows=[
            "####.####",
            "####.####",
            "####.####",
            ".........",
            "####.####",
            "####.####",
            "####.####",
        ],
        robots=[
            RobotSpec("R01", (3, 1), (3, 7)),
            RobotSpec("R02", (0, 4), (6, 4)),
        ],
    )
