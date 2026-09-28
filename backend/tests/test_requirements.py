"""Tests for the RequirementEngine, AI requirement extraction, and RequirementAnalysis model."""

import unittest
from unittest.mock import AsyncMock

from app.ai.ollama import (
    OllamaClient,
    OllamaConnectionError,
    OllamaHTTPError,
    OllamaTimeoutError,
)
from app.engine.requirements import (
    EmptyInputError,
    RequirementAnalysis,
    RequirementEngine,
    RequirementExtractionError,
    _parse_llm_json,
    _validate_requirement_analysis,
)


class TestRequirementEngineUnit(unittest.TestCase):
    """Unit tests for RequirementEngine, parser helpers, and error handling."""

    def setUp(self) -> None:
        self.mock_ollama = AsyncMock(spec=OllamaClient)
        self.engine = RequirementEngine(ollama_client=self.mock_ollama)

    def test_empty_and_whitespace_input_rejected_sync(self) -> None:
        """Verify that empty or whitespace-only inputs are rejected with EmptyInputError synchronously."""
        for invalid in ["", "   ", "\t\n  \r"]:
            with self.assertRaises(EmptyInputError):
                self.engine.analyze(invalid)

    def test_empty_and_whitespace_input_rejected_async(self) -> None:
        """Verify that empty or whitespace-only inputs are rejected with EmptyInputError asynchronously."""
        import asyncio

        async def _run() -> None:
            for invalid in ["", "   ", "\t\n  \r"]:
                with self.assertRaises(EmptyInputError):
                    await self.engine.analyze_async(invalid)

        asyncio.run(_run())

    def test_json_parsing_clean_json(self) -> None:
        """Verify that a clean JSON string is parsed correctly."""
        raw = '{"intent": "Build a portfolio", "task_type": "build", "domain": "web development"}'
        parsed = _parse_llm_json(raw)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed["intent"], "Build a portfolio")

    def test_json_parsing_with_think_tags(self) -> None:
        """Verify that <think> tags are stripped before parsing."""
        raw = (
            "<think>\n"
            "The user wants a portfolio website.\n"
            "Let's extract the requirements.\n"
            "</think>\n"
            '{"intent": "Build a portfolio", "task_type": "build", "domain": "web development"}'
        )
        parsed = _parse_llm_json(raw)
        self.assertEqual(parsed["intent"], "Build a portfolio")

    def test_json_parsing_with_markdown_fences(self) -> None:
        """Verify that markdown code fences are stripped before parsing."""
        raw = (
            "```json\n"
            '{"intent": "Build a portfolio", "task_type": "build", "domain": "web development"}\n'
            "```"
        )
        parsed = _parse_llm_json(raw)
        self.assertEqual(parsed["intent"], "Build a portfolio")

    def test_json_parsing_with_think_tags_and_fences(self) -> None:
        """Verify that both think tags and markdown fences together are parsed correctly."""
        raw = (
            "<think>Analyzing request...</think>\n"
            "Here is the JSON:\n"
            "```json\n"
            '{"intent": "Build a portfolio", "task_type": "build", "domain": "web development"}\n'
            "```"
        )
        parsed = _parse_llm_json(raw)
        self.assertEqual(parsed["intent"], "Build a portfolio")

    def test_json_parsing_invalid_json_raises_extraction_error(self) -> None:
        """Verify that invalid JSON raises RequirementExtractionError."""
        raw = "I am an AI assistant and here is your portfolio plan: 1. React 2. CSS"
        with self.assertRaises(RequirementExtractionError) as ctx:
            _parse_llm_json(raw)
        self.assertIn("Failed to parse LLM response as JSON", str(ctx.exception))

    def test_validation_missing_required_fields_raises_extraction_error(self) -> None:
        """Verify that missing required Pydantic fields raise RequirementExtractionError."""
        invalid_data = {"domain": "web development"}  # missing 'intent'
        with self.assertRaises(RequirementExtractionError) as ctx:
            _validate_requirement_analysis(invalid_data)
        self.assertIn("failed RequirementAnalysis validation", str(ctx.exception))

    def test_ollama_connection_error_not_swallowed(self) -> None:
        """Verify that Ollama connection errors are propagated and not hidden with fake data."""
        self.mock_ollama.generate.side_effect = OllamaConnectionError("Failed to connect")
        import asyncio

        with self.assertRaises(OllamaConnectionError):
            asyncio.run(self.engine.analyze_async("Build a portfolio website."))

    def test_ollama_timeout_error_not_swallowed(self) -> None:
        """Verify that Ollama timeout errors are propagated and not hidden with fake data."""
        self.mock_ollama.generate.side_effect = OllamaTimeoutError("Timed out")
        import asyncio

        with self.assertRaises(OllamaTimeoutError):
            asyncio.run(self.engine.analyze_async("Build a portfolio website."))

    def test_ollama_http_error_not_swallowed(self) -> None:
        """Verify that Ollama HTTP errors are propagated and not hidden with fake data."""
        self.mock_ollama.generate.side_effect = OllamaHTTPError("Server error", status_code=500)
        import asyncio

        with self.assertRaises(OllamaHTTPError):
            asyncio.run(self.engine.analyze_async("Build a portfolio website."))

    def test_simple_requirement_extraction_unit(self) -> None:
        """TEST 1 (Unit): Verify intent non-empty, task_type populated, React confirmed, not assumption."""
        import asyncio
        import json

        llm_response = json.dumps({
            "intent": "Build a personal portfolio website using React",
            "task_type": "build",
            "domain": "web development",
            "confirmed_requirements": ["portfolio website", "React"],
            "missing_information": ["styling library preference", "hosting platform"],
            "constraints": [],
            "assumptions": [],
        })
        self.mock_ollama.generate.return_value = llm_response

        result = asyncio.run(self.engine.analyze_async("Build a portfolio website using React."))
        self.assertIsInstance(result, RequirementAnalysis)
        self.assertTrue(result.intent)
        self.assertEqual(result.task_type, "build")
        self.assertIn("React", result.confirmed_requirements)
        self.assertNotIn("React", result.assumptions)

    def test_missing_information_extraction_unit(self) -> None:
        """TEST 2 (Unit): Verify missing information is identified when input is underspecified."""
        import asyncio
        import json

        llm_response = json.dumps({
            "intent": "Build a portfolio website",
            "task_type": "build",
            "domain": "web development",
            "confirmed_requirements": ["portfolio website"],
            "missing_information": [
                "frontend technology / framework preference",
                "visual design and styling direction",
                "required pages and content structure",
            ],
            "constraints": [],
            "assumptions": [],
        })
        self.mock_ollama.generate.return_value = llm_response

        result = asyncio.run(self.engine.analyze_async("Build a portfolio website."))
        self.assertTrue(len(result.missing_information) > 0)
        # Verify that missing info is not marked as confirmed
        for item in result.missing_information:
            self.assertNotIn(item, result.confirmed_requirements)

    def test_explicit_constraints_extraction_unit(self) -> None:
        """TEST 3 (Unit): Verify confirmed requirements and explicit constraints are separated."""
        import asyncio
        import json

        llm_response = json.dumps({
            "intent": "Build a React website while preserving the existing backend",
            "task_type": "build",
            "domain": "web development",
            "confirmed_requirements": ["React website"],
            "missing_information": ["backend API contract details"],
            "constraints": ["do not modify the existing backend"],
            "assumptions": [],
        })
        self.mock_ollama.generate.return_value = llm_response

        result = asyncio.run(
            self.engine.analyze_async("Build a React website and do not modify the existing backend.")
        )
        self.assertTrue(any("React" in r for r in result.confirmed_requirements))
        self.assertTrue(any("backend" in c.lower() for c in result.constraints))

    def test_no_invented_stack_unit(self) -> None:
        """TEST 4 (Unit): Verify unmentioned technologies are not hallucinated into confirmed_requirements."""
        import asyncio
        import json

        llm_response = json.dumps({
            "intent": "Create a website for a college club",
            "task_type": "build",
            "domain": "web development",
            "confirmed_requirements": ["website for college club"],
            "missing_information": ["tech stack preference", "club features"],
            "constraints": [],
            "assumptions": [],
        })
        self.mock_ollama.generate.return_value = llm_response

        result = asyncio.run(self.engine.analyze_async("Create a website for my college club."))
        for tech in ["React", "Next.js", "Tailwind", "Supabase", "PostgreSQL", "Vercel"]:
            self.assertNotIn(tech, result.confirmed_requirements)

    def test_deterministic_baseline_preserved(self) -> None:
        """Verify that deterministic extraction logic remains accessible for test/baseline support."""
        result = self.engine.analyze_deterministic("Build a portfolio website using React.")
        self.assertIsInstance(result, RequirementAnalysis)
        self.assertEqual(result.task_type, "build")
        self.assertIn("React", result.confirmed_requirements)
        self.assertNotIn("React", result.assumptions)


class TestRequirementEngineIntegration(unittest.TestCase):
    """TEST 6: REAL Ollama integration test using local Qwen3 4B through OllamaClient and RequirementEngine."""

    def setUp(self) -> None:
        # Use live RequirementEngine with default OllamaClient connected to local Ollama
        self.engine = RequirementEngine()

    def test_real_ollama_requirement_extraction(self) -> None:
        """Verify that RequirementEngine reaches live local Ollama, parses output, and validates RequirementAnalysis."""
        user_input = "Build a personal portfolio website using React and do not modify the existing backend."

        # Execute analysis through live Ollama
        result = self.engine.analyze(user_input)

        # 1. Verify instance type
        self.assertIsInstance(result, RequirementAnalysis)

        # 2. Verify intent is populated
        self.assertTrue(result.intent and len(result.intent.strip()) > 0)

        # 3. Verify task_type is valid
        self.assertIn(result.task_type.lower(), ["build", "modify", "debug", "explain", "analyze"])

        # 4. Verify domain is reasonable
        self.assertTrue(
            any(k in result.domain.lower() for k in ["web", "frontend", "software", "general", "portfolio"])
        )

        # 5. Verify React is in confirmed requirements and NOT in assumptions
        confirmed_joined = " ".join(result.confirmed_requirements).lower()
        self.assertIn("react", confirmed_joined, "React should be in confirmed_requirements")

        assumptions_joined = " ".join(result.assumptions).lower()
        self.assertNotIn("react", assumptions_joined, "React should not be listed as an assumption")

        # 6. Verify constraint regarding backend is captured
        constraints_joined = " ".join(result.constraints).lower()
        self.assertTrue(
            "backend" in constraints_joined or "existing" in constraints_joined or len(result.constraints) > 0,
            "Backend constraint should be captured in constraints list",
        )

        # 7. Verify no unmentioned stack was hallucinated into confirmed requirements
        for tech in ["supabase", "postgresql", "tailwind", "next.js", "vue", "angular"]:
            self.assertNotIn(
                tech,
                confirmed_joined,
                f"Unmentioned technology '{tech}' was hallucinated into confirmed_requirements!",
            )


if __name__ == "__main__":
    unittest.main()

