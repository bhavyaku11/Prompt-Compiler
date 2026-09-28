"""Comprehensive test suite for Task 29 Local Desktop Runtime Foundation.

Tests:
1. Backend readiness signal and /api/health responsiveness.
2. Runtime status endpoint (/api/runtime/status), service health, and secret safety.
3. Startup failure detection and timeout handling.
4. Process lifecycle manager with graceful termination and safe fallback.
5. SQLite persistence across simulated process restarts.
6. Data directory abstraction (APP_DATA_DIR / PROMPT_COMPILER_DATA_DIR).
7. Desktop host and port configuration.
8. Ollama availability and unavailability detection states.
9. Security invariant preservation (authentication and data ownership in desktop mode).
"""

import os
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.ai.ollama import OllamaClient
from app.auth import get_current_user
from app.config import Settings, _resolve_data_dir, _resolve_database_url
from app.database.base import Base
from app.database.models import (
    CompilationRecord,
    KnowledgeSourceRecord,
    ProjectMemoryRecord,
    ProjectRecord,
    UserRecord,
)
from app.database.repositories import (
    CompilationRepository,
    KnowledgeRepository,
    ProjectMemoryRepository,
    ProjectRepository,
    UserRepository,
)
from app.main import app
from app.runtime import DesktopBackendManager
from app.schemas.runtime import (
    DatabaseStatus,
    OllamaStatus,
    RuntimeInfo,
    RuntimeStatusResponse,
)


class TestHealthAndReadiness(unittest.TestCase):
    """TEST CATEGORY 1: Backend Readiness & Health Check."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_responds_ok(self) -> None:
        """Requirement 1 & 7: Verify /api/health returns HTTP 200 with status='ok'."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "prompt-compiler")

    def test_root_endpoint_metadata(self) -> None:
        """Verify root endpoint returns application running status."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "running")
        self.assertTrue(data.get("name"))
        self.assertTrue(data.get("version"))

    @patch("httpx.Client.get")
    def test_wait_for_ready_succeeds_on_200(self, mock_get: MagicMock) -> None:
        """Requirement 4: Verify wait_for_ready succeeds when health check returns 200."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        # Mock running process
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        manager.process = mock_proc

        ready = manager.wait_for_ready(timeout=2.0, poll_interval=0.05)
        self.assertTrue(ready)

    @patch("httpx.Client.get")
    def test_wait_for_ready_times_out(self, mock_get: MagicMock) -> None:
        """Requirement 3: Verify wait_for_ready raises TimeoutError when backend does not respond."""
        import httpx

        mock_get.side_effect = httpx.ConnectError("Connection refused")

        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        manager.process = mock_proc

        with self.assertRaises(TimeoutError):
            manager.wait_for_ready(timeout=0.3, poll_interval=0.05)

    def test_wait_for_ready_raises_on_premature_process_exit(self) -> None:
        """Requirement 3: Verify wait_for_ready raises RuntimeError if process dies during startup."""
        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Exited with error code 1
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = ("", "Port 8000 already in use")
        manager.process = mock_proc

        with self.assertRaises(RuntimeError) as ctx:
            manager.wait_for_ready(timeout=2.0, poll_interval=0.05)

        self.assertIn("terminated unexpectedly", str(ctx.exception))
        self.assertIn("Port 8000 already in use", str(ctx.exception))


class TestRuntimeStatusEndpoint(unittest.TestCase):
    """TEST CATEGORY 2: Runtime Status Inspection Endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_runtime_status_endpoint_structure(self) -> None:
        """Requirement 14 & 23: Verify /api/runtime/status returns consolidated service health."""
        response = self.client.get("/api/runtime/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Validate top-level keys
        self.assertEqual(data.get("backend"), "ready")
        self.assertIn("database", data)
        self.assertIn("ollama", data)
        self.assertIn("runtime", data)

        # Validate database status
        self.assertEqual(data["database"].get("status"), "ready")

        # Validate runtime info
        runtime = data["runtime"]
        self.assertIn(runtime.get("mode"), ["development", "desktop"])
        self.assertEqual(runtime.get("app_name"), "Prompt Compiler")
        self.assertTrue(runtime.get("version"))
        self.assertTrue(runtime.get("host"))
        self.assertIsInstance(runtime.get("port"), int)

    @patch("app.ai.ollama.OllamaClient.check_availability")
    def test_runtime_status_ollama_available_and_model_found(self, mock_avail: AsyncMock) -> None:
        """Requirement 13: Verify Ollama status reports available when reachable and model is found."""
        mock_avail.return_value = {
            "status": "available",
            "model": "qwen3:4b",
            "model_available": True,
            "details": "Model is installed and ready",
        }

        response = self.client.get("/api/runtime/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        ollama = data["ollama"]
        self.assertEqual(ollama["status"], "available")
        self.assertEqual(ollama["model"], "qwen3:4b")
        self.assertTrue(ollama["model_available"])

    @patch("app.ai.ollama.OllamaClient.check_availability")
    def test_runtime_status_ollama_unavailable(self, mock_avail: AsyncMock) -> None:
        """Requirement 14: Verify Ollama status reports unavailable cleanly without failing backend."""
        mock_avail.return_value = {
            "status": "unavailable",
            "model": "qwen3:4b",
            "model_available": False,
            "details": "Cannot reach Ollama daemon at 'http://127.0.0.1:11434'",
        }

        response = self.client.get("/api/runtime/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        ollama = data["ollama"]
        self.assertEqual(ollama["status"], "unavailable")
        self.assertFalse(ollama["model_available"])
        self.assertIn("Cannot reach Ollama", ollama["details"])
        self.assertEqual(data["backend"], "ready")

    @patch("app.api.runtime._check_database")
    def test_runtime_status_database_error(self, mock_db: MagicMock) -> None:
        """Requirement 14: Verify database error status is reported accurately."""
        mock_db.return_value = DatabaseStatus(status="error", details="Disk I/O error")

        response = self.client.get("/api/runtime/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["database"]["status"], "error")
        self.assertEqual(data["database"]["details"], "Disk I/O error")

    def test_runtime_status_leaks_zero_secrets(self) -> None:
        """Requirement 20: Verify runtime status endpoint never leaks Clerk keys or secret credentials."""
        with patch.dict(
            os.environ,
            {
                "CLERK_SECRET_KEY": "sk_test_super_secret_key_123",
                "CLERK_JWT_KEY": "jwt_public_key_456",
            },
        ):
            response = self.client.get("/api/runtime/status")
            self.assertEqual(response.status_code, 200)
            raw_text = response.text

            self.assertNotIn("sk_test_super_secret_key_123", raw_text)
            self.assertNotIn("jwt_public_key_456", raw_text)


class TestOllamaClientAvailabilityDetection(unittest.IsolatedAsyncioTestCase):
    """TEST CATEGORY 3: Ollama Availability Detection Logic."""

    async def test_ollama_check_availability_success(self) -> None:
        """Requirement 13: Verify OllamaClient.check_availability correctly parses tags endpoint."""
        client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen3:4b")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen3:4b", "size": 3200000000},
                {"name": "nomic-embed-text:latest", "size": 274000000},
            ]
        }

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            status = await client.check_availability()
            self.assertEqual(status["status"], "available")
            self.assertTrue(status["model_available"])

    async def test_ollama_check_availability_model_missing(self) -> None:
        """Requirement 13 & 14: Verify detection when Ollama is running but configured model is missing."""
        client = OllamaClient(base_url="http://127.0.0.1:11434", model="deepseek-r1:7b")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {"name": "qwen3:4b", "size": 3200000000},
            ]
        }

        with patch("httpx.AsyncClient.get", return_value=mock_resp):
            status = await client.check_availability()
            self.assertEqual(status["status"], "available")
            self.assertFalse(status["model_available"])
            self.assertIn("not installed", status["details"])

    async def test_ollama_check_availability_connection_error(self) -> None:
        """Requirement 14: Verify check_availability handles network failure gracefully without raising."""
        import httpx

        client = OllamaClient(base_url="http://127.0.0.1:11434", model="qwen3:4b")

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Daemon offline")):
            status = await client.check_availability()
            self.assertEqual(status["status"], "unavailable")
            self.assertFalse(status["model_available"])
            self.assertIn("Daemon offline", status["details"])


class TestDatabasePersistenceAcrossRestart(unittest.TestCase):
    """TEST CATEGORY 4: Database Survival Across Simulated Backend Restarts."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "persistent_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_database_entities_survive_simulated_restart(self) -> None:
        """Requirements 5, 6, 7, 8, 9, 12:

        Simulate process 1 lifecycle (create schema and records) -> terminate engine ->
        simulate process 2 lifecycle (new engine against same db file) -> verify records persist.
        """
        # ========================================================
        # PROCESS 1: Initialize DB, create user and domain records
        # ========================================================
        engine1 = create_engine(self.db_url)
        Base.metadata.create_all(engine1)
        SessionFactory1 = sessionmaker(bind=engine1)

        user_repo1 = UserRepository(SessionFactory1)
        user = user_repo1.get_or_create("clerk_persist_user_123")
        user_id = user.id

        import time

        with SessionFactory1() as session1:
            # 1. Project
            proj_record = ProjectRecord(
                project_id="proj-persist-123",
                name="Desktop Persistence Project",
                description="Verifies persistence across restart",
                user_id=user_id,
                created_at=time.time(),
                updated_at=time.time(),
            )
            session1.add(proj_record)
            session1.flush()

            # 2. Project Memory
            mem_record = ProjectMemoryRecord(
                id=1,
                project_id=proj_record.project_id,
                category="technology",
                content="Persistent SQLite Engine",
                source="user_confirmed",
                status="active",
                created_at=time.time(),
                updated_at=time.time(),
            )
            session1.add(mem_record)

            # 3. Knowledge Source
            source_record = KnowledgeSourceRecord(
                id=1,
                project_id=proj_record.project_id,
                source_name="readme.md",
                source_type="documentation",
                content_hash="abc123hash",
                chunk_count=1,
                created_at=time.time(),
            )
            session1.add(source_record)

            # 4. Compilation Record
            comp_record = CompilationRecord(
                compilation_id="comp-persist-123",
                input_text="Build a persistent desktop prompt compiler",
                compiled_prompt="Structured persistent prompt...",
                task_type="build",
                project_id=proj_record.project_id,
                user_id=user_id,
                created_at=time.time(),
            )
            session1.add(comp_record)
            session1.commit()

        # SIMULATE COMPLETE PROCESS DEATH / RESTART
        engine1.dispose()
        del engine1
        del SessionFactory1

        # Verify database file exists and is non-empty on disk
        self.assertTrue(os.path.exists(self.db_path))
        self.assertGreater(os.path.getsize(self.db_path), 0)

        # ========================================================
        # PROCESS 2: Reopen same database file, verify all entities
        # ========================================================
        engine2 = create_engine(self.db_url)
        SessionFactory2 = sessionmaker(bind=engine2)

        with SessionFactory2() as session2:
            # 1. Verify User survived
            user_reloaded = session2.scalars(
                select(UserRecord).where(UserRecord.clerk_user_id == "clerk_persist_user_123")
            ).first()
            self.assertIsNotNone(user_reloaded)
            self.assertEqual(user_reloaded.id, user_id)

            # 2. Verify Project survived
            proj_reloaded = session2.scalars(
                select(ProjectRecord).where(ProjectRecord.project_id == "proj-persist-123")
            ).first()
            self.assertIsNotNone(proj_reloaded)
            self.assertEqual(proj_reloaded.name, "Desktop Persistence Project")

            # 3. Verify Project Memory survived
            mem_reloaded = session2.scalars(
                select(ProjectMemoryRecord).where(ProjectMemoryRecord.id == 1)
            ).first()
            self.assertIsNotNone(mem_reloaded)
            self.assertEqual(mem_reloaded.content, "Persistent SQLite Engine")

            # 4. Verify Knowledge Source survived
            source_reloaded = session2.scalars(
                select(KnowledgeSourceRecord).where(KnowledgeSourceRecord.id == 1)
            ).first()
            self.assertIsNotNone(source_reloaded)
            self.assertEqual(source_reloaded.source_name, "readme.md")

            # 5. Verify Compilation Record survived
            comp_reloaded = session2.scalars(
                select(CompilationRecord).where(CompilationRecord.compilation_id == "comp-persist-123")
            ).first()
            self.assertIsNotNone(comp_reloaded)
            self.assertEqual(comp_reloaded.task_type, "build")
            self.assertEqual(comp_reloaded.user_id, user_id)
            self.assertEqual(comp_reloaded.input_text, "Build a persistent desktop prompt compiler")

        engine2.dispose()


class TestDataDirectoryAndConfiguration(unittest.TestCase):
    """TEST CATEGORY 5: Data Directory and Runtime Configuration."""

    def test_default_development_configuration(self) -> None:
        """Requirement 10: Verify default dev configuration uses ./data/prompt_compiler.db."""
        with patch.dict(os.environ, {}, clear=True):
            data_dir = _resolve_data_dir()
            self.assertIsNone(data_dir)
            db_url = _resolve_database_url()
            self.assertEqual(db_url, "sqlite:///./data/prompt_compiler.db")

    def test_app_data_dir_environment_variable(self) -> None:
        """Requirement 11: Verify APP_DATA_DIR resolution for macOS desktop application support."""
        with patch.dict(os.environ, {"APP_DATA_DIR": "/Library/Application Support/Prompt Compiler"}):
            data_dir = _resolve_data_dir()
            self.assertEqual(data_dir, "/Library/Application Support/Prompt Compiler")
            db_url = _resolve_database_url()
            self.assertEqual(
                db_url,
                "sqlite:////Library/Application Support/Prompt Compiler/prompt_compiler.db",
            )

    def test_prompt_compiler_data_dir_takes_precedence(self) -> None:
        """Requirement 11: Verify PROMPT_COMPILER_DATA_DIR resolution."""
        with patch.dict(
            os.environ,
            {
                "PROMPT_COMPILER_DATA_DIR": "/custom/prompt_compiler_data",
                "APP_DATA_DIR": "/fallback/data",
            },
        ):
            data_dir = _resolve_data_dir()
            self.assertEqual(data_dir, "/custom/prompt_compiler_data")
            db_url = _resolve_database_url()
            self.assertEqual(
                db_url,
                "sqlite:////custom/prompt_compiler_data/prompt_compiler.db",
            )

    def test_explicit_database_url_takes_precedence_over_data_dir(self) -> None:
        """Requirement 11: Explicit DATABASE_URL overrides automatic data directory database path."""
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "sqlite:////explicit/location.db",
                "APP_DATA_DIR": "/ignored/data",
            },
        ):
            db_url = _resolve_database_url()
            self.assertEqual(db_url, "sqlite:////explicit/location.db")

    def test_desktop_host_and_port_configuration(self) -> None:
        """Requirement 8 & 11: Verify desktop host and port settings can be configured cleanly."""
        settings_test = Settings(
            DESKTOP_BACKEND_HOST="127.0.0.1",
            DESKTOP_BACKEND_PORT=9000,
            DESKTOP_MODE=True,
        )
        self.assertEqual(settings_test.desktop_backend_host, "127.0.0.1")
        self.assertEqual(settings_test.desktop_backend_port, 9000)
        self.assertTrue(settings_test.desktop_mode)


class TestProcessLifecycleGracefulShutdown(unittest.TestCase):
    """TEST CATEGORY 6: Process Lifecycle and Graceful Termination."""

    def test_manager_initialization_defaults(self) -> None:
        """Verify DesktopBackendManager initializes with clean defaults."""
        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        self.assertEqual(manager.base_url, "http://127.0.0.1:8000")
        self.assertEqual(manager.health_url, "http://127.0.0.1:8000/api/health")
        self.assertEqual(manager.runtime_status_url, "http://127.0.0.1:8000/api/runtime/status")
        self.assertFalse(manager.is_running())

    def test_manager_shutdown_terminates_gracefully(self) -> None:
        """Requirement 16: Verify shutdown calls terminate() and handles clean exit."""
        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]  # Initially running, then terminated
        manager.process = mock_proc

        result = manager.shutdown(timeout=1.0)
        self.assertTrue(result)
        mock_proc.terminate.assert_called_once()
        self.assertIsNone(manager.process)

    def test_manager_shutdown_fallback_to_kill_on_timeout(self) -> None:
        """Requirement 16: Verify shutdown falls back to kill() if graceful exit times out."""
        manager = DesktopBackendManager(host="127.0.0.1", port=8000)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="uvicorn", timeout=1.0), 0]
        manager.process = mock_proc

        result = manager.shutdown(timeout=1.0)
        self.assertTrue(result)
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()
        self.assertIsNone(manager.process)


class TestSecurityInDesktopMode(unittest.TestCase):
    """TEST CATEGORY 7: Security Boundary & Authentication Enforcement in Desktop Mode."""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_desktop_mode_does_not_bypass_authentication(self) -> None:
        """Requirement 16, 20, 21: Verify authentication is strictly enforced on business endpoints."""
        # Unauthenticated request to /api/projects must return 401 Unauthorized
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 401)
        self.assertIn("WWW-Authenticate", response.headers)

        # Unauthenticated request to /api/compile must return 401 Unauthorized
        response = self.client.post("/api/compile", json={"input": "Test compile"})
        self.assertEqual(response.status_code, 401)

        # Unauthenticated request to /api/interview/start must return 401 Unauthorized
        response = self.client.post("/api/interview/start", json={"input": "Test interview"})
        self.assertEqual(response.status_code, 401)

    def test_desktop_mode_preserves_public_endpoints(self) -> None:
        """Verify health, runtime status, and presets remain accessible without auth."""
        # Health
        resp_health = self.client.get("/api/health")
        self.assertEqual(resp_health.status_code, 200)

        # Runtime Status
        resp_status = self.client.get("/api/runtime/status")
        self.assertEqual(resp_status.status_code, 200)

        # Presets
        resp_presets = self.client.get("/api/presets")
        self.assertEqual(resp_presets.status_code, 200)

    def test_user_ownership_cross_user_anti_probing_404_preserved(self) -> None:
        """Requirement 17 & 20: Verify anti-probing 404 security applies strictly."""
        # Set up mock users
        user_a = UserRecord(id=101, clerk_user_id="user_a_clerk")
        user_b = UserRecord(id=102, clerk_user_id="user_b_clerk")

        # Create project under User A
        app.dependency_overrides[get_current_user] = lambda: user_a
        create_resp = self.client.post("/api/projects", json={"name": "User A Secure Project"})
        self.assertEqual(create_resp.status_code, 201)
        proj_id = create_resp.json()["project_id"]

        # Switch to User B
        app.dependency_overrides[get_current_user] = lambda: user_b

        # Attempt to access User A's project as User B -> must return 404 Not Found (anti-probing)
        get_resp = self.client.get(f"/api/projects/{proj_id}")
        self.assertEqual(get_resp.status_code, 404)

        # Attempt to compile with User A's project as User B -> must return 404 Not Found
        comp_resp = self.client.post("/api/compile", json={"input": "Compile", "project_id": proj_id})
        self.assertEqual(comp_resp.status_code, 404)

        # Clean up overrides
        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
