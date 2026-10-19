import pytest

from search_algorithm.ad_star import ADStarPlanner, ad_star
from search_algorithm.astar import astar
from search_algorithm.grid import Grid


def test_ad_star_finds_optimal_path_when_reaching_epsilon_one():
    grid = Grid.from_rows([
        "......",
        ".####.",
        "......",
    ])
    start = (0, 0)
    goal = (2, 5)

    res_astar = astar(grid, start, goal)
    res_adstar = ad_star(grid, start, goal, initial_epsilon=2.5, min_epsilon=1.0)

    assert res_adstar.status == "found"
    assert res_adstar.cost == res_astar.cost
    assert res_adstar.path[0] == start
    assert res_adstar.path[-1] == goal
    assert len(res_adstar.solutions) >= 1


def test_ad_star_start_equals_goal():
    grid = Grid(3, 3)
    res = ad_star(grid, (1, 1), (1, 1))
    assert res.status == "found"
    assert res.cost == 0
    assert res.path == [(1, 1)]


def test_ad_star_unreachable_goal():
    grid = Grid.from_rows([
        "...",
        "###",
        "...",
    ])
    res = ad_star(grid, (0, 0), (2, 2))
    assert res.status == "unreachable"
    assert res.path == []
    assert res.cost is None


def test_ad_star_invalid_inputs():
    grid = Grid(3, 3, blocked=[(0, 0)])
    # Blocked start
    res = ad_star(grid, (0, 0), (2, 2))
    assert res.status == "invalid_input"

    # Out of bounds
    res2 = ad_star(grid, (0, 1), (5, 5))
    assert res2.status == "invalid_input"

    # Invalid grid
    res3 = ad_star("not_a_grid", (0, 1), (1, 1))
    assert res3.status == "invalid_input"


def test_ad_star_anytime_progression():
    grid = Grid.from_rows([
        "..........",
        ".########.",
        "..........",
        ".########.",
        "..........",
    ])
    planner = ADStarPlanner(grid, (0, 0), (4, 9), initial_epsilon=3.0, min_epsilon=1.0, epsilon_step=1.0)
    result = planner.plan()

    assert result.status == "found"
    assert len(result.solutions) > 0
    # Epsilon decreases monotonically
    epsilons = [s["epsilon"] for s in result.solutions]
    assert epsilons == sorted(epsilons, reverse=True)
    # Costs should not increase
    costs = [s["cost"] for s in result.solutions]
    for i in range(len(costs) - 1):
        assert costs[i] >= costs[i + 1]


def test_ad_star_dynamic_replanning_and_moving_start():
    grid = Grid(5, 5)
    planner = ADStarPlanner(grid, (0, 0), (4, 4), initial_epsilon=2.0, min_epsilon=1.0)
    initial_res = planner.plan()
    assert initial_res.status == "found"
    assert initial_res.cost == 8

    # Dynamic obstacle blocks direct diagonal path
    planner.update_cells({(1, 1): True, (2, 2): True, (3, 3): True})
    repaired_res = planner.plan()
    assert repaired_res.status == "found"
    assert (1, 1) not in repaired_res.path
    assert (2, 2) not in repaired_res.path
    assert (3, 3) not in repaired_res.path

    # Move start position
    planner.move_start((0, 1))
    moved_res = planner.plan()
    assert moved_res.status == "found"
    assert moved_res.path[0] == (0, 1)
