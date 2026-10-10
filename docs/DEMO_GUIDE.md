# Demonstration and evidence guide

## Setup and checks

Use Python 3.12 and run commands from the repository root. In PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

An existing environment can be reused. Do not recreate it before every run.
On Linux/macOS, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
Core search and replay use only the standard library; the visual app needs
Streamlit and tests need pytest. `constraints.txt` records the tested versions.

## Visual running sequence

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open the local URL printed in the terminal. Stop the server with Ctrl+C when
finished. `run_demo.bat` is a Windows shortcut once the environment is installed.

1. Select **Warehouse Corridor Changes** and reset. Show the map, route cost,
   robot, fixed goal, and the actual initial search metrics.
2. Click **Apply next scenario event**. The central aisle closes and the route
   repairs. Compare the new cost and valid detour with A*.
3. Apply the movement event. The robot advances one cell. Open the incremental
   state panel and show one initialization and an updated `k_m`.
4. Continue the remaining events to reopen the aisle. A valid optimal route is
   recomputed from the robot's current position.
5. Select **Unreachable Goal Recovery**, reset, and apply its two events. Show
   `unreachable`, then restoration after the only gap reopens. The goal itself
   is never blocked.
6. Try a manual cell change. Row and column are zero-based. Blocking the robot
   or goal is rejected. Reset before replaying scripted events after manual edits.
7. Demonstrate the integrated diagnostic starter using the sequence below.
   Its two illustrative rules are working; external rule data and actual
   forward chaining remain pending.
8. Download actual session JSON from **Evidence & methods**. It contains maps,
   events, computed routes, metrics, raw observations text, the diagnosis,
   diagnostic gate setting, and source metadata.

The planner survives ordinary interface reruns, overlay changes, and downloads.
A browser reload or Reset creates a new session. The live UI computes results;
it does not display pretyped benchmark values.

## Diagnostic pause and correction

Reset **Warehouse Corridor Changes**, select **Diagnostics**, and enable
**Apply diagnostic safety gate**. Editing the observations and leaving the text
box triggers a fresh diagnosis; allow the result to finish updating.

1. Enter `{}`. The status is `insufficient_evidence`, the three observations
   are missing, and the gate prevents movement.
2. Enter the motor case:

   ```json
   {
     "motor_temperature": "high",
     "movement_status": "stalled",
     "sensor_lidar": "clear"
   }
   ```

   The result is `ok` with `suspected_motor_overheating`, rule `R01`, an
   explanation grounded in the two motor observations, and `pause_robot`.
   Select **Route planner** to show that the movement control is disabled.
   Map changes remain available. Download this paused session from
   **Evidence & methods**.
3. Replace the raw observations with the corrected case:

   ```json
   {
     "motor_temperature": "normal",
     "movement_status": "moving",
     "sensor_lidar": "clear"
   }
   ```

   The previous finding and trace disappear. The result is `ok` with no
   matching finding, and the gate allows simulated movement.
4. Return to **Route planner**. Apply the aisle-closing event, then its movement
   event. The route cost changes from 10 to 12 after closing the aisle, then
   to 11 after one legal step. The map revision is 1 and the planner retains
   one initialization. An equally optimal route may use a different first step.
5. Download the corrected session. Compare its raw observations, empty
   findings, enabled gate, movement event, and route history with the paused
   export. Screenshots document the interface; the JSON records actual results.

The `ok` status means the supplied observations meet this starter's input
requirements. It does not certify that a physical robot is healthy. The gate
uses a limited simulation policy: a valid diagnosis without `pause_robot`
allows movement. See [EXPERT_SYSTEM.md](EXPERT_SYSTEM.md) for supported values,
simultaneous findings, and incomplete or invalid observations.

## Headless fallback and benchmark

```powershell
.\.venv\Scripts\python.exe -m search_algorithm.main --output artifacts/single-replay.json
.\.venv\Scripts\python.exe tools/replay_demo.py --output artifacts/demo
.\.venv\Scripts\python.exe tools/benchmark_search.py --output artifacts/benchmark --repeats 5
```

Replay exports actual plan records for all four scenarios. The benchmark writes
`raw.csv` and `summary.json` with initial, repair, and cumulative measurements.
Both exports contain source SHA, worktree cleanliness, environment, versions,
and scenario inputs. A dirty-worktree result is useful during development but
must not be presented as proof of an unchanged committed revision.

## Presentation responsibilities

The lead explains D* Lite's retained state, changed edges, A* comparison, the
independent UCS oracle, suitable use cases, and limitations. The teammate explains
the current rules, traceability, unknown observations, corrected facts, and
multiple findings. See [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md).

The starter merged through [PR #5](https://github.com/sar1p/AI-TE-303/pull/5).
It evaluates two independent rules once. Its pause/correction integration has
been exercised in a clean clone and live browser. This is distinct from the
remaining forward-chaining engine and standalone diagnostic CLI.

After the expanded module is reviewed and merged, restart the app and show a
derived conclusion enabling another rule. Run its independent CLI and repeat
the relevant tests and combined evidence capture. Do not describe the starter's
single-rule trace as a multi-step inference chain.

## Submission evidence

Preserve actual test output, GitHub Actions links, replay JSON, benchmark CSV/JSON,
and real browser screenshots. Record the screen while presenting the live
scenario changes; the recording is a team task and is not automatically completed
by the screenshot exports. A successful headless run proves execution, while
live input changes and the displayed route demonstrate interactive behavior.

The final combined rehearsal must run from a fresh clone on the teammate's
laptop. Local clean-clone reproduction by the lead is a separate check. Keep large
recordings outside tracked source. Selected verified results live in
[docs/evidence/](evidence/README.md), including the separate
[integrated starter snapshot](evidence/integrated-starter-2026-10-11/README.md).
Temporary development exports live in ignored `artifacts/`.

## Recovery

- Missing `streamlit` or `pytest`: install the pinned requirements into the same
  interpreter used for the command.
- Port occupied: add `--server.port 8502` and use the printed URL.
- Invalid manual edit or scripted event conflict: reset the scenario.
- Broken diagnostic import or result format: review the Diagnostics error and
  the module contract. Search-only mode is an independent fallback.
- Restore source from Git history or a verified external Git bundle; a virtual
  environment can be rebuilt from the pinned requirement files.
