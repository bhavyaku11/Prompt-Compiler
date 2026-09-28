"""Tests for the PromptCritic and validation engine."""

import unittest
from unittest.mock import AsyncMock

from app.ai.ollama import OllamaClient, OllamaConnectionError
from app.engine.critic import (
    PromptCritic,
    ValidationIssue,
    ValidationResult,
)
from app.engine.generator import PromptGenerator
from app.engine.requirements import RequirementAnalysis


class TestPromptCriticUnit(unittest.TestCase):
    """Unit tests for deterministic and LLM-assisted validation in PromptCritic."""

    def setUp(self) -> None:
        self.mock_client = AsyncMock(spec=OllamaClient)
        self.critic = PromptCritic(ollama_client=self.mock_client)

    def test_valid_build_prompt(self) -> None:
        """TEST 1: Valid build prompt with confirmed requirements preserved returns overall_valid=True."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
            missing_information=["hosting platform"],
        )
        prompt = (
            "# Objective\n"
            "Build a personal portfolio website using React.\n\n"
            "# Confirmed Requirements\n"
            "- React frontend framework\n"
            "- portfolio website structure\n\n"
            "# Open Decisions & Missing Information\n"
            "- hosting platform is an open decision to be determined.\n\n"
            "# Implementation Instructions\n"
            "1. Scaffold React project.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertTrue(result.overall_valid)
        self.assertIn("React", result.preserved_requirements)
        self.assertIn("portfolio website", result.preserved_requirements)
        self.assertEqual(len(result.missing_requirements), 0)
        self.assertEqual(len(result.violated_constraints), 0)
        self.assertEqual(len(result.invented_requirements), 0)

    def test_missing_confirmed_requirement(self) -> None:
        """TEST 2: Prompt omitting a confirmed requirement flags requirement_missing and overall_valid=False."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
        )
        # Prompt only mentions portfolio website, completely omitting React
        prompt = (
            "# Objective\n"
            "Build a portfolio website for displaying personal work.\n\n"
            "# Implementation Instructions\n"
            "Create HTML and CSS templates for projects.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertFalse(result.overall_valid)
        self.assertIn("React", result.missing_requirements)
        self.assertTrue(any(i.category == "requirement_missing" for i in result.issues))

    def test_missing_constraint(self) -> None:
        """TEST 3: Prompt omitting an explicit constraint flags constraint_missing and overall_valid=False."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
            constraints=["Do not modify the existing backend."],
        )
        prompt = (
            "# Objective\n"
            "Build a portfolio website.\n\n"
            "# Confirmed Requirements\n"
            "- portfolio website\n\n"
            "# Implementation Instructions\n"
            "Create modern responsive pages.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertFalse(result.overall_valid)
        self.assertIn("Do not modify the existing backend.", result.violated_constraints)
        self.assertTrue(any(i.category == "constraint_missing" for i in result.issues))

    def test_missing_information_preserved(self) -> None:
        """TEST 4: Missing information explicitly exposed as open decision produces no missing_information_lost error."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
            missing_information=["hosting platform"],
        )
        prompt = (
            "# Objective\n"
            "Build a portfolio website.\n\n"
            "# Open Decisions & Missing Information\n"
            "- hosting platform: open decision to be determined by the team.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertTrue(result.missing_information_preserved)
        self.assertFalse(any(i.category == "missing_information_lost" for i in result.issues))

    def test_missing_information_silently_resolved(self) -> None:
        """TEST 5: Missing information silently resolved with unconfirmed tech (Vercel) is caught."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
            missing_information=["hosting platform"],
        )
        # Prompt silently resolves hosting by mandating Vercel deployment
        prompt = (
            "# Objective\n"
            "Build a portfolio website.\n\n"
            "# Implementation Instructions\n"
            "Deploy the application to Vercel production environment.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertFalse(result.overall_valid)
        self.assertIn("vercel", [tech.lower() for tech in result.invented_requirements])
        self.assertTrue(any(i.category == "invented_requirement" for i in result.issues))

    def test_invented_technology_detection(self) -> None:
        """TEST 6: Prompt introducing unconfirmed technologies is flagged with invented_requirement."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
        )
        # Injects multiple unconfirmed frameworks/tools affirmatively
        prompt = (
            "# Objective\n"
            "Build a portfolio website.\n\n"
            "# Implementation Instructions\n"
            "Build the portfolio using React, Next.js, Tailwind CSS, Supabase and Vercel.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertFalse(result.overall_valid)
        invented_lower = [t.lower() for t in result.invented_requirements]
        for tech in ["react", "next.js", "tailwind", "supabase", "vercel"]:
            self.assertIn(tech, invented_lower, f"Expected {tech} in invented requirements")

    def test_mentioned_technology_in_prohibition(self) -> None:
        """TEST 7: Mentioning technologies inside negative prohibitions or open decisions is NOT flagged as invented."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["portfolio website"],
        )
        prompt = (
            "# Objective\n"
            "Build a portfolio website.\n\n"
            "# Confirmed Requirements\n"
            "- portfolio website\n\n"
            "# Open Decisions & Constraints\n"
            "- Do not assume React, Next.js, Tailwind, Supabase, PostgreSQL, or Vercel unless explicitly confirmed.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertEqual(
            len(result.invented_requirements),
            0,
            f"Prohibitive mentions were falsely flagged as invented: {result.invented_requirements}",
        )
        self.assertTrue(result.overall_valid)

    def test_empty_prompt_rejected(self) -> None:
        """TEST 8: Empty prompt fails with structural_problem and overall_valid=False."""
        analysis = RequirementAnalysis(
            intent="Build a website",
            task_type="build",
        )
        result = self.critic.validate_deterministic(analysis, "")
        self.assertFalse(result.overall_valid)
        self.assertFalse(result.structure_valid)
        self.assertTrue(any(i.category == "structural_problem" for i in result.issues))

    def test_whitespace_only_prompt_rejected(self) -> None:
        """TEST 9: Whitespace-only prompt fails with structural_problem and overall_valid=False."""
        analysis = RequirementAnalysis(
            intent="Build a website",
            task_type="build",
        )
        result = self.critic.validate_deterministic(analysis, "   \n\t  \r  ")
        self.assertFalse(result.overall_valid)
        self.assertFalse(result.structure_valid)
        self.assertTrue(any(i.category == "structural_problem" for i in result.issues))

    def test_task_type_mismatch(self) -> None:
        """TEST 10: Task type mismatch (debug task without debug context) produces a warning."""
        analysis = RequirementAnalysis(
            intent="Debug login failure",
            task_type="debug",
            domain="backend",
            confirmed_requirements=["login error"],
        )
        # Prompt only describes greenfield architecture without any error or debugging context
        prompt = (
            "# Objective\n"
            "Build and initialize a brand new authentication server from scratch with clean microservices.\n"
        )
        result = self.critic.validate_deterministic(analysis, prompt)
        self.assertFalse(result.task_type_valid)
        self.assertTrue(any(i.category == "task_type_mismatch" for i in result.issues))
        # Task type mismatch is registered as warning per policy
        mismatch_issue = next(i for i in result.issues if i.category == "task_type_mismatch")
        self.assertEqual(mismatch_issue.severity, "warning")

    def test_deterministic_validation_standalone(self) -> None:
        """TEST 11: Deterministic validation works independently without triggering OllamaClient."""
        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
        )
        prompt = (
            "# Objective\n"
            "Build a portfolio website using React.\n\n"
            "# Implementation Instructions\n"
            "Use React components.\n"
        )
        result = self.critic.validate(analysis, prompt, use_llm=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.overall_valid)
        self.mock_client.generate.assert_not_called()

    def test_llm_validation_integration_mocked(self) -> None:
        """TEST 12: PromptCritic -> OllamaClient -> parsed Pydantic result merges LLM findings."""
        import asyncio
        import json

        llm_response = json.dumps({
            "logical_inconsistencies": ["Contradictory state management advice in step 2"],
            "unclear_instructions": ["Unclear database migration instructions"],
            "unresolved_decisions_flagged": [],
            "invented_tech_detected": [],
            "is_actionable": True,
        })
        self.mock_client.generate.return_value = llm_response

        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
        )
        prompt = (
            "# Objective\n"
            "Build a personal portfolio website using React.\n\n"
            "# Implementation Instructions\n"
            "Follow standard practices.\n"
        )

        result = asyncio.run(self.critic.validate_async(analysis, prompt, use_llm=True))
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(any(i.category == "ambiguity" for i in result.issues))
        self.assertTrue(any(i.category == "quality_problem" for i in result.issues))
        self.mock_client.generate.assert_called_once()

    def test_invalid_llm_json_handled_cleanly(self) -> None:
        """TEST 13: Malformed LLM response is handled cleanly and does not mask deterministic checks."""
        import asyncio

        self.mock_client.generate.return_value = "This is not valid JSON at all!"

        analysis = RequirementAnalysis(
            intent="Build a portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React"],
        )
        # Prompt is missing React, so deterministic error must be preserved
        prompt = "# Objective\nBuild a generic website without mentioning any specific library.\n"

        result = asyncio.run(self.critic.validate_async(analysis, prompt, use_llm=True))
        # Overall valid must remain False because deterministic requirement_missing was found
        self.assertFalse(result.overall_valid)
        self.assertTrue(any(i.category == "requirement_missing" for i in result.issues))
        self.assertTrue(any("LLM semantic critique failed" in i.message for i in result.issues))

    def test_ollama_failure_propagates(self) -> None:
        """TEST 14: Ollama connection failures propagate directly and do not return fake validation results."""
        import asyncio

        self.mock_client.generate.side_effect = OllamaConnectionError("Failed to reach Ollama daemon")

        analysis = RequirementAnalysis(
            intent="Build a website",
            task_type="build",
        )
        prompt = "# Objective\nBuild a basic website with clear layout.\n"

        with self.assertRaises(OllamaConnectionError):
            asyncio.run(self.critic.validate_async(analysis, prompt, use_llm=True))


class TestPromptCriticIntegration(unittest.TestCase):
    """Real local Qwen3 4B integration test for PromptCritic."""

    def test_live_ollama_critic_validation(self) -> None:
        """Verify PromptCritic performs semantic review through live local Qwen3 4B."""
        # Use live PromptCritic connected to local Ollama
        critic = PromptCritic()

        analysis = RequirementAnalysis(
            intent="Build a personal portfolio website using React",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "portfolio website"],
            missing_information=["hosting platform"],
            constraints=["do not use third-party UI component libraries"],
        )

        prompt = (
            "# Objective\n"
            "Build a personal portfolio website using React.\n\n"
            "# Technical Domain & Context\n"
            "Frontend web development with vanilla React.\n\n"
            "# Confirmed Requirements\n"
            "- React\n"
            "- portfolio website\n\n"
            "# Constraints\n"
            "- do not use third-party UI component libraries\n\n"
            "# Open Decisions & Missing Information\n"
            "- hosting platform is open and must be determined later\n\n"
            "# Implementation Instructions\n"
            "1. Scaffold React project without external UI kits.\n"
            "2. Implement responsive portfolio sections.\n"
        )

        result = critic.validate(analysis, prompt, use_llm=True)

        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.overall_valid)
        self.assertIn("React", result.preserved_requirements)
        self.assertIn("portfolio website", result.preserved_requirements)
        self.assertEqual(len(result.missing_requirements), 0)
        self.assertEqual(len(result.violated_constraints), 0)


if __name__ == "__main__":
    unittest.main()
