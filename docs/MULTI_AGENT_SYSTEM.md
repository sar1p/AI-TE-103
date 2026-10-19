# Multi-Agent Warehouse Simulation

This package adds a small, deterministic warehouse simulation for multiple
goal-based robots. Each robot owns a persistent D* Lite planner for its own
start and fixed goal. A centralized traffic coordinator resolves one movement
proposal per robot against the positions observed at the start of each tick.
The planners remain independent; the coordinator does not compute a joint route
or claim global optimality.

## Run the example

From the repository root, print a JSON replay of the crossing scenario:

```powershell
.venv\Scripts\python.exe -m multi_agent_system --ticks 12
```

Write the same output to a file:

```powershell
.venv\Scripts\python.exe -m multi_agent_system --ticks 12 --output crossing.json
```

`--ticks` is required and must be a nonnegative integer. The JSON contains the
final snapshot and the event log, including controls, movement requests,
grants, denials, waits, and position updates.

## Python API

```python
from multi_agent_system import FleetSimulation, RobotSpec

simulation = FleetSimulation(
    rows=[".......", "......."],
    robots=[
        RobotSpec("R01", (0, 0), (0, 6)),
        RobotSpec("R02", (1, 6), (1, 0)),
    ],
)

state = simulation.tick(speed_factors={"R01": 0.5}, paused_ids={"R02"})
print(state["robots"])
```

`RobotSpec` is frozen and has fields `id`, `start`, and `goal`. IDs must be
unique, nonempty ASCII identifiers of up to 32 characters, beginning with a
letter or digit and continuing with letters, digits, `_`, or `-`. There must be
at least two robots; starting cells and goal cells must each be unique. Every
endpoint must be an open cell in the map. Starts and goals are checked
independently, so one robot may initially occupy another robot's goal. Such a
configuration can still create a wait or deadlock under the conservative
reservation rule.

`simulation.agents` maps IDs to `RobotAgent` instances. Each agent has its own
persistent `planner`; successful moves call `move_start` on that planner, and
map edits update the same planner rather than replacing it. The shared
`simulation.grid` and each planner's private grid receive the same validated
map revision.

`tick(speed_factors=None, paused_ids=())` defaults unspecified factors to `1.0`.
Factors must be finite real numbers in `[0, 1]`; booleans are rejected. On an
active, reachable, unpaused tick with a positive factor, the robot adds that
factor to its movement credit. It proposes its next route cell when the credit
reaches one, spends one unit only after a grant, and carries any fractional
surplus forward. If a request is denied, retained credit is capped at one so
waiting cannot build a multi-move burst. The reported post-tick credit stays
in `[0, 1]`. A zero factor prevents movement even when the robot retained a
full move from an earlier denial. A paused robot neither moves nor accrues
credit, even if its input factor is positive. Paused, unreachable, and arrived
robots do not accrue credit. Invalid controls are rejected before simulation
state changes.

`update_cells(changes)` validates the entire batch against the union of every
robot's current position and goal before changing the shared grid or any
planner. Blocking an occupied position or goal, malformed records, conflicting
updates, or out-of-bounds cells raise `GridError` without a partial update.

`clearance_cells(robot_id)` returns the minimum Manhattan distance from that
robot's current cell to a blocked cell or another robot's current cell, capped
at `5.0`. It is a dimensionless grid-cell input for a fuzzy caller, not a
physical distance or safety margin.

## Snapshot and event records

`snapshot()` returns a JSON-compatible, isolated dictionary:

- `tick`: completed simulation tick number.
- `map_revision`: shared grid revision.
- `rows`: current `.` and `#` map.
- `robots`: one record per robot, in construction order. Each contains its
  ID, position, goal, status, current path, remaining path cost, successful
  move count, cumulative traffic-denial ticks, effective speed factor,
  movement credit, and persistent planner initialization count.
- `status` is one of `ready`, `waiting`, `paused`, `arrived`, or `unreachable`.
- `messages`: event records with `tick`, `sender`, `receiver`, `kind`, and a
  JSON-compatible `payload`.

At each tick the coordinator uses a frozen view of all starting positions. It
denies any proposal whose destination is occupied at that instant, even if the
occupant also requested to move. It groups the remaining requests by
destination and chooses one requester using a deterministic rotating
round-robin order. Robots then react to their grants or denials. Arrived robots
remain in place and continue to reserve their goal cell.

## Safety boundary and limitations

For this discrete model, a granted transition ends in an open cell that was
unoccupied at tick start, and only one robot can receive a grant for a target
cell. Therefore accepted transitions cannot produce a same-cell collision at
the next tick boundary. Because entry into every start-of-tick occupied cell is
denied, opposite-direction edge swaps are also prevented. This rule also
rejects following a robot into a cell it vacates during the same tick, which
can reduce throughput.

This is a one-tick cell reservation, not a joint path planner, continuous-time
collision checker, physical footprint model, or deadlock resolver. A pair of
robots facing one another in a single-width corridor will keep waiting safely;
the simulator does not back either robot out or find a passing bay. More
complex cycles can also remain blocked. The rule does not establish safety for
real robots moving continuously between cells or under timing uncertainty.

### Research context and possible next step

Conflict-Based Search (CBS) plans individual paths and branches on detected
vertex or edge conflicts. It can optimize a specified joint path cost, but its
high-level search can grow substantially. Enhanced CBS (ECBS) trades exact
optimality for a user-specified suboptimality bound. Safe Interval Path
Planning (SIPP) searches configuration and collision-free time intervals for
dynamic-obstacle timing. Windowed Hierarchical Cooperative A* (WHCA*) performs
space-time search over a rolling finite horizon, giving a practical bounded
window but not a global optimality or deadlock-free claim.

Open-RMF illustrates a more operational traffic-management design: fleet
managers report expected itineraries to a shared schedule; the system detects
upcoming conflicts and asks participants to submit and accommodate alternative
itineraries, after which an evaluator selects a proposal. This repository's
coordinator is a deliberately smaller single-process teaching model.

If the coursework needs route-level conflict avoidance, a future opt-in
extension should keep the existing API and add a separate bounded planning
method, for example:

```python
result = simulation.plan_window(horizon=8, max_expansions=10_000)
```

That method should return explicit `found`, `horizon_exhausted`, or
`budget_exhausted` status and proposed per-robot paths. A prioritized
space-time A*/WHCA*-style implementation is the smaller first step; its
priority order can bias outcomes, and bounded search may report no plan even
when a longer plan exists. CBS is a better follow-on if the coursework needs a
clear optimal joint-cost comparison on small maps. Both would need movement
timing that matches fractional speed factors before their timed reservations
could be treated as authoritative. Neither belongs in the current tick API
without separate scope and tests.

For physical robots, a discrete simulation still would not replace
independent sensing and actuator-level collision handling. Nav2's Collision
Monitor documents a sensor-driven stop/slowdown layer that bypasses the normal
costmap/planner path; its documentation also states that a CPU-level instance
does not provide hard real-time safety certification.

Primary references:

- Sharon et al., [Conflict-Based Search for Optimal Multi-Agent Pathfinding](https://doi.org/10.1016/j.artint.2014.11.006), *Artificial Intelligence*, 2015.
- Barer et al., [Suboptimal Variants of the Conflict-Based Search Algorithm](https://doi.org/10.1609/socs.v5i1.18315), SoCS, 2014.
- Silver, [Cooperative Pathfinding](https://doi.org/10.1609/aiide.v1i1.18726), AIIDE, 2005.
- Phillips and Likhachev, [SIPP: Safe Interval Path Planning for Dynamic Environments](https://doi.org/10.1109/ICRA.2011.5980306), ICRA, 2011.
- Open-RMF, [Traffic management overview](https://openrmf.readthedocs.io/_/downloads/en/latest/pdf/) and [`rmf_traffic` negotiation API](https://github.com/open-rmf/rmf_traffic/blob/main/rmf_traffic/include/rmf_traffic/schedule/Negotiation.hpp).
- Nav2, [Collision Monitor node](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/) and [Using Collision Monitor](https://docs.nav2.org/rolling/tutorials/general_tutorials/using_collision_monitor/using_collision_monitor/).

Run the focused tests with:

```powershell
.venv\Scripts\python.exe -m pytest tests/multi_agent_system -q
```
