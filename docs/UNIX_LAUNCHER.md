# Linux and macOS launcher

The [README](../README.md#linux-and-macos-automatic-setup) gives the beginner
download block and the single `bash run.sh` command for an extracted archive.
`install.sh` defaults to `~/Downloads/AI-TE-303`, cloning with an existing Git or
downloading a source archive without Git. An existing complete copy is reused
without a pull or overwrite; unrelated or incomplete destinations are rejected.
Failed transfers use unique staging folders so the final location can be retried.
The installer claims a new destination with an atomic `mkdir` before copying
the validated checkout. If copying is interrupted, the partial destination is
preserved for inspection; choose another location to retry.

## Runtime provenance

`run.sh` supports Bash 3.2, including the version shipped with macOS. It checks
for a real project environment first. If a bootstrap interpreter is needed, it
downloads a private **uv 0.13.0** executable from the
[official Astral release](https://github.com/astral-sh/uv/releases/tag/0.13.0).
The published SHA256 values for its four selected assets are pinned in `run.sh`:

| Platform | Asset | SHA256 |
|---|---|---|
| Linux x86_64 | `uv-x86_64-unknown-linux-gnu.tar.gz` | `1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154` |
| Linux ARM64 | `uv-aarch64-unknown-linux-gnu.tar.gz` | `3ccfb6af6e242433eb552f7d9676abd5412c6595c497e990d9c8cb7b5bd4d2c3` |
| macOS Intel | `uv-x86_64-apple-darwin.tar.gz` | `5f44dcbde809b632f47c36fadb241cb4d6f9af71d0c8f172b5d2026d3dde742c` |
| macOS Apple Silicon | `uv-aarch64-apple-darwin.tar.gz` | `a9c1b29002cf3c83f07fa9cd8a887a3be0107d90e23189721221e7257db8e3d6` |

A compatible `python3.12` on PATH can be used to create the environment. Otherwise,
uv obtains CPython 3.12 from Astral's **python-build-standalone** distributions.
These are third-party builds, distinct from Python.org's Windows binary used by
the Windows launcher. See [Astral's Python installation guide](https://docs.astral.sh/uv/guides/install-python/).
`--managed-python` selects this private runtime for a new environment.

uv, downloaded Python, and its cache remain in ignored `.runtime` under the
project. `UV_PYTHON_INSTALL_DIR`, `UV_CACHE_DIR`, and `--no-bin` keep installation
local. The launcher does not run a global uv installer, use `sudo`, install
Homebrew/apt packages, create global Python command links, or edit shell profiles.
The macOS installer treats Apple's Git stub as unavailable when Command Line
Tools are absent, so trying the app does not trigger their installer.

## Environment and launch

The shell obtains Python before `tools/start_unix.py` starts, so a system Python
is not required. The helper holds a kernel file lock before creating or changing
`.venv`. The lock releases on process death; its ignored regular file remains,
so no stale PID-directory cleanup is required. A complete verified uv executable
is published atomically; uv manages concurrent private-runtime installation.

uv creates and seeds the environment even when a distribution does not bundle
`ensurepip`. Normal virtual-environment interpreter symlinks are allowed; a linked
`.venv` directory is rejected. An invalid environment is kept under a unique
`.venv-backup-*` name before replacement.

Dependency checks and the readiness stamp cover the pinned requirement and
constraint files. Changed files or failed checks trigger installation. Native
package wheels are required, so setup fails instead of attempting an unplanned
compiler build on an unsupported platform. A failed install does not start the
app or update the readiness stamp. Normal launches skip pytest; `--verify` runs
the application suite first, and `--setup-only` prepares without launching.
`--no-browser` and `--port 8580` support headless verification.

The server binds to loopback, chooses an available port through the next ten
ports, disables the initial email prompt, and asks Streamlit to open the default
browser after startup. Keep the terminal open and stop with Ctrl+C. Browser
launch requires a desktop session; headless servers still print their local URL.
A narrow probe-to-bind port race can cause startup failure; rerun to retry.

## Compatibility and verification

The native CI matrix covers Ubuntu 24.04 x86_64 and ARM64, macOS 14 Apple Silicon,
and macOS 15 Intel. Linux must use glibc compatible with the pinned native wheels
(glibc 2.28+); Alpine/musl and 32-bit hosts are not supported. macOS 14+ is the
documented target. No claim is made for every Linux distribution or old macOS.

`run.command` can be opened from a macOS Git clone. Finder behavior for a ZIP
depends on the extractor's executable permissions and macOS download controls.
The documented ZIP entry point is `bash run.sh` in Terminal. The launcher does
not remove quarantine attributes or disable Gatekeeper.

`tools/check_unix_launcher.py` runs on the native OS. It checks private-runtime
setup plus the full application suite, offline reuse, the macOS terminal entry
point, invalid-environment backup, dependency failure, existing-folder
preservation, incomplete archives, directory-link rejection, busy-port fallback,
duplicate-window handling, and server shutdown. Logs/results are retained under
ignored `artifacts/unix-launcher/`. Headless CI verifies shell entry points and
server behavior; it does not reproduce Finder dialogs or physical laptop setup.
