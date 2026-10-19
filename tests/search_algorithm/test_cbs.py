import pytest

from search_algorithm.cbs import AgentTask, CBSPlanner, cbs_search, find_first_conflict
from search_algorithm.grid import Grid


def test_cbs_parallel_agents_no_conflict():
    grid = Grid(4, 4)
    tasks = [
        AgentTask(agent_id=1, start=(0, 0), goal=(0, 3)),
        AgentTask(agent_id=2, start=(2, 0), goal=(2, 3)),
    ]
    planner = CBSPlanner(grid, tasks)
    res = planner.plan()

    assert res.status == "found"
    assert res.cost == 6  # 3 moves each
    assert res.makespan == 3
    assert find_first_conflict(res.paths) is None


def test_cbs_vertex_collision_resolution():
    # Crossing paths at center (1, 1)
    grid = Grid(3, 3)
    tasks = [
        AgentTask(agent_id="A", start=(1, 0), goal=(1, 2)),
        AgentTask(agent_id="B", start=(0, 1), goal=(2, 1)),
    ]
    res = cbs_search(grid, tasks)

    assert res.status == "found"
    assert find_first_conflict(res.paths) is None
    # Both reached their goal
    assert res.paths["A"][-1] == (1, 2)
    assert res.paths["B"][-1] == (2, 1)


def test_cbs_edge_swap_conflict_resolution():
    # Corridor with side pocket at (1, 1):
    # . . .
    # # . #
    grid = Grid.from_rows([
        "...",
        "#.#",
    ])
    # Agent 1 moves (0, 0) -> (0, 2)
    # Agent 2 moves (0, 2) -> (0, 0)
    # They would swap at (0, 1) unless one uses (1, 1) or waits
    tasks = [
        {"agent_id": 1, "start": (0, 0), "goal": (0, 2)},
        {"agent_id": 2, "start": (0, 2), "goal": (0, 0)},
    ]
    res = cbs_search(grid, tasks)

    assert res.status == "found"
    assert find_first_conflict(res.paths) is None
    assert res.paths[1][-1] == (0, 2)
    assert res.paths[2][-1] == (0, 0)


def test_cbs_three_agents():
    grid = Grid(5, 5)
    tasks = [
        AgentTask(agent_id=1, start=(0, 0), goal=(4, 4)),
        AgentTask(agent_id=2, start=(0, 4), goal=(4, 0)),
        AgentTask(agent_id=3, start=(2, 0), goal=(2, 4)),
    ]
    res = cbs_search(grid, tasks)

    assert res.status == "found"
    assert find_first_conflict(res.paths) is None
    for t in tasks:
        assert res.paths[t.agent_id][-1] == t.goal


def test_cbs_unreachable_agent():
    grid = Grid.from_rows([
        "...",
        "###",
        "...",
    ])
    tasks = [
        AgentTask(agent_id=1, start=(0, 0), goal=(2, 2)),
        AgentTask(agent_id=2, start=(0, 1), goal=(0, 2)),
    ]
    res = cbs_search(grid, tasks)
    assert res.status == "unreachable"


def test_cbs_invalid_inputs():
    grid = Grid(3, 3)
    # Duplicate start
    res = cbs_search(grid, [
        {"agent_id": 1, "start": (0, 0), "goal": (1, 1)},
        {"agent_id": 2, "start": (0, 0), "goal": (2, 2)},
    ])
    assert res.status == "invalid_input"

    # Non-grid
    res2 = cbs_search("invalid", [])
    assert res2.status == "invalid_input"


def test_cbs_to_dict_serialization():
    grid = Grid(3, 3)
    tasks = [
        AgentTask(agent_id=1, start=(0, 0), goal=(0, 1)),
        AgentTask(agent_id=2, start=(2, 0), goal=(2, 1)),
    ]
    res = cbs_search(grid, tasks)
    d = res.to_dict()
    assert d["status"] == "found"
    assert "1" in d["paths"] or 1 in d["paths"]
    assert isinstance(d["paths"]["1"], list)
    assert isinstance(d["agent_results"], list)
