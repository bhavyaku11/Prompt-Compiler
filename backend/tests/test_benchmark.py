"""Tests for Task 24: Quality Evaluation & Regression Benchmark Suite.

Verifies:
1. Evaluator detects preserved requirements (positive case).
2. Evaluator detects missing requirements (negative case).
3. Evaluator detects adhered constraints (positive case).
4. Evaluator detects violated constraints (negative case).
5. Evaluator detects affirmative unsupported forbidden assumptions (negative case).
6. Evaluator permits negated constraints without false positive hallucination (positive case).
7. Evaluator permits project-context-supported technologies (positive case).
8. Evaluator detects expected retrieval sources (positive case).
9. Evaluator detects missing retrieval sources (negative case).
10. Evaluator detects unexpected retrieval sources (negative precision case).
11. Multi-source retrieval coverage evaluates correctly across multiple documents.
12. Agent preset preservation detects preserved requirements and constraints across presets.
13. Agent preset preservation detects stripped requirements/constraints.
14. Evaluation produces strictly deterministic results across repeated runs.
15. Baseline comparison detects UNCHANGED when within tolerance.
16. Baseline comparison detects IMPROVED when metrics rise.
17. Baseline comparison detects REGRESSED when metrics drop beyond tolerance.
18. Baseline comparison detects new case failures.
19. Benchmark dataset integrity (unique IDs, covers build, modify, debug, explain, analyze).
20. End-to-end benchmark runner execution producing complete summary and telemetry.
"""

import json
from pathlib import Path
import tempfile
import unittest

from app.benchmark.baseline import BaselineManager
from app.benchmark.dataset import BENCHMARK_DATASET, get_benchmark_case, get_benchmark_cases
from app.benchmark.evaluator import QualityEvaluator
from app.benchmark.runner import BenchmarkRunner
from app.benchmark.schemas import (
    BenchmarkCase,
    BenchmarkRunSummary,
    CaseEvaluationResult,
)


class TestBenchmarkEvaluatorUnit(unittest.TestCase):
    """Unit tests verifying QualityEvaluator behavior on positive and negative cases."""

    def setUp(self) -> None:
        self.evaluator = QualityEvaluator()
        self.sample_case = BenchmarkCase(
            benchmark_id="BM-TEST-01",
            title="Sample User Auth",
            task_type="build",
            category="build",
            input_text="Build JWT authentication with SQLite. Do not use Supabase.",
            description="Test fixture case",
            expected_requirements=["JWT authentication", "SQLite database", "user registration"],
            expected_constraints=["Do not use Supabase", "preserve existing router"],
            expected_technologies=["JWT", "SQLite"],
            forbidden_assumptions=["MongoDB", "Supabase", "Redis"],
            applicable_agent_targets=["generic", "cursor"],
        )

    # 1. Preserved Requirements (Positive)
    def test_requirement_preservation_positive(self) -> None:
        prompt = (
            "# Objective\nBuild JWT authentication.\n\n"
            "# Confirmed Requirements\n- JWT authentication\n- SQLite database\n- user registration\n\n"
            "# Constraints\n- Do not use Supabase\n- preserve existing router"
        )
        preserved, missing, score = self.evaluator.evaluate_requirements(
            self.sample_case.expected_requirements, prompt
        )
        self.assertEqual(len(missing), 0)
        self.assertEqual(len(preserved), 3)
        self.assertEqual(score, 1.0)

    # 2. Missing Requirements (Negative)
    def test_requirement_preservation_negative(self) -> None:
        prompt = "# Objective\nBuild auth with JWT.\n\n# Requirements\n- JWT authentication\n"
        preserved, missing, score = self.evaluator.evaluate_requirements(
            self.sample_case.expected_requirements, prompt
        )
        self.assertIn("user registration", missing)
        self.assertIn("SQLite database", missing)
        self.assertEqual(len(preserved), 1)
        self.assertAlmostEqual(score, 1 / 3, places=2)

    # 3. Adhered Constraints (Positive)
    def test_constraint_adherence_positive(self) -> None:
        prompt = (
            "# Constraints\n"
            "- Do not use Supabase under any circumstances.\n"
            "- preserve existing router endpoints without modification."
        )
        adhered, violated, score = self.evaluator.evaluate_constraints(
            self.sample_case.expected_constraints, prompt
        )
        self.assertEqual(len(violated), 0)
        self.assertEqual(len(adhered), 2)
        self.assertEqual(score, 1.0)

    # 4. Violated Constraints (Negative)
    def test_constraint_adherence_negative(self) -> None:
        prompt = "# Implementation\nReplace the router completely."
        adhered, violated, score = self.evaluator.evaluate_constraints(
            self.sample_case.expected_constraints, prompt
        )
        self.assertEqual(len(adhered), 0)
        self.assertEqual(len(violated), 2)
        self.assertEqual(score, 0.0)

    # 5. Forbidden Assumption Detection (Negative)
    def test_forbidden_assumption_negative_detection(self) -> None:
        prompt = (
            "# Instructions\n"
            "Store user session documents in MongoDB collection and cache with Redis."
        )
        detected, score = self.evaluator.evaluate_forbidden_assumptions(
            self.sample_case.forbidden_assumptions, prompt
        )
        self.assertIn("MongoDB", detected)
        self.assertIn("Redis", detected)
        self.assertLess(score, 1.0)

    # 6. Forbidden Assumption Negated Excluded (Positive)
    def test_forbidden_assumption_positive_exclusion(self) -> None:
        prompt = (
            "# Constraints\n"
            "- Do not use Supabase or MongoDB.\n"
            "- Avoid Redis for session caching."
        )
        detected, score = self.evaluator.evaluate_forbidden_assumptions(
            self.sample_case.forbidden_assumptions, prompt
        )
        self.assertEqual(len(detected), 0)
        self.assertEqual(score, 1.0)

    # 7. Supported Contextual Detail (Positive)
    def test_forbidden_assumption_project_context_supported(self) -> None:
        prompt = "Connect to MongoDB replica set."
        project_context = {
            "technologies": ["MongoDB", "Python"],
            "constraints": ["Replica set connection"],
        }
        detected, score = self.evaluator.evaluate_forbidden_assumptions(
            ["MongoDB", "Redis"], prompt, project_context=project_context
        )
        # MongoDB is approved in project context, so it should not be flagged as a forbidden assumption
        self.assertNotIn("MongoDB", detected)
        self.assertEqual(score, 1.0)

    # 8. Retrieval Accuracy (Positive)
    def test_retrieval_accuracy_positive(self) -> None:
        case = BenchmarkCase(
            benchmark_id="BM-RET-01",
            title="Retrieval Test",
            task_type="build",
            category="knowledge",
            input_text="Test",
            description="Test",
            expected_knowledge_sources=["docs/auth.md", "src/auth.py"],
        )
        res = self.evaluator.evaluate_case(
            case=case,
            generated_prompt="Some prompt",
            retrieved_sources=["docs/auth.md", "src/auth.py"],
        )
        self.assertEqual(res.retrieval_source_recall, 1.0)
        self.assertEqual(res.retrieval_precision, 1.0)
        self.assertEqual(len(res.missing_knowledge_sources), 0)
        self.assertEqual(len(res.unexpected_knowledge_sources), 0)

    # 9. Retrieval Accuracy Missing Source (Negative)
    def test_retrieval_accuracy_missing_source(self) -> None:
        case = BenchmarkCase(
            benchmark_id="BM-RET-02",
            title="Retrieval Test Missing",
            task_type="build",
            category="knowledge",
            input_text="Test",
            description="Test",
            expected_knowledge_sources=["docs/auth.md", "src/auth.py"],
        )
        res = self.evaluator.evaluate_case(
            case=case,
            generated_prompt="Some prompt",
            retrieved_sources=["docs/auth.md"],
        )
        self.assertEqual(res.retrieval_source_recall, 0.5)
        self.assertEqual(res.retrieval_precision, 1.0)
        self.assertIn("src/auth.py", res.missing_knowledge_sources)
        self.assertFalse(res.passed)

    # 10. Retrieval Accuracy Unexpected Source (Negative Precision)
    def test_retrieval_accuracy_unexpected_source(self) -> None:
        case = BenchmarkCase(
            benchmark_id="BM-RET-03",
            title="Retrieval Test Unexpected",
            task_type="build",
            category="knowledge",
            input_text="Test",
            description="Test",
            expected_knowledge_sources=["docs/auth.md"],
        )
        res = self.evaluator.evaluate_case(
            case=case,
            generated_prompt="Some prompt",
            retrieved_sources=["docs/auth.md", "docs/billing.md"],
        )
        self.assertEqual(res.retrieval_source_recall, 1.0)
        self.assertEqual(res.retrieval_precision, 0.5)
        self.assertIn("docs/billing.md", res.unexpected_knowledge_sources)

    # 11. Multi-source Retrieval Evaluation
    def test_multi_source_retrieval(self) -> None:
        case = BenchmarkCase(
            benchmark_id="BM-MULTI-TEST",
            title="Multi-Source Test",
            task_type="build",
            category="multi_source",
            input_text="Multi",
            description="Multi",
            expected_knowledge_sources=["docs/spec.md", "src/code.py", "docs/db.md"],
        )
        res = self.evaluator.evaluate_case(
            case=case,
            generated_prompt="Prompt",
            retrieved_sources=["docs/spec.md", "src/code.py"],
        )
        # 2 out of 3 retrieved -> recall = 2/3
        self.assertAlmostEqual(res.retrieval_source_recall, 2 / 3, places=2)
        self.assertIn("docs/db.md", res.missing_knowledge_sources)

    # 12. Agent Preset Preservation (Positive)
    def test_agent_preset_preservation_positive(self) -> None:
        raw_prompt = (
            "# Confirmed Requirements\n- JWT authentication\n- SQLite database\n"
            "# Constraints\n- Do not use Supabase\n"
        )
        formatted_prompt = (
            "You are Cursor.\n"
            "## Requirements\n- JWT authentication\n- SQLite database\n"
            "## Constraints\n- Do not use Supabase\n"
        )
        score = self.evaluator.evaluate_preset_preservation(
            raw_compiled_prompt=raw_prompt,
            formatted_prompt=formatted_prompt,
            expected_requirements=["JWT authentication", "SQLite database"],
            expected_constraints=["Do not use Supabase"],
        )
        self.assertEqual(score, 1.0)

    # 13. Agent Preset Preservation (Negative)
    def test_agent_preset_preservation_negative(self) -> None:
        raw_prompt = (
            "# Confirmed Requirements\n- JWT authentication\n- SQLite database\n"
            "# Constraints\n- Do not use Supabase\n"
        )
        formatted_prompt = "You are Cursor. Just write code."
        score = self.evaluator.evaluate_preset_preservation(
            raw_compiled_prompt=raw_prompt,
            formatted_prompt=formatted_prompt,
            expected_requirements=["JWT authentication", "SQLite database"],
            expected_constraints=["Do not use Supabase"],
        )
        self.assertEqual(score, 0.0)

    # 14. Deterministic Evaluation
    def test_deterministic_results(self) -> None:
        prompt = (
            "# Objective\nBuild JWT authentication.\n\n"
            "# Confirmed Requirements\n- JWT authentication\n- SQLite database\n- user registration\n\n"
            "# Constraints\n- Do not use Supabase\n- preserve existing router"
        )
        res1 = self.evaluator.evaluate_case(self.sample_case, prompt, target_agent="cursor")
        res2 = self.evaluator.evaluate_case(self.sample_case, prompt, target_agent="cursor")

        self.assertEqual(res1.passed, res2.passed)
        self.assertEqual(res1.requirement_preservation_score, res2.requirement_preservation_score)
        self.assertEqual(res1.constraint_adherence_score, res2.constraint_adherence_score)
        self.assertEqual(res1.forbidden_assumption_score, res2.forbidden_assumption_score)
        self.assertEqual(res1.diagnostics, res2.diagnostics)


class TestBaselineManager(unittest.TestCase):
    """Unit tests for baseline comparison and regression detection."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.baseline_path = Path(self.tmp_dir.name) / "test_baseline.json"
        self.manager = BaselineManager(baseline_path=self.baseline_path, regression_tolerance=0.05)

        self.sample_summary = BenchmarkRunSummary(
            benchmark_version="1.0.0",
            timestamp="2026-09-25T00:00:00Z",
            total_cases=2,
            total_evaluations=2,
            passed_evaluations=2,
            failed_evaluations=0,
            requirement_preservation_rate=1.0,
            constraint_adherence_rate=1.0,
            forbidden_assumption_rate=1.0,
            retrieval_source_recall=1.0,
            retrieval_precision=1.0,
            multi_source_coverage=1.0,
            agent_preset_preservation_rate=1.0,
            case_results=[
                CaseEvaluationResult(
                    benchmark_id="BM-1",
                    target_agent="generic",
                    task_type="build",
                    passed=True,
                    requirement_preservation_score=1.0,
                    constraint_adherence_score=1.0,
                    forbidden_assumption_score=1.0,
                ),
                CaseEvaluationResult(
                    benchmark_id="BM-2",
                    target_agent="generic",
                    task_type="modify",
                    passed=True,
                    requirement_preservation_score=1.0,
                    constraint_adherence_score=1.0,
                    forbidden_assumption_score=1.0,
                ),
            ],
            failures=[],
        )
        self.manager.save_baseline(self.sample_summary)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    # 15. Unchanged Baseline
    def test_baseline_comparison_unchanged(self) -> None:
        comp = self.manager.compare(self.sample_summary)
        self.assertEqual(comp.status, "UNCHANGED")
        self.assertEqual(comp.regressions_count, 0)
        self.assertEqual(len(comp.new_failures), 0)

    # 16. Improved Baseline
    def test_baseline_comparison_improved(self) -> None:
        # Create baseline with 0.85 requirement rate
        lower_summary = self.sample_summary.model_copy(update={"requirement_preservation_rate": 0.85})
        self.manager.save_baseline(lower_summary)

        # Current summary has 1.0 -> improvement > 0.05
        comp = self.manager.compare(self.sample_summary)
        self.assertEqual(comp.status, "IMPROVED")
        self.assertGreater(comp.improvements_count, 0)
        self.assertEqual(comp.regressions_count, 0)

    # 17. Regressed Baseline
    def test_baseline_comparison_regressed_metric(self) -> None:
        regressed_summary = self.sample_summary.model_copy(
            update={"requirement_preservation_rate": 0.80}
        )
        comp = self.manager.compare(regressed_summary)
        self.assertEqual(comp.status, "REGRESSED")
        self.assertGreater(comp.regressions_count, 0)

    # 18. New Case Failure Detection
    def test_baseline_comparison_new_case_failure(self) -> None:
        failing_cases = [
            self.sample_summary.case_results[0].model_copy(update={"passed": False}),
            self.sample_summary.case_results[1],
        ]
        failed_summary = self.sample_summary.model_copy(update={"case_results": failing_cases})
        comp = self.manager.compare(failed_summary)
        self.assertEqual(comp.status, "REGRESSED")
        self.assertIn("BM-1:generic", comp.new_failures)


class TestBenchmarkDatasetAndRunner(unittest.TestCase):
    """Tests verifying benchmark dataset coverage and runner execution."""

    # 19. Dataset Integrity
    def test_benchmark_dataset_integrity(self) -> None:
        self.assertEqual(len(BENCHMARK_DATASET), 10)
        ids = [c.benchmark_id for c in BENCHMARK_DATASET]
        self.assertEqual(len(ids), len(set(ids)), "Benchmark IDs must be unique")

        task_types = {c.task_type for c in BENCHMARK_DATASET}
        self.assertTrue({"build", "modify", "debug", "explain", "analyze"}.issubset(task_types))

        # Check negative constraints exist
        neg_cases = [c for c in BENCHMARK_DATASET if c.category == "negative_constraints"]
        self.assertTrue(len(neg_cases) >= 1)

        # Check multi-source cases exist
        multi_cases = [c for c in BENCHMARK_DATASET if c.category == "multi_source"]
        self.assertTrue(len(multi_cases) >= 1)

        # Check project context cases exist
        ctx_cases = [c for c in BENCHMARK_DATASET if c.project_context is not None]
        self.assertTrue(len(ctx_cases) >= 1)

    # 20. Runner End-to-End Execution
    def test_benchmark_runner_end_to_end(self) -> None:
        runner = BenchmarkRunner()
        summary = runner.run()

        self.assertEqual(summary.total_cases, 10)
        self.assertEqual(summary.total_evaluations, 50)  # 10 cases * 5 agents
        self.assertEqual(summary.failed_evaluations, 0)
        self.assertEqual(summary.passed_evaluations, 50)

        self.assertEqual(summary.requirement_preservation_rate, 1.0)
        self.assertEqual(summary.constraint_adherence_rate, 1.0)
        self.assertEqual(summary.forbidden_assumption_rate, 1.0)
        self.assertEqual(summary.agent_preset_preservation_rate, 1.0)
        self.assertEqual(summary.retrieval_source_recall, 1.0)
        self.assertEqual(summary.multi_source_coverage, 1.0)
