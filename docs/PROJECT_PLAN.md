# AI-TE-103 Project Plan

## Group 1 repository and members

The repository was renamed from `AI-TE-303` to `AI-TE-103` after the team was
assigned group number 1. The member branches are:

- Muhammad Syarif Hidayat Hadari (`sar1p`): `dev1/muhammad-syarif-hidayat-hadari`.
- Zaedal Musthofa (`zaedalmusthofa`): `dev2/zaedal-musthofa`.
- Shared integration: protected `main`.

The member branches retain the existing work and use pull requests for
integration. Contributor identities and historical evidence are preserved.

## Scope extension: October 19, 2026

The user confirmed three coursework topics (expert systems, search, and
multi-agent systems), then requested fuzzy logic as a fourth method and a
primary-source review of more advanced approaches. The current extension adds
independent robot agents with explicit traffic messages and one-tick reservations,
Mamdani and zero-order Sugeno controllers, per-robot diagnosis priority, a shared
fleet demonstration, standalone CLIs, reproducible exports, and tests.

The four-method demonstration is simulated on a unit-cost grid. Controller
thresholds and battery percentages are illustrative. The coordinator does not
guarantee globally optimal routes or deadlock resolution. ANFIS, type-2 fuzzy
models, CBS/ECBS, WHCA*, and Open-RMF are researched alternatives, rather than
features claimed by the current implementation. See [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md),
[FUZZY_LOGIC.md](FUZZY_LOGIC.md), and [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md).

The dated sections below retain the original two-module plan and its historical
acceptance results; they do not limit this newer user-authorized extension.

## Original plan and completed baseline

Planning date: Friday, October 9, 2026. Submission / live demonstration: Tuesday, October 13, 2026, Asia/Jakarta.

Status: software implementation and running verification completed Sunday, October 11, 2026. [The current evidence](evidence/completed-system-2026-10-11/README.md) records 167 passing tests, eight matching diagnostic fixtures, nine clean-clone checks, real UI exports and a browser recording, combined integration, and passing main CI at source `118e95b50c2aa3196980435075a21ed6be789603`. Issue #3 is closed for completed software implementation and verification. Review and rehearsal are presentation preparation for Tuesday; they are not open software acceptance tasks. The October 9 scope sections below retain the original proposal.

## Project and scope

Proposed application title: **Warehouse Robot Diagnostics and Dynamic Route Planning**.

Repository name: `AI-TE-103`. Owner: `sar1p`. Use a dedicated checkout of this repository rather than the parent folder containing course materials.

The team has two members. The lead currently owns route planning, the application, and the expanded diagnostic engine, knowledge base, CLI, fixtures, and integration. The teammate contributed the original two-rule starter and now reviews the expanded implementation and rehearses the diagnostic presentation. Future contributions should be recorded under the actual contributor's own Git identity. All repository text, identifiers, comments, interface labels, documentation, commits, PRs, and workflow names use English.

The application runs locally in Python and simulates one warehouse robot. It has two separately runnable modules and one shared visual demonstration. No physical robot is required.

| Module | Required first version | Purpose |
|---|---|---|
| Expert system | External IF-THEN rules, forward chaining, explanation trace, unknown evidence, and recalculation after corrected facts | Explain possible robot faults and the observations behind each finding |
| Search | D* Lite with persistent incremental search state; repeated A* for comparison; UCS/Dijkstra as an independent correctness oracle | Repair a route after the robot moves or the map changes |
| Demo | Local Streamlit interface, named scenarios, step controls, blocked/unblocked cells, visible diagnoses and route metrics | Let the presenter change inputs and show actual computed behavior |
| Evidence | Automated tests, scenario replay, real exported results, clean-clone reproduction, and a screen recording | Demonstrate both correctness and reproducibility |

Bayesian reasoning is an optional extension after both required modules pass their tests and the complete demo works. Its parameters would need documented provenance. It is not required for the first release, and it is already mentioned in the supplied expert-system syllabus. No diagnosis percentages will be invented.

The first version excludes cloud deployment, chatbot APIs, physical motor control, multiple robots, continuous-space motion, and time-dependent collision prediction. These features are outside the two-day implementation target.

## Requirements and proposals

The supplied classroom notes describe a group repository, a manager/main branch, developer branches, module folders, and README content covering introduction, dependencies, usage, and running results. The expert-system slides describe a knowledge base, IF-THEN rules, and an inference engine. The search materials and LMS snapshot cover the established search algorithms used as our baselines.

D* Lite, the warehouse theme, the module split, the interface, and the acceptance tests below are project proposals. They are not additional lecturer requirements. The current deadline estimate comes from the user. Historical dates displayed in the LMS snapshot do not establish this assignment's current deadline.

## Module ownership

| Contributor | Current contribution | Next shared work |
|---|---|---|
| Teammate, zaedalmusthofa | Original R01/R02 starter, preserved as commit a57eebd8e93cb00a899ee792146707f96e750046 through normal merge PR #5 | Review current rules and traces; fresh-clone reproduction and presentation rehearsal; record any further work in the teammate's own commits |
| Lead | Route planning, application, shared contracts, and the expanded diagnostic engine, knowledge base, CLI, fixtures, and integration under the lead's own Git identity | Finish and record the remaining acceptance evidence |
| Both | Cross-review, integration acceptance, README accuracy, and final rehearsal | Confirm the results and limitations against actual current outputs |

The initial starter credit remains attached to its author. Current source ownership follows actual contributions and Git identities; coordinate shared-file changes through review.

Use the member branches in one shared repository. Preserve contributor identity in actual commits and review. A fork is optional and adds synchronization work.

## Module contract summary

The implementation boundary is frozen in [MODULE_CONTRACTS.md](MODULE_CONTRACTS.md). That document is authoritative for exact data types. This section summarizes the intended behavior.

### Diagnosis

`expert_system.engine.diagnose(facts: dict[str, object]) -> dict`

- Facts use documented names and types. An absent observation or `None` means unknown, never false.
- The function does not mutate the caller's facts. Each call starts a fresh inference session from the supplied raw observations.
- The result contains `status`, `findings`, `rule_trace`, `recommendations`, and `missing_facts`.
- Status is one of `ok`, `insufficient_evidence`, or `invalid_input`. Several supported findings may coexist; the engine does not assume that only one fault is possible.
- Trace entries identify the rule ID, observed/derived premises, produced conclusion, and English reason. Unsupported conclusions are excluded.
- Findings identify suspected conditions, not a claim of field-validated certainty. Rules record their source and validation status. Synthetic rules are marked `illustrative`.
- When a fact is corrected, the application replaces the raw observation and calls `diagnose` again. It must not feed old derived conclusions back into the next session.
- Contradictory representations of the same observation and invalid values produce a clear validation result. Document the exact combinations that are invalid; do not treat every unusual sensor combination as a contradiction.
- Recommendations can include English action IDs such as `pause_robot`, `check_power`, `check_drive`, and `check_encoder`. The module never imports the route planner or interface.

The current implementation scope is 11 illustrative rules, nine categorical observation fields, and six exposed suspected conditions. Three observations are required; six more are grouped into three optional pairs. The six findings are suspected motor overheating, lidar obstruction, battery power-path issue, battery-related stall, drive/encoder fault, and motor-connection fault. These remain software simulation cases until domain sources or expert review support the rules and thresholds. The count describes the current code, not a lecturer requirement or a measure of diagnostic quality.

### Route planning

- `DStarLitePlanner(grid, start, goal)` creates a search session.
- `move_start(position)` advances the current start without discarding the search session.
- `update_cells(changes)` applies a validated map update once.
- `plan() -> SearchResult` returns a route or an explicit unreachable result, plus metrics.
- `astar(grid, start, goal)` and the test oracle solve each current map snapshot independently.
- Results distinguish invalid input from an unreachable valid goal. A route contains its start and goal; each adjacent pair represents one valid move. Start equal to goal produces a one-cell route of cost zero.

Freeze the serialized result fields: `status` is `found`, `unreachable`, or `invalid_input`; `path` is a list of `[row, column]` integer pairs; `cost` is an integer for a found route and `null` otherwise. Unreachable and invalid results use an empty path. `metrics` contains nonnegative `processed_states`, `queue_pops`, `queue_pushes`, and finite `elapsed_ms`; the processing-counter definition is documented for each algorithm. Include the current map revision in exported replay records. Do not serialize infinite costs as nonstandard JSON numbers.

Reject coordinates outside the grid, blocked starts/goals, malformed updates, and an update that blocks the currently occupied start or fixed goal. Validate a start equal to goal before returning its zero-cost route. A goal is made unreachable by blocking its access, rather than blocking the goal cell itself. Reject an invalid event without partially mutating the map or search session.

The first version uses a finite four-neighbor grid, unit movement costs, blocked cells represented as impassable edges, Manhattan distance, and a fixed goal within a session. Search state includes `g`, `rhs`, the priority queue, and the start/key bookkeeping, and survives map changes. Changed edges update the affected vertices before repairing the path. A changed goal creates a new session. Follow the primary D* Lite pseudocode and handle outdated queue entries correctly.

Persist the planner in Streamlit session state between interface reruns. Apply map events once using event IDs or an equivalent explicit mechanism. A page reload may start a new session; the UI and scenario replay must make that behavior clear.

Test incremental reuse explicitly: instrument the initialization entry point and require exactly one initialization across a fixed-goal replay, verify the start/key bookkeeping follows the algorithm after movement, and check retained search values on an unaffected part of a controlled fixture. A test must fail if each map event reinitializes the search. Verify that a duplicate event ID does not move the robot, change the map revision, or apply an update a second time. Review the implementation in addition to these tests; route-cost agreement alone does not establish that the algorithm is incremental.

For comparisons, use the same map, start, goal, and map-event sequence. Compare valid route costs with the oracle, not necessarily the exact route geometry: multiple shortest routes may exist.

## Initial proposed repository layout

This is the October 9 outline, not a current file inventory; see the expert-system guide for the current module scope.

```text
AI-TE-103/
  README.md
  CONTRIBUTING.md
  requirements.txt
  requirements-dev.txt
  .gitignore
  app.py
  expert_system/
    __init__.py
    README.md
    main.py
    __main__.py
    engine.py
    knowledge_base.json
    scenarios.py
  search_algorithm/
    __init__.py
    README.md
    main.py
    grid.py
    models.py
    dstar_lite.py
    astar.py
  data/
    diagnostic_scenarios/
    search_scenarios/
  tests/
    expert_system/
    search_algorithm/
      oracle.py
    integration/
  tools/
    combined_demo.py
    replay_demo.py
    benchmark_search.py
  docs/
    PROJECT_PLAN.md
    MODULE_CONTRACTS.md
    TEAMMATE_TASKS.md
    EXPERT_SYSTEM.md
    SEARCH_ALGORITHM.md
    DEMO_GUIDE.md
    evidence/
  .github/
    workflows/
      tests.yml
```

Create only files needed by completed steps. Empty directories do not need placeholder files merely to inflate the structure. Each module gets its own README describing purpose, input, run command, output, and limitations.

Keep `.venv/`, caches, private `.env` files, Git bundles, and large temporary recordings outside tracked source. Keep the supplied lecture files and existing analysis backups in their current workspace locations. Copy the final English planning/handoff files into the new repository when implementation starts.

## Commit and push plan

A commit records one coherent, reviewable local change. A push transfers commits to the remote branch. For this beginner workflow, push after a tested commit or a short group of related tested commits. There is no target number of commits, and one push can contain several commits.

Suggested checkpoints below are work boundaries, not a requirement to fabricate a fixed history. Include behavior tests with the implementation they verify. A separate test commit is useful for an independent edge-case audit or regression discovered later.

| Checkpoint | Owner | Example English commit message | Observable outcome |
|---|---|---|---|
| Project bootstrap | Lead | `chore: initialize project layout and team documentation` | Scope, dependencies, contracts, ownership, and run instructions are recorded |
| Baseline search | Lead | `feat: add validated grid maps and A-star baseline` | A static map produces a validated route with tests and an independent oracle |
| Initial D* Lite search | Lead | `feat: implement D-star Lite initial planning` | Initial routes match optimal oracle costs |
| Incremental search | Lead | `feat: repair routes after map and start changes` | Blocking, reopening, and moving-start cases reuse search state and pass tests |
| Original diagnostic starter | Teammate | feat: add diagnostic rules and scenario fixtures | Original R01/R02 contribution remains in history under its author |
| Diagnostic engine expansion | Lead | feat: implement forward chaining and rule explanations | External rule data, chained inference, traces, scenarios, and CLI are present in source |
| Diagnostic review and correction audit | Teammate | docs: review diagnostic scenarios and limitations | Review current inputs, unknown/corrected behavior, explanations, and limits; record actual findings |
| Diagnostic integration and evidence | Lead and teammate | docs: record diagnostic integration evidence | Current UI/combined demo, fresh-clone run, and rehearsal are recorded after execution |
| Visual planning demo | Lead | `feat: visualize dynamic routes and planner metrics` | The presenter can move the start, edit obstacles, and view route results |
| Shared demonstration | Lead implementation, teammate review | `feat: connect diagnostic results to the simulation` | A completed diagnosis can visibly pause simulated movement and show a recommendation |
| Review and presentation rehearsal | Teammate | `docs: document diagnostic scenarios and limitations` | The teammate reviews the guide against actual output and rehearses the explanation |
| Final evidence | Both, owned artifacts | `docs: add verified demo evidence and comparison results` | Outputs reference the actual tested source revision and scenario IDs |

A practical PR grouping is bootstrap, baseline search, D* Lite, expert-system increments, visual demo, integration, and evidence. Each PR can contain several meaningful commits. The review scope should be small enough to inspect before merging.

Protect `main` after the initial repository bootstrap: require PRs, passing Python test checks once present, and prevent force pushes/deletion. With two contributors, cross-review feature PRs. Enable normal merge commits so individual feature commits remain visible in main's history. Squash merging combines them into one commit and is not the selected method for this assignment.

After a merge, start the next feature from updated main. Coordinate concurrent edits to shared knowledge-base, engine, and route-planner files through review.

## Running evidence and acceptance

| Scenario | Visible demonstration | Required check |
|---|---|---|
| Initial route | Map, start, goal, and planned route | Every move is valid; route cost equals the independent optimal oracle |
| Robot advances | Start moves along the grid | Search session persists; new route starts at the new position |
| Corridor closes | An obstacle is added to the current route | The next route avoids it and remains optimal on the changed map |
| Corridor reopens | The same obstacle is removed | The planner handles decreased costs and recovers a valid route |
| Goal disconnected and recovered | Access is fully closed and subsequently restored | Clear unreachable status, followed by valid recovery without a crash |
| Supported diagnosis | Confirmed observations are entered | Findings, rule IDs, and reasons correspond to those observations |
| Unknown evidence | One required observation is left unknown | No invented observation or unsupported definitive conclusion appears |
| Corrected observation | A previously supplied fact is changed | Earlier dependent conclusions disappear when no longer justified |
| Invalid evidence | A documented invalid value/combination is supplied | Clear invalid-input result rather than silent coercion |
| Combined demo | Diagnosis recommends pausing a robot | Simulated motion pauses and the explanation remains visible |

Export the actual scenario inputs, result summaries, and test output. Record the tested source commit SHA, scenario IDs, Python/dependency versions, environment, and whether there were uncommitted code changes. Do not type expected timings or successful results into reports before running the program.

Search metrics include route cost, processed/expanded states with a documented definition, queue operations, and algorithm time. Report initial planning separately from each repair and cumulative work. Exclude rendering, animation delays, and installation. Repeat timings, report a median, and include cases where incremental search gives no benefit. Memory measurements are optional and must be measured if reported. Do not promise that D* Lite is always faster than repeated A*.

Evidence package:

1. Live demo with input changes by the presenter.
2. Real screen recording of the named scenarios, kept outside source if large.
3. Exported replay results and benchmark CSV/JSON with source revision metadata.
4. Passing GitHub Actions for the integrated source revision.
5. Fresh clone on the teammate's laptop, followed by setup, tests, and both module demonstrations.
6. The tested release `v0.1.0`, selected after integration passes.

Documentation/evidence commits can follow a test run. Their metadata should reference the code revision actually tested; do not manufacture a self-referential commit SHA inside generated evidence.

## Proposed setup and commands

First inspect each member's existing Python and Git installations. Target one mutually available supported Python version, initially Python 3.12 or 3.13, and use the same tested version in CI. Reuse working installations. Use a project virtual environment and pin dependency versions after verifying compatibility.

Required dependencies are Streamlit for the interface and pytest for tests. The core diagnosis and search modules should otherwise use Python's standard library. GitHub CLI is optional for the teammate; Git or GitHub Desktop can perform their collaboration workflow.

Use these as reproduction commands from the repository root. Record their actual exit codes and outputs before reporting a result.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
.\.venv\Scripts\python.exe -m search_algorithm.main --scenario data/search_scenarios/corridor_changes.json
.\.venv\Scripts\python.exe tools/replay_demo.py --output artifacts/demo
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`requirements-dev.txt` should include `requirements.txt` plus pinned test dependencies. Directly invoking the virtual environment's Python avoids a PowerShell activation-policy change. UI access will be local, and the CLI commands provide a fallback if interface rendering is disrupted.

## Submission and demonstration schedule

Submission / live demonstration is Tuesday, October 13, 2026, Asia/Jakarta.
The implementation, integrated verification, running evidence, and tested
release are complete. Use [DEMO_GUIDE.md](DEMO_GUIDE.md) for the presentation
sequence and [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md) for each member's explanation.
Laptop setup, rule review, and rehearsal are presentation preparation; do not
record them as completed human actions unless the team has actually done them.

Push tested work to the shared repository during development. Before submission, save and verify a Git bundle of committed history outside the checkout. Preserve any uncommitted work separately. A fork is not required by this backup plan.

## Suitability and limits to explain

| Method | Suitable use | Limitation / unsuitable use |
|---|---|---|
| Rule-based diagnosis | A bounded set of observations and explainable domain rules | Novel faults and unsupported evidence need an explicit uncertain result; illustrative rules do not establish real-world accuracy |
| D* Lite | A route to a fixed goal with changing map information and a moving start | More bookkeeping than A*; small static maps may not benefit; this grid model does not solve time-dependent moving-obstacle avoidance |
| Repeated A* | Clear baseline for independently searching each current map | Recomputes its search for each changed snapshot in this comparison |

## Sources

- Supplied expert-system lecture slides, `P02-Expert System-WAC.pptx`, slides 4-8: knowledge base, rules, and inference engine. Original course files are outside this repository.
- Supplied search lecture slides, `P03-Search-WAC.pptx`: search baselines and heuristics.
- Supplied course LMS snapshot, pages 5-6: expert-system and search resource index.
- Supplied classroom photographs: team/repository/branch organization and README expectations.
- Koenig and Likhachev, [D* Lite, AAAI 2002](https://idm-lab.org/bib/abstracts/papers/aaai02b.pdf): primary algorithm reference.
- [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow): branch, commit, push, PR, review, and merge workflow.
- [GitHub merge methods](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/about-merge-methods-on-github): preserving feature commits with normal merge.
- [Streamlit local setup and run](https://docs.streamlit.io/get-started/installation/command-line) and [session state](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state): local UI and persistent session design.

These sources support the methods and workflow. The warehouse application, division of work, schedule, and acceptance criteria are this team's proposed design, not experimental results from those sources.
