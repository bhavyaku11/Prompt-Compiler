"""Baseline persistence and regression comparison engine for Prompt Compiler benchmarks."""

import json
import os
from pathlib import Path
from typing import Any

from app.benchmark.schemas import (
    BaselineComparisonResult,
    BenchmarkRunSummary,
    CaseEvaluationResult,
)

DEFAULT_BASELINE_PATH = Path(__file__).parent / "baseline.json"
DEFAULT_REGRESSION_TOLERANCE = 0.05  # 5% degradation threshold


class BaselineManager:
    """Manages reference quality baselines and performs regression comparisons."""

    def __init__(
        self,
        baseline_path: Path | str | None = None,
        regression_tolerance: float = DEFAULT_REGRESSION_TOLERANCE,
    ) -> None:
        self.baseline_path = Path(baseline_path) if baseline_path else DEFAULT_BASELINE_PATH
        self.regression_tolerance = regression_tolerance

    def load_baseline(self) -> dict[str, Any] | None:
        """Load the stored benchmark baseline if present."""
        if not self.baseline_path.exists():
            return None
        with open(self.baseline_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_baseline(self, summary: BenchmarkRunSummary) -> Path:
        """Save a BenchmarkRunSummary as the reference baseline."""
        # Convert summary to serializable dict
        data = {
            "benchmark_version": summary.benchmark_version,
            "timestamp": summary.timestamp,
            "total_cases": summary.total_cases,
            "total_evaluations": summary.total_evaluations,
            "passed_evaluations": summary.passed_evaluations,
            "failed_evaluations": summary.failed_evaluations,
            "metrics": {
                "requirement_preservation_rate": summary.requirement_preservation_rate,
                "constraint_adherence_rate": summary.constraint_adherence_rate,
                "forbidden_assumption_rate": summary.forbidden_assumption_rate,
                "retrieval_source_recall": summary.retrieval_source_recall,
                "retrieval_precision": summary.retrieval_precision,
                "multi_source_coverage": summary.multi_source_coverage,
                "agent_preset_preservation_rate": summary.agent_preset_preservation_rate,
            },
            "case_outcomes": {
                f"{r.benchmark_id}:{r.target_agent}": {
                    "passed": r.passed,
                    "requirement_preservation_score": r.requirement_preservation_score,
                    "constraint_adherence_score": r.constraint_adherence_score,
                    "forbidden_assumption_score": r.forbidden_assumption_score,
                    "retrieval_source_recall": r.retrieval_source_recall,
                }
                for r in summary.case_results
            },
        }

        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")

        return self.baseline_path

    def compare(self, current_summary: BenchmarkRunSummary) -> BaselineComparisonResult:
        """Compare a current benchmark summary against the saved baseline."""
        baseline = self.load_baseline()
        if baseline is None:
            return BaselineComparisonResult(
                status="UNCHANGED",
                regressions_count=0,
                improvements_count=0,
                new_failures=[],
                metric_deltas={},
                details=["No stored baseline found. Current run established as initial evaluation."],
            )

        baseline_metrics = baseline.get("metrics", {})
        baseline_cases = baseline.get("case_outcomes", {})

        metric_deltas: dict[str, float] = {}
        regressions_count = 0
        improvements_count = 0
        details: list[str] = []

        # 1. Compare aggregate metrics
        current_metrics = {
            "requirement_preservation_rate": current_summary.requirement_preservation_rate,
            "constraint_adherence_rate": current_summary.constraint_adherence_rate,
            "forbidden_assumption_rate": current_summary.forbidden_assumption_rate,
            "retrieval_source_recall": current_summary.retrieval_source_recall,
            "retrieval_precision": current_summary.retrieval_precision,
            "multi_source_coverage": current_summary.multi_source_coverage,
            "agent_preset_preservation_rate": current_summary.agent_preset_preservation_rate,
        }

        for metric_name, current_val in current_metrics.items():
            if current_val is None:
                continue
            base_val = baseline_metrics.get(metric_name)
            if base_val is None:
                continue

            delta = round(current_val - base_val, 4)
            metric_deltas[metric_name] = delta

            if delta < -self.regression_tolerance:
                regressions_count += 1
                details.append(
                    f"Regression in '{metric_name}': {base_val:.2%} -> {current_val:.2%} (delta: {delta:+.2%})"
                )
            elif delta > self.regression_tolerance:
                improvements_count += 1
                details.append(
                    f"Improvement in '{metric_name}': {base_val:.2%} -> {current_val:.2%} (delta: {delta:+.2%})"
                )

        # 2. Check for new case failures
        new_failures: list[str] = []
        for r in current_summary.case_results:
            key = f"{r.benchmark_id}:{r.target_agent}"
            base_case = baseline_cases.get(key)
            if base_case and base_case.get("passed", False) and not r.passed:
                new_failures.append(key)
                regressions_count += 1
                details.append(f"New case failure: {key} passed in baseline but failed in current run.")

        if regressions_count > 0:
            status = "REGRESSED"
        elif improvements_count > 0:
            status = "IMPROVED"
        else:
            status = "UNCHANGED"

        if not details:
            details.append("Current run results match baseline within configured tolerance.")

        return BaselineComparisonResult(
            status=status,
            regressions_count=regressions_count,
            improvements_count=improvements_count,
            new_failures=new_failures,
            metric_deltas=metric_deltas,
            details=details,
        )
