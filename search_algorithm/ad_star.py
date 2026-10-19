"""Anytime Dynamic A* (AD*) search on a finite four-neighbor grid.

Combines anytime heuristic search with dynamic replanning:
- Starts with an inflated heuristic weight epsilon >= 1.0 to find an initial
  bounded suboptimal path quickly.
- Progressively repairs and improves the path towards optimal (epsilon = 1.0)
  within a given time budget.
- Efficiently repairs routes when the grid environment changes dynamically.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import asdict, dataclass, field
from itertools import count
from time import perf_counter
from typing import Any

from .grid import Grid, GridError
from .models import Position, SearchMetrics, SearchResult, SearchStatus


def _manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class IntermediateSolution:
    epsilon: float
    cost: int
    path: list[Position]
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "epsilon": self.epsilon,
            "cost": self.cost,
            "path": [list(cell) for cell in self.path],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


@dataclass
class ADStarResult(SearchResult):
    """Search result with anytime progression details."""

    epsilon: float = 1.0
    solutions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["epsilon"] = self.epsilon
        data["solutions"] = self.solutions
        return data


Key = tuple[float, float]


class ADStarPlanner:
    """Anytime Dynamic A* planner for warehouse grid routing with a time budget."""

    def __init__(
        self,
        grid: Grid,
        start: Position,
        goal: Position,
        initial_epsilon: float = 2.5,
        min_epsilon: float = 1.0,
        epsilon_step: float = 0.5,
    ) -> None:
        if not isinstance(grid, Grid):
            raise GridError("grid must be a Grid instance")
        self.grid = grid.clone()
        self.start = self.grid.validate_position(start, "start")
        self.goal = self.grid.validate_position(goal, "goal")

        if initial_epsilon < 1.0:
            raise ValueError("initial_epsilon must be >= 1.0")
        if min_epsilon < 1.0:
            raise ValueError("min_epsilon must be >= 1.0")
        if epsilon_step <= 0.0:
            raise ValueError("epsilon_step must be positive")

        self.initial_epsilon = float(initial_epsilon)
        self.min_epsilon = float(min_epsilon)
        self.epsilon_step = float(epsilon_step)
        self.epsilon = self.initial_epsilon

        self._metrics = SearchMetrics()
        self._initialization_count = 0
        self._solutions: list[IntermediateSolution] = []

        # Search state (backward search from goal to start)
        self.g: dict[Position, float] = {}
        self.v: dict[Position, float] = {}
        self._open: list[tuple[float, float, int, Position]] = []
        self._open_entries: dict[Position, tuple[Key, int]] = {}
        self._closed: set[Position] = set()
        self._incons: set[Position] = set()
        self._sequence = count()

        self._initialize()

    def _initialize(self) -> None:
        self._initialization_count += 1
        cells = [(r, c) for r in range(self.grid.height) for c in range(self.grid.width)]
        self.g = dict.fromkeys(cells, math.inf)
        self.v = dict.fromkeys(cells, math.inf)
        self.g[self.goal] = 0.0

        self._open.clear()
        self._open_entries.clear()
        self._closed.clear()
        self._incons.clear()
        self._sequence = count()

        self._push(self.goal, self._key(self.goal))

    def _key(self, cell: Position) -> Key:
        h = _manhattan(cell, self.start)
        g_val = self.g[cell]
        v_val = self.v[cell]
        if v_val >= g_val:
            return (g_val + self.epsilon * h, g_val)
        return (v_val + h, v_val)

    def _push(self, cell: Position, key: Key) -> None:
        generation = next(self._sequence)
        self._open_entries[cell] = (key, generation)
        heapq.heappush(self._open, (*key, generation, cell))
        self._metrics.queue_pushes += 1

    def _discard_stale(self) -> None:
        while self._open:
            k1, k2, generation, cell = self._open[0]
            if self._open_entries.get(cell) == ((k1, k2), generation):
                return
            heapq.heappop(self._open)
            self._metrics.queue_pops += 1

    def _top_key(self) -> Key:
        self._discard_stale()
        if not self._open:
            return (math.inf, math.inf)
        return (self._open[0][0], self._open[0][1])

    def _pop(self) -> tuple[Position, Key]:
        self._discard_stale()
        k1, k2, _, cell = heapq.heappop(self._open)
        del self._open_entries[cell]
        self._metrics.queue_pops += 1
        return cell, (k1, k2)

    def _update_vertex(self, cell: Position) -> None:
        if cell != self.goal:
            min_cost = math.inf
            for neighbor in self.grid.neighbors(cell):
                edge = self.grid.cost(cell, neighbor)
                if edge != math.inf:
                    cost = edge + self.v[neighbor]
                    if cost < min_cost:
                        min_cost = cost
            self.g[cell] = min_cost

        if cell in self._open_entries:
            del self._open_entries[cell]

        if self.g[cell] != self.v[cell]:
            if cell not in self._closed:
                self._push(cell, self._key(cell))
            else:
                self._incons.add(cell)

    def _compute_or_improve_path(self, deadline: float | None = None) -> bool:
        start_key = self._key(self.start)
        while self._top_key() < start_key or self.v[self.start] < self.g[self.start]:
            if deadline is not None and perf_counter() >= deadline:
                return False
            if not self._open:
                break
            current, _ = self._pop()
            self._metrics.processed_states += 1

            if self.v[current] > self.g[current]:
                self.v[current] = self.g[current]
                self._closed.add(current)
                for neighbor in self.grid.neighbors(current):
                    self._update_vertex(neighbor)
            else:
                self.v[current] = math.inf
                self._update_vertex(current)
                for neighbor in self.grid.neighbors(current):
                    self._update_vertex(neighbor)
            start_key = self._key(self.start)

        return not math.isinf(self.g[self.start])

    def _extract_path(self) -> tuple[list[Position], int] | None:
        if math.isinf(self.g[self.start]):
            return None
        current = self.start
        path = [current]
        cost = 0

        visited = {current}
        while current != self.goal:
            best_neighbor = None
            best_val = math.inf
            for neighbor in self.grid.neighbors(current):
                edge = self.grid.cost(current, neighbor)
                if edge == math.inf:
                    continue
                val = edge + self.g[neighbor]
                if val < best_val:
                    best_val = val
                    best_neighbor = neighbor

            if best_neighbor is None or best_neighbor in visited:
                # Cycle or dead end
                return None
            current = best_neighbor
            visited.add(current)
            path.append(current)
            cost += 1

        return path, cost

    def update_cells(self, changes: dict[Position, bool]) -> None:
        """Apply dynamic obstacle changes and update affected states."""
        for cell, is_blocked in changes.items():
            valid_cell = self.grid.validate_position(cell, "changed_cell", require_open=False)
            if is_blocked:
                self.grid.blocked.add(valid_cell)
            else:
                self.grid.blocked.discard(valid_cell)

            self._update_vertex(valid_cell)
            for neighbor in self.grid.neighbors(valid_cell):
                self._update_vertex(neighbor)

    def move_start(self, new_start: Position) -> None:
        """Move the robot position without resetting previous search states."""
        self.start = self.grid.validate_position(new_start, "start")

    def plan(self, time_budget_ms: float | None = None) -> ADStarResult:
        """Run anytime search within the given time budget, refining the path."""
        started = perf_counter()
        deadline = started + (time_budget_ms / 1000.0) if time_budget_ms else None

        if self.start == self.goal:
            elapsed = (perf_counter() - started) * 1000.0
            self._metrics.elapsed_ms = elapsed
            return ADStarResult(
                status="found",
                path=[self.start],
                cost=0,
                metrics=self._metrics,
                epsilon=1.0,
                solutions=[
                    {
                        "epsilon": 1.0,
                        "cost": 0,
                        "path": [list(self.start)],
                        "elapsed_ms": round(elapsed, 3),
                    }
                ],
                message="Start is at goal.",
            )

        best_path: list[Position] | None = None
        best_cost: int | None = None
        current_epsilon = self.initial_epsilon

        while True:
            self.epsilon = current_epsilon
            reached = self._compute_or_improve_path(deadline)
            extraction = self._extract_path()

            if extraction is not None:
                path, cost = extraction
                best_path = path
                best_cost = cost
                elapsed = (perf_counter() - started) * 1000.0
                sol = IntermediateSolution(
                    epsilon=current_epsilon,
                    cost=cost,
                    path=path,
                    elapsed_ms=elapsed,
                )
                self._solutions.append(sol)

            if current_epsilon <= self.min_epsilon:
                break
            if deadline is not None and perf_counter() >= deadline:
                break

            # Decrease epsilon and prepare next iteration
            current_epsilon = max(self.min_epsilon, current_epsilon - self.epsilon_step)
            self.epsilon = current_epsilon

            # Move inconsistent states back to open
            for cell in self._incons:
                self._open_entries.pop(cell, None)
                self._push(cell, self._key(cell))
            self._incons.clear()

            # Re-key all items in open with new epsilon
            old_cells = list(self._open_entries.keys())
            self._open.clear()
            self._open_entries.clear()
            for cell in old_cells:
                self._push(cell, self._key(cell))

            self._closed.clear()

        total_elapsed = (perf_counter() - started) * 1000.0
        self._metrics.elapsed_ms = total_elapsed

        if best_path is not None and best_cost is not None:
            return ADStarResult(
                status="found",
                path=best_path,
                cost=best_cost,
                metrics=self._metrics,
                epsilon=current_epsilon,
                solutions=[s.to_dict() for s in self._solutions],
                message=f"Solution found with epsilon={current_epsilon:.2f}.",
            )

        return ADStarResult(
            status="unreachable",
            path=[],
            cost=None,
            metrics=self._metrics,
            epsilon=current_epsilon,
            solutions=[s.to_dict() for s in self._solutions],
            message="No route connects start and goal on the current map.",
        )


def ad_star(
    grid: Grid,
    start: object,
    goal: object,
    time_budget_ms: float | None = None,
    initial_epsilon: float = 2.5,
    min_epsilon: float = 1.0,
    epsilon_step: float = 0.5,
) -> ADStarResult:
    """One-shot helper to run AD* on a given grid map."""
    started = perf_counter()
    metrics = SearchMetrics()

    def finish(status: SearchStatus, message: str = "") -> ADStarResult:
        metrics.elapsed_ms = max(0.0, (perf_counter() - started) * 1000.0)
        return ADStarResult(status=status, metrics=metrics, message=message)

    if not isinstance(grid, Grid):
        return finish("invalid_input", "grid must be a Grid instance")

    try:
        start_cell = grid.validate_position(start, "start")
        goal_cell = grid.validate_position(goal, "goal")
    except GridError as err:
        return finish("invalid_input", str(err))

    try:
        planner = ADStarPlanner(
            grid,
            start_cell,
            goal_cell,
            initial_epsilon=initial_epsilon,
            min_epsilon=min_epsilon,
            epsilon_step=epsilon_step,
        )
        return planner.plan(time_budget_ms=time_budget_ms)
    except Exception as exc:
        return finish("invalid_input", str(exc))
