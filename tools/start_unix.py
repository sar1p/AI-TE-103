"""Create/check the project venv and start the app after run.sh finds Python."""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = ROOT / ".venv"


def run(*arguments, capture=False):
    return subprocess.run([str(ENVIRONMENT / "bin/python"), *map(str, arguments)], cwd=ROOT, stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None, text=True)


def dependencies_ready():
    for arguments in (
        ("-m", "pip", "check"),
        ("-c", "import streamlit,pytest; import expert_system,search_algorithm; assert streamlit.__version__ == '1.65.0'; assert pytest.__version__ == '9.1.1'"),
    ):
        result = run(*arguments, capture=True)
        if result.returncode:
            print(result.stdout, flush=True)
            return False
    return True


def available_port(first):
    for port in range(first, first + 11):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Ports {first} through {first + 10} are busy. Close an old demo window and try again.")


def environment_valid():
    if ENVIRONMENT.is_symlink():
        raise RuntimeError("Use a normal .venv folder, not a directory link.")
    if not (ENVIRONMENT / "pyvenv.cfg").is_file():
        return False
    try:
        result = run("-c", "import sys,os,pip; sys.exit(0 if sys.version_info[:2]==(3,12) and sys.maxsize>2**32 and sys.prefix!=sys.base_prefix and os.path.realpath(sys.prefix)==os.path.realpath(sys.argv[1]) else 1)", ENVIRONMENT, capture=True)
        return result.returncode == 0
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--managed-python", action="store_true", help="Use a private Python when creating an environment (handled by run.sh)")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--uv", default="", help=argparse.SUPPRESS)
    parser.add_argument("--base-python", default=sys.executable, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if not 1024 <= options.port <= 65525:
        parser.error("--port must be between 1024 and 65525")
    if sys.platform not in ("linux", "darwin"):
        raise RuntimeError("Use run.bat on Windows.")
    if sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise RuntimeError("Run bash run.sh so setup uses Python 3.12.")
    os.chdir(ROOT)
    lock_path = ROOT / ".launcher-lock"
    if lock_path.is_symlink():
        raise RuntimeError("Use a normal startup lock file, not a link.")
    if lock_path.exists() and not lock_path.is_file():
        raise RuntimeError("The startup lock must be a regular file, not a directory or special file.")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("This copy is already setting up or running in another window. Use that window or stop it with Ctrl+C.") from None
        return finish_setup(options)


def finish_setup(options):
    if not environment_valid():
        if not options.uv:
            raise RuntimeError("The environment changed during startup. Run bash run.sh again.")
        if ENVIRONMENT.exists():
            backup = ROOT / (".venv-backup-" + uuid.uuid4().hex)
            print(f"Keeping the old environment at: {backup}", flush=True)
            ENVIRONMENT.rename(backup)
        result = subprocess.run([options.uv, "venv", "--python", options.base_python, "--no-python-downloads", "--seed", str(ENVIRONMENT)], cwd=ROOT)
        if result.returncode or not environment_valid():
            raise RuntimeError("Environment creation failed. Check the error above and available disk space.")
    print("[2/3] Checking project libraries...", flush=True)
    stamp = "unix-setup-v1:" + ":".join(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("requirements.txt", "requirements-dev.txt", "constraints.txt"))
    stamp_file = ENVIRONMENT / ".ai-te-303-ready"
    existing = stamp_file.read_text().strip() if stamp_file.is_file() else ""
    if existing != stamp or not dependencies_ready():
        print("Installing libraries. First setup needs internet and may take a few minutes...", flush=True)
        if run("-m", "pip", "--disable-pip-version-check", "install", "--quiet", "--only-binary", ":all:", "-r", ROOT / "requirements-dev.txt", "-c", ROOT / "constraints.txt").returncode:
            raise RuntimeError("Library installation failed. Check the error above, then run bash run.sh again.")
        if not dependencies_ready():
            raise RuntimeError("The installed libraries did not pass their checks. The app has not been started.")
        stamp_file.write_text(stamp + "\n", encoding="ascii")
    else:
        print("The existing environment is ready; no installation is needed.", flush=True)
    if options.verify:
        print("Running the project tests...", flush=True)
        if run("-m", "pytest", "-q").returncode:
            raise RuntimeError("Project tests failed. The app has not been started.")
    if options.setup_only:
        print("[3/3] Setup complete. Run bash run.sh to open the app.", flush=True)
        return 0
    port = available_port(options.port)
    print(f"[3/3] Opening http://127.0.0.1:{port}\nKeep this terminal open. Press Ctrl+C here to stop the app.", flush=True)
    try:
        result = run("-m", "streamlit", "run", ROOT / "app.py", "--server.address", "127.0.0.1", "--server.port", port, "--server.headless", "true" if options.no_browser else "false", "--server.showEmailPrompt", "false", "--browser.gatherUsageStats", "false", "--logger.hideWelcomeMessage", "true")
    except KeyboardInterrupt:
        print("\nApplication stopped.", flush=True)
        return 0
    if result.returncode not in (0, -2, 130):
        raise RuntimeError("The app could not run. Check the message above, then try again.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nSetup interrupted. Run bash run.sh again to finish setup.", file=sys.stderr, flush=True)
        sys.exit(130)
    except (OSError, RuntimeError) as error:
        print(f"\nSetup stopped: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
