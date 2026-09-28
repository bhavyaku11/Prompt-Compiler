"""Quality Evaluation and Regression Benchmark Suite for Prompt Compiler."""

from app.benchmark.baseline import BaselineManager, DEFAULT_BASELINE_PATH
from app.benchmark.dataset import BENCHMARK_DATASET, get_benchmark_case, get_benchmark_cases
from app.benchmark.evaluator import QualityEvaluator
from app.benchmark.schemas import (
    BaselineComparisonResult,
    BenchmarkCase,
    BenchmarkRunSummary,
    CaseEvaluationResult,
)


def __getattr__(name: str):
    if name == "BenchmarkRunner":
        from app.benchmark.runner import BenchmarkRunner
        return BenchmarkRunner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BENCHMARK_DATASET",
    "BaselineComparisonResult",
    "BaselineManager",
    "BenchmarkCase",
    "BenchmarkRunSummary",
    "BenchmarkRunner",
    "CaseEvaluationResult",
    "DEFAULT_BASELINE_PATH",
    "QualityEvaluator",
    "get_benchmark_case",
    "get_benchmark_cases",
]
