"""Exercise the real Windows launchers in isolated project copies.

Run with Python 3.12 on Windows. --wrong-python supplies a different installed
Python to exercise migration. Logs and copies stay in ignored artifacts/.
"""

import argparse
import http.client
import json
import os
from pathlib import Path
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
import zipfile


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
OPTIONS = None
WORK = None
REPORT = None
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def snapshot(name):
    target = WORK / name
    target.mkdir()
    for name in ("app.py", "requirements.txt", "requirements-dev.txt", "constraints.txt", "run.bat", "run_demo.bat", "install.ps1", "pytest.ini"):
        shutil.copy2(ROOT / name, target / name)
    for name in (".streamlit", "data", "expert_system", "interface", "search_algorithm", "tests", "tools"):
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return target


def command(project, *arguments, installer=False):
    script = project / ("install.ps1" if installer else "tools/start_windows.ps1")
    return [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, arguments)]


def invoke(args, label, env=None, expected=0):
    result = subprocess.run(args, cwd=os.environ["SystemRoot"], env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", timeout=600)
    (REPORT / f"{label}.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(f"{label}: exit {result.returncode}, expected {expected}\n{result.stdout}")
    return result.stdout


def quote_ps(value):
    return "'" + str(value).replace("'", "''") + "'"


@unittest.skipUnless(sys.platform == "win32", "Windows launcher integration")
class LauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = snapshot("ZIP project & 100% ready")

    def test_01_first_setup_and_core_tests(self):
        output = invoke(command(self.project, "-Python", OPTIONS.python, "-SetupOnly", "-Verify"), "first-setup")
        self.assertIn("Setup complete", output)
        self.assertRegex(output, r"\d+ passed")
        self.assertTrue((self.project / ".venv/.ai-te-303-ready").is_file())

    def test_02_batch_alias_and_repeat_offline(self):
        stamp = self.project / ".venv/.ai-te-303-ready"
        before = stamp.stat().st_mtime_ns
        env = dict(os.environ, PIP_NO_INDEX="1")
        cmd = str(Path(os.environ["SystemRoot"]) / "System32/cmd.exe")
        for batch in ("run.bat", "run_demo.bat"):
            # CMD parses its command string itself; list2cmdline's backslash
            # escaping of embedded quotes is not CMD's quoting convention.
            output = invoke(f'"{cmd}" /d /s /c ""{self.project / batch}" -SetupOnly"', batch, env=env)
            self.assertIn("no installation is needed", output)
        self.assertEqual(stamp.stat().st_mtime_ns, before)

    def test_03_existing_folder_preserved(self):
        marker = self.project / "my-notes.txt"
        marker.write_text("keep my changes", encoding="utf-8")
        output = invoke(command(ROOT, "-Destination", self.project, "-SetupOnly", installer=True), "reuse-installer")
        self.assertIn("Using the existing project", output)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep my changes")
        foreign = WORK / "unrelated folder"
        foreign.mkdir()
        note = foreign / "keep.txt"
        note.write_text("original", encoding="utf-8")
        invoke(command(ROOT, "-Destination", foreign, "-SetupOnly", installer=True), "foreign-folder", expected=1)
        self.assertEqual(list(foreign.iterdir()), [note])

    def test_04_failed_install_stops_before_launch(self):
        project = snapshot("failed libraries")
        (project / "requirements-dev.txt").write_text("ai-te-303-missing-package-for-test==0.0.0\n", encoding="utf-8")
        env = dict(os.environ, PIP_NO_INDEX="1")
        output = invoke(command(project, "-Python", OPTIONS.python), "failed-libraries", env=env, expected=1)
        self.assertIn("Library installation failed", output)
        self.assertNotIn("[3/3] Opening", output)
        self.assertFalse((project / ".venv/.ai-te-303-ready").exists())

    def test_05_wrong_environment_preserved_and_replaced(self):
        if not OPTIONS.wrong_python:
            self.skipTest("Supply --wrong-python for the version-migration case")
        project = snapshot("wrong Python")
        invoke([OPTIONS.wrong_python, "-m", "venv", str(project / ".venv")], "make-wrong-env")
        marker = project / ".venv/original.txt"
        marker.write_text("preserve old environment", encoding="utf-8")
        output = invoke(command(project, "-Python", OPTIONS.python, "-SetupOnly"), "repair-wrong-env")
        self.assertIn("Keeping the old environment", output)
        backups = list(project.glob(".venv-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "original.txt").read_text(encoding="utf-8"), "preserve old environment")
        version = invoke([str(project / ".venv/Scripts/python.exe"), "-c", "import sys; print(sys.version_info[:2])"], "repaired-version")
        self.assertIn("(3, 12)", version)

    def test_06_failed_clone_can_retry(self):
        stub = WORK / "git-failure"
        stub.mkdir()
        (stub / "git.cmd").write_text('@echo off\r\nmkdir "%~3"\r\nexit /b 2\r\n', encoding="ascii")
        target = WORK / "clone target"
        env = dict(os.environ, PATH=str(stub) + os.pathsep + os.environ["PATH"])
        for attempt in (1, 2):
            output = invoke(command(ROOT, "-Destination", target, "-SetupOnly", installer=True), f"failed-clone-{attempt}", env=env, expected=1)
            self.assertIn("Clone failed", output)
            self.assertFalse(target.exists())

    def test_07_no_git_zip_flow(self):
        project = snapshot("zip source")
        archive = WORK / "snapshot.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for file in project.rglob("*"):
                if file.is_file():
                    bundle.write(file, "AI-TE-303-main/" + file.relative_to(project).as_posix())
        target = WORK / "no git installation"
        # Substitute only the transport, using a ZIP of this exact checkout.
        # The real extraction, validation, destination move and setup all run.
        script = WORK / "zip-transport.ps1"
        script.write_text(
            "$env:PATH = ''\n"
            "function Invoke-WebRequest { param([switch]$UseBasicParsing, $Uri, $OutFile); Copy-Item -LiteralPath " + quote_ps(archive) + " -Destination $OutFile }\n"
            "& " + quote_ps(ROOT / "install.ps1") + " -Destination " + quote_ps(target) + " -Python " + quote_ps(OPTIONS.python) + " -SetupOnly\nexit $LASTEXITCODE\n",
            encoding="utf-8",
        )
        output = invoke([str(POWERSHELL), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], "zip-without-git")
        self.assertIn("Git was not found", output)
        self.assertTrue((target / ".venv/.ai-te-303-ready").is_file())
        self.assertFalse((target / ".git").exists())

    def test_08_busy_port_and_single_launch(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            if port > 65525:
                self.skipTest("OS selected a port outside the launcher test range")
            log_path = REPORT / "busy-port.log"
            with log_path.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command(self.project, "-NoBrowser", "-Port", port), cwd=os.environ["SystemRoot"], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                try:
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        text = log_path.read_text(encoding="utf-8", errors="replace")
                        if "[3/3] Opening http://127.0.0.1:" in text:
                            line = next(line for line in text.splitlines() if "[3/3] Opening " in line)
                            url = line.split("Opening ", 1)[1]
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
                    repeat = invoke(command(self.project, "-SetupOnly"), "duplicate-window", expected=1)
                    self.assertIn("already setting up or running", repeat)
                finally:
                    if process.poll() is None:
                        try:
                            process.send_signal(signal.CTRL_BREAK_EVENT)
                        except OSError:
                            pass
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        # This PID belongs to this test's Popen instance. Never
                        # stop an existing user server or all Python processes.
                        taskkill = Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"
                        subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                        process.wait(timeout=10)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    LOCAL_HTTP.open(url + "/_stcore/health", timeout=1).close()
                except (OSError, http.client.HTTPException):
                    break
                time.sleep(0.2)
            else:
                self.fail("The test server did not stop after Ctrl+Break")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="64-bit Python 3.12 used to create environments")
    parser.add_argument("--wrong-python", help="An installed Python outside 3.12 for migration testing")
    OPTIONS = parser.parse_args()
    run_id = uuid.uuid4().hex
    REPORT = ROOT / "artifacts/windows-launcher" / run_id
    REPORT.mkdir(parents=True)
    # Keep package paths short even on Windows installations without long paths.
    WORK = Path(tempfile.gettempdir()) / ("ai303-test-" + run_id[:8])
    WORK.mkdir(parents=True)
    print(f"Launcher verification logs: {REPORT}", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LauncherTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (REPORT / "result.json").write_text(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)}, indent=2), encoding="utf-8")
    if result.wasSuccessful():
        temp_root = Path(tempfile.gettempdir()).resolve()
        resolved_work = WORK.resolve()
        if resolved_work.parent != temp_root or not resolved_work.name.startswith("ai303-test-"):
            raise RuntimeError("Refusing to remove a test folder outside its temporary parent")
        shutil.rmtree(resolved_work)
    sys.exit(0 if result.wasSuccessful() else 1)
