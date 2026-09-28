"""Tests for integrating Project Memory into the Prompt Compiler pipeline (Task 17).

Tests cover:
1. Compile without project_id behaves identically to before (backward compatibility).
2. Compile with valid project_id loads project context and active memory.
3. Compile with invalid project_id returns HTTP 404.
4. Project technologies reach the generation context.
5. Project constraints reach the generation context.
6. Project coding rules reach the generation context.
7. Project context remains separate from current user requirements.
8. Explicit current user requirement overrides conflicting project context.
9. Project memory is NOT automatically modified during compilation (read-only).
10. Compilation persistence records project_id in database.
11. Interview-based compilation propagates project_id and project context.
12. Existing API contracts remain compatible.
13. PromptCritic recognizes project context technologies to prevent false hallucination warnings.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from starlette.testclient import TestClient

from app.api.compile import (
    get_compilation_repository,
    get_project_service,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)
from app.database.repositories import (
    CompilationRepository,
    ProjectMemoryRepository,
    ProjectRepository,
)
from app.database.session import init_db, reset_db_engine
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import (
    PromptGenerationContext,
    PromptGenerationResult,
    PromptGenerator,
)
from app.engine.project_memory import ProjectMemoryService
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.project import ProjectCreate, ProjectMemoryCreate, ProjectContext
from app.templates.selector import TemplateSelector


class TestCompileWithProjectMemory(unittest.TestCase):
    """Unit and API integration tests for project memory compilation pipeline."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_compile_project_memory.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
        )
        self.compilation_repo = CompilationRepository(database_url=self.db_url)

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_compile_proj_mem")

        # Create a test project with standard memories
        self.project = self.service.create_project(
            name="E-Commerce API",
            description="REST API for online storefront",
            user_id=self.test_user.id,
        )
        self.project_id = self.project.project_id

        # Add active memories: tech stack, constraints, coding rules
        self.service.add_memory(
            project_id=self.project_id,
            category="technology",
            content="FastAPI backend framework",
            confidence=1.0,
            user_id=self.test_user.id,
        )
        self.service.add_memory(
            project_id=self.project_id,
            category="technology",
            content="PostgreSQL database",
            confidence=1.0,
            user_id=self.test_user.id,
        )
        self.service.add_memory(
            project_id=self.project_id,
            category="technology",
            content="React frontend framework",
            confidence=0.9,
            user_id=self.test_user.id,
        )
        self.service.add_memory(
            project_id=self.project_id,
            category="constraint",
            content="Do not modify existing public API contracts",
            confidence=1.0,
            user_id=self.test_user.id,
        )
        self.service.add_memory(
            project_id=self.project_id,
            category="coding_rule",
            content="Use strict Python type annotations everywhere",
            confidence=1.0,
            user_id=self.test_user.id,
        )

        self.client = TestClient(app)
        app.dependency_overrides.clear()
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_project_service] = lambda: self.service
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_01_compile_without_project_id_unchanged(self) -> None:
        """TEST 1: Compile request without project_id behaves identically to before."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build a calculator",
                task_type="build",
                domain="web",
                confirmed_requirements=["calculator"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild a calculator.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        resp = self.client.post("/api/compile", json={"input": "Build a calculator"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["task_type"], "build")
        self.assertIsNone(data["project_id"])
        self.assertIn("calculator", data["result"])

        # Verify analyze_async was called without project_context
        mock_req_engine.analyze_async.assert_called_once()
        args, kwargs = mock_req_engine.analyze_async.call_args
        self.assertIsNone(kwargs.get("project_context"))

    def test_02_compile_with_valid_project_id_loads_context(self) -> None:
        """TEST 2: Compile with valid project_id loads project context and passes to engine."""
        captured_context = {}

        async def fake_analyze(user_input, project_context=None):
            captured_context["analyze_context"] = project_context
            return RequirementAnalysis(
                intent="Add Stripe checkout",
                task_type="build",
                domain="e-commerce",
                confirmed_requirements=["Stripe checkout"],
                project_context_summary=project_context.to_context_string() if project_context else None,
            )

        async def fake_generate(analysis, template=None, project_context=None):
            captured_context["generate_context"] = project_context
            return PromptGenerationResult(
                final_prompt=f"# Objective\nAdd Stripe checkout to {project_context.project.name}.\n",
                template_name="Build Template",
                task_type="build",
            )

        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(side_effect=fake_analyze)
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(side_effect=fake_generate)
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Add Stripe checkout",
                "project_id": self.project_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_id"], self.project_id)
        self.assertIn("E-Commerce API", data["result"])

        # Check captured context
        ctx = captured_context["analyze_context"]
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.project.name, "E-Commerce API")
        self.assertIn("FastAPI", ctx.technologies[0])

    def test_03_compile_with_invalid_project_id_returns_404(self) -> None:
        """TEST 3: Compile with non-existent project_id returns HTTP 404."""
        non_existent_id = str(uuid4())
        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Build something",
                "project_id": non_existent_id,
            },
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_04_project_technologies_reach_prompt_generation_context(self) -> None:
        """TEST 4: Project technologies are formatted and present in PromptGenerationContext."""
        project_context = self.service.get_project_context(self.project_id)
        self.assertIsNotNone(project_context)

        analysis = RequirementAnalysis(
            intent="Add payment endpoint",
            task_type="build",
            domain="backend",
            confirmed_requirements=["payment endpoint"],
        )

        generator = PromptGenerator(ollama_client=AsyncMock())
        gen_ctx = generator.create_context(analysis, project_context=project_context)

        formatted = gen_ctx.format_project_context()
        self.assertIn("E-Commerce API", formatted)
        self.assertIn("FastAPI", formatted)
        self.assertIn("PostgreSQL", formatted)
        self.assertIn("React", formatted)

        # Check that it's formatted in the full generation prompt
        prompt = generator.build_generation_prompt(gen_ctx)
        self.assertIn("PROJECT CONTEXT (EXISTING APPLICATION BASELINE)", prompt)
        self.assertIn("FastAPI", prompt)
        self.assertIn("PostgreSQL", prompt)

    def test_05_project_constraints_reach_generation_context(self) -> None:
        """TEST 5: Project-level constraints reach PromptGenerationContext and prompt text."""
        project_context = self.service.get_project_context(self.project_id)
        self.assertIsNotNone(project_context)

        self.assertTrue(
            any("Do not modify existing public API contracts" in c for c in project_context.active_constraints)
        )

        generator = PromptGenerator(ollama_client=AsyncMock())
        analysis = RequirementAnalysis(
            intent="Add product export",
            task_type="build",
        )
        context = generator.create_context(analysis, project_context=project_context)
        prompt = generator.build_generation_prompt(context)
        self.assertIn("Do not modify existing public API contracts", prompt)

    def test_06_project_coding_rules_reach_generation_context(self) -> None:
        """TEST 6: Project-level coding rules reach PromptGenerationContext and prompt text."""
        project_context = self.service.get_project_context(self.project_id)
        self.assertIsNotNone(project_context)

        self.assertTrue(
            any("strict Python type annotations" in r for r in project_context.coding_rules)
        )

        generator = PromptGenerator(ollama_client=AsyncMock())
        analysis = RequirementAnalysis(
            intent="Add analytics module",
            task_type="build",
        )
        context = generator.create_context(analysis, project_context=project_context)
        prompt = generator.build_generation_prompt(context)
        self.assertIn("strict Python type annotations", prompt)

    def test_07_project_context_separated_from_user_requirements(self) -> None:
        """TEST 7: Project context items are NOT injected as newly confirmed user requirements."""
        project_context = self.service.get_project_context(self.project_id)
        engine = RequirementEngine(ollama_client=AsyncMock())

        # Analyze using deterministic extraction with project context passed
        analysis = engine.analyze_deterministic(
            "Add user authentication",
            project_context=project_context,
        )

        # Confirmed requirements should only contain user input items, NOT background tech
        self.assertTrue(any("user authentication" in r.lower() for r in analysis.confirmed_requirements))
        for tech in ["fastapi", "postgresql", "react"]:
            self.assertNotIn(tech, [r.lower() for r in analysis.confirmed_requirements])

        # Project context is recorded in project_context_summary
        self.assertIsNotNone(analysis.project_context_summary)
        self.assertIn("E-Commerce API", analysis.project_context_summary)

    def test_08_explicit_user_requirement_overrides_conflicting_project_context(self) -> None:
        """TEST 8: Explicit user requirement takes precedence over conflicting project baseline."""
        project_context = self.service.get_project_context(self.project_id)
        generator = PromptGenerator(ollama_client=AsyncMock())

        # User wants Vue instead of the project baseline React
        analysis = RequirementAnalysis(
            intent="Build this admin page using Vue instead",
            task_type="build",
            domain="frontend",
            confirmed_requirements=["admin page", "Vue"],
        )

        context = generator.create_context(analysis, project_context=project_context)
        prompt = generator.build_generation_prompt(context)

        # The prompt instructions clearly specify the precedence hierarchy
        self.assertIn("Current explicit user requirements have HIGHEST priority and override any conflicting project baseline", prompt)
        self.assertIn("Note: Explicit Current User Requirements below take precedence over Project Context in case of conflict.", prompt)

        # Both the baseline React and the override Vue are visible to the LLM with explicit guidance
        self.assertIn("Vue", prompt)
        self.assertIn("React", prompt)

    def test_09_no_automatic_memory_creation_during_compile(self) -> None:
        """TEST 9: Compilation does NOT create or alter project memories (read-only context)."""
        memories_before = self.service.get_project_context(self.project_id).memories
        count_before = len(memories_before)

        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Add Supabase OAuth",
                task_type="build",
                confirmed_requirements=["Supabase OAuth"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nAdd Supabase OAuth.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Add Supabase OAuth",
                "project_id": self.project_id,
            },
        )
        self.assertEqual(resp.status_code, 200)

        # Ensure memory count and contents remain identical
        memories_after = self.service.get_project_context(self.project_id).memories
        self.assertEqual(len(memories_after), count_before)
        contents_after = [m.content for m in memories_after]
        self.assertNotIn("supabase", [c.lower() for c in contents_after])

    def test_10_compilation_persistence_records_project_id(self) -> None:
        """TEST 10: Compilation record persists project_id and can be listed by project."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Add newsletter signup",
                task_type="build",
                confirmed_requirements=["newsletter signup"],
            )
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nAdd newsletter signup.\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Add newsletter signup",
                "project_id": self.project_id,
            },
        )
        self.assertEqual(resp.status_code, 200)

        # Verify record in database
        project_records = self.compilation_repo.list_by_project(self.project_id)
        self.assertGreaterEqual(len(project_records), 1)
        latest = project_records[0]
        self.assertEqual(latest.project_id, self.project_id)
        self.assertIn("newsletter signup", latest.input_text)

    def test_11_interview_compilation_with_project_id(self) -> None:
        """TEST 11: Interview flow preserves project_id and passes project context to compile."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build an invoice generator",
                task_type="build",
                domain="finance",
                confirmed_requirements=["invoice generator"],
                missing_information=["export format"],
            )
        )
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        # Start interview with project_id
        start_resp = self.client.post(
            "/api/interview/start",
            json={
                "input": "Build an invoice generator",
                "project_id": self.project_id,
            },
        )
        self.assertEqual(start_resp.status_code, 200)
        session_data = start_resp.json()
        session_id = session_data["session_id"]
        self.assertEqual(session_data["project_id"], self.project_id)

        # Mock generator and critic for compile
        captured_compile_context = {}

        async def fake_compile_generate(analysis, template=None, project_context=None):
            captured_compile_context["project_context"] = project_context
            return PromptGenerationResult(
                final_prompt="# Objective\nInvoice generator using PDF export.\n",
                template_name="Build Template",
                task_type="build",
            )

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(side_effect=fake_compile_generate)
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True)
        )

        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        # Compile from interview session
        compile_resp = self.client.post(f"/api/interview/{session_id}/compile")
        self.assertEqual(compile_resp.status_code, 200)
        compile_data = compile_resp.json()
        self.assertEqual(compile_data["project_id"], self.project_id)
        self.assertEqual(compile_data["interview_session_id"], session_id)

        # Verify generator received project context
        ctx = captured_compile_context.get("project_context")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.project.name, "E-Commerce API")

    def test_12_interview_start_with_invalid_project_id_returns_404(self) -> None:
        """TEST 12: Interview start with non-existent project_id returns HTTP 404."""
        fake_id = str(uuid4())
        resp = self.client.post(
            "/api/interview/start",
            json={
                "input": "Build something",
                "project_id": fake_id,
            },
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_13_critic_does_not_flag_project_context_technologies(self) -> None:
        """TEST 13: PromptCritic includes project context technologies in confirmed text."""
        project_context = self.service.get_project_context(self.project_id)
        critic = PromptCritic(ollama_client=AsyncMock())

        # Analysis only has 'Add caching layer' (doesn't explicitly mention FastAPI or PostgreSQL)
        analysis = RequirementAnalysis(
            intent="Add caching layer",
            task_type="build",
            domain="backend",
            confirmed_requirements=["caching layer"],
        )

        # Generated prompt references project context: FastAPI and PostgreSQL
        prompt = (
            "# Objective\n"
            "Add caching layer to existing FastAPI and PostgreSQL application.\n\n"
            "# Implementation\n"
            "Scaffold Redis cache for FastAPI routes.\n"
        )

        # When project_context is supplied, FastAPI and PostgreSQL should NOT be flagged as invented
        result = critic.validate_deterministic(analysis, prompt, project_context=project_context)
        invented_names = [issue.message for issue in result.issues if issue.category == "technology_invented"]
        self.assertFalse(any("FastAPI" in msg for msg in invented_names))
        self.assertFalse(any("PostgreSQL" in msg for msg in invented_names))


if __name__ == "__main__":
    unittest.main()
