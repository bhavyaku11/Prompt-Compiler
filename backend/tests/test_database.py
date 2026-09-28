"""Tests for SQLite persistence foundation, models, repositories, and API integration."""

import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.config import Settings, settings
from app.database.base import Base
from app.database.models import (
    CompilationRecord,
    InterviewSessionRecord,
    RequirementAnalysisRecord,
)
from app.database.repositories import (
    CompilationRepository,
    InterviewSessionRepository,
    RequirementAnalysisRepository,
)
from app.database.session import (
    get_engine,
    get_session_factory,
    init_db,
    reset_db_engine,
)
from app.api.compile import (
    get_compilation_repository,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_interviewer,
    get_requirement_engine,
)
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.interviewer import InterviewSession, PromptInterviewer, SqliteInterviewSessionStore
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.api import CompileRequest
from app.schemas.interview import (
    InterviewAnswer,
    InterviewAnswerRequest,
    InterviewQuestion,
    InterviewSessionResponse,
    InterviewStartRequest,
)


class TestDatabaseFoundation(unittest.TestCase):
    """Test database initialization, table creation, and engine setup."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_prompt_compiler.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()

    def tearDown(self):
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_database_initialization_and_tables(self):
        """TEST 1 & 2: Database initializes successfully and tables are created."""
        engine = init_db(self.db_url)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        self.assertIn("interview_sessions", table_names)
        self.assertIn("requirement_analyses", table_names)
        self.assertIn("compilations", table_names)

        # Verify WAL mode is set on SQLite connection
        with engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            self.assertEqual(journal_mode.lower(), "wal")


class TestRepositories(unittest.TestCase):
    """Test repository CRUD operations, transactions, and domain mapping."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_prompt_compiler.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        init_db(self.db_url)
        self.interview_repo = InterviewSessionRepository(database_url=self.db_url)
        self.req_repo = RequirementAnalysisRepository(database_url=self.db_url)
        self.comp_repo = CompilationRepository(database_url=self.db_url)

    def tearDown(self):
        reset_db_engine()
        self.temp_dir.cleanup()

    def _sample_analysis(self, intent: str = "Build an auth system") -> RequirementAnalysis:
        return RequirementAnalysis(
            intent=intent,
            task_type="backend_api",
            domain="security",
            confirmed_requirements=["JWT auth", "Token refresh endpoint"],
            missing_information=["Token TTL duration"],
            constraints=["Stateless auth"],
            assumptions=["Use HMAC SHA256"],
        )

    def _sample_session(self, session_id: str = "test-session-123") -> InterviewSession:
        return InterviewSession(
            session_id=session_id,
            original_input="Build a JWT authentication system",
            status="in_progress",
            turn=1,
            unresolved_topics=["Token TTL duration"],
            asked_topics=["Token TTL duration"],
            questions=[
                InterviewQuestion(
                    id="q1",
                    topic="Token TTL duration",
                    question="What should the access token lifespan be?",
                    options=["15 minutes", "1 hour", "24 hours"],
                    allow_custom=True,
                )
            ],
            answers={},
            current_analysis=self._sample_analysis(),
        )

    def test_interview_session_crud(self):
        """TEST 3, 4, 5: Interview session can be inserted, retrieved, and updated."""
        session = self._sample_session()
        created = self.interview_repo.create(session)
        self.assertEqual(created.session_id, session.session_id)

        # Retrieve
        retrieved = self.interview_repo.get_by_session_id(session.session_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.session_id, session.session_id)
        self.assertEqual(retrieved.original_input, session.original_input)
        self.assertEqual(retrieved.status, "in_progress")
        self.assertEqual(len(retrieved.questions), 1)
        self.assertEqual(retrieved.questions[0].topic, "Token TTL duration")
        self.assertEqual(retrieved.current_analysis.domain, "security")

        # Update
        session.turn = 2
        session.status = "ready"
        session.answers["q1"] = "15 minutes"
        updated = self.interview_repo.update(session)
        self.assertEqual(updated.status, "ready")
        self.assertEqual(updated.turn, 2)
        self.assertEqual(len(updated.answers), 1)

        # Verify updated persistence
        refetched = self.interview_repo.get_by_session_id(session.session_id)
        self.assertEqual(refetched.status, "ready")
        self.assertEqual(len(refetched.answers), 1)
        self.assertEqual(refetched.answers["q1"], "15 minutes")

    def test_requirement_analysis_persists(self):
        """TEST 6: RequirementAnalysis persists and is retrievable."""
        analysis = self._sample_analysis()
        record = self.req_repo.save(analysis, interview_session_id="session-xyz")
        self.assertIsNotNone(record.id)
        self.assertEqual(record.intent, analysis.intent)
        self.assertEqual(record.confirmed_requirements, analysis.confirmed_requirements)

        # Retrieve by session id
        retrieved = self.req_repo.get_by_session_id("session-xyz")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.intent, analysis.intent)
        self.assertEqual(retrieved.task_type, "backend_api")

    def test_compilation_record_persists(self):
        """TEST 7: CompilationRecord persists and is retrievable."""
        record = self.comp_repo.save(
            input_text="Generate login API",
            compiled_prompt="Implement POST /login with email and password...",
            task_type="backend_api",
            template_name="backend_api_prompt_template",
            requirements_summary={"intent": "User login"},
            validation_summary={"overall_valid": True},
            refinement_attempts=1,
            interview_session_id="session-xyz",
        )
        self.assertIsNotNone(record.id)
        self.assertEqual(record.task_type, "backend_api")
        self.assertEqual(record.interview_session_id, "session-xyz")

        # Retrieve by id
        fetched = self.comp_repo.get_by_id(record.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.input_text, "Generate login API")
        self.assertEqual(fetched.refinement_attempts, 1)

        # List recent
        recent = self.comp_repo.list_recent(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].id, record.id)

    def test_interview_session_survives_repository_recreation(self):
        """TEST 8: Interview session survives repository recreation."""
        session = self._sample_session("survive-repo-test")
        self.interview_repo.create(session)

        # Recreate repository instance
        new_repo = InterviewSessionRepository(database_url=self.db_url)
        restored = new_repo.get_by_session_id("survive-repo-test")
        self.assertIsNotNone(restored)
        self.assertEqual(restored.session_id, "survive-repo-test")
        self.assertEqual(restored.original_input, session.original_input)

    def test_interview_session_survives_application_restart_simulation(self):
        """TEST 9: Interview session survives simulated backend process restart."""
        session = self._sample_session("restart-sim-session")
        self.interview_repo.create(session)

        # Also persist a requirement analysis record
        self.req_repo.save(session.current_analysis, interview_session_id=session.session_id)

        # SIMULATE COMPLETE BACKEND RESTART:
        # 1. Reset global database engine & connection pool
        reset_db_engine()
        del self.interview_repo
        del self.req_repo

        # 2. Re-initialize database layer as if application startup lifespan runs
        new_engine = init_db(self.db_url)
        fresh_interview_repo = InterviewSessionRepository(database_url=self.db_url)
        fresh_req_repo = RequirementAnalysisRepository(database_url=self.db_url)

        # 3. Retrieve session and requirement analysis
        restored_session = fresh_interview_repo.get_by_session_id("restart-sim-session")
        self.assertIsNotNone(restored_session)
        self.assertEqual(restored_session.session_id, "restart-sim-session")
        self.assertEqual(restored_session.current_analysis.intent, session.current_analysis.intent)
        self.assertEqual(len(restored_session.questions), 1)
        self.assertEqual(restored_session.questions[0].topic, "Token TTL duration")

        restored_analysis = fresh_req_repo.get_by_session_id("restart-sim-session")
        self.assertIsNotNone(restored_analysis)
        self.assertEqual(restored_analysis.intent, session.current_analysis.intent)

    def test_database_rollback_on_failure(self):
        """TEST 16: Database rollback works correctly after a persistence failure."""
        session_factory = get_session_factory(self.db_url)
        
        # Test intentional rollback on error in session context
        try:
            with session_factory() as session:
                rec = CompilationRecord(
                    input_text="Rollback test",
                    compiled_prompt="Prompt content",
                )
                session.add(rec)
                session.flush()
                # Simulate error before commit
                raise RuntimeError("Simulated transaction failure")
        except RuntimeError:
            pass

        # Assert no records were committed
        with session_factory() as session:
            count = session.query(CompilationRecord).filter_by(input_text="Rollback test").count()
            self.assertEqual(count, 0)

    def test_ttl_cleanup_removes_expired_sessions(self):
        """TEST 19: TTL/expiration cleanup works as expected."""
        session = self._sample_session("expired-session")
        # Save with negative TTL so it is immediately expired
        self.interview_repo.create(session, ttl_seconds=-10)

        # Verify it exists initially when bypassing TTL check
        active = self.interview_repo.get("expired-session", check_ttl=False)
        self.assertIsNotNone(active)

        # Run cleanup
        deleted = self.interview_repo.cleanup_expired()
        self.assertEqual(deleted, 1)

        # Verify it no longer exists
        after_cleanup = self.interview_repo.get("expired-session", check_ttl=False)
        self.assertIsNone(after_cleanup)


class TestAPIWithPersistence(unittest.TestCase):
    """Test API integration with SQLite persistence."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_api_prompt_compiler.db")
        self.db_url = f"sqlite:///{self.db_path}"
        # Patch settings database URL property
        self.settings_patcher = patch.object(Settings, "DATABASE_URL", self.db_url)
        self.settings_patcher.start()
        
        reset_db_engine()
        init_db(self.db_url)
        
        # Use clean sqlite store in interviewer
        self.store = SqliteInterviewSessionStore(database_url=self.db_url)
        self.interviewer = PromptInterviewer(store=self.store)
        self.compilation_repo = CompilationRepository(database_url=self.db_url)

        from app.api.compile import get_compilation_repository, get_prompt_interviewer
        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="legacy_local_user")
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_prompt_interviewer] = lambda: self.interviewer
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.settings_patcher.stop()
        reset_db_engine()
        self.temp_dir.cleanup()

    def _sample_analysis(self) -> RequirementAnalysis:
        return RequirementAnalysis(
            intent="Build an email notification worker",
            task_type="build",
            domain="messaging",
            confirmed_requirements=["SMTP support"],
            missing_information=["deployment"],
            constraints=["Async processing"],
            assumptions=["Use Redis queue"],
        )

    def test_interview_start_and_get_endpoints_persist(self):
        """TEST 10 & 12: Interview start endpoint persists session and GET retrieves it."""
        analysis = self._sample_analysis()
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        # 1. Start interview
        response = self.client.post(
            "/api/interview/start",
            json={"input": "Build an email notification worker"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        session_id = data["session_id"]
        self.assertEqual(data["status"], "in_progress")
        self.assertEqual(data["turn"], 1)

        # 2. Verify directly from SQLite repository
        repo = InterviewSessionRepository(database_url=self.db_url)
        persisted = repo.get_by_session_id(session_id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.session_id, session_id)
        self.assertEqual(persisted.original_input, "Build an email notification worker")

        # 3. GET /api/interview/{session_id} retrieves persisted state
        get_resp = self.client.get(f"/api/interview/{session_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["session_id"], session_id)

    def test_interview_answer_endpoint_persists_updates(self):
        """TEST 11: Interview answer endpoint persists updated answers."""
        analysis = self._sample_analysis()
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        # Start session
        start_resp = self.client.post(
            "/api/interview/start",
            json={"input": "Build an email notification worker"},
        )
        self.assertEqual(start_resp.status_code, 200)
        session_id = start_resp.json()["session_id"]
        q_id = start_resp.json()["questions"][0]["id"]

        # Submit answer
        ans_resp = self.client.post(
            f"/api/interview/{session_id}/answer",
            json={
                "answers": [
                    {
                        "question_id": q_id,
                        "topic": "deployment",
                        "answer": "Deploy with Docker",
                    }
                ]
            },
        )
        self.assertEqual(ans_resp.status_code, 200)
        self.assertEqual(ans_resp.json()["status"], "ready")

        # Verify persisted in SQLite
        repo = InterviewSessionRepository(database_url=self.db_url)
        persisted = repo.get_by_session_id(session_id)
        self.assertEqual(persisted.status, "ready")
        self.assertEqual(len(persisted.answers), 1)
        self.assertEqual(persisted.answers[q_id], "Deploy with Docker")

    def test_interview_compile_persists_compilation_record(self):
        """TEST 13: Interview compile endpoint persists a CompilationRecord."""
        # Pre-seed a ready session
        session = InterviewSession(
            session_id="ready-session-123",
            original_input="Build email sender",
            status="ready",
            turn=1,
            unresolved_topics=[],
            asked_topics=[],
            questions=[],
            answers={},
            current_analysis=self._sample_analysis(),
            user_id=self.test_user.id,
        )
        repo = InterviewSessionRepository(database_url=self.db_url)
        repo.create(session)

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="Compiled prompt output for email worker",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(return_value=ValidationResult(overall_valid=True))
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        compile_resp = self.client.post("/api/interview/ready-session-123/compile")
        self.assertEqual(compile_resp.status_code, 200)
        data = compile_resp.json()
        self.assertEqual(data["interview_session_id"], "ready-session-123")

        # Verify CompilationRecord exists in database
        records = self.compilation_repo.list_recent(limit=5)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].interview_session_id, "ready-session-123")
        self.assertEqual(records[0].input_text, "Build email sender")

        # Verify session status is updated to 'compiled' in SQLite
        updated_session = repo.get_by_session_id("ready-session-123")
        self.assertEqual(updated_session.status, "compiled")

    def test_post_compile_persists_compilation_record(self):
        """TEST 14 & 15: POST /api/compile persists record and remains backward compatible."""
        analysis = self._sample_analysis()
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="Compiled prompt output for standalone compilation",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(return_value=ValidationResult(overall_valid=True))
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        response = self.client.post(
            "/api/compile",
            json={"input": "Build a worker process"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertIn("requirements", data)
        self.assertIn("validation", data)

        # Verify CompilationRecord exists in DB
        records = self.compilation_repo.list_recent(limit=5)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].input_text, "Build a worker process")
        self.assertEqual(records[0].compiled_prompt, "Compiled prompt output for standalone compilation")

    def test_unknown_session_returns_404(self):
        """TEST 17: Unknown session returns 404."""
        response = self.client.get("/api/interview/non-existent-session-id")
        self.assertEqual(response.status_code, 404)

    def test_completed_session_returns_409_on_answer(self):
        """TEST 18: Completed/ready session returns 409 on further answers."""
        session = InterviewSession(
            session_id="already-ready-session",
            original_input="Build email sender",
            status="ready",
            turn=1,
            unresolved_topics=[],
            asked_topics=[],
            questions=[],
            answers={},
            current_analysis=self._sample_analysis(),
            user_id=self.test_user.id,
        )
        repo = InterviewSessionRepository(database_url=self.db_url)
        repo.create(session)

        response = self.client.post(
            "/api/interview/already-ready-session/answer",
            json={"answers": [{"question_id": "q1", "topic": "t", "answer": "a"}]},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
