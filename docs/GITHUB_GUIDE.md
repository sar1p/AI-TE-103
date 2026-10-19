# GitHub workflow for this two-member project

Repository: [sar1p/AI-TE-103](https://github.com/sar1p/AI-TE-103).
Both members have their own identities and work on member branches in the
shared repository. A separate fork is optional; it does not replace a backup.

## Group 1 branches

| Member | Account | Persistent working branch |
|---|---|---|
| Muhammad Syarif Hidayat Hadari | `sar1p` | `dev1/muhammad-syarif-hidayat-hadari` |
| Zaedal Musthofa | `zaedalmusthofa` | `dev2/zaedal-musthofa` |

`main` is the protected integration branch. Git branch names cannot contain
spaces, so member names use lowercase words separated by hyphens. The branch
label does not change authorship or give one member credit for the other's work.

After a fresh clone, fetch both branches and create only your own local tracking
branch. Dev 1 runs:

```powershell
git fetch origin
git switch --track origin/dev1/muhammad-syarif-hidayat-hadari
```

Dev 2 runs:

```powershell
git fetch origin
git switch --track origin/dev2/zaedal-musthofa
```

Use `git switch` without `--track origin/` after the local branch already exists.
For an older clone, update its remote before fetching:

```powershell
git remote set-url origin https://github.com/sar1p/AI-TE-103.git
git fetch origin --prune
```

## What each action does

| Action | Purpose | Example |
|---|---|---|
| Clone | Download a working copy and its Git history | Clone this repository once on your laptop |
| Fetch | Download remote history without changing your files | Inspect new teammate commits |
| Pull | Fetch and update the current branch | Update local `main` after a merge |
| Branch | Keep each member's work separate while it is being developed | `dev1/muhammad-syarif-hidayat-hadari` or `dev2/zaedal-musthofa` |
| Fork | Create a personal GitHub copy of another repository | Optional here because both members can use this shared repository |
| Stage | Select the exact changes for a commit | Stage the rule loader and its tests |
| Commit | Record a complete local change | Add a validated rule loader |
| Push | Upload one or more commits to GitHub | Share your tested member branch |
| Pull request | Present branch changes for review and CI | Explain new rules and actual test results |
| Merge commit | Join approved feature history into `main` | Retain the teammate's original commits |

One commit should describe a coherent change that can be reviewed and explained.
Include the behavior tests with that implementation. Several commits may be
pushed together or reviewed in one PR. Do not split changes merely to increase
the contribution count.

## First setup on a new laptop

Follow the [README development setup](../README.md#development-setup) for the
Windows, Linux, and macOS download and automatic launch steps. Anyone can try the public app
without a GitHub sign-in. The installer creates a Git clone when Git is already
installed and falls back to a ZIP when it is not; it does not install Git. You
can also download the ZIP from GitHub, extract it, and double-click `run.bat`.
Neither Git nor Python needs to be installed to run an extracted ZIP. First
setup needs an internet connection. The Windows launcher requires 64-bit
Windows 10 or 11.

Linux and macOS users can paste the Terminal block in the README, or run
`bash run.sh` from an extracted project. The environment and dependencies are
prepared automatically. The macOS clone also includes `run.command` as a
Terminal entry point. See [UNIX_LAUNCHER.md](UNIX_LAUNCHER.md) for supported
platforms and the difference between Finder and Terminal launch.

To make commits, use a real Git clone so your work has repository history. If
Git is not installed, install it separately and clone the repository before
contributing; the automatic ZIP fallback is for running the app. To push to the
shared repository, sign in to your own GitHub account and accept the invitation.
GitHub Desktop is an alternative to Git commands; GitHub CLI is optional.

For later sessions, double-click `run.bat` in the project folder or follow
[DEMO_GUIDE.md](DEMO_GUIDE.md). Keep the terminal open while the app runs and
press Ctrl+C to stop it. If an older project folder reports that `run.bat` is
missing, follow the update instruction shown by the installer before continuing.

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
git switch dev1/muhammad-syarif-hidayat-hadari
git merge --ff-only origin/main
```

The example uses Dev 1. Zaedal uses `dev2/zaedal-musthofa` instead. A member
branch is reused; do not recreate it for every task or delete it after a merge.

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
git push -u origin dev1/muhammad-syarif-hidayat-hadari
```

Open a PR targeting `main`, explain the final behavior and actual validation,
and request the other member's review. A draft PR can be used for unfinished
work. Continue fixing and testing on the same branch. Later pushes use
`git push` once the upstream is configured.

The lead merges with a normal merge commit after required checks pass. This
repository protects `main` and uses merge commits to retain actual authorship.
Both members then update local `main` with `git pull --ff-only origin main`.
Use `git switch branch-name` to revisit an existing branch; `-c` creates a new one.
Merge current `main` into your member branch before beginning its next change.

## Current handoff and contribution credit

[PR #5](https://github.com/sar1p/AI-TE-103/pull/5) merged the original
`zaedalmusthofa` starter commit together with integration fixes. The original
commit remains in `main`, and the GitHub contributor API confirmed both
`sar1p` and `zaedalmusthofa` after the merge. Corrections made by the lead keep
the lead's own identity. A profile page may refresh later than the API.

The lead completed the external rules, forward chaining, CLI, tests, interface,
and integration. That later work uses the lead's identity. The teammate's
original contribution remains credited without needing an artificial commit.
Further contributions should describe actual review findings, fixes, or
documentation work. Read [TEAMMATE_TASKS.md](TEAMMATE_TASKS.md) and
[the closed issue #3](https://github.com/sar1p/AI-TE-103/issues/3) for the completed
software record. The original presentation date, October 13, 2026, is historical;
the current review and rehearsal cover all four methods. Begin any further change
by updating your member branch from current `main`.

## Recovery

Git history preserves tracked commits; it does not preserve ignored files,
virtual environments, uncommitted work, or GitHub settings. Keep credentials
outside the repository. The lead maintains a verified offline Git bundle.

If a merged change causes a regression, create a repair or revert branch, test
it, and submit another PR. For a merge commit, `git revert -m 1 MERGE_SHA` is a
reviewable way to undo its effect; first identify the exact merge and inspect
the proposed change. Do not rewrite protected `main` history.
