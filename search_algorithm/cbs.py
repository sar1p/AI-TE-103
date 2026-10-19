"""Conflict-Based Search (CBS) for Multi-Agent Path Finding (MAPF).

Solves optimal, collision-free multi-agent routing on a finite warehouse grid:
- Low-level search: space-time A* for individual agents respecting vertex and edge constraints.
- High-level search: Conflict Tree (CT) resolving vertex collisions (same cell at same time)
  and edge swap collisions (agents swapping adjacent cells at the same time).
"""

from __future__ import annotations

import heapq
from dataclasses import asdict, dataclass, field
from itertools import count
from time import perf_counter
from typing import Any, Literal

from .grid import Grid, GridError
from .models import Position

CBSStatus = Literal["found", "unreachable", "invalid_input"]


def _manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass(frozen=True)
class VertexConstraint:
    agent: int | str
    cell: Position
    time: int


@dataclass(frozen=True)
class EdgeConstraint:
    agent: int | str
    from_cell: Position
    to_cell: Position
    time: int


@dataclass
class Conflict:
    agent1: int | str
    agent2: int | str
    time: int
    conflict_type: Literal["vertex", "edge"]
    cell: Position | None = None
    from_cell: Position | None = None
    to_cell: Position | None = None


@dataclass
class AgentTask:
    agent_id: int | str
    start: Position
    goal: Position


@dataclass
class AgentResult:
    agent_id: int | str
    start: Position
    goal: Position
    path: list[Position]
    cost: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "start": list(self.start),
            "goal": list(self.goal),
            "path": [list(cell) for cell in self.path],
            "cost": self.cost,
        }


@dataclass
class CBSResult:
    status: CBSStatus
    paths: dict[int | str, list[Position]] = field(default_factory=dict)
    cost: int | None = None
    makespan: int | None = None
    agent_results: list[AgentResult] = field(default_factory=list)
    conflicts_resolved: int = 0
    expanded_ct_nodes: int = 0
    elapsed_ms: float = 0.0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "paths": {str(k): [list(cell) for cell in v] for k, v in self.paths.items()},
            "cost": self.cost,
            "makespan": self.makespan,
            "agent_results": [a.to_dict() for a in self.agent_results],
            "conflicts_resolved": self.conflicts_resolved,
            "expanded_ct_nodes": self.expanded_ct_nodes,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "message": self.message,
        }


def _get_path_cell(path: list[Position], t: int) -> Position:
    if not path:
        raise ValueError("Cannot sample an empty path")
    if t >= len(path):
        return path[-1]
    return path[t]


def find_first_conflict(paths: dict[int | str, list[Position]]) -> Conflict | None:
    """Detect the earliest vertex or edge swap conflict between any two agents."""
    agents = list(paths.keys())
    if len(agents) < 2:
        return None

    max_len = max(len(p) for p in paths.values())

    for t in range(max_len):
        # 1. Check Vertex Conflicts at time t
        occupied: dict[Position, int | str] = {}
        for agent in agents:
            pos = _get_path_cell(paths[agent], t)
            if pos in occupied:
                return Conflict(
                    agent1=occupied[pos],
                    agent2=agent,
                    time=t,
                    conflict_type="vertex",
                    cell=pos,
                )
            occupied[pos] = agent

        # 2. Check Edge Conflicts between time t and t + 1
        if t < max_len - 1:
            for i in range(len(agents)):
                a1 = agents[i]
                p1_curr = _get_path_cell(paths[a1], t)
                p1_next = _get_path_cell(paths[a1], t + 1)

                for j in range(i + 1, len(agents)):
                    a2 = agents[j]
                    p2_curr = _get_path_cell(paths[a2], t)
                    p2_next = _get_path_cell(paths[a2], t + 1)

                    if p1_curr == p2_next and p1_next == p2_curr and p1_curr != p1_next:
                        return Conflict(
                            agent1=a1,
                            agent2=a2,
                            time=t,
                            conflict_type="edge",
                            from_cell=p1_curr,
                            to_cell=p1_next,
                        )

    return None


def low_level_astar(
    grid: Grid,
    start: Position,
    goal: Position,
    vertex_constraints: set[tuple[Position, int]],
    edge_constraints: set[tuple[Position, Position, int]],
    max_time: int = 120,
) -> list[Position] | None:
    """Space-time A* for a single agent subject to vertex and edge constraints."""
    if (start, 0) in vertex_constraints:
        return None

    # Check the latest constraint on the goal cell
    latest_goal_constraint = -1
    for cell, t in vertex_constraints:
        if cell == goal and t > latest_goal_constraint:
            latest_goal_constraint = t

    serial = count()
    frontier: list[tuple[int, int, int, Position, int]] = []
    # (f_score, g_cost, serial, current_cell, timestep)
    heapq.heappush(frontier, (_manhattan(start, goal), 0, next(serial), start, 0))

    best_g: dict[tuple[Position, int], int] = {(start, 0): 0}
    parent: dict[tuple[Position, int], tuple[Position, int]] = {}

    while frontier:
        _, g_cost, _, curr_cell, curr_t = heapq.heappop(frontier)

        if g_cost > best_g.get((curr_cell, curr_t), float("inf")):
            continue

        if curr_cell == goal and curr_t > latest_goal_constraint:
            # Reconstruct path
            path: list[Position] = []
            state = (curr_cell, curr_t)
            while state in parent:
                path.append(state[0])
                state = parent[state]
            path.append(start)
            path.reverse()
            return path

        if curr_t >= max_time:
            continue

        next_t = curr_t + 1
        # Possible actions: move to open neighbor or wait at current cell
        candidates = list(grid.neighbors(curr_cell)) + [curr_cell]

        for cand in candidates:
            # Check edge cost if moving
            if cand != curr_cell and grid.cost(curr_cell, cand) == float("inf"):
                continue

            # Vertex constraint check
            if (cand, next_t) in vertex_constraints:
                continue

            # Edge constraint check (if moving)
            if cand != curr_cell and (curr_cell, cand, curr_t) in edge_constraints:
                continue

            next_g = g_cost + 1
            state_key = (cand, next_t)
            if next_g < best_g.get(state_key, float("inf")):
                best_g[state_key] = next_g
                parent[state_key] = (curr_cell, curr_t)
                h_cost = _manhattan(cand, goal)
                heapq.heappush(
                    frontier,
                    (next_g + h_cost, next_g, next(serial), cand, next_t),
                )

    return None


@dataclass
class CTNode:
    constraints: set[VertexConstraint | EdgeConstraint]
    paths: dict[int | str, list[Position]]
    cost: int
    serial: int = 0

    def __lt__(self, other: "CTNode") -> bool:
        if self.cost == other.cost:
            return self.serial < other.serial
        return self.cost < other.cost


class CBSPlanner:
    """Conflict-Based Search planner for multi-agent path finding."""

    def __init__(self, grid: Grid, tasks: list[AgentTask]) -> None:
        if not isinstance(grid, Grid):
            raise GridError("grid must be a Grid instance")
        self.grid = grid.clone()
        self.tasks = tasks
        self._validate_tasks()

    def _validate_tasks(self) -> None:
        starts = set()
        goals = set()
        for t in self.tasks:
            valid_start = self.grid.validate_position(t.start, f"agent {t.agent_id} start")
            valid_goal = self.grid.validate_position(t.goal, f"agent {t.agent_id} goal")
            if valid_start in starts:
                raise GridError(f"Duplicate start position {valid_start}")
            if valid_goal in goals:
                raise GridError(f"Duplicate goal position {valid_goal}")
            starts.add(valid_start)
            goals.add(valid_goal)

    def plan(self, max_nodes: int = 500, time_limit_ms: float = 10000.0) -> CBSResult:
        started = perf_counter()
        deadline = started + (time_limit_ms / 1000.0)

        # Build initial paths
        initial_paths: dict[int | str, list[Position]] = {}
        for task in self.tasks:
            path = low_level_astar(self.grid, task.start, task.goal, set(), set())
            if path is None:
                elapsed = (perf_counter() - started) * 1000.0
                return CBSResult(
                    status="unreachable",
                    elapsed_ms=elapsed,
                    message=f"Agent {task.agent_id} cannot reach its goal independently.",
                )
            initial_paths[task.agent_id] = path

        root_cost = sum(len(p) - 1 for p in initial_paths.values())
        serial_gen = count()
        root = CTNode(
            constraints=set(),
            paths=initial_paths,
            cost=root_cost,
            serial=next(serial_gen),
        )

        open_nodes: list[CTNode] = [root]
        expanded_count = 0
        conflicts_resolved = 0

        while open_nodes:
            if perf_counter() >= deadline:
                elapsed = (perf_counter() - started) * 1000.0
                return CBSResult(
                    status="unreachable",
                    expanded_ct_nodes=expanded_count,
                    conflicts_resolved=conflicts_resolved,
                    elapsed_ms=elapsed,
                    message="CBS search reached time limit without finding conflict-free solution.",
                )

            if expanded_count >= max_nodes:
                elapsed = (perf_counter() - started) * 1000.0
                return CBSResult(
                    status="unreachable",
                    expanded_ct_nodes=expanded_count,
                    conflicts_resolved=conflicts_resolved,
                    elapsed_ms=elapsed,
                    message="CBS search reached maximum node expansion limit.",
                )

            curr_node = heapq.heappop(open_nodes)
            expanded_count += 1

            conflict = find_first_conflict(curr_node.paths)
            if conflict is None:
                # Goal reached: conflict-free paths found!
                elapsed = (perf_counter() - started) * 1000.0
                agent_results = []
                for task in self.tasks:
                    p = curr_node.paths[task.agent_id]
                    agent_results.append(
                        AgentResult(
                            agent_id=task.agent_id,
                            start=task.start,
                            goal=task.goal,
                            path=p,
                            cost=len(p) - 1,
                        )
                    )
                makespan = max((len(p) - 1 for p in curr_node.paths.values()), default=0)
                return CBSResult(
                    status="found",
                    paths=curr_node.paths,
                    cost=curr_node.cost,
                    makespan=makespan,
                    agent_results=agent_results,
                    conflicts_resolved=conflicts_resolved,
                    expanded_ct_nodes=expanded_count,
                    elapsed_ms=elapsed,
                    message="Optimal collision-free multi-agent paths found.",
                )

            conflicts_resolved += 1

            # Branching on conflict
            if conflict.conflict_type == "vertex":
                assert conflict.cell is not None
                branch_constraints = [
                    VertexConstraint(conflict.agent1, conflict.cell, conflict.time),
                    VertexConstraint(conflict.agent2, conflict.cell, conflict.time),
                ]
            else:
                assert conflict.from_cell is not None and conflict.to_cell is not None
                branch_constraints = [
                    EdgeConstraint(conflict.agent1, conflict.from_cell, conflict.to_cell, conflict.time),
                    EdgeConstraint(conflict.agent2, conflict.to_cell, conflict.from_cell, conflict.time),
                ]

            for constraint in branch_constraints:
                new_constraints = set(curr_node.constraints)
                new_constraints.add(constraint)

                # Re-plan low level for the constrained agent
                v_cons: set[tuple[Position, int]] = set()
                e_cons: set[tuple[Position, Position, int]] = set()
                for c in new_constraints:
                    if c.agent == constraint.agent:
                        if isinstance(c, VertexConstraint):
                            v_cons.add((c.cell, c.time))
                        elif isinstance(c, EdgeConstraint):
                            e_cons.add((c.from_cell, c.to_cell, c.time))

                task_for_agent = next(t for t in self.tasks if t.agent_id == constraint.agent)
                new_path = low_level_astar(
                    self.grid,
                    task_for_agent.start,
                    task_for_agent.goal,
                    v_cons,
                    e_cons,
                )

                if new_path is not None:
                    new_paths = dict(curr_node.paths)
                    new_paths[constraint.agent] = new_path
                    new_cost = sum(len(p) - 1 for p in new_paths.values())
                    child = CTNode(
                        constraints=new_constraints,
                        paths=new_paths,
                        cost=new_cost,
                        serial=next(serial_gen),
                    )
                    heapq.heappush(open_nodes, child)

        elapsed = (perf_counter() - started) * 1000.0
        return CBSResult(
            status="unreachable",
            expanded_ct_nodes=expanded_count,
            conflicts_resolved=conflicts_resolved,
            elapsed_ms=elapsed,
            message="No conflict-free solution exists under constraints.",
        )


def cbs_search(
    grid: Grid,
    agents: list[dict[str, Any]] | list[AgentTask],
    max_nodes: int = 500,
    time_limit_ms: float = 10000.0,
) -> CBSResult:
    """Helper function to execute CBS multi-agent path finding."""
    started = perf_counter()
    if not isinstance(grid, Grid):
        return CBSResult(
            status="invalid_input",
            elapsed_ms=max(0.0, (perf_counter() - started) * 1000.0),
            message="grid must be a Grid instance",
        )

    tasks: list[AgentTask] = []
    try:
        for item in agents:
            if isinstance(item, AgentTask):
                tasks.append(item)
            elif isinstance(item, dict):
                tasks.append(
                    AgentTask(
                        agent_id=item["agent_id"],
                        start=tuple(item["start"]),
                        goal=tuple(item["goal"]),
                    )
                )
            else:
                raise ValueError(f"Unsupported agent item type: {type(item)}")
        planner = CBSPlanner(grid, tasks)
        return planner.plan(max_nodes=max_nodes, time_limit_ms=time_limit_ms)
    except Exception as exc:
        return CBSResult(
            status="invalid_input",
            elapsed_ms=max(0.0, (perf_counter() - started) * 1000.0),
            message=str(exc),
        )
