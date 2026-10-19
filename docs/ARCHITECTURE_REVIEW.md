# Architecture Review: Four AI-TE-103 Modules

**Review date:** 2026-10-19

**Scope:** Python module boundaries, test and benchmark practice, safety and unknown-input handling, fuzzy-controller interpretability, multi-robot coordination, and evidence exports.

This is a source-informed review for a coursework simulator. It separates current repository facts from recommendations. It is not an adversarial review of the in-progress feature implementation, a physical-robot assessment, or a production-readiness finding.

## Baseline evidence and constraints

The baseline repository already separated the route planner, expert system, and Streamlit integration into importable packages. The module contracts keep the route planner and expert system independently usable; the UI adapts their results. The dependency files pin Streamlit and pytest. The project runs from a flat repository layout with **pythonpath = .** in **pytest.ini**.

The baseline app had **Route planner**, **Diagnostics**, and **Evidence & methods** tabs. Its integration tests select controls mainly by stable widget keys and assert session/planner persistence, one planner initialization, and no state mutation on invalid or gated movement. They do not select a tab by index. The extension preserves those controls and appends **Fleet coordination** and **Fuzzy speed control**. Streamlit renders each tab's body on reruns, so tab rendering must not create or advance simulations; persistent state belongs in distinct session-state entries and changes only after explicit actions.

The present diagnostic gate fails closed: movement is allowed only when the adapter is ready, the result status is **ok**, recommendations have the validated shape, and none requests **pause_robot**. The gate pauses movement while leaving planning and map edits available. The session API also rejects a disallowed move before consuming its event ID. These are useful contracts to preserve.

The existing evidence export records actual planner session data, diagnostic input and output, gate state, and environment metadata including source commit and dirty state. New exports should follow that evidence-first pattern.

## Recommendations by module

| Area | Practical choice for this coursework app | Advanced option if scope grows |
|---|---|---|
| Python packaging and module boundaries | Keep the domain modules as separate importable packages and keep Streamlit in the app/interface layer. Give each module a small public API with JSON-compatible inputs and outputs. Keep dependencies pointing from the interface toward domain modules; domain modules should not import Streamlit. The Python tutorial documents package and subpackage imports and warns that **__init__.py** can run code at import time, so keep package initialization light. | If distributing installable artifacts, add **pyproject.toml** metadata, declare runtime and optional feature dependencies, and test built artifacts from a clean environment. PyPA explains that a **src** layout catches some accidental imports from the checkout, but it also requires installation to run the package. That extra step is not needed solely to add two modules to this local app. |
| Search and reproducible tests | Keep correctness separate from speed claims. Continue validating route legality and optimal cost against an independent oracle; tied optimal paths need not have identical geometry. Parameterize boundary and invalid-input cases. Add module tests for exact deterministic outputs and app integration tests for rerun persistence, gate behavior, unique widget keys, and unchanged legacy controls. Use seeded or fixed scenarios for fleet behavior. | For broader performance claims, benchmark the same maps and event sequences, separate initial planning from repairs and whole-session totals, repeat runs, retain raw samples, and record the source revision and environment. Alternate or randomize algorithm order to reduce order effects. Report the chosen summary statistic and avoid comparing internal operation counters as if they had the same meaning. |
| Expert-system facts and safety boundary | Keep observed, unknown, incomplete, and invalid input states distinct. **None** or missing means unknown; it must not silently become a normal reading, zero, or permission to move. Preserve the existing rule that incomplete, malformed, pending, or fault-paused diagnosis blocks simulated movement when the gate is enabled. | If inputs ever come from telemetry, add explicit source and freshness metadata and define stale-data behavior before using it to permit motion. A software gate is one policy layer; it does not replace a physical safety system or prove that motion is safe. |
| Mamdani fuzzy controller | Show the input ranges, membership functions, linguistic rules, rule firing strengths, aggregate output, defuzzification method, and resulting recommendation. Label membership values as degrees and the output as a simulated recommendation; do not label them probability, calibrated confidence, or physical speed. Test input bounds, overlaps, coverage of the declared universe, deterministic output, and non-finite rejection. | Calibrate parameters only with a documented domain basis, such as reviewed operating limits or a held-out measurement set. Preserve the original settings and report sensitivity to reasonable parameter changes. The scikit-fuzzy examples are useful references for standard Mamdani control construction and visualization, but adding that package is optional; a small standard-library core is adequate while it meets the project’s needs. |
| Multi-robot coordination | State the simulation model explicitly: map, robot IDs, positions, goals, update order, conflict rule, wait behavior, and what counts as a completed run. Keep stepping deterministic. Test the implemented conflict model at shared cells, opposing edge traversals, shared goals, no-path states, and repeated waits; report any deadlock or starvation that the model permits. | A fleet manager with a shared traffic schedule and negotiation is a substantially broader system. Open-RMF’s negotiation API explicitly models participants and proposals and notes that a non-optimal mode is the default. Use it as a future comparison point, not as evidence that a small two-robot simulation has equivalent conflict resolution. |

These module recommendations are proposals, not claims that every system must use the same structure or algorithm. In particular, the requested fuzzy controller and fleet simulation should remain teaching demonstrations unless separate domain validation supports stronger claims.

## Implemented choices and advanced alternatives

The review led to a four-method extension. The choices below distinguish source
capabilities from this repository's actual implementation:

The [recorded running evidence](evidence/four-method-2026-10-19/README.md)
contains actual replays, CI results, raw measurements, browser exports, and
screenshots. It documents the checked source revision and simulation limits.

| Method | Implemented choice | More advanced option | Evidence needed before adopting it |
|---|---|---|---|
| Expert system | External illustrative rules, forward chaining, fresh inference, and grounded explanations | Bayesian-network diagnosis with explicit uncertainty | A justified graph and prior/conditional distributions. A Bayesian network needs these distributions; this project has no basis for inventing diagnostic probabilities. |
| Search | Persistent D* Lite per robot, with A* and the independent cost oracle retained | Anytime Dynamic A* (AD*) | A defined planning-time budget and acceptable suboptimality policy. AD* can improve a solution while time remains and repair it after changes; the small unit-cost demonstration does not yet require that tradeoff. |
| Multi-agent coordination | Independent robot decisions plus conservative one-tick traffic reservations | CBS/ECBS or rolling-window cooperative search | A precise joint objective, reservation horizon, movement-time model, computational budget, and no-solution handling. Fractional fuzzy cadence must be represented before a timed plan can authorize moves. |
| Fuzzy logic | Mamdani plus an implemented zero-order Sugeno comparison, with exposed calculation traces | ANFIS or interval type-2 inference | Representative training/validation data for adaptation, or a justified model of membership uncertainty. Neither is supplied by the current synthetic cases. |

The Sugeno comparison is an added feature, not a claim that it is always more
accurate. The response-surface/timing tool alternates evaluation order and retains
raw measurements. It times full public calls, including explanation construction;
Mamdani builds an aggregate curve whereas Sugeno has no corresponding fuzzy output
set. This difference is part of the measured API cost and must accompany timing claims.

Primary references for this selection:

- [Poole and Mackworth, Belief Networks](https://artint.info/3e/html/ArtInt3e.Ch9.S3.html): a Bayesian network includes conditional distributions and root priors.
- [Likhachev et al., Anytime Dynamic A*](https://www.cs.cmu.edu/~ggordon/likhachev-etal.anytime-dstar.pdf): combines anytime improvement with replanning after changed information.
- [Sharon et al., Conflict-Based Search](https://doi.org/10.1016/j.artint.2014.11.006): joint non-conflicting paths through constrained individual searches. This repository does not implement CBS.
- [MathWorks, Mamdani and Sugeno](https://www.mathworks.com/help/fuzzy/types-of-fuzzy-inference-systems.html): fuzzy-output aggregation/defuzzification versus singleton weighted outputs.
- [MathWorks, ANFIS](https://www.mathworks.com/help/fuzzy/neuro-adaptive-learning-and-anfis.html): adaptive tuning from training data. See the fuzzy guide for the original papers and additional alternatives.

## Safety priority and unknown data

For this app, use the existing diagnostic gate as the permission check for every simulated robot movement. If it blocks movement, a fuzzy speed output or fleet priority must not re-enable movement. If the controller returns no usable result, treat that as unavailable input and keep movement blocked when the gate is active. Map edits and route inspection can remain available because they do not move a robot in the simulation.

Nav2 illustrates a more complete physical-robot architecture: its Collision Monitor operates below the navigation planner, processes sensor input, and is placed last in the velocity-output chain. Its documentation also explicitly says that the CPU-level node does not provide hard real-time safety certification. That distinction is useful here: a simulation gate, cell reservation, or fuzzy slowdown is not a certified safety mechanism. The project should say exactly which simulated invariant it checks and name unmodelled hazards.

For multi-robot results, a “no conflict observed” statement should name the model, scenario set, and checks performed. It should not be generalized to arbitrary schedules or physical robots. If one diagnosis is shared across the fleet, state that the gate blocks all fleet movement; if diagnosis becomes per-robot, export and enforce a gate result per robot.

## Evidence and export policy

Keep exports factual and reproducible:

- Record the actual inputs, scenario or seed, each applied event or simulation tick, current parameters and rule table, actual outputs, and whether the gate was enabled.
- Include source revision, dirty-worktree status, runtime, dependency versions, and UTC timestamp where available. Hash versioned rule/configuration content if the export needs to identify it precisely.
- Preserve unknown values as null or an explicit unknown state. Do not infer an unobserved clearance, battery value, diagnosis, collision-free guarantee, or speed.
- Label all generated scenarios and uncalibrated controller settings as illustrative. Use “recommended speed” or “simulated output,” never “motor command,” unless the project actually sends commands to hardware.
- Keep scenario expectations distinct from computed results. A mismatch should remain visible in the export rather than being rewritten as a pass.

The existing app evidence payload and **interface/evidence.py** provide a local pattern for provenance; **docs/MODULE_CONTRACTS.md** and **docs/UI_DESIGN.md** already describe the diagnostic and route-planning limits.

## Sources opened on 2026-10-19

- Python package structure and import behavior: [Python Tutorial, Modules and Packages](https://docs.python.org/3.13/tutorial/modules.html).
- Flat versus **src** layout tradeoffs: [Python Packaging User Guide, src layout vs. flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/?highlight=src).
- Project metadata, dependency groups, and command entry points: [Python Packaging User Guide, Writing your pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/?highlight=2023).
- Data-driven tests: [pytest, How to parametrize fixtures and test functions](https://pytest.org/en/latest/how-to/parametrize.html).
- Timing noise and repeated measurements: [Python 3.12 Library Reference, timeit](https://docs.python.org/3.12/library/timeit.html).
- Algorithm rationale: Koenig and Likhachev, [D* Lite, Carnegie Mellon University publication record](https://publications.ri.cmu.edu/d-lite). The paper supports incremental replanning and reports experiments for its studied applications; it does not establish a universal speed ranking for this repository’s scenarios.
- Fuzzy model construction and visualization: [scikit-fuzzy, Mamdani Control System Advanced Example](https://scikit-fuzzy.github.io/scikit-fuzzy/auto_examples/plot_control_system_advanced.html) and [Tipping Problem Example](https://scikit-fuzzy.github.io/scikit-fuzzy/auto_examples/plot_tipping_problem_newapi.html). These demonstrate membership functions, rules, simulation, and control-surface visualization; they do not validate this project’s ranges.
- Safety layering and certification boundary: [Nav2 Collision Monitor Node](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/collision_monitor/configuring_collision_monitor_node/) and [Using Collision Monitor](https://docs.nav2.org/rolling/tutorials/general_tutorials/using_collision_monitor/using_collision_monitor/).
- Fleet schedule negotiation: [Open-RMF rmf_traffic CentralizedNegotiation API](https://openrmf.readthedocs.io/projects/rmf-traffic/en/latest/api/classrmf__traffic_1_1agv_1_1CentralizedNegotiation.html).
