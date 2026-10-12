# Windows launcher implementation

For the beginner download and launch steps, use the [README](../README.md#development-setup).
`run.bat` and the compatibility entry point `run_demo.bat` both call
`tools/start_windows.ps1`. A ZIP copy uses the same setup as a Git clone.

## Runtime and environment

The launcher validates a project environment as a real virtual environment
rooted under this copy's `.venv`, using 64-bit Python 3.12. For a new environment,
it checks installed Python executables, the Windows Python launcher and registry,
then a previously downloaded private runtime. `-Python` supplies an explicit
interpreter for environment creation; it does not replace an already valid
environment. Candidate discovery disables the Python install manager's automatic
global install only during the check, then restores the process setting.

If no compatible interpreter exists, the launcher downloads the **full** runtime:

- URL: `https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.zip`
- SHA256: `8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d`
- Provenance: [Python.org Windows runtime index](https://www.python.org/ftp/python/index-windows.json).

The pinned hash is checked before extraction. This full distribution supports
`venv` and pip; the embeddable distribution is not used. Python 3.12.10 is the
last full 3.12 release with official Windows binaries; later security releases
are source-only, so this fallback is not the latest security release.
[Official release notes](https://www.python.org/downloads/release/python-31210/).
An already installed compatible newer 3.12 patch can be used instead.

Downloads and extracted runtimes stay in ignored `.runtime`. The launcher does
not install Python or Git globally, change the user's PATH, or change persistent
PowerShell execution policy. The batch entry point starts a child PowerShell
process with an execution policy for that process only.

A broken or wrong-version `.venv` is preserved as `.venv-backup-<unique-id>` before
creating a new one. Do not delete those backups if you still need their contents.
The readiness stamp hashes all three requirements/constraint files. Installation
runs again if those files change or dependency/import checks fail. A stamp is
written only after a successful installation and check. Installation failures
stop before the application starts. Windows `WinError 206` means the project
path is too long; move the complete project directly under Downloads and retry.

## Download and launch behavior

`install.ps1` defaults to the current user's `Downloads\AI-TE-303`. It clones
with an existing Git executable, or downloads the main-branch ZIP without Git.
Transfers use a unique staging folder so a failed clone does not occupy the final
destination. Existing project copies are reused without a pull or overwrite;
incomplete or unrelated destinations require an explicit update or relocation.

A project-scoped mutex prevents two windows from modifying the same environment
or launching the same copy simultaneously. The launcher chooses an available
loopback port from the requested port through the next ten ports. A process
claiming a port after the probe can still cause a startup failure; the launcher
reports it so the user can retry. Separate project copies can run independently.

Streamlit opens the default browser after its server starts. The launch disables
the first-run email prompt and uses the selected loopback address. Keep the
terminal open, and stop the app with Ctrl+C. `-NoBrowser` starts only the server;
`-Port 8580` changes the first port to try; `-SetupOnly` prepares without launch;
`-Verify` also runs the project tests before launch. Normal launches do not run
the full test suite.

## Verification

The Windows CI job runs the actual PowerShell 5.1 scripts and batch entry points
from an unrelated working directory, using isolated copies with spaces and shell
characters in their folder names. `tools/check_windows_launcher.py` covers first
setup plus the project suite, both batch entry points, offline environment reuse,
preservation of existing folders, pip failure, wrong-version environment backup,
failed-clone retry, the no-Git ZIP flow, busy-port fallback, and duplicate-window
handling. The ZIP integration case substitutes a ZIP transport fixture from the
exact checkout; it exercises extraction and setup rather than GitHub availability.
Public download checks and the private-runtime fallback are checked separately.

```powershell
python tools/check_windows_launcher.py --python "C:\Path\to\python312.exe" --wrong-python "C:\Path\to\python314.exe"
```

Verification copies use short temporary paths. Logs and results are retained
under ignored `artifacts/windows-launcher/` and uploaded by CI. Historical
application evidence remains tied to its original source revisions.
