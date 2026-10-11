# GitHub workflow for this two-member project

Repository: [sar1p/AI-TE-303](https://github.com/sar1p/AI-TE-303).
Both members have their own identities and can work on feature branches in the
shared repository. A separate fork is optional; it does not replace a backup.

## What each action does

| Action | Purpose | Example |
|---|---|---|
| Clone | Download a working copy and its Git history | Clone this repository once on your laptop |
| Fetch | Download remote history without changing your files | Inspect new teammate commits |
| Pull | Fetch and update the current branch | Update local `main` after a merge |
| Branch | Keep a feature or review separate while it is being developed | `review/diagnostic-explanation` |
| Fork | Create a personal GitHub copy of another repository | Optional here because both members can use this shared repository |
| Stage | Select the exact changes for a commit | Stage the rule loader and its tests |
| Commit | Record a complete local change | Add a validated rule loader |
| Push | Upload one or more commits to GitHub | Share the tested feature branch |
| Pull request | Present branch changes for review and CI | Explain new rules and actual test results |
| Merge commit | Join approved feature history into `main` | Retain the teammate's original commits |

One commit should describe a coherent change that can be reviewed and explained.
Include the behavior tests with that implementation. Several commits may be
pushed together or reviewed in one PR. Do not split changes merely to increase
the contribution count.

## First setup on a new laptop

Install Git and Python 3.12, sign in to your own GitHub account, and accept the
repository's collaborator invitation. GitHub Desktop is an alternative to the
Git commands below. GitHub CLI is optional.

Clone into a new folder, then run from that folder:

```powershell
git clone https://github.com/sar1p/AI-TE-303.git
cd AI-TE-303
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -c constraints.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Wait for dependency installation to finish before testing. Run the application
with `run_demo.bat` or follow [DEMO_GUIDE.md](DEMO_GUIDE.md).

Before committing, inspect your repository's author configuration:

```powershell
git config --get user.name
git config --get user.email
```

Use your own name and an email verified on your own GitHub account, or the
account's GitHub-provided noreply address. Git authorship and GitHub sign-in are
separate. Signing in as yourself does not repair an incorrectly authored commit.
Do not use the other member's identity for work you performed.

## Start and finish one feature

Check for existing changes before switching branches:

```powershell
git status
git switch main
git pull --ff-only origin main
git switch -c review/diagnostic-explanation
```

`--ff-only` refuses to create an unexpected local merge. If it fails or you have
uncommitted work, inspect the difference and preserve the work before proceeding.
Do not use a hard reset or force push as a routine update method.

The external loader and forward-chaining engine are already implemented.
Review them, reproduce a case, and make a real correction or clarification if
needed. The following example records a verified explanation change; stage only
the paths that actually belong to your work:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/expert_system -q
git diff
git add docs/EXPERT_SYSTEM.md
git diff --cached
git commit -m "docs: clarify diagnostic observation examples"
git push -u origin review/diagnostic-explanation
```

Open a PR targeting `main`, explain the final behavior and actual validation,
and request the other member's review. A draft PR can be used for unfinished
work. Continue fixing and testing on the same branch. Later pushes use
`git push` once the upstream is configured.

The lead merges with a normal merge commit after required checks pass. This
repository protects `main` and uses merge commits to retain actual authorship.
Both members then update local `main` with `git pull --ff-only origin main`.
Use `git switch branch-name` to revisit an existing branch; `-c` creates a new one.

## Current handoff and contribution credit

[PR #5](https://github.com/sar1p/AI-TE-303/pull/5) merged the original
`zaedalmusthofa` starter commit together with integration fixes. The original
commit remains in `main`, and the GitHub contributor API confirmed both
`sar1p` and `zaedalmusthofa` after the merge. Corrections made by the lead keep
the lead's own identity. A profile page may refresh later than the API.

The lead completed the external rules, forward chaining, CLI, tests, interface,
and integration. That later work uses the lead's identity. The teammate's
original contribution remains credited without needing an artificial commit.
Further contributions should describe actual review findings, fixes, or
documentation work. Read [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md) and
[the closed issue #3](https://github.com/sar1p/AI-TE-303/issues/3) for the completed
software record. Review and rehearsal prepare the team for Tuesday, October 13,
2026. Begin any further change from current `main` on a new branch.

## Recovery

Git history preserves tracked commits; it does not preserve ignored files,
virtual environments, uncommitted work, or GitHub settings. Keep credentials
outside the repository. The lead maintains a verified offline Git bundle.

If a merged change causes a regression, create a repair or revert branch, test
it, and submit another PR. For a merge commit, `git revert -m 1 MERGE_SHA` is a
reviewable way to undo its effect; first identify the exact merge and inspect
the proposed change. Do not rewrite protected `main` history.
