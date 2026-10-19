"""Contract and safety tests for the bounded fleet simulation core."""

import json
import math
import random

import pytest

from multi_agent_system import FleetSimulation, RobotSpec, crossing_scenario
from multi_agent_system.cli import main
from multi_agent_system.coordinator import TrafficCoordinator
from search_algorithm.grid import GridError


def _robots(simulation):
    return {robot["id"]: robot for robot in simulation.snapshot()["robots"]}


def _assert_no_vertex_or_edge_collisions(previous, current):
    old_positions = {robot_id: tuple(value["position"]) for robot_id, value in previous.items()}
    new_positions = {robot_id: tuple(value["position"]) for robot_id, value in current.items()}
    assert len(set(new_positions.values())) == len(new_positions)
    for first_id, first_old in old_positions.items():
        for second_id, second_old in old_positions.items():
            if first_id >= second_id:
                continue
            assert not (
                new_positions[first_id] == second_old
                and new_positions[second_id] == first_old
            )


def test_crossing_logs_conflict_and_both_robots_arrive_safely():
    simulation = crossing_scenario()
    previous = _robots(simulation)

    for _ in range(20):
        state = simulation.tick()
        current = _robots(simulation)
        assert all(0.0 <= robot["movement_credit"] <= 1.0 for robot in current.values())
        _assert_no_vertex_or_edge_collisions(previous, current)
        previous = current
        if all(robot["status"] == "arrived" for robot in current.values()):
            break

    robots = _robots(simulation)
    assert robots["R01"]["position"] == [3, 7]
    assert robots["R02"]["position"] == [6, 4]
    assert all(robot["status"] == "arrived" for robot in robots.values())
    assert any(
        message["kind"] == "denial"
        and message["payload"]["reason"] == "cell_conflict"
        for message in simulation.messages
    )
    assert any(message["kind"] == "request" for message in simulation.messages)
    assert any(message["kind"] == "grant" for message in simulation.messages)
    assert any(message["kind"] == "position_update" for message in simulation.messages)
    assert state["tick"] == simulation.tick_count


def test_head_on_swap_is_denied_for_both_robots():
    simulation = FleetSimulation(
        [".."],
        [
            RobotSpec("left", (0, 0), (0, 1)),
            RobotSpec("right", (0, 1), (0, 0)),
        ],
    )

    state = simulation.tick()

    assert [robot["position"] for robot in state["robots"]] == [[0, 0], [0, 1]]
    denials = [message for message in simulation.messages if message["kind"] == "denial"]
    assert len(denials) == 2
    assert {message["payload"]["reason"] for message in denials} == {"occupied_start"}
    assert all(robot["status"] == "waiting" for robot in state["robots"])


def test_coordinator_rotates_same_cell_conflict_priority():
    coordinator = TrafficCoordinator(["R01", "R02"])
    start = {"R01": (0, 0), "R02": (0, 2)}
    proposals = {"R01": (0, 1), "R02": (0, 1)}

    first = coordinator.resolve(proposals, start)
    second = coordinator.resolve(proposals, start)

    assert first["R01"].granted and not first["R02"].granted
    assert second["R02"].granted and not second["R01"].granted


def test_paused_robot_does_not_move_or_accrue_credit():
    simulation = FleetSimulation(
        ["....", "...."],
        [
            RobotSpec("R1", (0, 0), (0, 3)),
            RobotSpec("R2", (1, 3), (1, 0)),
        ],
    )
    simulation.tick(speed_factors={"R1": 0.5, "R2": 0.0})
    before = _robots(simulation)["R1"]
    assert before["movement_credit"] == pytest.approx(0.5)

    simulation.tick(speed_factors={"R1": 1.0, "R2": 0.0}, paused_ids=["R1"])
    paused = _robots(simulation)["R1"]

    assert paused["position"] == [0, 0]
    assert paused["movement_credit"] == pytest.approx(0.5)
    assert paused["status"] == "paused"
    control = [
        message
        for message in simulation.messages
        if message["tick"] == 2 and message["receiver"] == "R1" and message["kind"] == "control"
    ][0]
    assert control["payload"]["effective_speed_factor"] == 0.0
    assert control["payload"]["paused"] is True

    simulation.tick(speed_factors={"R1": 0.5, "R2": 0.0})
    resumed = _robots(simulation)["R1"]
    assert resumed["position"] == [0, 1]
    assert resumed["movement_credit"] == 0.0


def test_fractional_movement_credit_handles_repeated_tenths():
    simulation = FleetSimulation(
        ["..........", ".........."],
        [
            RobotSpec("slow", (0, 0), (0, 9)),
            RobotSpec("idle", (1, 9), (1, 0)),
        ],
    )

    for _ in range(9):
        simulation.tick(speed_factors={"slow": 0.1, "idle": 0.0})
    assert _robots(simulation)["slow"]["position"] == [0, 0]
    assert _robots(simulation)["slow"]["movement_credit"] == pytest.approx(0.9)

    simulation.tick(speed_factors={"slow": 0.1, "idle": 0.0})
    slow = _robots(simulation)["slow"]
    assert slow["position"] == [0, 1]
    assert slow["movement_credit"] == 0.0


@pytest.mark.parametrize(("factor", "expected_steps"), [(0.4, 2), (0.6, 3)])
def test_fractional_surplus_is_carried_after_each_granted_move(factor, expected_steps):
    simulation = FleetSimulation(
        ["...........", "..........."],
        [
            RobotSpec("paced", (0, 0), (0, 10)),
            RobotSpec("idle", (1, 10), (1, 0)),
        ],
    )

    for _ in range(5):
        simulation.tick(speed_factors={"paced": factor, "idle": 0.0})

    paced = _robots(simulation)["paced"]
    assert paced["steps"] == expected_steps
    assert 0.0 <= paced["movement_credit"] <= 1.0


def test_zero_speed_suppresses_move_with_credit_retained_from_denial():
    simulation = FleetSimulation(
        [".."],
        [
            RobotSpec("left", (0, 0), (0, 1)),
            RobotSpec("right", (0, 1), (0, 0)),
        ],
    )
    simulation.tick()
    before = _robots(simulation)
    assert all(robot["movement_credit"] == 1.0 for robot in before.values())

    simulation.tick(speed_factors={"left": 0.0, "right": 0.0})
    stopped = _robots(simulation)
    assert [robot["position"] for robot in stopped.values()] == [[0, 0], [0, 1]]
    assert all(robot["movement_credit"] == 1.0 for robot in stopped.values())
    waits = [
        message
        for message in simulation.messages
        if message["tick"] == 2 and message["kind"] == "wait"
    ]
    assert len(waits) == 2
    assert {message["payload"]["reason"] for message in waits} == {"zero_speed"}


def test_tick_rejects_invalid_controls_without_mutating_state():
    simulation = crossing_scenario()
    simulation.tick(speed_factors={"R01": 0.25})
    invalid_calls = [
        {"speed_factors": {"missing": 0.5}},
        {"speed_factors": {"R01": True}},
        {"speed_factors": {"R01": math.nan}},
        {"speed_factors": {"R01": math.inf}},
        {"speed_factors": {"R01": -0.01}},
        {"speed_factors": {"R01": 1.01}},
        {"speed_factors": []},
        {"paused_ids": ["missing"]},
        {"paused_ids": "R01"},
    ]

    for kwargs in invalid_calls:
        before = simulation.snapshot()
        with pytest.raises(ValueError):
            simulation.tick(**kwargs)
        assert simulation.snapshot() == before


def test_map_batch_validates_union_of_positions_and_goals_atomically():
    simulation = FleetSimulation(
        [".....", "....."],
        [
            RobotSpec("A", (0, 0), (0, 4)),
            RobotSpec("B", (1, 0), (1, 4)),
        ],
    )
    planners = {robot_id: agent.planner for robot_id, agent in simulation.agents.items()}
    search_tables = {robot_id: agent.planner.g for robot_id, agent in simulation.agents.items()}
    rhs_tables = {robot_id: agent.planner.rhs for robot_id, agent in simulation.agents.items()}

    with pytest.raises(GridError):
        simulation.update_cells(
            [{"cell": [0, 2], "blocked": True}, {"cell": [1, 4], "blocked": True}]
        )
    assert simulation.grid.to_rows() == [".....", "....."]
    assert simulation.grid.revision == 0
    for robot_id, agent in simulation.agents.items():
        assert agent.planner is planners[robot_id]
        assert agent.planner.grid.to_rows() == [".....", "....."]
        assert agent.planner.g is search_tables[robot_id]
        assert agent.planner.initialization_count == 1

    assert simulation.update_cells([{"cell": [0, 2], "blocked": True}]) == {(0, 2)}
    assert simulation.grid.revision == 1
    for robot_id, agent in simulation.agents.items():
        assert agent.planner is planners[robot_id]
        assert agent.planner.g is search_tables[robot_id]
        assert agent.planner.rhs is rhs_tables[robot_id]
        assert agent.planner.grid.revision == simulation.grid.revision
        assert agent.planner.initialization_count == 1

    simulation.tick()
    for robot_id, agent in simulation.agents.items():
        assert agent.planner is planners[robot_id]
        assert agent.planner.g is search_tables[robot_id]
        assert agent.planner.rhs is rhs_tables[robot_id]
        assert agent.planner.initialization_count == 1


def test_fixed_seed_fleet_stress_preserves_transition_and_map_invariants():
    factors = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    for seed in range(30):
        rng = random.Random(seed)
        height = width = 6
        blocked = {
            (row, column)
            for row in range(height)
            for column in range(width)
            if rng.random() < 0.16
        }
        open_cells = [
            (row, column)
            for row in range(height)
            for column in range(width)
            if (row, column) not in blocked
        ]
        starts = rng.sample(open_cells, 3)
        goals = rng.sample(open_cells, 3)
        rows = [
            "".join("#" if (row, column) in blocked else "." for column in range(width))
            for row in range(height)
        ]
        robot_ids = ("R1", "R2", "R3")
        simulation = FleetSimulation(
            rows,
            [
                RobotSpec(robot_id, start, goal)
                for robot_id, start, goal in zip(robot_ids, starts, goals)
            ],
        )
        planners = {robot_id: agent.planner for robot_id, agent in simulation.agents.items()}
        previous = {robot_id: agent.position for robot_id, agent in simulation.agents.items()}

        for tick_index in range(20):
            speed_factors = {
                robot_id: rng.choice(factors) for robot_id in robot_ids
            }
            paused_ids = {
                robot_id for robot_id in robot_ids if rng.random() < 0.15
            }
            simulation.tick(speed_factors=speed_factors, paused_ids=paused_ids)

            current = {robot_id: agent.position for robot_id, agent in simulation.agents.items()}
            assert len(set(current.values())) == len(robot_ids), (seed, tick_index)
            for robot_id, position in current.items():
                assert position not in simulation.grid.blocked, (seed, tick_index, robot_id)
                assert simulation.agents[robot_id].goal not in simulation.grid.blocked
                distance = abs(position[0] - previous[robot_id][0]) + abs(
                    position[1] - previous[robot_id][1]
                )
                assert distance <= 1, (seed, tick_index, robot_id, distance)
                if robot_id in paused_ids or speed_factors[robot_id] == 0.0:
                    assert position == previous[robot_id], (seed, tick_index, robot_id)
                assert 0.0 <= simulation.agents[robot_id].movement_credit <= 1.0
                assert simulation.agents[robot_id].planner is planners[robot_id]
                assert simulation.agents[robot_id].planner.initialization_count == 1
                assert simulation.agents[robot_id].planner.start == position

            _assert_no_vertex_or_edge_collisions(
                {robot_id: {"position": list(value)} for robot_id, value in previous.items()},
                {robot_id: {"position": list(value)} for robot_id, value in current.items()},
            )
            previous = current

            if tick_index % 5 == 4:
                protected = {
                    cell
                    for agent in simulation.agents.values()
                    for cell in (agent.position, agent.goal)
                }
                candidates = [
                    (row, column)
                    for row in range(height)
                    for column in range(width)
                    if (row, column) not in protected
                ]
                cell = rng.choice(candidates)
                simulation.update_cells(
                    [{"cell": cell, "blocked": cell not in simulation.grid.blocked}]
                )

            expected_rows = simulation.grid.to_rows()
            for robot_id, agent in simulation.agents.items():
                assert agent.planner is planners[robot_id]
                assert agent.planner.grid.to_rows() == expected_rows
                assert agent.planner.grid.revision == simulation.grid.revision
                assert agent.planner.initialization_count == 1


def test_paused_unreachable_robot_recovers_after_route_reopens():
    simulation = FleetSimulation(
        [".....", ".....", "....."],
        [
            RobotSpec("A", (1, 0), (1, 4)),
            RobotSpec("B", (0, 0), (0, 4)),
        ],
    )
    agent = simulation.agents["A"]
    planner = agent.planner

    simulation.tick(speed_factors={"A": 1.0, "B": 0.0}, paused_ids={"A"})
    assert agent.status == "paused"
    assert agent.movement_credit == 0.0

    barrier = [
        {"cell": (row, 2), "blocked": True}
        for row in range(3)
    ]
    simulation.update_cells(barrier)
    assert agent.status == "unreachable"
    assert agent.path == []
    assert agent.cost is None
    assert agent.movement_credit == 0.0

    simulation.tick(speed_factors={"A": 1.0, "B": 0.0}, paused_ids={"A"})
    assert agent.status == "paused"
    assert agent.movement_credit == 0.0
    simulation.update_cells([{"cell": (1, 2), "blocked": False}])
    assert agent.path[0] == agent.position
    assert agent.path[-1] == agent.goal
    assert agent.status == "paused"

    simulation.tick(speed_factors={"A": 0.0, "B": 0.0})
    assert agent.status == "ready"
    assert agent.planner is planner
    assert agent.planner.initialization_count == 1
    assert 0.0 <= agent.movement_credit <= 1.0


@pytest.mark.parametrize(
    "robots",
    [
        [RobotSpec("only", (0, 0), (0, 1))],
        [RobotSpec("same", (0, 0), (0, 1)), RobotSpec("same", (1, 0), (1, 1))],
        [RobotSpec("unsafe/id", (0, 0), (0, 1)), RobotSpec("ok", (1, 0), (1, 1))],
        [RobotSpec("A", (0, 0), (0, 1)), RobotSpec("B", (0, 0), (1, 1))],
        [RobotSpec("A", (0, 0), (0, 1)), RobotSpec("B", (1, 0), (0, 1))],
        [RobotSpec("A", (0, 0), (0, 1)), RobotSpec("B", (1, 0), (1, 8))],
    ],
)
def test_constructor_rejects_invalid_fleet_specs(robots):
    with pytest.raises((ValueError, GridError)):
        FleetSimulation(["....", "...."], robots)


def test_snapshots_are_deeply_isolated_and_json_serializable():
    simulation = crossing_scenario()
    simulation.tick()
    snapshot = simulation.snapshot()
    json.dumps(snapshot)
    snapshot["rows"][0] = "........."
    snapshot["robots"][0]["position"][0] = 999
    snapshot["robots"][0]["path"].clear()
    snapshot["messages"][0]["payload"]["paused"] = "changed"

    fresh = simulation.snapshot()
    assert fresh["rows"][0] == "####.####"
    assert fresh["robots"][0]["position"] != [999, 1]
    assert fresh["robots"][0]["path"]
    assert fresh["messages"][0]["payload"]["paused"] is False


def test_clearance_uses_blocked_cells_and_other_robot_positions():
    simulation = FleetSimulation(
        ["#....", ".....", "....."],
        [
            RobotSpec("A", (1, 0), (2, 4)),
            RobotSpec("B", (1, 3), (2, 0)),
        ],
    )
    assert simulation.clearance_cells("A") == 1.0
    assert simulation.clearance_cells("B") == 3.0
    with pytest.raises(ValueError):
        simulation.clearance_cells("missing")


def test_cli_writes_replay_json_and_rejects_negative_ticks(tmp_path):
    output_path = tmp_path / "replay.json"
    assert main(["--ticks", "4", "--output", str(output_path)]) == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["ticks_run"] == 4
    assert output["messages"]
    assert output["final"]["tick"] == 4

    with pytest.raises(SystemExit):
        main(["--ticks", "-1"])
