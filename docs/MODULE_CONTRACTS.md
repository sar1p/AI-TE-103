# Module contracts

These contracts define the boundaries between independently runnable AI modules.
Coordinates are zero-based (row, column) pairs, encoded as JSON arrays.

## Route planning

Grid(height, width, blocked=()) uses finite four-neighbor movement at unit cost.
Grid.from_rows(rows) accepts equally sized strings containing . and #.
Manhattan distance is the heuristic. A blocked cell has impassable incident edges.

astar(grid, start, goal) returns a SearchResult. Invalid endpoints return
invalid_input. DStarLitePlanner(grid, start, goal) validates endpoints and raises
GridError on invalid construction. It owns a copy of the map so outside changes
cannot silently alter its edge costs. Its public methods are:

- plan() -> SearchResult
- move_start(position): one legal adjacent move, or the unchanged current cell.
- update_cells(changes): an atomic batch of {"cell": [row, column], "blocked": bool}.

Updates cannot block the current robot or goal. Unknown keys, noninteger/boolean
coordinates, out-of-bounds cells, conflicting duplicate updates, and invalid
types are rejected before mutation. A goal change starts a new planner session.

~~~json
{
  "status": "found",
  "path": [[0, 0], [0, 1]],
  "cost": 1,
  "metrics": {
    "processed_states": 2,
    "queue_pops": 2,
    "queue_pushes": 3,
    "elapsed_ms": 0.12
  },
  "message": ""
}
~~~

This is an illustration of the shape, not measured output. status is found,
unreachable, or invalid_input. A failed result has path: [] and cost: null.
The path includes both endpoints. A valid start equal to the goal has cost zero.
No JSON infinity or NaN is emitted.

## Diagnosis

The public module entry point is:

expert_system.engine.diagnose(facts: dict[str, object]) -> dict

The engine also exposes load_knowledge_base(path=None), validate_knowledge_base(payload),
and infer(facts, knowledge_base) for validated external rule data and focused fixtures.
The default knowledge base is expert_system/knowledge_base.json. The engine does not
import Streamlit or route-planner code.

### Raw observation schema

All nine raw observations are categorical strings with exact allowed values:

| Observation | Values | Evidence group |
|---|---|---|
| motor_temperature | normal, high | Required |
| movement_status | moving, idle, stalled | Required |
| sensor_lidar | clear, blocked | Required |
| battery_voltage | normal, low | Optional power group |
| battery_connection | connected, disconnected | Optional power group |
| drive_status | normal, fault | Optional drive_feedback group |
| encoder_feedback | present, absent | Optional drive_feedback group |
| motor_connection | connected, disconnected | Optional motor_path group |
| motor_enable | enabled, disabled | Optional motor_path group |

An absent key or null means unknown, never false. The first three observations are
required. An optional group is inactive when all its members are absent or null.
When at least one member is known, every other member in that group becomes
required for completeness. Missing evidence does not prevent inference from other
known facts; the result can contain findings while status is insufficient_evidence.

### Result shape and status

Return exactly these JSON-compatible top-level fields:

~~~json
{
  "status": "insufficient_evidence",
  "findings": [],
  "rule_trace": [],
  "recommendations": [],
  "missing_facts": ["motor_temperature"]
}
~~~

The sample only illustrates shape. The fields are:

- status: ok, insufficient_evidence, or invalid_input.
- findings: ordered records shaped as {"condition": str, "rule_ids": [str]}.
- rule_trace: ordered records shaped as {"rule_id": str, "premises": dict,
  "conclusion": dict, "reason": str}.
- recommendations: records shaped as {"action": str, "reason": str}.
- missing_facts: names of required observations or missing members of activated
  optional groups, in knowledge-base order.

ok means accepted evidence is complete within this schema. It does not mean the
robot is healthy or prove that unsupported faults are absent. A complete input
may have no findings. insufficient_evidence reports missing observations but can
still carry findings and recommendations supported by known facts. invalid_input
returns empty findings, trace, recommendations, and missing_facts.

A diagnosis starts with a fresh copy of the caller's raw facts and does not mutate
them. Corrections replace raw facts and invoke a fresh diagnosis; derived facts
from an earlier call are not accepted as raw input. Unknown observation names,
wrong types, unsupported values, arrays, objects, and non-finite values are invalid.
The function raises KnowledgeBaseError if the external knowledge base cannot be
loaded or validated; a configuration problem is not reported as user invalid_input.

### Knowledge-base and inference rules

The JSON knowledge base has schema_version 1 and exactly these top-level fields:
schema_version, provenance, required_observations, observations, groups, and rules.
Its provenance must identify the content as illustrative. The current file has
11 rules and six exposed conditions:

- suspected_motor_overheating (R01)
- lidar_obstruction (R02)
- battery_power_path_issue (R05)
- battery_related_stall (R06)
- drive_encoder_fault (R09)
- motor_connection_fault (R11)

The remaining rules derive intermediate facts for multi-step chains. Rule entries
declare a unique ID, illustrative validation label, premises, conclusion, reason,
whether to expose a finding, and recommendations. Premises must refer to a
declared raw or derived fact and an allowed value. Conflicting values assigned to
the same derived condition are rejected. Finding rules must include pause_robot
in the conclusion and recommendations; intermediate rules do not publish
recommendations.

Rules execute in knowledge-base order in deterministic sweeps until a sweep derives
no new fact. A rule ID fires at most once in a diagnosis, so cycles terminate.
Each trace record preserves the rule's declared premises and conclusion. Findings
include the ordered rule IDs in the supporting proof. Recommendations are
deduplicated by their exact action and reason. Current action IDs include pause_robot, check_power, check_drive, and check_encoder. Every current rule and explanation
is illustrative; no physical accuracy or causal validity is asserted.

The JSON loader rejects duplicate object keys and non-finite numbers. Schema errors
raise KnowledgeBaseError. knowledge_base_metadata includes the source label, raw
source-file SHA-256, schema version, and provenance for evidence exports.

### CLI and named scenarios

Run the independent diagnostic CLI without opening the visual app:

~~~powershell
.\.venv\Scripts\python.exe -m expert_system --list-scenarios
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe -m expert_system --facts facts.json
~~~

Exactly one of --scenario ID, --facts PATH, --list-scenarios, or --all is required.
--facts accepts - for standard input. --knowledge-base PATH selects a validated
knowledge base. --output PATH (also --output-file PATH) writes the emitted JSON
to a file and stdout.

The eight scenario IDs are battery-multi-hop, corrected-observations,
drive-encoder-multi-hop, empty-input, invalid-observation,
motor-connection-multi-hop, partial-power, and simultaneous-faults. Each fixture
declares its own expected status and ordered exposed-condition list. --all returns
0 only when each actual result matches its fixture expectation, including the
intentional invalid-input case. A single invalid diagnosis returns exit code 2;
malformed input, unknown scenario, and knowledge-base failures also return 2.
Exports retain the supplied raw facts and include environment and knowledge-base
metadata. Scenario exports include their expected result and expectation_match.

### Simulation integration

When the diagnostic safety gate is enabled, movement requires an accepted ok
diagnosis without a pause_robot recommendation. Incomplete or invalid input also
blocks movement. With the gate disabled, search runs independently of diagnosis.
The gate does not control a physical robot.
The combined demonstration in tools/combined_demo.py checks that a map edit is
allowed while movement is paused, an attempted move is rejected without changing
the simulation, and corrected observations permit one step with the same planner
instance and initialization count of one. The script also checks its expected
10, 12, 11 route costs against A*. [The clean-clone combined export](evidence/completed-system-2026-10-11/combined-demo.json)
records all seven checks passing. The teammate's independent review and
two-person presentation rehearsal remain unverified.

The diagnostics module is suitable for demonstrating a bounded, explainable rule
system. It is unsuitable for field diagnosis, safety certification, or claims of
measured accuracy, reliability, or physical suitability.

## Fuzzy speed proposals

`fuzzy_logic.evaluate_speed(clearance_cells, battery_percent)` evaluates Mamdani
max-min inference. `evaluate_sugeno_speed` uses the same antecedents with
zero-order singleton consequents. Both require finite non-boolean numbers in
the documented universes, return strict JSON-compatible proof records, and
raise `FuzzyInputError` before producing output for invalid inputs.

The output contains `inputs`, `memberships`, nine `rules` with activations,
`output.speed_percent`, `output.speed_factor`, `aggregation`, `defuzzification`,
and illustrative provenance. Mamdani exposes 201 aggregate samples and a
composite-trapezoidal centroid approximation. Sugeno has an empty aggregation
list and exposes singleton weighted contributions. `configuration()` returns
an isolated copy of the rules, membership definitions, and method metadata.

Output percentages are normalized cadence proposals. A tick has no physical
time calibration. Membership degrees are not probabilities. Diagnostic stops,
zero synthetic battery, and denied traffic reservations override movement.

## Independent agents and traffic coordination

`multi_agent_system.FleetSimulation(rows, robots)` accepts a grid and at least
two validated `RobotSpec(id, start, goal)` records. IDs, starting positions,
and goals are distinct. Each robot owns a persistent D* Lite planner and local
position, goal, route, state, movement credit, and counters.

`tick(speed_factors=None, paused_ids=())` validates all controls before mutation.
Factors lie in [0,1]; unspecified factors default to one. Accumulated credit
permits at most one move per tick. Successful moves preserve fractional
surplus; denied requests retain at most one credit, preventing a stored burst.
Zero speed and paused state suppress movement even with earned credit.

Agents propose their own next cells. A rotating-priority coordinator only grants
unique destinations that were free at the start of the tick. Messages record
requests, decisions, reasons, and position updates. The conservative rule rejects
same-cell conflicts, swaps, and following into a newly vacated cell. It can
deadlock and does not optimize a joint trajectory.

`update_cells(changes)` protects all current robot positions and goals and
prevalidates the entire batch before updating every retained planner. Planning
can recover after reopening an aisle. Snapshot `status` is the last tick's
operating state until the next tick; map updates repair the route immediately.
`clearance_cells(robot_id)` computes capped Manhattan distance to known blocked
cells or other robots. It does not infer physical sensor distance.

## Integrated fleet control

`interface.fleet_session.FleetControlSession` composes the four methods.
Battery percentages and categorical diagnostic observations are separate inputs.
Every step evaluates a fresh diagnosis per robot, computes the selected fuzzy
proposal, applies diagnosis/zero-battery stop priority, and requests traffic
reservations only through the simulation API. Unknown or invalid diagnostic
evidence blocks that robot. The independent single-robot workspace retains its
explicit optional gate for search-only demonstrations.

`to_dict()` exports current fleet state, rules/configuration, next-step proposals,
last-step controls, per-tick records, raw observations, and limitations. Viewing
or exporting does not advance the simulation. The app adds source/environment
metadata to its shared export, and the standalone replay records it explicitly.
