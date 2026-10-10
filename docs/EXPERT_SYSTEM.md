# Warehouse robot diagnostic expert system

Implementation scope updated Sunday, October 11, 2026. The repository contains an external JSON knowledge base, schema validation, deterministic forward chaining, a standalone JSON CLI, and eight named diagnostic fixtures. Full acceptance remains open while end-to-end UI and combined-demo evidence, a fresh-clone reproduction, and the teammate's review and presentation rehearsal are still to be recorded. See [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md).

The teammate's original commit [a57eebd8e93cb00a899ee792146707f96e750046](https://github.com/sar1p/AI-TE-303/commit/a57eebd8e93cb00a899ee792146707f96e750046) introduced the initial R01 and R02 rules. The normal merge through [PR #5](https://github.com/sar1p/AI-TE-303/pull/5) preserved that contribution and its zaedalmusthofa author credit. The lead expanded the knowledge base, engine, CLI, fixtures, and integration using the lead's own Git identity. The teammate's current work is independent review and presentation rehearsal; any later implementation work should appear in that contributor's own commits.

## Input observations

The knowledge base declares nine categorical string observations. The first three are required for a complete diagnosis. The remaining observations are optional in three paired groups.

| Observation | Allowed values | Requirement |
|---|---|---|
| motor_temperature | normal, high | Required |
| movement_status | moving, idle, stalled | Required |
| sensor_lidar | clear, blocked | Required |
| battery_voltage | normal, low | Optional group power |
| battery_connection | connected, disconnected | Optional group power |
| drive_status | normal, fault | Optional group drive_feedback |
| encoder_feedback | present, absent | Optional group drive_feedback |
| motor_connection | connected, disconnected | Optional group motor_path |
| motor_enable | enabled, disabled | Optional group motor_path |

An omitted key or null means unknown. It never means a known negative. An optional group stays inactive if neither member has a known value; once one member is supplied, the other member is reported missing until it is supplied. A finding supported by known facts can still appear when the overall status is insufficient_evidence.

Only the listed raw names, string types, and values are accepted. Unknown names, numbers, booleans, arrays, objects, unsupported strings, and non-finite values are invalid. The JSON readers also reject duplicate object keys. Invalid facts return invalid_input with empty findings, trace, recommendations, and missing-fact lists.

ok means the required and activated optional-group evidence is complete and accepted by this schema. It does not mean the robot is healthy or that every fault has been ruled out. A complete input with no matching rule returns ok with no findings.

## Knowledge base and inference

expert_system/knowledge_base.json uses schema version 1. Its provenance labels the rules as classroom simulation examples; no rule is validated against a manufacturer manual, domain expert, or measured robot fault. The file contains 11 rules, of which six expose suspected conditions:

| Rule(s) | Inference | Exposed condition |
|---|---|---|
| R01 | High temperature and stalled movement | suspected_motor_overheating |
| R02 | Blocked lidar | lidar_obstruction |
| R03, R04, R05 | Low battery and disconnected battery connection derive an internal power-path fact, then a power-path issue | battery_power_path_issue |
| R06 | A derived power-path issue with stalled movement | battery_related_stall |
| R07, R08, R09 | Drive fault and absent encoder feedback derive a combined finding | drive_encoder_fault |
| R10, R11 | Disconnected motor connection with motor enabled | motor_connection_fault |

R03, R04, R07, R08, and R10 derive intermediate facts used by later rules; they do not expose findings on their own. Rules are read in knowledge-base order and swept until no new fact is derived. Each rule ID fires at most once per diagnosis, so cycles terminate. The trace records each firing in order. An exposed finding's rule_ids includes the rules supporting its derivation. Recommendations are deduplicated by action and reason.

Every rule and its explanation is marked illustrative. The categories and chains demonstrate knowledge-base representation and explainable inference; they do not establish causal relationships. For example, the battery_related_stall label is a simulated rule conclusion, not evidence that low voltage caused a real stall. The system does not calculate probabilities, confidence, accuracy, or physical reliability.

The engine starts a fresh inference session from the supplied raw facts on every call and does not mutate the input. Correcting an observation and calling the engine again removes conclusions that no longer follow from those facts. A later call must not use earlier derived conditions as raw evidence.

## Diagnosis result contract

expert_system.engine.diagnose(facts) returns exactly these JSON-compatible top-level fields:

| Field | Meaning |
|---|---|
| status | ok, insufficient_evidence, or invalid_input |
| findings | Ordered records of condition and supporting rule_ids |
| rule_trace | Ordered records of rule_id, declared premises, conclusion, and English reason |
| recommendations | Records containing an action ID and English reason |
| missing_facts | Required observations or activated optional-group members that are unknown |

The exact contract, knowledge-base schema, and integration behavior are frozen in [MODULE_CONTRACTS.md](MODULE_CONTRACTS.md). A knowledge-base loading or validation error raises KnowledgeBaseError, which is a configuration failure rather than an observation-level invalid_input.

## Standalone CLI

Run commands from the repository root with the project environment:

~~~powershell
.\.venv\Scripts\python.exe -m expert_system --list-scenarios
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe -m expert_system --facts facts.json
Get-Content -Raw facts.json | .\.venv\Scripts\python.exe -m expert_system --facts -
.\.venv\Scripts\python.exe -m expert_system --facts facts.json --knowledge-base custom-kb.json --output artifacts/diagnosis.json
~~~

The mutually exclusive input options are --scenario ID, --facts PATH (use - for standard input), --list-scenarios, and --all. --knowledge-base PATH selects another schema-validated knowledge base. --output PATH and --output-file PATH save the same JSON document that is printed to standard output. The CLI does not launch the visual app.

Exports include environment metadata and knowledge-base metadata: source path, SHA-256 of the source file bytes, schema version, and provenance. Scenario exports also include the raw facts, expected status and conditions, and expectation_match. Fact exports preserve the raw input facts and identify their source. --all exports every fixture and an aggregate scenario_validation record with failed IDs. The combined demonstration records a separate canonical-JSON hash; it is not the raw-file SHA-256 reported by the CLI.

There are eight fixtures: battery-multi-hop, corrected-observations, drive-encoder-multi-hop, empty-input, invalid-observation, motor-connection-multi-hop, partial-power, and simultaneous-faults. --all returns exit code 0 when every fixture matches its hand-written expected status and condition list. The intentional invalid-observation fixture is part of that expected set, so its expected invalid_input result does not fail the aggregate run. A single invalid case or invalid raw-facts input returns exit code 2; a single scenario also returns 2 if its actual result does not match its expectation. Malformed JSON, a missing scenario, or an invalid knowledge base reports an error on standard error and returns 2.

## Visual and combined demonstration

Start the application with:

~~~powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
~~~

In Diagnostics, use the named cases or provide raw observations from the declared schema. The UI's pause_robot recommendation gates the simulated Move action. Search planning remains a separate module.

The headless integration sequence is in tools/combined_demo.py:

~~~powershell
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
~~~

The script defines a chained battery diagnosis that pauses movement. It permits a map edit while paused, checks that a movement attempt is rejected without changing simulation state, corrects the raw observations, and then allows one step using the same planner instance with an initialization count of one. It also checks the scripted route costs 10 → 12 → 11 against A*. The JSON export contains the raw observation sequence, diagnosis traces, environment metadata, knowledge-base counts and canonical JSON SHA-256, rejected-move details, search-session records, and named checks. These are checks the script performs when run; this document does not claim a successful run or a completed presentation rehearsal.

## Suitable use and limits

This engine is suitable for demonstrating a small, bounded rule base, deterministic multi-step inference, traceable explanations, unknown versus known categorical observations, compatible simultaneous findings, and recalculation after correction.

It is unsuitable for physical robot control, safety certification, field diagnosis, numeric temperature interpretation, unlisted fault classes, or claims of measured diagnostic accuracy or reliability. Missing rules and inaccurate observations can leave a real fault undetected. All six exposed conditions remain illustrative software findings.

## Verification and evidence

The repository includes behavior, schema, CLI, and integration tests. To collect current results, run the relevant commands and preserve their actual output:

~~~powershell
.\.venv\Scripts\python.exe -m pytest tests/expert_system tests/integration -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
~~~

A complete acceptance record still needs the actual tested source revision, environment details, CLI and combined-demo output, a fresh-clone reproduction, and teammate review and presentation rehearsal. Do not infer these results from the presence of code or fixtures. The earlier search-only screenshots do not demonstrate expert-system execution. Issue #3 remains open until the agreed deliverables and rehearsal have been checked.
