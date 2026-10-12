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
    for name in (".streamlit", "data", "expert_system", "interface", "search_algorithm", "tests", "tools"):
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def command(project, *arguments):
    return ["/bin/bash", str(project / "run.sh"), *map(str, arguments)]


def invoke(args, label, env=None, expected=0):
    result = subprocess.run(args, cwd="/", env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
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


@unittest.skipUnless(sys.platform in ("linux", "darwin"), "Native Linux/macOS verification")
class UnixLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = snapshot("ZIP project & 100% ready")

    def test_01_private_python_first_setup_and_core_suite(self):
        output = invoke(command(self.project, "--managed-python", "--setup-only", "--verify"), "first-setup")
        self.assertRegex(output, r"\d+ passed")
        self.assertIn("Setup complete", output)
        python = self.project / ".venv/bin/python"
        base = invoke([str(python), "-c", "import sys; print(sys.base_prefix)"], "private-python-prefix").strip()
        self.assertTrue(Path(base).resolve().is_relative_to((self.project / ".runtime/python").resolve()))
        self.assertTrue(lock_is_free(self.project))

    def test_02_offline_repeat_and_macos_entry_point(self):
        stamp = self.project / ".venv/.ai-te-303-ready"
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
        stamp = self.project / ".venv/.ai-te-303-ready"
        original_stamp = stamp.read_bytes()
        try:
            requirements.write_text("ai-te-303-test-missing-package==0.0.0\n")
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
        env = dict(os.environ, AI_TE_303_DIRECTORY=str(self.project), PIP_NO_INDEX="1")
        output = invoke(["/bin/bash", str(ROOT / "install.sh"), "--setup-only"], "existing-project", env=env)
        self.assertIn("Using the existing project", output)
        self.assertEqual(note.read_text(), "keep this change")
        foreign = WORK / "unrelated folder"
        foreign.mkdir()
        note = foreign / "keep.txt"
        note.write_text("original")
        invoke(["/bin/bash", str(ROOT / "install.sh"), "--setup-only"], "unrelated-folder", env=dict(os.environ, AI_TE_303_DIRECTORY=str(foreign)), expected=1)
        self.assertEqual(list(foreign.iterdir()), [note])

    def test_05_incomplete_copy_and_symlink_rejected(self):
        incomplete = snapshot("incomplete copy")
        (incomplete / "constraints.txt").unlink()
        invoke(command(incomplete, "--setup-only"), "incomplete-copy", expected=1)
        self.assertFalse((incomplete / ".venv").exists())
        linked = snapshot("linked environment")
        (linked / ".venv").symlink_to(self.project / ".venv", target_is_directory=True)
        invoke(command(linked, "--setup-only"), "linked-env", expected=1)
        self.assertTrue((self.project / ".venv/.ai-te-303-ready").is_file())

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


if __name__ == "__main__":
    token = uuid.uuid4().hex
    REPORT = ROOT / "artifacts/unix-launcher" / token
    REPORT.mkdir(parents=True)
    WORK = Path(tempfile.mkdtemp(prefix="ai303-unix-"))
    print(f"Native platform: {sys.platform}; logs: {REPORT}", flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(UnixLauncherTests))
    (REPORT / "result.json").write_text(json.dumps({"platform": sys.platform, "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}, indent=2))
    if result.wasSuccessful():
        if WORK.resolve().parent != Path(tempfile.gettempdir()).resolve() or not WORK.name.startswith("ai303-unix-"):
            raise RuntimeError("Refusing to remove a test folder outside its temporary parent")
        shutil.rmtree(WORK)
    sys.exit(0 if result.wasSuccessful() else 1)
