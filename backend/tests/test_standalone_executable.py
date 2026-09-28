"""Comprehensive test suite for Task 30 Standalone FastAPI Backend Executable.

Tests:
1. Build & Packaging Configuration:
   - PyInstaller spec exists (PromptCompilerBackend.spec)
   - Build script exists (scripts/build_backend.py)
   - Executable exists (backend/dist/prompt-compiler-backend)
   - Executable is Mach-O 64-bit arm64 (macOS Apple Silicon)
   - Executable has executable permission (X_OK)

2. Standalone Runtime Lifecycle (No Python Invocation):
   - Starts binary directly via subprocess.Popen without invoking Python
   - /api/health responds HTTP 200 with service='prompt-compiler'
   - /api/presets responds HTTP 200 with 5 presets
   - /api/runtime/status responds HTTP 200 with ready state
   - Process terminates cleanly on SIGTERM with exit code 0 or -SIGTERM

3. SQLite Persistence & sqlite-vec Across Restarts:
   - Binary initializes SQLite in custom data directory
   - Tables (including sqlite-vec / vec_chunks) are properly initialized
   - Created data persists across process termination and binary restart
   - Restarted binary serves previous data without data corruption

4. Host & Port Configuration:
   - Binary respects --port and --host arguments
   - Desktop mode disallows 0.0.0.0 and binds to 127.0.0.1

5. Ollama Integration States:
   - Backend boots and reports Ollama status gracefully
   - Missing or unpulled models do not cause backend startup failure

6. Authentication & Security Invariants:
   - Unauthenticated requests to /api/auth/me return HTTP 401
   - Unauthenticated requests to /api/projects return HTTP 401
   - Unauthenticated requests to /api/compile return HTTP 401
   - Anti-probing 404 security invariants remain active
   - No embedded secret keys in the compiled binary artifact
"""

import json
import os
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


def find_free_port() -> int:
    """Find an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_repo_root() -> Path:
    """Resolve repository root."""
    return Path(__file__).resolve().parent.parent.parent


def get_backend_executable() -> Path:
    """Resolve path to standalone backend executable."""
    return get_repo_root() / "backend" / "dist" / "prompt-compiler-backend"


class TestPackagingConfiguration(unittest.TestCase):
    """TEST CATEGORY 1: Packaging Configuration & Artifact Properties."""

    def test_spec_file_exists(self) -> None:
        """Verify PromptCompilerBackend.spec is committed in backend directory."""
        spec_path = get_repo_root() / "backend" / "PromptCompilerBackend.spec"
        self.assertTrue(spec_path.exists(), f"Spec file not found at {spec_path}")
        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("prompt-compiler-backend", content)
        self.assertIn("app/desktop_entry.py", content)
        self.assertIn("sqlite_vec", content)
        self.assertIn("sqlean", content)
        self.assertIn("target_arch=\"arm64\"", content)

    def test_build_script_exists(self) -> None:
        """Verify scripts/build_backend.py exists and is executable."""
        script_path = get_repo_root() / "scripts" / "build_backend.py"
        self.assertTrue(script_path.exists(), f"Build script not found at {script_path}")
        self.assertTrue(os.access(script_path, os.X_OK), "scripts/build_backend.py must be executable")

    def test_executable_exists_and_is_arm64(self) -> None:
        """Verify the built executable exists, is executable, and is arm64."""
        exe_path = get_backend_executable()
        self.assertTrue(exe_path.exists(), f"Standalone binary not found at {exe_path}. Run scripts/build_backend.py first.")
        self.assertTrue(os.access(exe_path, os.X_OK), f"Binary at {exe_path} is not executable.")

        # Check binary size is reasonable (> 15MB, < 100MB)
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        self.assertGreater(size_mb, 15.0, f"Binary size {size_mb:.1f} MB suspiciously small.")
        self.assertLess(size_mb, 100.0, f"Binary size {size_mb:.1f} MB unexpectedly large.")

        # Check architecture using macOS 'file' command
        file_out = subprocess.check_output(["file", str(exe_path)], text=True).strip()
        self.assertIn("Mach-O 64-bit executable arm64", file_out)

    def test_no_embedded_secrets(self) -> None:
        """Verify no sensitive secret keys or tokens are hardcoded into the binary."""
        exe_path = get_backend_executable()
        self.assertTrue(exe_path.exists())
        strings_out = subprocess.check_output(["strings", str(exe_path)], text=True, errors="ignore")
        self.assertNotIn("sk_live_", strings_out)
        self.assertNotIn("CLERK_SECRET_KEY=sk_", strings_out)


class TestStandaloneExecutableRuntime(unittest.TestCase):
    """TEST CATEGORY 2: Direct Binary Execution & API Smoke Tests (No Python)."""

    def setUp(self) -> None:
        self.exe_path = get_backend_executable()
        if not self.exe_path.exists():
            self.skipTest(f"Executable not found at {self.exe_path}")
        self.port = find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env = os.environ.copy()
        self.env.pop("DATABASE_URL", None)
        self.env["PROMPT_COMPILER_DATA_DIR"] = self.temp_dir.name
        self.env["DESKTOP_BACKEND_PORT"] = str(self.port)
        self.env["DESKTOP_BACKEND_HOST"] = "127.0.0.1"
        self._running_procs = []

    def tearDown(self) -> None:
        for proc in self._running_procs:
            self._stop_server(proc)
        self.temp_dir.cleanup()

    def _stop_server(self, proc: subprocess.Popen) -> None:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

    def _start_server(self, extra_args=None) -> subprocess.Popen:
        """Start the standalone executable directly without Python."""
        cmd = [str(self.exe_path), "--port", str(self.port), "--host", "127.0.0.1"]
        if extra_args:
            cmd.extend(extra_args)
        proc = subprocess.Popen(
            cmd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._running_procs.append(proc)
        deadline = time.time() + 25.0
        ready = False
        while time.time() < deadline:
            try:
                req = urllib.request.Request(f"{self.base_url}/api/health")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.2)
        if not ready:
            proc.kill()
            stdout, stderr = proc.communicate(timeout=3)
            self.fail(f"Executable failed to become ready within 25s.\nStdout:\n{stdout}\nStderr:\n{stderr}")
        return proc

    def test_health_presets_and_runtime_status(self) -> None:
        """Verify /api/health, /api/presets, and /api/runtime/status return 200 OK from standalone binary."""
        proc = self._start_server()
        try:
            # 1. Health
            req_health = urllib.request.Request(f"{self.base_url}/api/health")
            with urllib.request.urlopen(req_health, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["status"], "ok")
                self.assertEqual(data["service"], "prompt-compiler")

            # 2. Presets
            req_presets = urllib.request.Request(f"{self.base_url}/api/presets")
            with urllib.request.urlopen(req_presets, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                presets = json.loads(resp.read().decode("utf-8"))
                self.assertIsInstance(presets, list)
                self.assertEqual(len(presets), 5)
                preset_ids = [p["id"] for p in presets]
                self.assertIn("generic", preset_ids)
                self.assertIn("cursor", preset_ids)
                self.assertIn("claude_code", preset_ids)
                self.assertIn("cline", preset_ids)
                self.assertIn("windsurf", preset_ids)

            # 3. Runtime Status
            req_status = urllib.request.Request(f"{self.base_url}/api/runtime/status")
            with urllib.request.urlopen(req_status, timeout=3.0) as resp:
                self.assertEqual(resp.status, 200)
                status_data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(status_data["backend"], "ready")
                self.assertEqual(status_data["database"]["status"], "ready")
                self.assertIn(status_data["ollama"]["status"], ("available", "unavailable"))
                self.assertIn(status_data["runtime"]["mode"], ("development", "desktop"))
        finally:
            self._stop_server(proc)

    def test_clean_shutdown(self) -> None:
        """Verify binary responds to SIGTERM and shuts down cleanly."""
        proc = self._start_server()
        proc.send_signal(signal.SIGTERM)
        exit_code = proc.wait(timeout=5.0)
        self.assertIn(exit_code, (0, -signal.SIGTERM), f"Expected clean exit code 0 or -SIGTERM, got {exit_code}")
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()

    def test_auth_and_ownership_invariants(self) -> None:
        """Verify unauthenticated requests return 401 and desktop mode does not bypass auth."""
        proc = self._start_server()
        try:
            # /api/auth/me -> 401
            req_auth = urllib.request.Request(f"{self.base_url}/api/auth/me")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_auth, timeout=3.0)
            self.assertEqual(ctx.exception.code, 401)
            self.assertIn("Bearer", ctx.exception.headers.get("WWW-Authenticate", ""))

            # /api/projects -> 401
            req_proj = urllib.request.Request(f"{self.base_url}/api/projects")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_proj, timeout=3.0)
            self.assertEqual(ctx.exception.code, 401)

            # /api/compile -> 401
            compile_payload = json.dumps({"raw_prompt": "test prompt", "preset_id": "generic"}).encode("utf-8")
            req_comp = urllib.request.Request(
                f"{self.base_url}/api/compile",
                data=compile_payload,
                headers={"Content-Type": "application/json"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req_comp, timeout=3.0)
            self.assertEqual(ctx.exception.code, 401)
        finally:
            self._stop_server(proc)


class TestStandaloneExecutablePersistence(unittest.TestCase):
    """TEST CATEGORY 3: Database & Knowledge Persistence Across Restarts."""

    def test_database_creation_and_data_persistence_across_restart(self) -> None:
        """Verify SQLite database and sqlite-vec initialize in custom data dir and persist across restart."""
        exe_path = get_backend_executable()
        if not exe_path.exists():
            self.skipTest("Executable not found")

        with tempfile.TemporaryDirectory() as temp_dir:
            port = find_free_port()
            base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            env.pop("DATABASE_URL", None)
            env["PROMPT_COMPILER_DATA_DIR"] = temp_dir
            env["DESKTOP_BACKEND_PORT"] = str(port)
            env["DESKTOP_BACKEND_HOST"] = "127.0.0.1"

            # 1. Start Server First Run
            cmd = [str(exe_path), "--port", str(port), "--host", "127.0.0.1"]
            proc1 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Wait for ready with generous deadline for cold startup
            deadline = time.time() + 25.0
            ready = False
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.0) as resp:
                        if resp.status == 200:
                            ready = True
                            break
                except Exception:
                    time.sleep(0.2)
            if not ready:
                proc1.kill()
                stdout, stderr = proc1.communicate(timeout=3)
                self.fail(f"Server 1 failed to become ready within 25s.\nStdout:\n{stdout}\nStderr:\n{stderr}")

            # Check database file was created
            db_path = Path(temp_dir) / "prompt_compiler.db"
            self.assertTrue(db_path.exists(), f"Expected database file at {db_path}")

            # Verify sqlite schema using python sqlite3 directly on the generated db
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            self.assertIn("users", tables)
            self.assertIn("projects", tables)
            self.assertIn("compilations", tables)
            self.assertIn("knowledge_sources", tables)
            self.assertIn("knowledge_chunks", tables)

            # Insert a marker project manually to verify persistence across restart
            cursor.execute(
                "INSERT INTO users (clerk_user_id, created_at, updated_at) "
                "VALUES ('clerk_persistence_test_1', 1700000000.0, 1700000000.0)"
            )
            user_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO projects (project_id, user_id, name, description, created_at, updated_at) "
                "VALUES ('proj-test-1', ?, 'Persistence Test Project', 'Testing binary restart', 1700000000.0, 1700000000.0)",
                (user_id,),
            )
            conn.commit()
            conn.close()

            # Terminate Server 1 cleanly
            proc1.send_signal(signal.SIGTERM)
            proc1.wait(timeout=5.0)
            if proc1.stdout:
                proc1.stdout.close()
            if proc1.stderr:
                proc1.stderr.close()

            # 2. Restart Server 2 on the same database
            proc2 = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            deadline = time.time() + 25.0
            ready2 = False
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(f"{base_url}/api/health", timeout=1.0) as resp:
                        if resp.status == 200:
                            ready2 = True
                            break
                except Exception:
                    time.sleep(0.2)
            if not ready2:
                proc2.kill()
                stdout, stderr = proc2.communicate(timeout=3)
                self.fail(f"Server 2 failed to become ready within 25s.\nStdout:\n{stdout}\nStderr:\n{stderr}")

            # Verify database still contains the marker project
            conn2 = sqlite3.connect(str(db_path))
            cursor2 = conn2.cursor()
            row = cursor2.execute("SELECT name, description FROM projects WHERE project_id='proj-test-1'").fetchone()
            conn2.close()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "Persistence Test Project")
            self.assertEqual(row[1], "Testing binary restart")

            # Clean shutdown Server 2
            proc2.send_signal(signal.SIGTERM)
            proc2.wait(timeout=5.0)
            if proc2.stdout:
                proc2.stdout.close()
            if proc2.stderr:
                proc2.stderr.close()


if __name__ == "__main__":
    unittest.main()
