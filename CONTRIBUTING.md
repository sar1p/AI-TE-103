# Contributing

Use English for source code, comments, interface text, documentation, branch
names, commits, pull requests, and workflow names.

## Current collaboration

The teammate's original commit a57eebd8e93cb00a899ee792146707f96e750046 by
zaedalmusthofa introduced the initial R01 and R02 rules. Its original commit
and contributor attribution were preserved by the normal merge through PR #5.
The lead expanded and integrated the current engine, knowledge base, CLI, and
fixtures using the lead's own Git identity. The teammate's current work is review
and presentation rehearsal. Future work from either contributor should be
recorded with that contributor's configured Git identity.

Coordinate overlapping edits through review. Current diagnostic behavior and
presentation preparation are described in
[TEAMMATE_TASKS.md](docs/TEAMMATE_TASKS.md). For branch setup, see
[GITHUB_GUIDE.md](docs/GITHUB_GUIDE.md). [Issue #3](https://github.com/sar1p/AI-TE-303/issues/3)
is closed for completed software implementation and verification. Review,
laptop setup, and rehearsal are preparation for the Tuesday, October 13 presentation.
The [completed-system snapshot](docs/evidence/completed-system-2026-10-11/README.md)
already records the lead's clean-clone checks, CLI/UI runs, and screen recording.

## Daily workflow

1. Update local main with git switch main and git pull --ff-only.
2. Create a branch for one coherent change.
3. Make the change and run the checks that apply to it.
4. Stage only intended files and inspect git diff --staged.
5. Commit a complete change with a descriptive message.
6. Push the branch and open a reviewable pull request.
7. Address review comments on that branch.
8. Merge after required checks pass, preserving contributor history through a
   merge commit. Update main before starting the next change.

A commit records a local version. A push uploads commits. A branch isolates
work. A pull request makes a change reviewable. Avoid invented authors, force
pushes, and rewriting shared history.

## Validation and evidence

Use the project virtual environment and the pinned dependency files. Run the
relevant behavior tests and report the exact commands and results. The
diagnostic aggregate command is:

~~~powershell
.\.venv\Scripts\python.exe -m expert_system --all
~~~

It exits 0 when all eight hand-written fixture expectations match, including
the intentional invalid-input fixture. A single invalid fixture or invalid raw
facts input returns exit code 2 by design.

For the current acceptance record, also run the expert-system and integration
tests, the standalone combined demonstration, and a fresh-clone reproduction.
Record the actual tested source revision and environment. Keep credentials,
virtual environments, temporary exports, lecture documents, and personal files
out of Git. Do not claim diagnosis accuracy or successful reproduction from
screenshots, expected results, or the presence of implementation code alone.
