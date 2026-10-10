# Expert system

The diagnostic module loads expert_system/knowledge_base.json, validates its schema, and applies deterministic forward chaining to categorical raw observations. The knowledge base contains 11 illustrative rules over nine observations and exposes six suspected conditions. It includes intermediate facts, ordered explanations, recommendations, and eight named input scenarios.

The teammate's original commit a57eebd8e93cb00a899ee792146707f96e750046 introduced R01 and R02 and remains credited to zaedalmusthofa through the normal merge of PR #5. The lead expanded the engine, knowledge base, CLI, fixtures, and integration under the lead's own Git identity. Current review and presentation tasks are tracked in [TEAMMATE_TASKS.md](../docs/TEAMMATE_TASKS.md).

## Run

From the repository root:

~~~powershell
.\.venv\Scripts\python.exe -m expert_system --list-scenarios
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe -m expert_system --facts facts.json
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
~~~

The CLI accepts one of --scenario ID, --facts PATH, --list-scenarios, or --all. Use --facts - to read a JSON object from standard input. --knowledge-base PATH selects another schema-validated JSON knowledge base, and --output PATH saves the emitted JSON as well as printing it. Scenario and facts exports include the raw observations and environment/knowledge-base metadata. The knowledge-base metadata includes the source file's SHA-256, schema version, and provenance.

--all checks the eight fixtures against their hand-written expected status and condition lists. It returns 0 when all expectations match, including the intentional invalid-input fixture. Running one invalid scenario or passing invalid facts returns 2 by design. See [the full guide](../docs/EXPERT_SYSTEM.md) for exit behavior, output shape, and examples.

## Evidence and limits

Missing keys and null mean unknown. Three observations are required; optional observations are grouped in pairs and only become incomplete when one member is supplied without the other. ok means the accepted evidence is complete within this schema, not that the robot is healthy. Each rule is labeled illustrative. The module is an educational simulation and must not be used to control a physical robot or to claim validated diagnostic accuracy.

[The completed-system evidence](../docs/evidence/completed-system-2026-10-11/README.md) records 167 passing tests, eight matching diagnostic fixtures, standard-library CLI execution, the combined demonstration, a clean-clone reproduction, real browser exports, and a silent recording at source `118e95b50c2aa3196980435075a21ed6be789603`. Issue #3 remains open for the teammate's independent review, laptop reproduction, and presentation rehearsal.
