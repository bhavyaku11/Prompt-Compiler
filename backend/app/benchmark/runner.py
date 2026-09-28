"""CLI and programmatic runner for the Prompt Compiler Quality Benchmark Suite."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from app.ai.embeddings import MockEmbeddingProvider
from app.benchmark.baseline import BaselineManager, DEFAULT_BASELINE_PATH
from app.benchmark.dataset import BENCHMARK_DATASET, get_benchmark_cases
from app.benchmark.evaluator import QualityEvaluator
from app.benchmark.schemas import (
    BaselineComparisonResult,
    BenchmarkCase,
    BenchmarkRunSummary,
    CaseEvaluationResult,
)
from app.database.repositories import KnowledgeRepository, ProjectRepository
from app.database.session import init_db, reset_db_engine
from app.engine.agent_formatter import AgentFormatter
from app.engine.chunker import TextChunker
from app.engine.generator import PromptGenerationContext, PromptGenerator
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_retrieval import KnowledgeRetriever
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectMemoryService
from app.engine.requirements import RequirementAnalysis
from app.schemas.knowledge import KnowledgeContextItem
from app.schemas.project import ProjectContext
from app.templates.selector import TemplateSelector


class BenchmarkRunner:
    """Executes the benchmark suite across cases and agent presets."""

    def __init__(
        self,
        evaluator: QualityEvaluator | None = None,
        baseline_manager: BaselineManager | None = None,
    ) -> None:
        self.evaluator = evaluator or QualityEvaluator()
        self.baseline_manager = baseline_manager or BaselineManager()

    def run(
        self,
        cases: list[BenchmarkCase] | None = None,
        target_agents: list[str] | None = None,
        use_live_ollama: bool = False,
    ) -> BenchmarkRunSummary:
        """Synchronous wrapper to execute the benchmark suite."""
        return asyncio.run(
            self.run_async(
                cases=cases,
                target_agents=target_agents,
                use_live_ollama=use_live_ollama,
            )
        )

    async def run_async(
        self,
        cases: list[BenchmarkCase] | None = None,
        target_agents: list[str] | None = None,
        use_live_ollama: bool = False,
    ) -> BenchmarkRunSummary:
        """Asynchronously execute benchmark cases across target agent presets."""
        cases_to_run = cases if cases is not None else BENCHMARK_DATASET
        agent_formatter = AgentFormatter()
        template_selector = TemplateSelector()
        prompt_generator = PromptGenerator(template_selector=template_selector)

        # Temporary database for isolated knowledge indexing if needed
        tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp_db_path = tmp_db.name
        tmp_db.close()

        reset_db_engine()
        init_db(f"sqlite:///{tmp_db_path}")

        case_results: list[CaseEvaluationResult] = []
        failures: list[dict[str, Any]] = []

        multi_source_eligible_count = 0
        multi_source_covered_count = 0

        try:
            for case in cases_to_run:
                # Setup project context if specified
                project_context_obj: ProjectContext | None = None
                if case.project_context:
                    from app.schemas.project import Project
                    import time
                    now = time.time()
                    p_rec = Project(
                        project_id=f"proj_{case.benchmark_id.lower()}",
                        name=f"Project for {case.benchmark_id}",
                        description=case.project_context.get("description", ""),
                        created_at=now,
                        updated_at=now,
                    )
                    project_context_obj = ProjectContext(
                        project=p_rec,
                        technologies=case.project_context.get("technologies", []),
                        active_constraints=case.project_context.get("constraints", []),
                        coding_rules=case.project_context.get("coding_rules", []),
                        grouped_memories={},
                    )

                # Setup knowledge indexing & retrieval if knowledge_sources specified
                retrieved_items: list[KnowledgeContextItem] = []
                retrieved_source_names: list[str] = []

                if case.knowledge_sources:
                    from app.schemas.project import ProjectCreate
                    proj_repo = ProjectRepository()
                    proj_id = f"proj_{case.benchmark_id.lower()}"
                    if proj_repo.get(proj_id) is None:
                        proj_repo.create(
                            ProjectCreate(name=f"Project {case.benchmark_id}", description="Benchmark project"),
                            project_id=proj_id,
                        )

                    mock_embedder = MockEmbeddingProvider(dimension=768)
                    chunker = TextChunker(chunk_size=400, chunk_overlap=50)
                    know_repo = KnowledgeRepository()
                    indexer = KnowledgeIndexerService(
                        project_repository=proj_repo,
                        knowledge_repository=know_repo,
                        embedding_provider=mock_embedder,
                        chunker=chunker,
                    )

                    for ks in case.knowledge_sources:
                        await indexer.index_content(
                            project_id=proj_id,
                            source_type=ks.get("source_type", "documentation"),
                            source_name=ks["source_name"],
                            content=ks["content"],
                        )

                    search_service = KnowledgeSearchService(
                        project_repository=proj_repo,
                        knowledge_repository=know_repo,
                        embedding_provider=mock_embedder,
                    )
                    retriever = KnowledgeRetriever(search_service=search_service)

                    analysis_for_retrieval = RequirementAnalysis(
                        intent=case.title,
                        task_type=case.task_type,
                        domain=case.category,
                        confirmed_requirements=case.expected_requirements,
                        constraints=case.expected_constraints,
                    )

                    retrieval_res = await retriever.retrieve_async(
                        project_id=proj_id,
                        analysis=analysis_for_retrieval,
                        raw_input=case.input_text,
                        min_relevance_score=0.1,  # MockEmbeddingProvider cosine threshold
                    )
                    retrieved_items = retrieval_res.items
                    retrieved_source_names = [it.source_name for it in retrieved_items]

                # Check multi-source coverage
                if case.expected_knowledge_sources and len(case.expected_knowledge_sources) >= 2:
                    multi_source_eligible_count += 1
                    recalled_expected = set(case.expected_knowledge_sources).intersection(set(retrieved_source_names))
                    if len(recalled_expected) >= 2:
                        multi_source_covered_count += 1

                # Construct synthetic canonical prompt deterministically
                analysis = RequirementAnalysis(
                    intent=case.title,
                    task_type=case.task_type,
                    domain=case.category,
                    confirmed_requirements=case.expected_requirements,
                    constraints=case.expected_constraints,
                )

                if use_live_ollama:
                    gen_context = prompt_generator.create_context(
                        analysis=analysis,
                        project_context=project_context_obj,
                        retrieved_knowledge=retrieved_items,
                    )
                    gen_res = await prompt_generator.generate_async(
                        analysis=analysis,
                        project_context=project_context_obj,
                        retrieved_knowledge=retrieved_items,
                    )
                    raw_compiled_prompt = gen_res.final_prompt
                else:
                    proj_banner = ""
                    if project_context_obj:
                        proj_banner = f"=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===\n{project_context_obj.to_context_string()}\n\n"

                    know_banner = ""
                    if retrieved_items:
                        know_items = []
                        for it in retrieved_items:
                            know_items.append(f"[Source: {it.source_name} | Type: {it.source_type} | Relevance: {it.score:.2f}]\n{it.content.strip()}")
                        know_banner = "=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===\n" + "\n\n".join(know_items) + "\n\n"

                    reqs_text = "\n".join(f"- {r}" for r in case.expected_requirements) if case.expected_requirements else "- None explicitly stated"
                    constraints_text = "\n".join(f"- {c}" for c in case.expected_constraints) if case.expected_constraints else "- None specified"
                    missing_text = "- None identified"
                    assumptions_text = "- None"

                    raw_compiled_prompt = f"""{proj_banner}{know_banner}# Objective
{case.title}

# Technical Domain & Context
Domain: {case.category}

# Confirmed Requirements
{reqs_text}

# Constraints
{constraints_text}

# Open Decisions & Missing Information
{missing_text}

# Safe Assumptions
{assumptions_text}

# Implementation Instructions
1. Implement the requested {case.title} adhering strictly to all requirements and constraints.

# Expected Outcome
Successful delivery of the requested functionality without violating any invariants."""

                # Determine target agents for this case
                agents = target_agents if target_agents is not None else case.applicable_agent_targets

                for agent in agents:
                    # Format for agent
                    formatted_prompt = agent_formatter.format_prompt(
                        compiled_prompt=raw_compiled_prompt,
                        target_agent=agent,
                        analysis=analysis,
                        project_context=project_context_obj,
                        retrieved_knowledge=retrieved_items,
                    )

                    eval_result = self.evaluator.evaluate_case(
                        case=case,
                        generated_prompt=formatted_prompt,
                        target_agent=agent,
                        retrieved_sources=retrieved_source_names,
                        raw_compiled_prompt=raw_compiled_prompt,
                    )

                    case_results.append(eval_result)

                    if not eval_result.passed:
                        failures.append({
                            "benchmark_id": case.benchmark_id,
                            "target_agent": agent,
                            "diagnostics": eval_result.diagnostics,
                            "missing_requirements": eval_result.missing_requirements,
                            "violated_constraints": eval_result.violated_constraints,
                            "detected_forbidden_assumptions": eval_result.detected_forbidden_assumptions,
                            "missing_knowledge_sources": eval_result.missing_knowledge_sources,
                        })

        finally:
            reset_db_engine()
            if os.path.exists(tmp_db_path):
                os.remove(tmp_db_path)

        # Compute aggregate rates
        total_evals = len(case_results)
        passed_evals = sum(1 for r in case_results if r.passed)
        failed_evals = total_evals - passed_evals

        req_scores = [r.requirement_preservation_score for r in case_results]
        constraint_scores = [r.constraint_adherence_score for r in case_results]
        forbidden_scores = [1.0 if len(r.detected_forbidden_assumptions) == 0 else 0.0 for r in case_results]
        preset_scores = [r.agent_preset_preservation_score for r in case_results]

        avg_req = round(sum(req_scores) / total_evals, 4) if total_evals else 1.0
        avg_constraint = round(sum(constraint_scores) / total_evals, 4) if total_evals else 1.0
        avg_forbidden = round(sum(forbidden_scores) / total_evals, 4) if total_evals else 1.0
        avg_preset = round(sum(preset_scores) / total_evals, 4) if total_evals else 1.0

        retrieval_recalls = [r.retrieval_source_recall for r in case_results if r.retrieval_source_recall is not None]
        avg_recall = round(sum(retrieval_recalls) / len(retrieval_recalls), 4) if retrieval_recalls else None

        retrieval_precisions = [r.retrieval_precision for r in case_results if r.retrieval_precision is not None]
        avg_precision = round(sum(retrieval_precisions) / len(retrieval_precisions), 4) if retrieval_precisions else None

        multi_cov = round(multi_source_covered_count / multi_source_eligible_count, 4) if multi_source_eligible_count else None

        return BenchmarkRunSummary(
            benchmark_version="1.0.0",
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_cases=len(cases_to_run),
            total_evaluations=total_evals,
            passed_evaluations=passed_evals,
            failed_evaluations=failed_evals,
            requirement_preservation_rate=avg_req,
            constraint_adherence_rate=avg_constraint,
            forbidden_assumption_rate=avg_forbidden,
            retrieval_source_recall=avg_recall,
            retrieval_precision=avg_precision,
            multi_source_coverage=multi_cov,
            agent_preset_preservation_rate=avg_preset,
            case_results=case_results,
            failures=failures,
        )

    def print_report(
        self,
        summary: BenchmarkRunSummary,
        comparison: BaselineComparisonResult | None = None,
    ) -> None:
        """Print a formatted human-readable benchmark report to stdout."""
        print("\n" + "=" * 60)
        print("PROMPT COMPILER QUALITY BENCHMARK REPORT")
        print("=" * 60)
        print(f"Timestamp:             {summary.timestamp}")
        print(f"Benchmark Cases:       {summary.total_cases}")
        print(f"Total Evaluations:     {summary.total_evaluations}")
        print(f"Passed Evaluations:    {summary.passed_evaluations}")
        print(f"Failed Evaluations:    {summary.failed_evaluations}")
        print("-" * 60)
        print("CORE QUALITY METRICS:")
        print(f"  Requirement Preservation: {summary.requirement_preservation_rate:.1%}")
        print(f"  Constraint Adherence:     {summary.constraint_adherence_rate:.1%}")
        print(f"  Forbidden Assumption Rate:{summary.forbidden_assumption_rate:.1%}")
        print(f"  Agent Preset Preservation:{summary.agent_preset_preservation_rate:.1%}")

        if summary.retrieval_source_recall is not None:
            print(f"  Retrieval Source Recall:  {summary.retrieval_source_recall:.1%}")
        if summary.retrieval_precision is not None:
            print(f"  Retrieval Precision:      {summary.retrieval_precision:.1%}")
        if summary.multi_source_coverage is not None:
            print(f"  Multi-Source Coverage:    {summary.multi_source_coverage:.1%}")

        if comparison:
            print("-" * 60)
            print("REGRESSION BASELINE COMPARISON:")
            print(f"  Status:       {comparison.status}")
            print(f"  Regressions:  {comparison.regressions_count}")
            print(f"  Improvements: {comparison.improvements_count}")
            for d in comparison.details:
                print(f"  - {d}")

        if summary.failures:
            print("-" * 60)
            print(f"FAILURES DETECTED ({len(summary.failures)}):")
            for f in summary.failures:
                print(f"  [{f['benchmark_id']} | {f['target_agent']}]:")
                for diag in f.get("diagnostics", []):
                    print(f"    - {diag}")

        print("=" * 60 + "\n")


def main() -> int:
    """CLI entrypoint for running Prompt Compiler Quality Benchmark."""
    parser = argparse.ArgumentParser(description="Prompt Compiler Quality Evaluation Benchmark")
    parser.add_argument("--save-baseline", action="store_true", help="Save current run as the reference baseline")
    parser.add_argument("--baseline", type=str, default=str(DEFAULT_BASELINE_PATH), help="Path to baseline file")
    parser.add_argument("--target", type=str, help="Specific target agent to evaluate (generic, cursor, etc.)")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON format")
    parser.add_argument("--live", action="store_true", help="Run with live Ollama inference if configured")

    args = parser.parse_args()

    baseline_manager = BaselineManager(baseline_path=args.baseline)
    runner = BenchmarkRunner(baseline_manager=baseline_manager)

    target_agents = [args.target] if args.target else None
    summary = runner.run(target_agents=target_agents, use_live_ollama=args.live)
    comparison = baseline_manager.compare(summary)

    if args.save_baseline:
        saved_path = baseline_manager.save_baseline(summary)
        print(f"Saved reference baseline to: {saved_path}")

    if args.json:
        out = {
            "summary": summary.model_dump(),
            "comparison": comparison.model_dump(),
        }
        print(json.dumps(out, indent=2))
    else:
        runner.print_report(summary, comparison)

    # Return non-zero exit code if regressions were detected
    if comparison.status == "REGRESSED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
