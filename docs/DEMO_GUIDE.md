# Demonstration and evidence guide

Submission / live demonstration: Tuesday, October 13, 2026, Asia/Jakarta.

The application is **Warehouse Operations**, a local simulation combining
external-rule diagnostics with D* Lite route repair. All observation categories,
rules, and scenarios are illustrative. They demonstrate software behavior rather
than establish a physical robot's condition.

## Setup and checks

For a new laptop, follow the [README development setup](../README.md#development-setup).
Windows uses a PowerShell download block or `run.bat` inside an extracted ZIP.
Linux/macOS use a Terminal download block or `bash run.sh` inside the extracted
project folder. Both paths prepare Python 3.12 and the libraries, then open the
local app. You do not need Git, Python, or a GitHub sign-in to start. First setup
needs internet and the normal download/archive utilities described in the README.

On first start, `run.bat` prepares the Python 3.12 runtime and project
environment, installs and checks dependencies, and opens the local app in your
default browser. It reuses the environment on later starts unless requirements
changed. If port 8501 is busy, the launcher chooses the next available port.
Keep the terminal open during the demo and press Ctrl+C to stop the app.
`run_demo.bat` still works as a compatibility alias.

To run the project checks before opening the app, open the project folder in
File Explorer, type `powershell` in its address bar, press Enter, and use:

```powershell
.\run.bat -Verify
```

This prepares the environment, runs pytest, and then starts the app. Use
`.\run.bat -SetupOnly` to prepare the environment without launching it, or pass
`-Python "C:\Path\to\python.exe"` to supply a specific validated Python 3.12
installation when creating the environment. On Linux/macOS, use
`bash run.sh --verify` for the equivalent test-and-launch sequence, or
`bash run.sh --setup-only` to prepare without launching.

## Live demonstration

1. Select **Warehouse Corridor Changes** and reset the simulation. The route
   costs 10 moves, map revision is zero, and the robot starts at `(4, 1)`.
2. Open **Diagnostics**. Select **Battery Power-Path Chain** and press
   **Load preset**. The result lists `battery_power_path_issue` and
   `battery_related_stall`, with firing order R03, R04, R05, R06.
3. Expand **Inference trace and source proofs (4 steps)**. R03 and R04 independently
   derive facts from raw power observations. R05 uses those derived facts;
   R06 combines the derived power-path issue with the stalled movement observation.
   The firing list is chronological; it does not imply R04 depends on R03.
4. Enable **Apply diagnostic safety gate** and return to **Route planner**.
   Movement controls are disabled. Apply the next scenario event to block the
   central aisle: revision becomes one and route cost becomes 12. Map repair
   remains available while movement is paused.
5. In **Evidence & methods**, download the session JSON. It records the exact
   raw observations, findings, fired rules, gate state, routes, source commit,
   environment, and knowledge-base source hash.
6. Return to **Diagnostics**. In **Observation draft**, change Movement status
   to `moving`, Battery voltage to `normal`, and Battery connection to
   `connected`. Press **Apply observations and evaluate**. The old findings
   and trace disappear because inference starts from the corrected raw input.
7. In **Route planner**, movement is enabled. Apply the next scenario event
   to move one step. Position becomes `(3, 1)` and remaining route cost is 11.
   Expand the retained-planner history: initialization count remains one.
8. Download a second session JSON. Compare both exports: the findings changed,
   while the map revision and retained search state reflect the real events.

The **Corrected Observations** preset is another way to clear the initial
fault case. **Partial Power Evidence** demonstrates a missing optional-group
member; **Simultaneous Fault Findings** demonstrates several compatible findings.
`Unknown` is JSON `null`, never a negative observation. An optional group becomes
required only after at least one member is known.

The guided form is a separate draft. Manual edits in **Advanced observations
(JSON)** are evaluated as the active input. Press **Load current JSON into draft**
to synchronize the guided fields; only submitting the draft replaces that active
input. Duplicate keys and non-finite numbers are rejected. With the gate enabled,
invalid or incomplete input blocks movement. With the gate disabled, the route
simulation operates independently of diagnosis.

## Run each module without the interface

```powershell
.\.venv\Scripts\python.exe -m expert_system --list-scenarios
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop --output artifacts/battery-diagnosis.json
.\.venv\Scripts\python.exe -m expert_system --all --output artifacts/diagnostics.json
.\.venv\Scripts\python.exe -m search_algorithm.main --output artifacts/single-replay.json
.\.venv\Scripts\python.exe tools/replay_demo.py --output artifacts/demo
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
.\.venv\Scripts\python.exe tools/benchmark_search.py --output artifacts/benchmark --repeats 5
```

The eight diagnostic fixtures declare explicit expected statuses and conditions.
`--all` succeeds only when every result matches those expectations, including
the intentional invalid-input fixture. A single invalid scenario or invalid
raw-facts input returns exit code 2 by design. These are fixture checks, not
measurements of diagnostic accuracy. `python -m expert_system.main` is an
equivalent CLI entry point. See [EXPERT_SYSTEM.md](EXPERT_SYSTEM.md) for all flags.

The combined tool runs the real engine and planner. It verifies the battery
chain, accepts a map change during the pause, attempts a move and checks rejection
without mutation, corrects the observations, and resumes using the same planner.
Its exported costs are checked against A*; its initialization count must remain one.

Four search scenarios cover aisle closure/reopening, movement with retained
state, unreachable-goal recovery, and widespread changes. Benchmarks report
initial, repair, and cumulative work separately. Do not promise that D* Lite is
always faster than A*: small maps or expensive initialization can favor A*.

## Evidence and presentation

Current and historical source revisions are identified separately in
[the evidence index](evidence/README.md). Preserve actual JSON, test output,
screenshots or recordings, source commit, environment, and file checksums.
Development exports belong in ignored `artifacts/`. Old evidence is retained
as historical measurement rather than relabeled as current output.

The lead explains route repair and integration. The teammate explains the
knowledge base, raw versus derived facts, missing evidence, and correction.
Before presenting, the teammate should pull current main, reproduce the commands
on their laptop, review the rules, and rehearse the live sequence. A recorded
software demonstration does not establish that this independent rehearsal occurred.
See [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md) for presentation preparation.
