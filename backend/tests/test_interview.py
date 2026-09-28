"""Unit and integration tests for Prompt Interview Mode."""

import unittest
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from app.ai.ollama import (
    OllamaClient,
    OllamaConnectionError,
    OllamaTimeoutError,
)
from app.api.compile import (
    get_ollama_client,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_interviewer,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)
from app.engine.critic import PromptCritic, ValidationIssue, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.interviewer import (
    InvalidAnswerError,
    InterviewSession,
    InterviewSessionStore,
    PromptInterviewer,
    SessionCompletedError,
    SessionNotFoundError,
)
from app.engine.refiner import PromptRefiner, RefinementResult
from app.engine.requirements import (
    EmptyInputError,
    RequirementAnalysis,
    RequirementEngine,
)
from app.main import app
from app.schemas.interview import (
    InterviewAnswer,
    InterviewAnswerRequest,
    InterviewQuestion,
    InterviewStartRequest,
)
from app.templates.selector import TemplateSelector


class TestPromptInterviewerUnit(unittest.IsolatedAsyncioTestCase):
    """Unit tests for the PromptInterviewer engine component."""

    def setUp(self) -> None:
        self.store = InterviewSessionStore(ttl_seconds=3600.0)
        self.interviewer = PromptInterviewer(
            ollama_client=None,
            session_store=self.store,
            max_questions_per_turn=3,
            max_turns=3,
        )

    async def test_filter_material_missing_topics_excludes_confirmed(self) -> None:
        """TEST 1: Confirmed requirements are not asked about again."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website with React and Tailwind deployed on Vercel",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "Tailwind CSS", "Vercel"],
            missing_information=["frontend framework", "styling library", "deployment platform", "database"],
            constraints=[],
            assumptions=[],
        )
        candidates = self.interviewer._filter_material_missing_topics(analysis, already_asked=set())
        # React, Tailwind, and Vercel are confirmed, so only database should remain
        self.assertEqual(len(candidates), 1)
        self.assertIn("database", candidates[0].lower())

    async def test_filter_material_missing_topics_excludes_already_asked(self) -> None:
        """TEST 2: Topics that were already asked in previous turns are not repeated."""
        analysis = RequirementAnalysis(
            intent="Build an e-commerce backend",
            task_type="build",
            domain="backend",
            confirmed_requirements=["REST API"],
            missing_information=["database storage", "authentication method"],
            constraints=[],
            assumptions=[],
        )
        candidates = self.interviewer._filter_material_missing_topics(
            analysis, already_asked={"database"}
        )
        self.assertEqual(len(candidates), 1)
        self.assertIn("auth", candidates[0].lower())

    async def test_max_questions_per_turn_strictly_bounded(self) -> None:
        """TEST 3: Never returns more than max_questions_per_turn."""
        analysis = RequirementAnalysis(
            intent="Build a large portal",
            task_type="build",
            domain="web development",
            confirmed_requirements=[],
            missing_information=[
                "deployment platform",
                "authentication method",
                "database storage",
                "styling framework",
                "primary framework",
            ],
            constraints=[],
            assumptions=[],
        )
        questions = await self.interviewer.generate_questions_async(
            analysis=analysis,
            already_asked=set(),
            use_llm=False,
        )
        self.assertLessEqual(len(questions), 3)

    async def test_start_session_no_missing_info_immediately_ready(self) -> None:
        """TEST 4: Starting a session with no missing information results in status='ready' and 0 questions."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio with React, Tailwind, Vercel, Supabase Auth, PostgreSQL",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "Tailwind", "Vercel", "Supabase Auth", "PostgreSQL"],
            missing_information=[],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        session = await self.interviewer.start_session_async(
            input_text="Complete specification input",
            requirement_engine=mock_req_engine,
            use_llm=False,
        )
        self.assertEqual(session.status, "ready")
        self.assertEqual(session.questions, [])

    async def test_start_session_with_missing_info_creates_questions(self) -> None:
        """TEST 5: Starting a session with missing information creates questions and in_progress status."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=[],
            missing_information=["deployment platform", "authentication method"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        session = await self.interviewer.start_session_async(
            input_text="Build a portfolio website",
            requirement_engine=mock_req_engine,
            use_llm=False,
        )
        self.assertEqual(session.status, "in_progress")
        self.assertEqual(len(session.questions), 2)
        self.assertEqual(session.turn, 1)

    async def test_answers_update_requirements_and_remove_missing(self) -> None:
        """TEST 6: Submitting concrete answers updates confirmed_requirements and removes them from missing_information."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["Portfolio site"],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        session = await self.interviewer.start_session_async(
            input_text="Build a portfolio website",
            requirement_engine=mock_req_engine,
            use_llm=False,
        )
        self.assertEqual(len(session.questions), 1)
        q_id = session.questions[0].id

        updated_session = await self.interviewer.submit_answers_async(
            session_id=session.session_id,
            answers=[InterviewAnswer(question_id=q_id, answer="Vercel")],
            use_llm=False,
        )

        # Confirm Vercel was added to confirmed_requirements
        confirmed_strs = " ".join(updated_session.current_analysis.confirmed_requirements)
        self.assertIn("Vercel", confirmed_strs)
        # Confirm deployment is no longer in missing_information
        self.assertEqual(len(updated_session.current_analysis.missing_information), 0)
        # Session should now be ready
        self.assertEqual(updated_session.status, "ready")

    async def test_leave_unspecified_does_not_invent_answers(self) -> None:
        """TEST 7: User choosing 'Leave unspecified' does NOT invent a technology."""
        analysis = RequirementAnalysis(
            intent="Build an internal API",
            task_type="build",
            domain="backend",
            confirmed_requirements=["REST API"],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        session = await self.interviewer.start_session_async(
            input_text="Build an internal API",
            requirement_engine=mock_req_engine,
            use_llm=False,
        )
        q_id = session.questions[0].id

        updated_session = await self.interviewer.submit_answers_async(
            session_id=session.session_id,
            answers=[InterviewAnswer(question_id=q_id, answer="Leave unspecified")],
            use_llm=False,
        )

        # Must NOT add Vercel, AWS, or any invented tech to confirmed_requirements
        confirmed_text = " ".join(updated_session.current_analysis.confirmed_requirements)
        self.assertNotIn("Vercel", confirmed_text)
        self.assertNotIn("AWS", confirmed_text)
        # Must record that the user left it unspecified in assumptions
        assumption_text = " ".join(updated_session.current_analysis.assumptions)
        self.assertIn("unspecified", assumption_text.lower())
        self.assertEqual(updated_session.status, "ready")

    async def test_completed_session_rejects_further_answers(self) -> None:
        """TEST 8: Submitting answers to a completed session raises SessionCompletedError."""
        analysis = RequirementAnalysis(
            intent="Build app",
            task_type="build",
            domain="general",
            confirmed_requirements=["complete"],
            missing_information=[],
            constraints=[],
            assumptions=[],
        )
        session = InterviewSession(
            original_input="Build app",
            current_analysis=analysis,
            questions=[],
            status="ready",
        )
        await self.store.save(session)

        with self.assertRaises(SessionCompletedError):
            await self.interviewer.submit_answers_async(
                session_id=session.session_id,
                answers=[InterviewAnswer(question_id="q1", answer="Vercel")],
            )

    async def test_invalid_question_id_raises_invalid_answer_error(self) -> None:
        """TEST 9: Answering a non-existent question ID raises InvalidAnswerError."""
        analysis = RequirementAnalysis(
            intent="Build app",
            task_type="build",
            domain="general",
            confirmed_requirements=[],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        session = await self.interviewer.start_session_async(
            input_text="Build app",
            requirement_engine=mock_req_engine,
            use_llm=False,
        )
        with self.assertRaises(InvalidAnswerError):
            await self.interviewer.submit_answers_async(
                session_id=session.session_id,
                answers=[InterviewAnswer(question_id="unknown_q", answer="Vercel")],
            )

    async def test_session_store_not_found(self) -> None:
        """TEST 10: Unknown session raises SessionNotFoundError."""
        with self.assertRaises(SessionNotFoundError):
            await self.store.get("non-existent-uuid")


class TestInterviewAPI(unittest.TestCase):
    """Integration test suite for the Interview API endpoints."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides.clear()

        # Set up an isolated interviewer engine for the test
        self.store = InterviewSessionStore()
        self.interviewer = PromptInterviewer(
            ollama_client=None,
            session_store=self.store,
            max_questions_per_turn=3,
            max_turns=3,
        )
        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_interview")
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_prompt_interviewer] = lambda: self.interviewer

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_interview_mode_disabled_default_compile_works(self) -> None:
        """TEST 1: /api/compile works normally when interview_mode is false or omitted."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React"],
            missing_information=["hosting"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild a portfolio website.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        # interview_mode omitted (default False)
        resp = self.client.post("/api/compile", json={"input": "Build a portfolio website"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Build a portfolio website", data["result"])
        self.assertIsNone(data.get("interview_session_id"))

    def test_start_interview_with_missing_info(self) -> None:
        """TEST 2: POST /api/interview/start creates a session and returns questions."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a personal portfolio",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio"],
            missing_information=["deployment platform", "database persistence"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        resp = self.client.post("/api/interview/start", json={"input": "Build a personal portfolio"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("session_id", data)
        self.assertEqual(data["status"], "in_progress")
        self.assertGreaterEqual(len(data["questions"]), 1)
        self.assertLessEqual(len(data["questions"]), 3)
        self.assertEqual(data["turn"], 1)

    def test_start_interview_no_missing_info_is_ready(self) -> None:
        """TEST 3: POST /api/interview/start with complete info returns status='ready' and 0 questions."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a React portfolio on Vercel with Tailwind",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "Vercel", "Tailwind"],
            missing_information=[],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        resp = self.client.post("/api/interview/start", json={"input": "Build a React portfolio on Vercel with Tailwind"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["questions"], [])

    def test_submit_answers_and_progress(self) -> None:
        """TEST 4: POST /api/interview/{session_id}/answer records answers and reaches ready state."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio"],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        start_resp = self.client.post("/api/interview/start", json={"input": "Build a portfolio website"})
        session_id = start_resp.json()["session_id"]
        q_id = start_resp.json()["questions"][0]["id"]

        # Submit answer
        ans_resp = self.client.post(
            f"/api/interview/{session_id}/answer",
            json={"answers": [{"question_id": q_id, "answer": "Vercel"}]},
        )
        self.assertEqual(ans_resp.status_code, 200)
        data = ans_resp.json()
        self.assertEqual(data["status"], "ready")
        confirmed_strs = " ".join(data["requirements"]["confirmed_requirements"])
        self.assertIn("Vercel", confirmed_strs)

    def test_get_interview_session(self) -> None:
        """TEST 5: GET /api/interview/{session_id} retrieves session details."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build app",
            task_type="build",
            domain="general",
            confirmed_requirements=[],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        start_resp = self.client.post("/api/interview/start", json={"input": "Build app"})
        session_id = start_resp.json()["session_id"]

        get_resp = self.client.get(f"/api/interview/{session_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["session_id"], session_id)

    def test_compile_from_interview_session(self) -> None:
        """TEST 6: POST /api/interview/{session_id}/compile compiles using clarified requirements."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio"],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        start_resp = self.client.post("/api/interview/start", json={"input": "Build a portfolio website"})
        session_id = start_resp.json()["session_id"]
        q_id = start_resp.json()["questions"][0]["id"]

        # Submit answer to become ready
        self.client.post(
            f"/api/interview/{session_id}/answer",
            json={"answers": [{"question_id": q_id, "answer": "Vercel"}]},
        )

        # Mock compiler pipeline dependencies
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild a portfolio website deployed on Vercel.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        compile_resp = self.client.post(f"/api/interview/{session_id}/compile")
        self.assertEqual(compile_resp.status_code, 200)
        data = compile_resp.json()
        self.assertIn("Vercel", data["result"])
        self.assertEqual(data["interview_session_id"], session_id)

    def test_compile_api_with_interview_session_id(self) -> None:
        """TEST 7: POST /api/compile accepts interview_session_id to compile directly from clarified state."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React"],
            missing_information=["deployment platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        start_resp = self.client.post("/api/interview/start", json={"input": "Build a portfolio website"})
        session_id = start_resp.json()["session_id"]
        q_id = start_resp.json()["questions"][0]["id"]

        self.client.post(
            f"/api/interview/{session_id}/answer",
            json={"answers": [{"question_id": q_id, "answer": "Netlify"}]},
        )

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild a portfolio website deployed on Netlify.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        resp = self.client.post(
            "/api/compile",
            json={"input": "Build a portfolio website", "interview_session_id": session_id},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Netlify", data["result"])
        self.assertEqual(data["interview_session_id"], session_id)

    def test_compile_api_interview_mode_without_session_returns_400(self) -> None:
        """TEST 8: POST /api/compile with interview_mode=True and no session_id returns 400 Bad Request."""
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build something", "interview_mode": True},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("interview mode requested", resp.json()["detail"].lower())

    def test_unknown_session_returns_404(self) -> None:
        """TEST 9: Non-existent session returns 404 for answer, get, and compile endpoints."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp_ans = self.client.post(
            f"/api/interview/{fake_id}/answer",
            json={"answers": [{"question_id": "q1", "answer": "AWS"}]},
        )
        self.assertEqual(resp_ans.status_code, 404)

        resp_get = self.client.get(f"/api/interview/{fake_id}")
        self.assertEqual(resp_get.status_code, 404)

        resp_compile = self.client.post(f"/api/interview/{fake_id}/compile")
        self.assertEqual(resp_compile.status_code, 404)

    def test_empty_input_rejected_on_start(self) -> None:
        """TEST 10: Empty or whitespace input on /api/interview/start returns 422."""
        resp = self.client.post("/api/interview/start", json={"input": "   "})
        self.assertEqual(resp.status_code, 422)

    def test_ollama_failure_propagates_cleanly(self) -> None:
        """TEST 11: Ollama failure during start returns 503 Service Unavailable."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            side_effect=OllamaConnectionError("Connection refused")
        )
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        resp = self.client.post("/api/interview/start", json={"input": "Build something"})
        self.assertEqual(resp.status_code, 503)

    def test_health_endpoint_still_passing(self) -> None:
        """TEST 12: GET /api/health still passes with status 'ok'."""
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
