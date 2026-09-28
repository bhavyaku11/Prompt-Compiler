"""Integration tests for the complete compiler pipeline exposed via POST /api/compile."""

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
    get_requirement_engine,
    get_template_selector,
)
from app.engine.critic import PromptCritic, ValidationIssue, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.requirements import (
    RequirementAnalysis,
    RequirementEngine,
    RequirementExtractionError,
)
from app.main import app
from app.templates.definitions import BuildTemplate
from app.templates.selector import TemplateSelector, UnsupportedTaskTypeError


from app.auth import get_current_user
from app.database.models import UserRecord


class TestCompileAPI(unittest.TestCase):
    """Integration test suite for the POST /api/compile endpoint."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides.clear()
        self.test_user = UserRecord(id=1, clerk_user_id="user_test_compile")
        app.dependency_overrides[get_current_user] = lambda: self.test_user

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_basic_end_to_end_pipeline(self) -> None:
        """TEST 1: Valid build request executes complete pipeline and returns HTTP 200 with non-empty result."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a personal portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
            missing_information=["hosting platform"],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild a personal portfolio website using React.\n",
                template_name="Build Template",
                task_type="build",
            )
        )

        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(
                overall_valid=True,
                issues=[],
                preserved_requirements=["React", "portfolio website"],
                missing_requirements=[],
                violated_constraints=[],
                invented_requirements=[],
                missing_information_preserved=True,
                task_type_valid=True,
                structure_valid=True,
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        response = self.client.post(
            "/api/compile",
            json={"input": "Build a personal portfolio website using React."},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["input"], "Build a personal portfolio website using React.")
        self.assertTrue(data["result"].startswith("# Objective"))
        self.assertEqual(data["task_type"], "build")
        self.assertEqual(data["template_name"], "Build Template")
        self.assertIsNotNone(data["requirements"])
        self.assertEqual(data["requirements"]["task_type"], "build")
        self.assertIsNotNone(data["validation"])
        self.assertTrue(data["validation"]["overall_valid"])

    def test_requirement_extraction_is_connected(self) -> None:
        """TEST 2: Verify RequirementEngine is invoked with the raw user input and passes RequirementAnalysis downstream."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        valid_prompt = (
            "# Objective\nCreate a portfolio website for my projects.\n\n"
            "# Confirmed Requirements\n- portfolio website\n\n"
            "# Context\nWeb development portfolio.\n"
        )
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=valid_prompt,
                template_name="Build Template",
                task_type="build",
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        user_input = "Create a portfolio website for my projects"
        response = self.client.post("/api/compile", json={"input": user_input})


        self.assertEqual(response.status_code, 200)
        mock_req_engine.analyze_async.assert_called_once_with(user_input)
        mock_generator.generate_async.assert_called_once_with(analysis)

    def test_template_selection_is_connected(self) -> None:
        """TEST 3: Verify the task type produced by RequirementEngine reaches TemplateSelector."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build a web app",
            task_type="build",
            domain="web development",
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        mock_selector = MagicMock(spec=TemplateSelector)
        mock_selector.select = MagicMock(return_value=BuildTemplate())

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nBuild prompt.\n",
                template_name="Build Template",
                task_type="build",
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_template_selector] = lambda: mock_selector
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        response = self.client.post("/api/compile", json={"input": "Build a web app."})

        self.assertEqual(response.status_code, 200)
        mock_selector.select.assert_called_once_with("build")

    def test_generator_is_connected(self) -> None:
        """TEST 4: Verify that the API receives and returns the exact prompt from PromptGenerator."""
        expected_prompt = "# Objective\nHighly customized unique prompt generated by PromptGenerator.\n"
        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=expected_prompt,
                template_name="Build Template",
                task_type="build",
            )
        )

        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(intent="Build an app", task_type="build")
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        response = self.client.post("/api/compile", json={"input": "Build an app."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], expected_prompt)

    def test_critic_is_connected(self) -> None:
        """TEST 5: Verify PromptCritic is invoked with analysis and generated prompt, and validation result reaches response."""
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(
                overall_valid=True,
                issues=[
                    ValidationIssue(
                        category="quality_problem",
                        severity="info",
                        message="Prompt is well specified.",
                    )
                ],
                preserved_requirements=["React"],
                missing_requirements=[],
                violated_constraints=[],
                invented_requirements=[],
            )
        )

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nPrompt with React.\n",
                template_name="Build Template",
                task_type="build",
            )
        )

        mock_req_engine = MagicMock(spec=RequirementEngine)
        analysis = RequirementAnalysis(
            intent="Build with React",
            task_type="build",
            confirmed_requirements=["React"],
        )
        mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        response = self.client.post("/api/compile", json={"input": "Build with React."})

        self.assertEqual(response.status_code, 200)
        mock_critic.validate_async.assert_called_once_with(
            analysis,
            "# Objective\nPrompt with React.\n",
            use_llm=False,
        )
        data = response.json()
        self.assertTrue(data["validation"]["overall_valid"])
        self.assertEqual(len(data["validation"]["issues"]), 1)
        self.assertEqual(data["validation"]["issues"][0]["message"], "Prompt is well specified.")

    def test_invalid_generated_prompt_returns_200_with_false_validity(self) -> None:
        """TEST 6: Invalid generated prompt (overall_valid=False) returns normal HTTP 200 with validation issues, not 500."""
        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(
                overall_valid=False,
                issues=[
                    ValidationIssue(
                        category="requirement_missing",
                        severity="error",
                        message="React was omitted from the generated prompt.",
                    )
                ],
                preserved_requirements=[],
                missing_requirements=["React"],
                violated_constraints=[],
                invented_requirements=[],
            )
        )

        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build with React",
                task_type="build",
                confirmed_requirements=["React"],
            )
        )

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nPrompt without React.\n",
                template_name="Build Template",
                task_type="build",
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        response = self.client.post("/api/compile", json={"input": "Build with React."})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["validation"]["overall_valid"])
        self.assertEqual(data["validation"]["missing_requirements"], ["React"])
        self.assertEqual(data["validation"]["issues"][0]["category"], "requirement_missing")

    def test_ollama_connection_failure_returns_503(self) -> None:
        """TEST 7: Ollama connection failure returns HTTP 503 Service Unavailable."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            side_effect=OllamaConnectionError("Failed to reach Ollama daemon")
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        response = self.client.post("/api/compile", json={"input": "Build a site."})
        self.assertEqual(response.status_code, 503)
        self.assertIn("Ollama service unavailable", response.json()["detail"])

    def test_ollama_timeout_returns_504(self) -> None:
        """TEST 8: Ollama timeout returns HTTP 504 Gateway Timeout."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            side_effect=OllamaTimeoutError("Request timed out after 120s")
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        response = self.client.post("/api/compile", json={"input": "Build a site."})
        self.assertEqual(response.status_code, 504)
        self.assertIn("Ollama request timed out", response.json()["detail"])

    def test_invalid_input_payload_rejected(self) -> None:
        """TEST 9: Invalid JSON schema payload returns HTTP 422 Unprocessable Entity."""
        # Non-string input
        response = self.client.post("/api/compile", json={"input": 12345})
        self.assertEqual(response.status_code, 422)

        # Missing input field
        response_missing = self.client.post("/api/compile", json={})
        self.assertEqual(response_missing.status_code, 422)

    def test_empty_or_whitespace_input_rejected(self) -> None:
        """TEST 10: Empty or whitespace-only input returns HTTP 422 Unprocessable Entity."""
        for invalid in ["", "   ", "\t\n  \r"]:
            response = self.client.post("/api/compile", json={"input": invalid})
            self.assertEqual(response.status_code, 422)

    def test_unsupported_task_type_returns_422(self) -> None:
        """TEST 11: Unsupported task type produces clean HTTP 422 error without selecting default."""
        mock_req_engine = MagicMock(spec=RequirementEngine)
        # Requirement analysis produces unknown task type
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Optimize database",
                task_type="unsupported_quantum_task",
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        response = self.client.post("/api/compile", json={"input": "Do something strange."})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Unsupported task type", response.json()["detail"])

    def test_health_endpoint_regression(self) -> None:
        """TEST 12: GET /api/health still functions correctly without regressing."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "prompt-compiler"})


if __name__ == "__main__":
    unittest.main()
