"""Domain schemas and evaluation models for Prompt Compiler Quality Benchmark."""

from typing import Any
from pydantic import BaseModel, Field


class BenchmarkCase(BaseModel):
    """Deterministic benchmark case definition for evaluating prompt compiler quality."""

    benchmark_id: str = Field(
        ...,
        description="Unique identifier for the benchmark case (e.g., BM-BUILD-01).",
    )
    title: str = Field(
        ...,
        description="Short human-readable title describing the benchmark task.",
    )
    task_type: str = Field(
        ...,
        description="Canonical task type: build, modify, debug, explain, analyze.",
    )
    input_text: str = Field(
        ...,
        description="The raw user prompt input provided to the compiler.",
    )
    description: str = Field(
        ...,
        description="Detailed description of the evaluation scenario and objectives.",
    )
    expected_requirements: list[str] = Field(
        default_factory=list,
        description="Key explicit requirements that must survive into the generated prompt.",
    )
    expected_constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints or boundaries (including negative constraints) that must be adhered to.",
    )
    expected_technologies: list[str] = Field(
        default_factory=list,
        description="Explicit technologies required by the task.",
    )
    forbidden_assumptions: list[str] = Field(
        default_factory=list,
        description="Technologies or major requirements that must NOT be affirmatively introduced without evidence.",
    )
    project_context: dict[str, Any] | None = Field(
        default=None,
        description="Optional persistent project context (description, technologies, constraints, coding rules).",
    )
    knowledge_sources: list[dict[str, Any]] | None = Field(
        default=None,
        description="Optional knowledge sources indexed in the local repository for this test case.",
    )
    expected_knowledge_sources: list[str] | None = Field(
        default=None,
        description="Expected knowledge source names to be retrieved for this task.",
    )
    applicable_agent_targets: list[str] = Field(
        default_factory=lambda: ["generic", "cursor", "claude_code", "cline", "windsurf"],
        description="Agent presets evaluated for this case.",
    )
    category: str = Field(
        default="general",
        description="Evaluation category (e.g. build, modify, debug, explain, analyze, multi_source, project_context).",
    )


class CaseEvaluationResult(BaseModel):
    """Detailed evaluation result of a single benchmark case against an agent preset."""

    benchmark_id: str = Field(..., description="ID of the evaluated benchmark case.")
    target_agent: str = Field(..., description="The agent preset evaluated.")
    task_type: str = Field(..., description="The task type.")
    passed: bool = Field(..., description="Whether all evaluation criteria passed for this case and agent.")
    
    # Quantitative metric scores (0.0 to 1.0)
    requirement_preservation_score: float = Field(
        ...,
        description="Fraction of expected confirmed requirements preserved in prompt (0.0 - 1.0).",
    )
    constraint_adherence_score: float = Field(
        ...,
        description="Fraction of explicit constraints adhered to in prompt (0.0 - 1.0).",
    )
    forbidden_assumption_score: float = Field(
        ...,
        description="1.0 if zero forbidden assumptions detected; scaled down per detected violation.",
    )
    retrieval_source_recall: float | None = Field(
        default=None,
        description="Fraction of expected knowledge sources retrieved (None if no knowledge expected).",
    )
    retrieval_precision: float | None = Field(
        default=None,
        description="Fraction of retrieved knowledge sources that were expected (None if no knowledge expected).",
    )
    agent_preset_preservation_score: float = Field(
        default=1.0,
        description="Fraction of prompt requirements/constraints retained after agent preset formatting.",
    )

    # Detailed itemized lists
    preserved_requirements: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    adhered_constraints: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)
    detected_forbidden_assumptions: list[str] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)
    missing_knowledge_sources: list[str] = Field(default_factory=list)
    unexpected_knowledge_sources: list[str] = Field(default_factory=list)

    diagnostics: list[str] = Field(
        default_factory=list,
        description="Actionable explanations for any failures or warnings.",
    )
    raw_output_snippet: str = Field(
        default="",
        description="Truncated snippet of the evaluated prompt for quick inspection.",
    )


class BenchmarkRunSummary(BaseModel):
    """Aggregate quality evaluation summary across all benchmark cases and presets."""

    benchmark_version: str = Field(default="1.0.0", description="Version of the benchmark suite.")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the benchmark run.")
    total_cases: int = Field(..., description="Number of distinct benchmark cases evaluated.")
    total_evaluations: int = Field(..., description="Total case-agent evaluations performed.")
    passed_evaluations: int = Field(..., description="Total case-agent evaluations that passed.")
    failed_evaluations: int = Field(..., description="Total case-agent evaluations that failed.")

    # Macro aggregate metric rates
    requirement_preservation_rate: float = Field(
        ...,
        description="Aggregate proportion of expected requirements preserved.",
    )
    constraint_adherence_rate: float = Field(
        ...,
        description="Aggregate proportion of expected constraints adhered to.",
    )
    forbidden_assumption_rate: float = Field(
        ...,
        description="Aggregate proportion of evaluations with zero forbidden assumptions.",
    )
    retrieval_source_recall: float | None = Field(
        default=None,
        description="Aggregate recall across knowledge-backed benchmark cases.",
    )
    retrieval_precision: float | None = Field(
        default=None,
        description="Aggregate precision across knowledge-backed benchmark cases.",
    )
    multi_source_coverage: float | None = Field(
        default=None,
        description="Proportion of multi-source cases where >= 2 expected sources were retrieved.",
    )
    agent_preset_preservation_rate: float = Field(
        default=1.0,
        description="Aggregate rate at which agent formatting preserves prompt content.",
    )

    case_results: list[CaseEvaluationResult] = Field(
        default_factory=list,
        description="Itemized results for every case and agent evaluation.",
    )
    failures: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Itemized list of failures with actionable diagnostic details.",
    )


class BaselineComparisonResult(BaseModel):
    """Comparison of a benchmark run against a stored reference baseline."""

    status: str = Field(
        ...,
        description="Status of comparison: UNCHANGED, IMPROVED, or REGRESSED.",
    )
    regressions_count: int = Field(
        default=0,
        description="Number of metric regressions detected beyond tolerance threshold.",
    )
    improvements_count: int = Field(
        default=0,
        description="Number of metric improvements detected.",
    )
    new_failures: list[str] = Field(
        default_factory=list,
        description="List of benchmark_id/agent combinations that passed in baseline but failed currently.",
    )
    metric_deltas: dict[str, float] = Field(
        default_factory=dict,
        description="Delta between current run and baseline for each macro metric.",
    )
    details: list[str] = Field(
        default_factory=list,
        description="Human-readable summary of differences.",
    )
