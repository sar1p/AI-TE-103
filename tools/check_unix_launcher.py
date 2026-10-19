"""Verify Linux/macOS setup with private Python on the actual native platform."""

import http.client
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
WORK = None
REPORT = None
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def snapshot(name):
    target = WORK / name
    target.mkdir()
    for name in ("app.py", "requirements.txt", "requirements-dev.txt", "constraints.txt", "run.sh", "run.command", "install.sh", "pytest.ini"):
        shutil.copy2(ROOT / name, target / name)
    for name in (".streamlit", "data", "expert_system", "fuzzy_logic", "interface", "multi_agent_system", "search_algorithm", "tests", "tools"):
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def command(project, *arguments):
    return ["/bin/bash", str(project / "run.sh"), *map(str, arguments)]


def invoke(args, label, env=None, expected=0, timeout=600):
    result = subprocess.run(args, cwd="/", env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
    (REPORT / f"{label}.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(f"{label}: exit {result.returncode}, expected {expected}\n{result.stdout}")
    return result.stdout


def lock_is_free(project):
    with (project / ".launcher-lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


def shell_quote(value):
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


@unittest.skipUnless(sys.platform in ("linux", "darwin"), "Native Linux/macOS verification")
class UnixLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = snapshot("ZIP project & 100% ready")

    def test_00_snapshot_includes_importable_app_packages(self):
        packages = ("fuzzy_logic", "multi_agent_system")
        for package in packages:
            self.assertTrue((self.project / package / "__init__.py").is_file())

        root = repr(str(self.project.resolve()))
        code = (
            "import pathlib, fuzzy_logic, multi_agent_system; "
            f"root = pathlib.Path({root}).resolve(); "
            "assert pathlib.Path(fuzzy_logic.__file__).resolve().is_relative_to(root); "
            "assert pathlib.Path(multi_agent_system.__file__).resolve().is_relative_to(root); "
            "print('fixture packages imported')"
        )
        output = invoke(
            [sys.executable, "-c", code],
            "fixture-package-imports",
            env=dict(os.environ, PYTHONPATH=str(self.project)),
        )
        self.assertIn("fixture packages imported", output)

    def test_00_missing_module_stops_before_setup_and_preserves_existing_copy(self):
        project = snapshot("missing fuzzy package")
        entry = project / "fuzzy_logic/__init__.py"
        preserved = entry.with_suffix(".saved")
        entry.rename(preserved)
        output = invoke(command(project, "--setup-only"), "missing-module", expected=1)
        self.assertIn("missing fuzzy_logic/__init__.py", output)
        self.assertFalse((project / ".venv").exists())
        output = invoke(
            ["/bin/bash", str(ROOT / "install.sh"), "--setup-only"],
            "incomplete-existing-project", expected=1,
            env=dict(os.environ, AI_TE_103_DIRECTORY=str(project)),
        )
        self.assertIn("Nothing was overwritten", output)
        self.assertTrue(preserved.is_file())
        self.assertFalse(entry.exists())

    def test_01_private_python_first_setup_and_core_suite(self):
        output = invoke(command(self.project, "--managed-python", "--setup-only", "--verify"), "first-setup")
        self.assertRegex(output, r"\d+ passed")
        self.assertIn("Setup complete", output)
        python = self.project / ".venv/bin/python"
        base = invoke([str(python), "-c", "import sys; print(sys.base_prefix)"], "private-python-prefix").strip()
        self.assertTrue(Path(base).resolve().is_relative_to((self.project / ".runtime/python").resolve()))
        self.assertTrue(lock_is_free(self.project))

    def test_02_offline_repeat_and_macos_entry_point(self):
        stamp = self.project / ".venv/.ai-te-103-ready"
        before = stamp.stat().st_mtime_ns
        env = dict(os.environ, PIP_NO_INDEX="1", UV_OFFLINE="1")
        for filename in ("run.sh", "run.command"):
            output = invoke(["/bin/bash", str(self.project / filename), "--setup-only"], filename, env=env)
            self.assertIn("no installation is needed", output)
        self.assertEqual(stamp.stat().st_mtime_ns, before)

    def test_03_environment_backup_and_dependency_failure(self):
        # Invalid metadata is enough to reject an environment without executing
        # an interpreter that might install packages outside the project.
        cfg = self.project / ".venv/pyvenv.cfg"
        cfg.rename(cfg.with_name("original-pyvenv.cfg"))
        output = invoke(command(self.project, "--managed-python", "--setup-only"), "replace-invalid-env")
        self.assertIn("Keeping the old environment", output)
        backups = list(self.project.glob(".venv-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertTrue((backups[0] / "original-pyvenv.cfg").is_file())
        requirements = self.project / "requirements-dev.txt"
        original = requirements.read_bytes()
        stamp = self.project / ".venv/.ai-te-103-ready"
        original_stamp = stamp.read_bytes()
        try:
            requirements.write_text("ai-te-103-test-missing-package==0.0.0\n")
            output = invoke(command(self.project), "failed-install", env=dict(os.environ, PIP_NO_INDEX="1"), expected=1)
            self.assertIn("Library installation failed", output)
            self.assertNotIn("[3/3] Opening", output)
            self.assertEqual(stamp.read_bytes(), original_stamp)
        finally:
            requirements.write_bytes(original)
        self.assertTrue(lock_is_free(self.project))

    def test_04_installer_preserves_existing_folders(self):
        note = self.project / "my-notes.txt"
        note.write_text("keep this change")
        env = dict(os.environ, AI_TE_103_DIRECTORY=str(self.project), PIP_NO_INDEX="1")
        output = invoke(["/bin/bash", str(ROOT / "install.sh"), "--setup-only"], "existing-project", env=env)
        self.assertIn("Using the existing project", output)
        self.assertEqual(note.read_text(), "keep this change")
        foreign = WORK / "unrelated folder"
        foreign.mkdir()
        note = foreign / "keep.txt"
        note.write_text("original")
        invoke(["/bin/bash", str(ROOT / "install.sh"), "--setup-only"], "unrelated-folder", env=dict(os.environ, AI_TE_103_DIRECTORY=str(foreign)), expected=1)
        self.assertEqual(list(foreign.iterdir()), [note])

    def test_05_incomplete_copy_and_symlink_rejected(self):
        incomplete = snapshot("incomplete copy")
        (incomplete / "constraints.txt").unlink()
        invoke(command(incomplete, "--setup-only"), "incomplete-copy", expected=1)
        self.assertFalse((incomplete / ".venv").exists())
        linked = snapshot("linked environment")
        (linked / ".venv").symlink_to(self.project / ".venv", target_is_directory=True)
        invoke(command(linked, "--setup-only"), "linked-env", expected=1)
        self.assertTrue((self.project / ".venv/.ai-te-103-ready").is_file())

    def test_06_busy_port_and_duplicate_launch(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            if port > 65525:
                self.skipTest("Ephemeral port outside the test range")
            log_path = REPORT / "busy-port.log"
            with log_path.open("w") as log:
                process = subprocess.Popen(command(self.project, "--no-browser", "--port", port), cwd="/", stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
                try:
                    deadline = time.monotonic() + 45
                    url = None
                    while time.monotonic() < deadline:
                        text = log_path.read_text()
                        match = re.search(r"\[3/3\] Opening (http://127\.0\.0\.1:\d+)", text)
                        if match:
                            url = match.group(1)
                            self.assertNotEqual(url, f"http://127.0.0.1:{port}")
                            try:
                                with LOCAL_HTTP.open(url + "/_stcore/health", timeout=1) as response:
                                    if response.read() == b"ok":
                                        break
                            except (OSError, http.client.HTTPException):
                                pass
                        if process.poll() is not None:
                            self.fail(text)
                        time.sleep(0.2)
                    else:
                        self.fail("Server was not ready: " + text)
                    repeat = invoke(command(self.project, "--setup-only"), "duplicate-window", expected=1)
                    self.assertIn("already setting up or running", repeat)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    LOCAL_HTTP.open(url + "/_stcore/health", timeout=1).close()
                except (OSError, http.client.HTTPException):
                    break
                time.sleep(0.2)
            else:
                self.fail("The test server did not stop")
        self.assertTrue(lock_is_free(self.project))

    def test_07_setup_interruption_is_not_success(self):
        log_path = REPORT / "interrupted-verify.log"
        with log_path.open("w") as log:
            process = subprocess.Popen(command(self.project, "--verify", "--setup-only"), cwd="/", stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    text = log_path.read_text()
                    if "Running the project tests" in text:
                        os.killpg(process.pid, signal.SIGINT)
                        break
                    if process.poll() is not None:
                        self.fail(text)
                    time.sleep(0.05)
                else:
                    self.fail("Verification did not start")
                self.assertNotEqual(process.wait(timeout=15), 0)
                self.assertNotIn("Setup complete", log_path.read_text())
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
        self.assertTrue(lock_is_free(self.project))

    def test_08_archive_installer_without_git(self):
        source = snapshot("archive source")
        archive = WORK / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(source, arcname="AI-TE-103-main")
        binaries = WORK / "without-git-bin"
        binaries.mkdir()
        # Restrict PATH to ordinary native utilities, excluding Git and Python.
        for name in ("uname", "dirname", "mkdir", "basename", "mktemp", "tar", "gzip", "cp", "rm", "awk", "grep", "ldd", "ln", "chmod", "sha256sum", "shasum"):
            actual = shutil.which(name)
            if actual:
                (binaries / name).symlink_to(actual)
        curl = binaries / "curl"
        curl.write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do\n if [ \"$1\" = --output ]; then shift; cp " + shell_quote(archive) + " \"$1\"; exit 0; fi\n shift\ndone\nexit 2\n")
        curl.chmod(0o755)
        bash = binaries / "bash"
        # Reuse the verified runtime cache to keep this transport test offline
        # at bootstrap; the actual destination launcher and pip still run.
        bash.write_text("#!/bin/sh\nproject=$(dirname \"$1\")\ncp -R -p " + shell_quote(self.project / ".runtime") + " \"$project/.runtime\"\nexec /bin/bash \"$@\"\n")
        bash.chmod(0o755)
        target = WORK / "archive destination"
        env = dict(os.environ, PATH=str(binaries), AI_TE_103_DIRECTORY=str(target))
        output = invoke(["/bin/bash", str(ROOT / "install.sh"), "--managed-python", "--setup-only"], "archive-installer", env=env)
        self.assertIn("Git was not found", output)
        self.assertIn("Setup complete", output)
        self.assertTrue((target / ".venv/.ai-te-103-ready").is_file())
        self.assertFalse((target / ".git").exists())
        self.assertEqual(list(WORK.glob(".AI-TE-103-download.*")), [])
        self.assertEqual((target / "run.sh").read_bytes(), (ROOT / "run.sh").read_bytes())


if __name__ == "__main__":
    token = uuid.uuid4().hex
    REPORT = ROOT / "artifacts/unix-launcher" / token
    REPORT.mkdir(parents=True)
    WORK = Path(tempfile.mkdtemp(prefix="ai103-unix-"))
    print(f"Native platform: {sys.platform}; logs: {REPORT}", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnixLauncherTests))
    (REPORT / "result.json").write_text(json.dumps({"platform": sys.platform, "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}, indent=2))
    if result.wasSuccessful():
        if WORK.resolve().parent != Path(tempfile.gettempdir()).resolve() or not WORK.name.startswith("ai103-unix-"):
            raise RuntimeError("Refusing to remove a test folder outside its temporary parent")
        shutil.rmtree(WORK)
    sys.exit(0 if result.wasSuccessful() else 1)
