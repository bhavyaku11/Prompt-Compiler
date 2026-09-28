"""Unit and integration tests for Prompt Templates and PromptGenerator."""

import unittest
from unittest.mock import AsyncMock

from app.ai.ollama import OllamaClient, OllamaConnectionError, OllamaTimeoutError
from app.engine.generator import (
    PromptGenerationContext,
    PromptGenerationResult,
    PromptGenerator,
    _sanitize_output,
)
from app.engine.requirements import RequirementAnalysis
from app.templates.base import PromptTemplate
from app.templates.definitions import (
    AnalyzeTemplate,
    BuildTemplate,
    DebugTemplate,
    ExplainTemplate,
    ModifyTemplate,
)
from app.templates.selector import (
    TemplateSelector,
    UnsupportedTaskTypeError,
)


class TestTemplateSelector(unittest.TestCase):
    """Tests for template discovery and deterministic selection."""

    def setUp(self) -> None:
        self.selector = TemplateSelector()

    def test_build_template_selection(self) -> None:
        """TEST 1: task_type='build' selects BuildTemplate."""
        template = self.selector.get_template("build")
        self.assertIsInstance(template, BuildTemplate)
        self.assertEqual(template.task_type, "build")
        self.assertEqual(template.name, "Build Template")

    def test_modify_template_selection(self) -> None:
        """TEST 2: task_type='modify' selects ModifyTemplate."""
        template = self.selector.get_template("modify")
        self.assertIsInstance(template, ModifyTemplate)
        self.assertEqual(template.task_type, "modify")
        self.assertEqual(template.name, "Modify Template")

    def test_debug_template_selection(self) -> None:
        """TEST 3: task_type='debug' selects DebugTemplate."""
        template = self.selector.get_template("debug")
        self.assertIsInstance(template, DebugTemplate)
        self.assertEqual(template.task_type, "debug")
        self.assertEqual(template.name, "Debug Template")

    def test_explain_template_selection(self) -> None:
        """TEST 4: task_type='explain' selects ExplainTemplate."""
        template = self.selector.get_template("explain")
        self.assertIsInstance(template, ExplainTemplate)
        self.assertEqual(template.task_type, "explain")
        self.assertEqual(template.name, "Explain Template")

    def test_analyze_template_selection(self) -> None:
        """TEST 5: task_type='analyze' selects AnalyzeTemplate."""
        template = self.selector.get_template("analyze")
        self.assertIsInstance(template, AnalyzeTemplate)
        self.assertEqual(template.task_type, "analyze")
        self.assertEqual(template.name, "Analyze Template")

    def test_unsupported_task_type_raises(self) -> None:
        """TEST 6: Unsupported task types fail clearly with UnsupportedTaskTypeError."""
        invalid_types = ["unknown", "deploy", "optimize", "", "   ", "random_task"]
        for task_type in invalid_types:
            with self.assertRaises(UnsupportedTaskTypeError):
                self.selector.get_template(task_type)

    def test_case_and_whitespace_normalization(self) -> None:
        """Verify template selector handles casing and leading/trailing whitespace."""
        template = self.selector.get_template("  BUILD  ")
        self.assertIsInstance(template, BuildTemplate)
        template_modify = self.selector.get_template("MoDiFy")
        self.assertIsInstance(template_modify, ModifyTemplate)


class TestPromptGenerationContext(unittest.TestCase):
    """Tests for context preparation, formatting, and requirement fidelity."""

    def setUp(self) -> None:
        self.selector = TemplateSelector()

    def test_requirement_preservation(self) -> None:
        """TEST 7: Confirmed requirements are preserved in the generation context."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
        )
        template = self.selector.select(analysis.task_type)
        context = PromptGenerationContext(requirement_analysis=analysis, template=template)

        formatted_reqs = context.format_confirmed_requirements()
        self.assertIn("React", formatted_reqs)
        self.assertIn("portfolio website", formatted_reqs)

    def test_constraint_preservation(self) -> None:
        """TEST 8: Explicit constraints are preserved in the generation context."""
        analysis = RequirementAnalysis(
            intent="Build a web feature",
            task_type="build",
            domain="web development",
            constraints=["do not modify the existing backend", "use only vanilla CSS"],
        )
        template = self.selector.select(analysis.task_type)
        context = PromptGenerationContext(requirement_analysis=analysis, template=template)

        formatted_constraints = context.format_constraints()
        self.assertIn("do not modify the existing backend", formatted_constraints)
        self.assertIn("use only vanilla CSS", formatted_constraints)

    def test_missing_information_preservation(self) -> None:
        """TEST 9: Missing information items reach the generation context as open decisions."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            missing_information=["deployment target", "visual theme preference"],
        )
        template = self.selector.select(analysis.task_type)
        context = PromptGenerationContext(requirement_analysis=analysis, template=template)

        formatted_missing = context.format_missing_information()
        self.assertIn("deployment target", formatted_missing)
        self.assertIn("visual theme preference", formatted_missing)
        self.assertIn("Open Decision", formatted_missing)

    def test_no_invented_technology_in_prompt_construction(self) -> None:
        """TEST 10: Constructed generation instruction does NOT inject unconfirmed technologies."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
            missing_information=["frontend technology", "hosting target"],
        )
        generator = PromptGenerator(template_selector=self.selector)
        context = generator.create_context(analysis)
        prompt = generator.build_generation_prompt(context)

        unconfirmed = ["Next.js", "Tailwind", "Supabase", "PostgreSQL", "Vercel"]
        confirmed_section = context.format_confirmed_requirements()
        for tech in unconfirmed:
            self.assertNotIn(
                tech,
                confirmed_section,
                f"Technology '{tech}' was injected into confirmed requirements!",
            )


class TestPromptGeneratorUnit(unittest.TestCase):
    """Unit tests for PromptGenerator with mocked OllamaClient and sanitization checks."""

    def setUp(self) -> None:
        self.mock_client = AsyncMock(spec=OllamaClient)
        self.generator = PromptGenerator(ollama_client=self.mock_client)

    def test_generator_with_mocked_ollama(self) -> None:
        """TEST 11: RequirementAnalysis -> PromptGenerator -> OllamaClient.generate() returns result."""
        import asyncio

        mock_llm_output = (
            "# Objective\n"
            "Build a personal portfolio website using React.\n\n"
            "# Confirmed Requirements\n"
            "- React\n"
            "- portfolio website\n\n"
            "# Implementation Instructions\n"
            "1. Initialize React project.\n"
        )
        self.mock_client.generate.return_value = mock_llm_output

        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
        )

        result = asyncio.run(self.generator.generate_async(analysis))
        self.assertIsInstance(result, PromptGenerationResult)
        self.assertEqual(result.task_type, "build")
        self.assertEqual(result.template_name, "Build Template")
        self.assertIn("React", result.final_prompt)
        self.mock_client.generate.assert_called_once()

    def test_sync_generate_interface(self) -> None:
        """Verify synchronous generate() interface works correctly."""
        self.mock_client.generate.return_value = "# Objective\nClean sync prompt."
        analysis = RequirementAnalysis(
            intent="Explain REST APIs",
            task_type="explain",
            domain="backend",
        )
        result = self.generator.generate(analysis)
        self.assertIsInstance(result, PromptGenerationResult)
        self.assertEqual(result.task_type, "explain")
        self.assertEqual(result.template_name, "Explain Template")

    def test_sanitize_output_strips_thinking_tags(self) -> None:
        """Verify _sanitize_output removes reasoning tags."""
        raw = "<think>Let us construct the prompt...</think>\n# Objective\nBuild a site."
        sanitized = _sanitize_output(raw)
        self.assertEqual(sanitized, "# Objective\nBuild a site.")

    def test_sanitize_output_strips_markdown_code_fences(self) -> None:
        """Verify _sanitize_output removes outer markdown fences."""
        raw = "```markdown\n# Objective\nBuild a site.\n```"
        sanitized = _sanitize_output(raw)
        self.assertEqual(sanitized, "# Objective\nBuild a site.")

    def test_sanitize_output_strips_conversational_filler(self) -> None:
        """Verify _sanitize_output removes conversational introductory phrases."""
        raw = "Here is the compiled prompt:\n\n# Objective\nBuild a site."
        sanitized = _sanitize_output(raw)
        self.assertEqual(sanitized, "# Objective\nBuild a site.")

    def test_ollama_errors_not_swallowed(self) -> None:
        """Verify Ollama errors are propagated directly from PromptGenerator."""
        import asyncio

        self.mock_client.generate.side_effect = OllamaConnectionError("Cannot reach Ollama")
        analysis = RequirementAnalysis(
            intent="Build a site",
            task_type="build",
        )
        with self.assertRaises(OllamaConnectionError):
            asyncio.run(self.generator.generate_async(analysis))


class TestPromptGeneratorIntegration(unittest.TestCase):
    """Real local Qwen3 4B integration test for PromptGenerator."""

    def test_live_ollama_prompt_generation(self) -> None:
        """Verify PromptGenerator generates a complete structured prompt via live local Qwen3 4B."""
        # Use live generator connected to local Ollama
        generator = PromptGenerator()

        analysis = RequirementAnalysis(
            intent="Build a personal portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
            missing_information=["styling preference", "hosting platform"],
            constraints=["do not use third-party UI component libraries"],
        )

        result = generator.generate(analysis)

        # 1. Verify result structure
        self.assertIsInstance(result, PromptGenerationResult)
        self.assertEqual(result.task_type, "build")
        self.assertEqual(result.template_name, "Build Template")

        # 2. Verify prompt is non-empty and substantial
        self.assertTrue(result.final_prompt and len(result.final_prompt.strip()) > 50)

        # 3. Verify confirmed requirements are preserved
        prompt_lower = result.final_prompt.lower()
        self.assertIn("react", prompt_lower, "React should be preserved in generated prompt")
        self.assertIn("portfolio", prompt_lower, "Portfolio requirement should be preserved")

        # 4. Verify negative constraint is preserved
        self.assertTrue(
            "third-party" in prompt_lower or "component" in prompt_lower or "constraint" in prompt_lower,
            "Constraint should be referenced in generated prompt",
        )


if __name__ == "__main__":
    unittest.main()
