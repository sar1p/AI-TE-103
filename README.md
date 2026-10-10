# AI-TE-303

**Warehouse Robot Diagnostics and Dynamic Route Planning**

[![Python validation](https://github.com/sar1p/AI-TE-303/actions/workflows/tests.yml/badge.svg)](https://github.com/sar1p/AI-TE-303/actions/workflows/tests.yml)

A two-member Artificial Intelligence coursework project. D* Lite repairs a
warehouse robot's route after map changes and movement. Repeated A* provides a
baseline. A separate expert system uses external IF-THEN rules and forward
chaining to explain suspected robot faults and the observations supporting them.

## Implementation status

- Project layout, ownership, and module contracts: established.
- D* Lite, A*, validated maps, and independent search tests: implemented.
- Streamlit demonstration, scenario replay, benchmark exports, and diagnostic adapter: implemented.
- Expert system: validated external rule data, deterministic forward chaining,
  grounded explanations, unknown evidence, corrected observations, and an independent CLI.
- Diagnostic scope: nine categorical observations, eleven illustrative rules,
  six supported findings, and eight named scenarios.

See [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) for scope and
[TEAMMATE_TASKS.md](docs/TEAMMATE_TASKS.md) for contribution history and the review/presentation handoff.

## Development setup

Use Python 3.12. From this repository in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Run commands through the virtual environment's Python directly. Activating it
and changing PowerShell's execution policy are unnecessary. Core search will use
only the standard library, as does the expert-system engine. Streamlit provides
the local visual application.

After setup, Windows users can double-click `run_demo.bat`. Stop the server with
Ctrl+C. See [DEMO_GUIDE.md](docs/DEMO_GUIDE.md) for the live presentation sequence.

## Run without the interface

```powershell
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop --output artifacts/battery-diagnosis.json
.\.venv\Scripts\python.exe -m expert_system --all --output artifacts/diagnostic-scenarios.json
.\.venv\Scripts\python.exe -m search_algorithm.main --output artifacts/single-replay.json
.\.venv\Scripts\python.exe tools/replay_demo.py --output artifacts/demo
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
.\.venv\Scripts\python.exe tools/benchmark_search.py --output artifacts/benchmark --repeats 5
```

Four synthetic scenarios cover a blocked/reopened aisle, movement with retained
search state, unreachable-goal recovery, and widespread map changes. Exports
contain actual inputs, computed routes, metrics, source SHA, and environment.
Development exports go to ignored `artifacts/`.

The diagnostic replay checks each named case against its explicit expected
status and conditions, including intentionally incomplete or invalid cases.
The combined replay demonstrates a battery inference chain, rejected movement,
map repair, corrected observations, and resumed movement with one retained
planner. Exports include the raw inputs and knowledge-base provenance/hash.

Verified running results, source metadata, real screenshots, and clean-clone
checks are in [docs/evidence/](docs/evidence/README.md).

The [completed-system snapshot](docs/evidence/completed-system-2026-10-11/README.md)
records 167 passing tests, eight matching diagnostic fixtures, an actual
pause/correction browser demo, and a silent screen recording from a clean clone.
The teammate's independent review and laptop rehearsal remain the human handoff.

![Warehouse route after diagnosis correction](docs/evidence/completed-system-2026-10-11/warehouse-overview-wide.jpg)

## Why these methods

| Method | Role | Limits |
|---|---|---|
| D* Lite | Repair routes while the start moves toward a fixed goal and map connectivity changes | Initialization and extensive changes can cost more than reuse saves |
| A* | Fresh shortest-path baseline for the current map | Repeats search after each update |
| UCS / Dijkstra | Independent optimal-cost oracle in tests | Used for correctness, not the interactive planner |
| Forward-chaining expert system | Explain categorical observations through an inspectable rule chain, including power, drive feedback, and motor connection cases | Limited to declared observations and illustrative rules; no measured diagnostic accuracy |

The grid supports four-neighbor unit-cost movement. Weighted terrain, diagonal
motion, multiple robots, and physical control are outside this implementation.
See [SEARCH_ALGORITHM.md](docs/SEARCH_ALGORITHM.md) for algorithm details,
metric definitions, benchmark boundaries, and suitable/unsuitable uses.

The diagnostic safety gate requires a valid `ok` diagnosis without `pause_robot`
before allowing movement. A missing engine is shown as pending. The search-only
simulation remains independently usable. Adapter tests use synthetic contract
fixtures; separate engine, CLI, and Streamlit integration tests exercise the
actual rule data and correction behavior. `ok` means the supplied observations
are complete under this knowledge base, rather than a physical health or safety
certificate. See [EXPERT_SYSTEM.md](docs/EXPERT_SYSTEM.md) for supported
observations, inference semantics, suitable uses, and limitations.

The interface uses a restrained operations layout with separate route,
diagnostic, and evidence tabs. A guided observation draft and named presets
support the live demo; the advanced JSON input rejects ambiguous or non-finite
data. See [UI_DESIGN.md](docs/UI_DESIGN.md) for the design references and layout decisions.

## Collaboration

Use feature branches, tested commits, pull requests, and merge commits.
Each member uses their own account for their actual work.
See [CONTRIBUTING.md](CONTRIBUTING.md) and
[MODULE_CONTRACTS.md](docs/MODULE_CONTRACTS.md). New GitHub users can follow
[GITHUB_GUIDE.md](docs/GITHUB_GUIDE.md) for setup, commits, pushes, PRs, and recovery.

The expert-system handoff is tracked in
[issue #3](https://github.com/sar1p/AI-TE-303/issues/3). The teammate's
`zaedalmusthofa` account has collaborator access and an attributed starter commit.
That original commit remains in the main history. The lead completed the rule
engine expansion, tests, interface, and integration; those later changes use
the lead's identity. The teammate's next responsibility is review and rehearsal.

The classroom materials establish the assignment background. The warehouse
theme and advanced algorithm are this team's design choices. Simulation results
do not establish performance or diagnostic reliability on physical robots.

## Method reference

Sven Koenig and Maxim Likhachev, *D* Lite*, AAAI 2002.
[Primary paper](https://idm-lab.org/bib/abstracts/papers/aaai02b.pdf).
Implementation and experiment details are documented in the method guide and
versioned running evidence. Synthetic benchmark results do not establish a
universal speed advantage for D* Lite.
