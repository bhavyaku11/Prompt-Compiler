"""Unit tests for PromptRefiner and the automated prompt refinement loop."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.ollama import OllamaConnectionError
from app.engine.critic import PromptCritic, ValidationIssue, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.refiner import PromptRefiner, RefinementResult
from app.engine.requirements import RequirementAnalysis
from app.templates.definitions import BuildTemplate


class TestPromptRefinerUnit(unittest.TestCase):
    """Unit test suite for PromptRefiner and the automated refinement loop."""

    def setUp(self) -> None:
        self.mock_generator = MagicMock(spec=PromptGenerator)
        self.mock_critic = MagicMock(spec=PromptCritic)
        self.refiner = PromptRefiner(
            prompt_generator=self.mock_generator,
            prompt_critic=self.mock_critic,
            max_iterations=2,
        )

        self.sample_analysis = RequirementAnalysis(
            intent="Build a portfolio website",
            task_type="build",
            domain="web development",
            confirmed_requirements=["React", "Projects section"],
            missing_information=["deployment platform", "styling system"],
            constraints=["Must be responsive"],
            assumptions=["Static website"],
        )

        self.valid_prompt = (
            "# Objective\nBuild a portfolio website using React.\n\n"
            "# Confirmed Requirements\n- React\n- Projects section\n\n"
            "# Constraints\n- Must be responsive\n\n"
            "# Open Decisions\n- deployment platform\n- styling system\n"
        )

        self.initial_generation = PromptGenerationResult(
            final_prompt=self.valid_prompt,
            template_name="Build Template",
            task_type="build",
        )

    def test_already_valid_prompt_no_refinement(self) -> None:
        """TEST 1: If the initial prompt is already valid, stop immediately with 0 refinement attempts."""
        valid_result = ValidationResult(
            overall_valid=True,
            issues=[],
            preserved_requirements=["React", "Projects section"],
            missing_requirements=[],
            violated_constraints=[],
            invented_requirements=[],
        )
        self.mock_critic.validate_async = AsyncMock(return_value=valid_result)

        result: RefinementResult = self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        self.assertEqual(result.refinement_attempts, 0)
        self.assertTrue(result.converged)
        self.assertEqual(result.final_prompt, self.valid_prompt)
        self.assertEqual(self.mock_critic.validate_async.call_count, 1)
        self.mock_generator.generate_async.assert_not_called()
        self.mock_generator.refine_async.assert_not_called()

    def test_invalid_prompt_becomes_valid_after_first_refinement(self) -> None:
        """TEST 2: Invalid prompt is refined once, succeeds on second validation, and stops with 1 attempt."""
        invalid_first_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="requirement_missing",
                    severity="error",
                    message="Confirmed requirement 'Projects section' is missing.",
                )
            ],
            preserved_requirements=["React"],
            missing_requirements=["Projects section"],
            violated_constraints=[],
            invented_requirements=[],
        )

        valid_second_result = ValidationResult(
            overall_valid=True,
            issues=[],
            preserved_requirements=["React", "Projects section"],
            missing_requirements=[],
            violated_constraints=[],
            invented_requirements=[],
        )

        self.mock_critic.validate_async = AsyncMock(
            side_effect=[invalid_first_result, valid_second_result]
        )

        refined_prompt = self.valid_prompt + "\n# Extra\nRefined with projects section."
        self.mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt=refined_prompt,
                template_name="Build Template",
                task_type="build",
            )
        )

        result = self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        self.assertEqual(result.refinement_attempts, 1)
        self.assertTrue(result.converged)
        self.assertEqual(result.final_prompt, refined_prompt)
        self.assertEqual(self.mock_critic.validate_async.call_count, 2)
        self.assertEqual(self.mock_generator.generate_async.call_count, 1)

    def test_prompt_remains_invalid_stops_at_configured_maximum(self) -> None:
        """TEST 3: Persistently invalid prompt stops at max_iterations without infinite looping."""
        persistent_invalid_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="requirement_missing",
                    severity="error",
                    message="Confirmed requirement 'Projects section' is missing.",
                )
            ],
            preserved_requirements=["React"],
            missing_requirements=["Projects section"],
            violated_constraints=[],
            invented_requirements=[],
        )

        self.mock_critic.validate_async = AsyncMock(return_value=persistent_invalid_result)
        self.mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nStill missing section.\n",
                template_name="Build Template",
                task_type="build",
            )
        )

        result = self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        # Configured max_iterations is 2
        self.assertEqual(result.refinement_attempts, 2)
        self.assertFalse(result.converged)
        self.assertEqual(self.mock_generator.generate_async.call_count, 2)
        # 1 initial validation + 2 post-refinement validations = 3 total validations
        self.assertEqual(self.mock_critic.validate_async.call_count, 3)

    def test_custom_maximum_iterations_respected(self) -> None:
        """TEST 4: Custom max_iterations=3 is strictly respected."""
        custom_refiner = PromptRefiner(
            prompt_generator=self.mock_generator,
            prompt_critic=self.mock_critic,
            max_iterations=3,
        )

        invalid_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="structural_problem",
                    severity="error",
                    message="Prompt too short.",
                )
            ],
        )
        self.mock_critic.validate_async = AsyncMock(return_value=invalid_result)
        self.mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="Draft prompt.",
                template_name="Build Template",
                task_type="build",
            )
        )

        result = custom_refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        self.assertEqual(result.refinement_attempts, 3)
        self.assertEqual(self.mock_generator.generate_async.call_count, 3)
        self.assertEqual(self.mock_critic.validate_async.call_count, 4)

    def test_requirement_preservation_in_refinement(self) -> None:
        """TEST 5: Confirmed requirements from RequirementAnalysis are passed to refinement generation."""
        invalid_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="invented_requirement",
                    severity="error",
                    message="Invented unconfirmed PostgreSQL.",
                )
            ],
            invented_requirements=["PostgreSQL"],
        )
        valid_result = ValidationResult(overall_valid=True)

        self.mock_critic.validate_async = AsyncMock(
            side_effect=[invalid_result, valid_result]
        )
        self.mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="Refined prompt without PostgreSQL.",
                template_name="Build Template",
                task_type="build",
            )
        )

        self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        # Check call arguments to generate_async during refinement
        self.mock_generator.generate_async.assert_called_once()
        call_args = self.mock_generator.generate_async.call_args
        passed_analysis = call_args[0][0]
        self.assertEqual(passed_analysis.confirmed_requirements, ["React", "Projects section"])
        self.assertEqual(call_args[1]["validation_result"], invalid_result)

    def test_missing_information_preservation_in_refinement(self) -> None:
        """TEST 6: Missing information remains present in the analysis during refinement."""
        invalid_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="missing_information_lost",
                    severity="error",
                    message="Missing info styling system was silently resolved.",
                )
            ],
        )
        valid_result = ValidationResult(overall_valid=True)
        self.mock_critic.validate_async = AsyncMock(
            side_effect=[invalid_result, valid_result]
        )
        self.mock_generator.generate_async = AsyncMock(
            return_value=self.initial_generation
        )

        self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        passed_analysis = self.mock_generator.generate_async.call_args[0][0]
        self.assertEqual(passed_analysis.missing_information, ["deployment platform", "styling system"])

    def test_task_type_preservation(self) -> None:
        """TEST 7: Task type remains consistent throughout the refinement loop."""
        invalid_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="task_type_mismatch",
                    severity="error",
                    message="Task type formatting mismatch.",
                )
            ],
        )
        valid_result = ValidationResult(overall_valid=True)
        self.mock_critic.validate_async = AsyncMock(
            side_effect=[invalid_result, valid_result]
        )
        self.mock_generator.generate_async = AsyncMock(
            return_value=self.initial_generation
        )

        result = self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        self.assertEqual(result.task_type, "build")

    def test_critic_failure_propagates(self) -> None:
        """TEST 8: Upstream Ollama errors during critic execution propagate without being swallowed."""
        self.mock_critic.validate_async = AsyncMock(
            side_effect=OllamaConnectionError("Ollama connection failed during validation.")
        )

        with self.assertRaises(OllamaConnectionError):
            self.refiner.run_loop(
                analysis=self.sample_analysis,
                initial_generation=self.initial_generation,
            )

    def test_non_actionable_issue_terminates_loop_early(self) -> None:
        """TEST 9: Non-actionable validation issue does not trigger pointless generation attempts."""
        non_actionable_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="unknown_system_state",
                    severity="error",
                    message="Unfixable external condition.",
                )
            ],
        )
        self.mock_critic.validate_async = AsyncMock(return_value=non_actionable_result)

        result = self.refiner.run_loop(
            analysis=self.sample_analysis,
            initial_generation=self.initial_generation,
        )

        self.assertEqual(result.refinement_attempts, 0)
        self.assertFalse(result.converged)
        self.mock_generator.generate_async.assert_not_called()

    def test_build_refinement_prompt_structure(self) -> None:
        """TEST 10: Verify PromptGenerator.build_refinement_prompt formats feedback, constraints, and previous prompt."""
        generator = PromptGenerator()
        context = generator.create_context(self.sample_analysis)

        validation_result = ValidationResult(
            overall_valid=False,
            issues=[
                ValidationIssue(
                    category="requirement_missing",
                    severity="error",
                    message="Missing 'Projects section'",
                ),
                ValidationIssue(
                    category="invented_requirement",
                    severity="error",
                    message="Invented 'PostgreSQL'",
                ),
            ],
            preserved_requirements=["React"],
            missing_requirements=["Projects section"],
            violated_constraints=["Must be responsive"],
            invented_requirements=["PostgreSQL"],
        )

        prompt = generator.build_refinement_prompt(
            context=context,
            previous_prompt="Previous draft prompt text here.",
            validation_result=validation_result,
        )

        self.assertIn("Prompt Compiler Refinement Engine", prompt)
        self.assertIn("Missing 'Projects section'", prompt)
        self.assertIn("Invented 'PostgreSQL'", prompt)
        self.assertIn("Projects section", prompt)
        self.assertIn("PostgreSQL", prompt)
        self.assertIn("Must be responsive", prompt)
        self.assertIn("Previous draft prompt text here.", prompt)
        self.assertIn("=== INPUT REQUIREMENT ANALYSIS ===", prompt)
        self.assertIn("=== VALIDATION FEEDBACK TO FIX ===", prompt)
        self.assertIn("=== PREVIOUS DRAFT (TO BE REFINED) ===", prompt)


if __name__ == "__main__":
    unittest.main()
