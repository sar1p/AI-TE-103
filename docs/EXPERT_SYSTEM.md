# Expert-system starter and integration review

The teammate's original commit `a57eebd8e93cb00a899ee792146707f96e750046`
introduces two robot-diagnostic rules. The integration correction keeps that
commit in history and fixes its output format, input validation, and English
explanations. This is a starter, not the complete planned forward-chaining module.

## Supported observations

| Observation | Accepted known values | Unknown |
|---|---|---|
| `motor_temperature` | `normal`, `high` | Missing key or JSON `null` |
| `movement_status` | `moving`, `idle`, `stalled` | Missing key or JSON `null` |
| `sensor_lidar` | `clear`, `blocked` | Missing key or JSON `null` |

Only these categorical observations are supported. Additional names, numeric
temperatures, booleans, arrays, objects, and unlisted strings return
`invalid_input` without firing rules. JSON parsing and non-finite values are also
checked by the application adapter. Invalid evidence cannot allow gated movement.

Every call starts from the supplied raw facts and leaves them unchanged. Missing
or `null` evidence is unknown. If any supported observation is unknown, the result
is `insufficient_evidence`, even when the available observations support a finding.
Known evidence is evaluated in deterministic R01, R02 order.

## Illustrative rules

| Rule | Required known observations | Suspected condition | Recommendation |
|---|---|---|---|
| R01 | High motor temperature and stalled movement | `suspected_motor_overheating` | `pause_robot`; inspect motor temperature and drive load |
| R02 | Blocked lidar sensor | `lidar_obstruction` | `pause_robot`; inspect the sensor for an obstruction |

Provenance: these are teammate-proposed classroom simulation rules, not rules
validated against a manufacturer manual, a domain expert, or measured robot
faults. A high temperature plus stalled movement does not establish causation.
No cooling duration, confidence percentage, or diagnostic accuracy is asserted.

The output uses the exact fields in [MODULE_CONTRACTS.md](MODULE_CONTRACTS.md):
`findings` contain condition and rule IDs; trace records use singular
`conclusion`; recommendations contain action and reason. Each supported finding
has a grounded trace. Two compatible findings may coexist. Returned trace data
does not share mutable rule dictionaries with later calls.

## Reproduce through the application

From a setup repository, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open Diagnostics, enable **Apply diagnostic safety gate**, and enter:

```json
{
  "motor_temperature": "high",
  "movement_status": "stalled",
  "sensor_lidar": "clear"
}
```

Expected: a valid `ok` result with R01, `suspected_motor_overheating`, and
`pause_robot`. Here `ok` means a complete, supported diagnostic evaluation, not
that the robot is healthy. The **Move robot one step** button is disabled.

Correct the observations:

```json
{
  "motor_temperature": "normal",
  "movement_status": "moving",
  "sensor_lidar": "clear"
}
```

Expected: `ok`, no fired rules, no remaining findings or pause recommendations.
The gate allows one simulated move without resetting the route planner.
This does not establish the absence of faults outside the two-rule knowledge base.
In particular, high temperature with moving status, or normal temperature with
stalled status, does not match R01. With a clear lidar and all three observations
present, those inputs also allow simulated movement. The starter has no standalone
temperature or stall alarm; add and validate such rules if the agreed scope
requires them. Do not use this movement policy to control a physical robot.

Other hand-written expectations:

| Input change or case | Expected result |
|---|---|
| Set `sensor_lidar` to `blocked` in the corrected input | R02 and a pause recommendation |
| Motor fault input with `sensor_lidar: "blocked"` | R01 and R02; both findings retained |
| `{}` or all three values `null` | `insufficient_evidence`; all three observations missing |
| `{"sensor_lidar": "blocked"}` | R02 retained, two missing observations, `insufficient_evidence`, movement paused |
| Replace the temperature with `[]`, movement with `17`, and lidar with `true` | `invalid_input`, no invented findings, movement paused |

The Evidence tab exports the actual diagnosis and raw observations alongside the
computed route, source metadata, and gate state. Record the source commit when
collecting new evidence. Existing screenshots under `docs/evidence/` describe the
earlier search-only demonstration and are not proof of this engine's execution.

## Verification and remaining work

```powershell
.\.venv\Scripts\python.exe -m pytest tests/expert_system tests/integration/test_expert_system_app.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

New tests exercise actual engine outputs, malformed and incomplete observations,
simultaneous findings, corrected facts, fresh rule data, and real Streamlit pause
and resume behavior. The older adapter fixtures remain useful for testing a
missing or broken module, but cannot substitute for actual engine integration.

The teammate still owns external rule loading and schema validation, a genuine
multi-rule forward-chaining engine with termination checks, expanded diagnostic
scenarios, an independent CLI, and fresh-clone/recorded presentation evidence.
Keep [issue #3](https://github.com/sar1p/AI-TE-303/issues/3) open until its complete
acceptance criteria are verified. Additional rules need documented provenance
and independent expected outcomes before their scope is claimed complete.
