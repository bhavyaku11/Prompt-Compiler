"""Unit and integration tests for agent-specific formatting presets (Task 19)."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.testclient import TestClient

from app.database.session import get_engine, get_session_factory
from app.engine.agent_formatter import AgentFormatter
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.interviewer import PromptInterviewer
from app.engine.project_memory import ProjectMemoryService
from app.engine.refiner import PromptRefiner, RefinementResult
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.agent_preset import AgentPreset, AgentTarget, SUPPORTED_AGENTS
from app.schemas.api import CompileRequest, CompileResponse
from app.schemas.interview import InterviewStartRequest
from app.schemas.project import ProjectContext
from app.templates.agent_presets import (
    AgentPresetRegistry,
    UnsupportedAgentPresetError,
    get_preset,
    is_supported,
    list_presets,
    validate_agent,
)
from app.api.compile import (
    get_agent_formatter,
    get_compilation_repository,
    get_project_service,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_interviewer,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)


class TestAgentPresetsUnit(unittest.TestCase):
    """Unit tests for agent preset registry, schemas, and deterministic formatter."""

    def setUp(self) -> None:
        self.formatter = AgentFormatter()
        self.sample_analysis = RequirementAnalysis(
            intent="Build an interactive analytics dashboard",
            task_type="build",
            domain="finance",
            confirmed_requirements=[
                "Use React for frontend",
                "Use FastAPI for backend",
                "Use PostgreSQL for storage",
                "Implement JWT authentication",
            ],
            constraints=[
                "Do not use Docker in production",
                "All endpoints must use type hints",
            ],
            missing_information=["Theme preference"],
            assumptions=["Assume modern evergreen browsers"],
        )
        self.sample_prompt = (
            "# Objective\n"
            "Build an interactive analytics dashboard for financial transactions.\n\n"
            "# Technical Domain & Context\n"
            "Financial technology web platform.\n\n"
            "# Confirmed Requirements\n"
            "- Use React for frontend\n"
            "- Use FastAPI for backend\n"
            "- Use PostgreSQL for storage\n"
            "- Implement JWT authentication\n\n"
            "# Constraints\n"
            "- Do not use Docker in production\n"
            "- All endpoints must use type hints\n\n"
            "# Open Decisions & Missing Information\n"
            "- Theme preference (Open Decision)\n\n"
            "# Safe Assumptions\n"
            "- Assume modern evergreen browsers\n\n"
            "# Implementation Instructions\n"
            "1. Initialize React repository\n"
            "2. Create FastAPI auth routers\n"
            "3. Setup PostgreSQL connection pool\n\n"
            "# Expected Outcome\n"
            "Fully functioning financial dashboard passing all unit tests."
        )

    def test_preset_registry_has_all_five_presets(self) -> None:
        """TEST 1: Preset registry contains generic, cursor, claude_code, cline, and windsurf."""
        presets = list_presets()
        preset_ids = [p.id for p in presets]
        expected = ["generic", "cursor", "claude_code", "cline", "windsurf"]
        for exp in expected:
            self.assertIn(exp, preset_ids)
        self.assertEqual(len(presets), 5)

    def test_validate_agent_normalizes_and_rejects_unknown(self) -> None:
        """TEST 2: validate_agent normalizes valid inputs and rejects unknown agent IDs cleanly."""
        self.assertEqual(validate_agent("cursor"), "cursor")
        self.assertEqual(validate_agent("CURSOR"), "cursor")
        self.assertEqual(validate_agent("  claude_code  "), "claude_code")
        self.assertEqual(validate_agent(None), "generic")
        self.assertEqual(validate_agent(""), "generic")

        with self.assertRaises(UnsupportedAgentPresetError) as ctx:
            validate_agent("unknown_agent_xyz")
        self.assertIn("Unsupported target agent 'unknown_agent_xyz'", str(ctx.exception))

    def test_is_supported_check(self) -> None:
        """TEST 3: is_supported accurately validates agents."""
        self.assertTrue(is_supported("generic"))
        self.assertTrue(is_supported("cursor"))
        self.assertTrue(is_supported("claude_code"))
        self.assertTrue(is_supported("cline"))
        self.assertTrue(is_supported("windsurf"))
        self.assertFalse(is_supported("copilot"))
        self.assertFalse(is_supported(None))

    def test_generic_preset_returns_canonical_prompt(self) -> None:
        """TEST 4: Generic preset preserves the canonical compiled prompt without distortion."""
        formatted = self.formatter.format_prompt(
            compiled_prompt=self.sample_prompt,
            target_agent="generic",
            analysis=self.sample_analysis,
        )
        self.assertEqual(formatted, self.sample_prompt)

    def test_cursor_preset_structure_and_semantic_preservation(self) -> None:
        """TEST 5: Cursor preset places Context at the top, followed by Objective, Requirements, and Constraints & Rules."""
        formatted = self.formatter.format_prompt(
            compiled_prompt=self.sample_prompt,
            target_agent="cursor",
            analysis=self.sample_analysis,
        )

        self.assertIn("# Context", formatted)
        self.assertIn("# Objective", formatted)
        self.assertIn("# Requirements", formatted)
        self.assertIn("# Constraints & Rules", formatted)
        self.assertIn("# Implementation Instructions", formatted)
        self.assertIn("# Validation", formatted)

        # Context must appear before Objective in Cursor preset
        context_idx = formatted.index("# Context")
        objective_idx = formatted.index("# Objective")
        self.assertLess(context_idx, objective_idx)

        # Semantic preservation check
        self.assertIn("React", formatted)
        self.assertIn("FastAPI", formatted)
        self.assertIn("PostgreSQL", formatted)
        self.assertIn("JWT authentication", formatted)
        self.assertIn("Do not use Docker in production", formatted)
        self.assertIn("All endpoints must use type hints", formatted)

    def test_claude_code_preset_structure_and_semantic_preservation(self) -> None:
        """TEST 6: Claude Code preset includes explicit Role, Task, Project Context, and Verification."""
        formatted = self.formatter.format_prompt(
            compiled_prompt=self.sample_prompt,
            target_agent="claude_code",
            analysis=self.sample_analysis,
        )

        self.assertIn("# Role", formatted)
        self.assertIn("Act as an expert software engineering agent executing this task in the workspace.", formatted)
        self.assertIn("# Task", formatted)
        self.assertIn("# Project Context", formatted)
        self.assertIn("# Requirements", formatted)
        self.assertIn("# Constraints", formatted)
        self.assertIn("# Implementation Steps", formatted)
        self.assertIn("# Verification", formatted)

        # Semantic preservation check
        self.assertIn("React", formatted)
        self.assertIn("FastAPI", formatted)
        self.assertIn("PostgreSQL", formatted)
        self.assertIn("JWT authentication", formatted)
        self.assertIn("Do not use Docker in production", formatted)

    def test_cline_preset_structure_and_semantic_preservation(self) -> None:
        """TEST 7: Cline preset formats with Task headline, Context, Requirements, and Validation."""
        formatted = self.formatter.format_prompt(
            compiled_prompt=self.sample_prompt,
            target_agent="cline",
            analysis=self.sample_analysis,
        )

        self.assertIn("# Task", formatted)
        self.assertIn("# Context", formatted)
        self.assertIn("# Requirements", formatted)
        self.assertIn("# Constraints", formatted)
        self.assertIn("# Implementation", formatted)
        self.assertIn("# Validation", formatted)

        # Semantic preservation check
        self.assertIn("React", formatted)
        self.assertIn("FastAPI", formatted)
        self.assertIn("PostgreSQL", formatted)

    def test_windsurf_preset_structure_and_semantic_preservation(self) -> None:
        """TEST 8: Windsurf preset formats with Task, Context, Requirements, Implementation, and Verification."""
        formatted = self.formatter.format_prompt(
            compiled_prompt=self.sample_prompt,
            target_agent="windsurf",
            analysis=self.sample_analysis,
        )

        self.assertIn("# Task", formatted)
        self.assertIn("# Context", formatted)
        self.assertIn("# Requirements", formatted)
        self.assertIn("# Constraints", formatted)
        self.assertIn("# Implementation", formatted)
        self.assertIn("# Verification", formatted)

        # Semantic preservation check
        self.assertIn("React", formatted)
        self.assertIn("FastAPI", formatted)
        self.assertIn("PostgreSQL", formatted)

    def test_formatting_is_deterministic(self) -> None:
        """TEST 9: Formatting is completely deterministic across repeated executions."""
        output1 = self.formatter.format_prompt(self.sample_prompt, "cursor", self.sample_analysis)
        output2 = self.formatter.format_prompt(self.sample_prompt, "cursor", self.sample_analysis)
        self.assertEqual(output1, output2)

        output3 = self.formatter.format_prompt(self.sample_prompt, "claude_code", self.sample_analysis)
        output4 = self.formatter.format_prompt(self.sample_prompt, "claude_code", self.sample_analysis)
        self.assertEqual(output3, output4)

    def test_project_context_preserved_and_separated_from_user_requirements(self) -> None:
        """TEST 10: Project context baseline is preserved with clear separation and precedence."""
        from app.schemas.project import Project
        sample_proj = Project(
            project_id="proj_sample",
            name="Core SaaS Backend",
            description="Production payments microservice",
            created_at=1000.0,
            updated_at=1000.0,
        )
        project_context = ProjectContext(
            project=sample_proj,
            technologies=["FastAPI", "PostgreSQL", "Redis"],
            active_constraints=["Must never modify billing table schema directly"],
            coding_rules=["Always use pydantic v2 schemas"],
        )


        for agent in ["cursor", "claude_code", "cline", "windsurf"]:
            formatted = self.formatter.format_prompt(
                compiled_prompt=self.sample_prompt,
                target_agent=agent,
                analysis=self.sample_analysis,
                project_context=project_context,
            )

            # Project baseline must be present
            self.assertIn("=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===", formatted)
            self.assertIn("Must never modify billing table schema directly", formatted)
            self.assertIn("Always use pydantic v2 schemas", formatted)
            self.assertIn("Core SaaS Backend", formatted)

            # User requirements must remain distinct under # Requirements
            req_block_idx = formatted.index("# Requirements")
            self.assertIn("Use React for frontend", formatted[req_block_idx:])


class TestAgentPresetsAPI(unittest.TestCase):
    """API integration tests for agent-specific prompt compilation."""

    def setUp(self) -> None:
        self.test_db_path = f"/tmp/test_agent_presets_{os.getpid()}.db"
        self.db_url = f"sqlite:///{self.test_db_path}"
        self.engine = get_engine(self.db_url)
        self.session_factory = get_session_factory(self.engine)
        self.client = TestClient(app)

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_agent_presets")
        app.dependency_overrides[get_current_user] = lambda: self.test_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except OSError:
                pass

    def test_api_presets_discovery_endpoint(self) -> None:
        """TEST 11: GET /api/presets lists all 5 registered presets."""
        response = self.client.get("/api/presets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 5)
        ids = [p["id"] for p in data]
        self.assertIn("generic", ids)
        self.assertIn("cursor", ids)
        self.assertIn("claude_code", ids)
        self.assertIn("cline", ids)
        self.assertIn("windsurf", ids)

    def test_api_compile_defaults_to_generic(self) -> None:
        """TEST 12: POST /api/compile with omitted target_agent defaults to 'generic'."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build markdown notes",
                task_type="build",
                domain="web",
                confirmed_requirements=["Markdown rendering"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        canonical_prompt = "# Objective\nBuild markdown notes.\n\n# Confirmed Requirements\n- Markdown rendering\n"
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=canonical_prompt,
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(return_value=ValidationResult(overall_valid=True))

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        response = self.client.post("/api/compile", json={"input": "Build markdown notes."})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_agent"], "generic")
        self.assertEqual(data["result"], canonical_prompt)

    def test_api_compile_with_cursor_target_agent(self) -> None:
        """TEST 13: POST /api/compile with target_agent='cursor' formats for Cursor."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build markdown notes",
                task_type="build",
                domain="web",
                confirmed_requirements=["Markdown rendering", "Export to PDF"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=(
                    "# Objective\nBuild markdown notes app.\n\n"
                    "# Confirmed Requirements\n- Markdown rendering\n- Export to PDF\n\n"
                    "# Implementation Instructions\n1. Setup markdown parser\n"
                ),
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
            json={
                "input": "Build markdown notes.",
                "target_agent": "cursor",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_agent"], "cursor")
        self.assertIn("# Context", data["result"])
        self.assertIn("# Objective", data["result"])
        self.assertIn("# Requirements", data["result"])
        self.assertIn("Markdown rendering", data["result"])
        self.assertIn("Export to PDF", data["result"])

    def test_api_compile_with_claude_code_target_agent(self) -> None:
        """TEST 14: POST /api/compile with target_agent='claude_code' formats for Claude Code."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build a fast CLI calculator",
                task_type="build",
                domain="cli",
                confirmed_requirements=["Rust language", "Clap for argument parsing"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=(
                    "# Objective\nBuild a fast CLI calculator.\n\n"
                    "# Confirmed Requirements\n- Rust language\n- Clap for argument parsing\n"
                ),
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
            json={
                "input": "Build a fast CLI calculator.",
                "target_agent": "claude_code",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_agent"], "claude_code")
        self.assertIn("# Role", data["result"])
        self.assertIn("# Task", data["result"])
        self.assertIn("# Requirements", data["result"])
        self.assertIn("Rust language", data["result"])
        self.assertIn("Clap for argument parsing", data["result"])

    def test_api_compile_unknown_agent_rejected_with_422(self) -> None:
        """TEST 15: POST /api/compile with an unsupported target agent returns HTTP 422."""
        response = self.client.post(
            "/api/compile",
            json={
                "input": "Build an app.",
                "target_agent": "unsupported_copilot_preset",
            },
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("Unsupported target agent", str(data))

    def test_api_compile_persists_target_agent_in_compilation_record(self) -> None:
        """TEST 16: CompilationRecord in database persists target_agent."""
        repo = get_compilation_repository()
        record = repo.save(
            input_text="Build something",
            compiled_prompt="# Objective\nSomething",
            task_type="build",
            target_agent="windsurf",
        )
        fetched = repo.get_by_id(record.compilation_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.target_agent, "windsurf")

    def test_interview_start_and_compile_preserves_target_agent(self) -> None:
        """TEST 17: Interview lifecycle stores target_agent and applies preset on interview compile."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build blog platform",
                task_type="build",
                domain="web",
                confirmed_requirements=["Next.js", "Tailwind CSS"],
                missing_information=[],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild blog platform.\n\n# Confirmed Requirements\n- Next.js\n- Tailwind CSS\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(return_value=ValidationResult(overall_valid=True))

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        # Start interview with target_agent='cline'
        start_res = self.client.post(
            "/api/interview/start",
            json={
                "input": "Build a blog platform.",
                "target_agent": "cline",
            },
        )
        self.assertEqual(start_res.status_code, 200)
        session_data = start_res.json()
        self.assertEqual(session_data["target_agent"], "cline")
        session_id = session_data["session_id"]

        # Compile from interview
        compile_res = self.client.post(f"/api/interview/{session_id}/compile")
        self.assertEqual(compile_res.status_code, 200)
        compiled_data = compile_res.json()
        self.assertEqual(compiled_data["target_agent"], "cline")
        self.assertIn("# Task", compiled_data["result"])
        self.assertIn("# Context", compiled_data["result"])
        self.assertIn("# Requirements", compiled_data["result"])
        self.assertIn("Next.js", compiled_data["result"])
        self.assertIn("Tailwind CSS", compiled_data["result"])

    def test_formatting_does_not_call_ollama(self) -> None:
        """TEST 18: Formatter does not invoke OllamaClient (strictly zero LLM calls for formatting)."""
        formatter = AgentFormatter()
        prompt = "# Objective\nTest prompt\n\n# Confirmed Requirements\n- Item 1\n"
        with patch("app.ai.ollama.OllamaClient.generate") as mock_ollama_call:
            for agent in SUPPORTED_AGENTS:
                formatter.format_prompt(prompt, target_agent=agent)
            mock_ollama_call.assert_not_called()
