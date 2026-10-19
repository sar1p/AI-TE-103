# AI-TE-103 Teammate Review and Handoff

Group 1: Muhammad Syarif Hidayat Hadari (`sar1p`) works on
`dev1/muhammad-syarif-hidayat-hadari`; Zaedal Musthofa (`zaedalmusthofa`) works
on `dev2/zaedal-musthofa`. Both submit pull requests to protected `main`.

## October 19 extension: independent review still available

The current extension adds multi-agent coordination and fuzzy control to the
expert system and search demonstration. See the [four-method running
evidence](evidence/four-method-2026-10-19/README.md) and
[architecture review](ARCHITECTURE_REVIEW.md). The original contribution record
below remains unchanged. The original October 13 presentation date is historical;
no replacement submission date has been confirmed for this extension.

The teammate can make a substantive, attributable contribution by completing
these checks on their own laptop and recording what actually happens:

1. Set up the PR's head revision, or `main` after merge. Record `git rev-parse
   HEAD`, operating system, Python version, and the commands used. Do not reuse
   the lead's screenshots as evidence of a separate run.
2. Run both integrated replays below. Inspect the reservation denial, each
   robot's single retained planner, the positive fuzzy proposal overridden by
   diagnosis, and movement after corrected observations. Record failures as
   failures rather than editing the expected output.
3. In **Fleet coordination**, reset, apply the battery fault preset to R01, and
   advance enough ticks to observe R01 staying still while R02 can move. Apply
   corrected observations and show R01 moving again. Save the session evidence
   and an actual screenshot or short recording.
4. In **Fuzzy speed control**, use clearance `3` and battery `85`. Explain the
   active rules and why Mamdani gives about `58.31%` while Sugeno gives `63.75%`.
   Change an input and explain the changed activations. Neither result is a
   probability or a calibrated motor speed.
5. Explain why next-cell reservations can leave robots waiting in a narrow
   head-on corridor, and why CBS/ECBS or rolling-window search is a separate
   extension. Use the linked research without claiming those algorithms are
   implemented here.
6. Commit a short English review/rehearsal report under `docs/reviews/` on
   `dev2/zaedal-musthofa` using the teammate's own GitHub identity, then open a PR.
   Include the tested revision, actual observations, evidence references,
   limitations, and any concrete correction. Report writing and fixes count
   as real work; no placeholder commits are needed.

```powershell
.\.venv\Scripts\python.exe tools/fleet_demo.py --method mamdani --output artifacts/teammate-fleet-mamdani.json
.\.venv\Scripts\python.exe tools/fleet_demo.py --method sugeno --output artifacts/teammate-fleet-sugeno.json
.\.venv\Scripts\python.exe -m pytest -q
```

The lead can present search/replanning and traffic decisions; the teammate can
present diagnostic inference, fuzzy calculations, and their independent review.
Both members should be able to explain the full four-method flow.

## Historical October 11 implementation and handoff

Status updated Sunday, October 11, 2026. The lead has completed and integrated the external schema-validated knowledge base, deterministic fixed-point inference, standalone JSON CLI, and eight named diagnostic fixtures. [The completed-system evidence](evidence/completed-system-2026-10-11/README.md) records a clean remote clone, nine successful checks, 167 passing tests, actual UI pause/correction exports, the combined demonstration, and a silent browser recording. Issue #3 is closed for completed software implementation and verification. Submission / live demonstration is Tuesday, October 13, 2026, Asia/Jakarta. The guidance below supports presentation preparation.

## Contribution record

The teammate's original commit [a57eebd8e93cb00a899ee792146707f96e750046](https://github.com/sar1p/AI-TE-103/commit/a57eebd8e93cb00a899ee792146707f96e750046), by zaedalmusthofa, introduced the initial R01 motor-temperature/stall rule and R02 lidar rule. The normal merge through [PR #5](https://github.com/sar1p/AI-TE-103/pull/5) preserved the original commit and its contributor credit.

The lead later expanded the knowledge base and inference engine, corrected and integrated the module, and added the CLI and named fixtures under the lead's own Git identity. This current expansion does not change attribution for the teammate's starter. The teammate's next role is to review the current behavior and rehearse the diagnostic explanation. Any future code or documentation contribution from the teammate should be committed using that contributor's own configured identity so the history reflects the actual work.

## Current implementation

| Area | Current source scope |
|---|---|
| Knowledge base | Schema version 1, 11 illustrative rules, nine categorical string observations |
| Evidence policy | Three required observations plus three optional two-observation groups |
| Exposed conditions | Six illustrative findings; internal derived facts support multi-step chains |
| Inference | Deterministic rule-order sweeps to a fixed point; each rule ID fires at most once per call |
| Result | Status, findings, ordered trace, recommendations, and missing observations |
| Reproduction | Eight named JSON scenarios and an independent CLI |
| Integration sequence | Headless combined demonstration with pause, map repair, corrected evidence, and retained planner checks |

All rules are illustrative classroom simulation rules. No physical fault accuracy, causal validity, reliability, or safety claim is established. Exact inputs, outputs, status behavior, fixture IDs, CLI options, and limitations are in [EXPERT_SYSTEM.md](EXPERT_SYSTEM.md) and the frozen [MODULE_CONTRACTS.md](MODULE_CONTRACTS.md).

## Review and rehearsal tasks

1. Review each rule's premises, intermediate facts, exposed condition, reason, and recommendation against the JSON knowledge base. Check that documentation calls all rules illustrative.
2. Review missing and null evidence, partial optional groups, invalid values, simultaneous findings, and corrected observations. Confirm that a later diagnosis is recomputed from raw facts.
3. Run the CLI's aggregate fixture command and inspect its exported raw facts, expected outcomes, metadata, and knowledge-base source hash. The aggregate includes the intentional invalid-input fixture.
4. Run the combined demonstration and inspect its recorded sequence: movement pauses for a chained battery finding, a map edit is accepted during the pause, a move is rejected without mutating the session, corrected observations allow a step, and the planner remains initialized once.
5. Reproduce from a fresh clone, record the actual source revision and environment, then rehearse the explanation and limitations for the presentation.
6. If review finds a real issue or new implementation work is needed, make that change in an attributable commit and describe the behavior and checks actually performed.

## Commands

Run from the repository root after setting up the project environment:

~~~powershell
.\.venv\Scripts\python.exe -m expert_system --list-scenarios
.\.venv\Scripts\python.exe -m expert_system --scenario battery-multi-hop
.\.venv\Scripts\python.exe -m expert_system --all
.\.venv\Scripts\python.exe -m pytest tests/expert_system tests/integration -q
.\.venv\Scripts\python.exe tools/combined_demo.py --output artifacts/combined-demo.json
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
~~~

For --all, exit code 0 means every fixture matches its hand-written expected status and condition list, including the intentional invalid-input case. A single invalid scenario or invalid facts input returns exit code 2 by design. Do not treat that individual code as the aggregate fixture convention.

## Delivery status

The software checks are recorded at source `118e95b50c2aa3196980435075a21ed6be789603`, merged through [PR #7](https://github.com/sar1p/AI-TE-103/pull/7). The contributor snapshot confirms zaedalmusthofa and retains the original starter commit. Issue #3 is closed because implementation and recorded software verification are complete. Use the review and rehearsal guidance to prepare for Tuesday's presentation. The verified clone and silent recording do not establish that either member's separate rehearsal has occurred.
