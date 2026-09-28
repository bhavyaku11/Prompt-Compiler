"""Knowledge Retrieval Service coordinating semantic context retrieval for prompt compilation.

Provides:
- Deterministic multi-query generation from structured requirements.
- Result merging and chunk-level deduplication across queries (preserving max score).
- Task-type-aware source-type weighting (documentation, code, text, configuration).
- Relevance threshold filtering.
- Source diversity balancing (preventing single-source monopolies on competitive candidates).
- Context character budgeting and safe truncation.
- Provenance references with query attribution.
- Detailed telemetry and partial failure resilience.
- Strict project isolation.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.ai.embeddings import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingModelUnavailableError,
)
from app.config import settings
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectNotFoundError
from app.engine.requirements import RequirementAnalysis
from app.schemas.api import KnowledgeReference, KnowledgeRetrievalTelemetry
from app.schemas.knowledge import KnowledgeContextItem

logger = logging.getLogger(__name__)


# Conservative task-type-aware source-type weight multipliers.
# Weights are deliberately bounded within [0.95, 1.15] to prevent weakly relevant
# chunks from artificially eclipsing strongly relevant chunks.
TASK_SOURCE_WEIGHTS: dict[str, dict[str, float]] = {
    "build": {
        "documentation": 1.05,
        "code": 1.05,
        "text": 1.00,
    },
    "modify": {
        "code": 1.10,
        "documentation": 1.05,
        "text": 1.00,
    },
    "debug": {
        "code": 1.15,
        "documentation": 1.00,
        "text": 0.95,
    },
    "explain": {
        "documentation": 1.15,
        "code": 1.05,
        "text": 1.00,
    },
    "analyze": {
        "documentation": 1.15,
        "code": 1.05,
        "text": 1.00,
    },
}

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "documentation": 1.00,
    "code": 1.00,
    "text": 1.00,
}


@dataclass
class MergedCandidate:
    """Internal candidate representation during multi-query merging and ranking."""

    chunk_id: str
    source_id: str
    source_name: str
    source_type: str
    chunk_index: int
    content: str
    raw_score: float
    effective_score: float
    metadata: dict[str, Any]
    matched_queries: list[str] = field(default_factory=list)


@dataclass
class RetrievalExecutionResult:
    """Structured result of knowledge retrieval for prompt compilation."""

    items: list[KnowledgeContextItem] = field(default_factory=list)
    references: list[KnowledgeReference] = field(default_factory=list)
    telemetry: KnowledgeRetrievalTelemetry = field(default_factory=KnowledgeRetrievalTelemetry)


class KnowledgeRetriever:
    """Coordinates project knowledge retrieval, multi-query expansion, relevance filtering,
    source-type weighting, source diversity, and context budgeting for compilation.
    """

    def __init__(
        self,
        search_service: KnowledgeSearchService,
        min_relevance_score: float | None = None,
        top_k: int | None = None,
        max_context_chars: int | None = None,
        max_retrieval_queries: int | None = None,
        source_weighting_enabled: bool | None = None,
        source_diversity_enabled: bool | None = None,
        diversity_ratio: float | None = None,
    ) -> None:
        self._search_service = search_service
        self._min_relevance_score = min_relevance_score
        self._top_k = top_k
        self._max_context_chars = max_context_chars
        self._max_retrieval_queries = max_retrieval_queries
        self._source_weighting_enabled = source_weighting_enabled
        self._source_diversity_enabled = source_diversity_enabled
        self._diversity_ratio = diversity_ratio

    def build_retrieval_query(
        self,
        analysis: RequirementAnalysis | None,
        raw_input: str,
    ) -> str:
        """Construct the primary deterministic, compact search query from requirement analysis.

        Maintains full backward compatibility with Task 21 callers.
        """
        queries = self.build_retrieval_queries(analysis, raw_input, max_queries=1)
        if queries:
            return queries[0]
        return raw_input.strip()[:500]

    def build_retrieval_queries(
        self,
        analysis: RequirementAnalysis | None,
        raw_input: str,
        max_queries: int | None = None,
    ) -> list[str]:
        """Construct a bounded list of deterministic, focused search queries from requirement analysis.

        Zero LLM calls are made. Queries are constructed along distinct semantic dimensions:
        1. Primary intent and core domain/requirement overview.
        2. Technical implementation details and explicit constraints.
        3. Architectural context, design specifications, and open decision topics.

        Args:
            analysis: Validated RequirementAnalysis or None.
            raw_input: Original raw user requirement.
            max_queries: Optional limit override (defaults to config limit).

        Returns:
            Deterministic, deduplicated list of search query strings bounded to max_queries.
        """
        limit = (
            max_queries
            if max_queries is not None
            else (
                self._max_retrieval_queries
                if self._max_retrieval_queries is not None
                else settings.knowledge_max_retrieval_queries
            )
        )
        limit = max(1, limit)

        if analysis is None:
            cleaned = " ".join(raw_input.strip().split())[:500].strip()
            return [cleaned] if cleaned else []

        queries: list[str] = []
        seen_normalized: set[str] = set()

        def _add_query(q_str: str) -> None:
            cleaned = " ".join(q_str.strip().split())[:500].strip()
            if not cleaned:
                return
            norm = cleaned.lower()
            if norm not in seen_normalized and len(queries) < limit:
                seen_normalized.add(norm)
                queries.append(cleaned)

        intent = analysis.intent.strip()
        domain = analysis.domain.strip() if analysis.domain else ""
        has_specific_domain = bool(domain and domain.lower() not in ("general", "other", "unknown", "general software", ""))
        conf_reqs = [r.strip() for r in analysis.confirmed_requirements if r.strip()]
        constraints = [c.strip() for c in analysis.constraints if c.strip()]
        missing_info = [m.strip() for m in analysis.missing_information if m.strip()]

        # Query 1: Primary Task / Intent Overview
        parts1: list[str] = []
        if intent:
            parts1.append(intent)
        if has_specific_domain:
            parts1.append(f"Domain: {domain}")
        if conf_reqs:
            req_snippet = " ".join(conf_reqs[:3])
            if req_snippet:
                parts1.append(req_snippet)
        query1 = ". ".join(parts1).strip()
        if not query1:
            query1 = raw_input.strip()
        _add_query(query1)

        # Query 2: Technical / Implementation Details
        if len(queries) < limit:
            parts2: list[str] = []
            if has_specific_domain:
                parts2.append(f"{domain} implementation")
            elif intent:
                parts2.append(f"Implementation for {intent}")

            if conf_reqs:
                parts2.append(" ".join(conf_reqs[:3]))
            if constraints:
                parts2.append("Constraints: " + " ".join(constraints[:2]))

            query2 = ". ".join(parts2).strip()
            _add_query(query2)

        # Query 3: Architectural / System Context
        if len(queries) < limit:
            parts3: list[str] = []
            if intent:
                parts3.append(f"Architecture and specifications for {intent}")
            if missing_info:
                parts3.append("Decisions: " + " ".join(missing_info[:2]))
            elif constraints:
                parts3.append("Architectural constraints: " + " ".join(constraints[:2]))
            elif has_specific_domain:
                parts3.append(f"System architecture: {domain}")

            query3 = ". ".join(parts3).strip()
            _add_query(query3)

        # Fallback if somehow no query was generated
        if not queries:
            fallback = " ".join(raw_input.strip().split())[:500].strip()
            if fallback:
                queries.append(fallback)

        return queries[:limit]

    def calculate_source_type_weight(
        self,
        task_type: str | None,
        source_type: str,
        metadata: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> float:
        """Calculate conservative deterministic multiplier based on task type and source category."""
        if not enabled:
            return 1.0

        task_key = (task_type or "build").strip().lower()
        weights = TASK_SOURCE_WEIGHTS.get(task_key, DEFAULT_SOURCE_WEIGHTS)
        weight = weights.get(source_type.strip().lower(), 1.0)

        # Check if configuration subtype (e.g. JSON configuration files)
        if metadata and metadata.get("subtype") == "configuration":
            if task_key in ("build", "modify", "debug"):
                weight = max(weight, 1.10)

        return weight

    def apply_source_diversity(
        self,
        candidates: list[MergedCandidate],
        top_k: int,
        diversity_ratio: float = 0.8,
        enabled: bool = True,
    ) -> list[MergedCandidate]:
        """Balance candidates across distinct source documents without forcing weak results.

        Strategy:
        1. Always select the single strongest candidate.
        2. Promote competitive candidates from unrepresented sources (score >= top_score * diversity_ratio).
        3. Fill remaining slots up to top_k by score descending.
        """
        if not enabled or len(candidates) <= 1:
            return candidates[:top_k]

        top_score = candidates[0].effective_score
        diversity_min_score = top_score * diversity_ratio

        selected: list[MergedCandidate] = []
        selected_chunk_ids: set[str] = set()
        selected_source_ids: set[str] = set()

        # Pass 1: Select the strongest candidate
        selected.append(candidates[0])
        selected_chunk_ids.add(candidates[0].chunk_id)
        selected_source_ids.add(candidates[0].source_id)

        # Pass 2: Select competitive candidates from unrepresented sources
        for c in candidates[1:]:
            if len(selected) >= top_k:
                break
            if c.source_id not in selected_source_ids and c.effective_score >= diversity_min_score:
                selected.append(c)
                selected_chunk_ids.add(c.chunk_id)
                selected_source_ids.add(c.source_id)

        # Pass 3: Fill remaining slots by score from any source
        for c in candidates:
            if len(selected) >= top_k:
                break
            if c.chunk_id not in selected_chunk_ids:
                selected.append(c)
                selected_chunk_ids.add(c.chunk_id)

        # Sort final selection strictly by effective score descending with deterministic tie-breaking
        selected.sort(key=lambda c: (-c.effective_score, c.source_name, c.chunk_index, c.chunk_id))
        return selected

    async def retrieve_async(
        self,
        project_id: str | None,
        analysis: RequirementAnalysis | None,
        raw_input: str,
        enabled: bool = True,
        top_k: int | None = None,
        min_relevance_score: float | None = None,
        max_context_chars: int | None = None,
        max_queries: int | None = None,
        source_weighting: bool | None = None,
        source_diversity: bool | None = None,
        diversity_ratio: float | None = None,
    ) -> RetrievalExecutionResult:
        """Execute scoped multi-query semantic knowledge retrieval with relevance thresholding,
        source-type weighting, source diversity, and context budgeting.

        Args:
            project_id: Target project ID (or None if unassociated).
            analysis: Validated RequirementAnalysis or None.
            raw_input: Original user input string.
            enabled: Request-level retrieval toggle.
            top_k: Maximum chunks to include.
            min_relevance_score: Minimum cosine similarity threshold.
            max_context_chars: Maximum character budget for retrieved text.
            max_queries: Maximum number of search queries to generate.
            source_weighting: Toggle for task-type-aware source weighting.
            source_diversity: Toggle for multi-source diversity balancing.
            diversity_ratio: Minimum score ratio relative to top score for diversity promotion.

        Returns:
            RetrievalExecutionResult with contextual items, provenance references, and telemetry.
        """
        start_time = time.perf_counter()

        # 1. Check feature toggle
        if not enabled or not settings.knowledge_retrieval_enabled:
            return RetrievalExecutionResult(
                items=[],
                references=[],
                telemetry=KnowledgeRetrievalTelemetry(
                    attempted=False,
                    skipped=True,
                    skip_reason="retrieval_disabled",
                    latency_ms=0.0,
                ),
            )

        # 2. Check project association
        if not project_id:
            return RetrievalExecutionResult(
                items=[],
                references=[],
                telemetry=KnowledgeRetrievalTelemetry(
                    attempted=False,
                    skipped=True,
                    skip_reason="no_project_id",
                    latency_ms=0.0,
                ),
            )

        # 3. Resolve parameters & configuration
        k = (
            top_k
            if top_k is not None
            else (
                self._top_k
                if self._top_k is not None
                else settings.knowledge_retrieval_top_k
            )
        )
        min_score = (
            min_relevance_score
            if min_relevance_score is not None
            else (
                self._min_relevance_score
                if self._min_relevance_score is not None
                else settings.knowledge_min_relevance_score
            )
        )
        char_budget = (
            max_context_chars
            if max_context_chars is not None
            else (
                self._max_context_chars
                if self._max_context_chars is not None
                else settings.knowledge_max_context_chars
            )
        )
        q_limit = (
            max_queries
            if max_queries is not None
            else (
                self._max_retrieval_queries
                if self._max_retrieval_queries is not None
                else settings.knowledge_max_retrieval_queries
            )
        )
        use_weighting = (
            source_weighting
            if source_weighting is not None
            else (
                self._source_weighting_enabled
                if self._source_weighting_enabled is not None
                else settings.knowledge_source_weighting_enabled
            )
        )
        use_diversity = (
            source_diversity
            if source_diversity is not None
            else (
                self._source_diversity_enabled
                if self._source_diversity_enabled is not None
                else settings.knowledge_source_diversity_enabled
            )
        )
        div_ratio = (
            diversity_ratio
            if diversity_ratio is not None
            else (
                self._diversity_ratio
                if self._diversity_ratio is not None
                else settings.knowledge_source_diversity_min_score_ratio
            )
        )

        # 4. Generate deterministic search queries
        queries = self.build_retrieval_queries(analysis, raw_input, max_queries=q_limit)
        if not queries:
            return RetrievalExecutionResult(
                items=[],
                references=[],
                telemetry=KnowledgeRetrievalTelemetry(
                    attempted=False,
                    skipped=True,
                    skip_reason="empty_query",
                    latency_ms=0.0,
                ),
            )

        task_type = analysis.task_type if analysis else "build"

        # 5. Execute searches across all unique queries (fault-tolerant)
        successful_queries = 0
        failed_queries = 0
        last_exception: Exception | None = None
        raw_count_total = 0

        # Mapping: chunk_id -> MergedCandidate
        merged_candidates: dict[str, MergedCandidate] = {}

        for query_str in queries:
            try:
                search_response = await self._search_service.search(
                    project_id=project_id,
                    query=query_str,
                    top_k=settings.knowledge_search_top_k,
                )
                successful_queries += 1
                raw_results = search_response.results
                raw_count_total += len(raw_results)

                for r in raw_results:
                    raw_score = r.score
                    weight = self.calculate_source_type_weight(
                        task_type=task_type,
                        source_type=r.source_type,
                        metadata=r.metadata,
                        enabled=use_weighting,
                    )
                    effective_score = round(min(1.0, raw_score * weight), 4)

                    if r.chunk_id in merged_candidates:
                        existing = merged_candidates[r.chunk_id]
                        # Retain maximum score across matching queries
                        if effective_score > existing.effective_score:
                            existing.effective_score = effective_score
                            existing.raw_score = max(existing.raw_score, raw_score)
                        if query_str not in existing.matched_queries:
                            existing.matched_queries.append(query_str)
                    else:
                        merged_candidates[r.chunk_id] = MergedCandidate(
                            chunk_id=r.chunk_id,
                            source_id=r.source_id,
                            source_name=r.source_name,
                            source_type=r.source_type,
                            chunk_index=r.chunk_index,
                            content=r.content,
                            raw_score=raw_score,
                            effective_score=effective_score,
                            metadata=r.metadata,
                            matched_queries=[query_str],
                        )

            except ProjectNotFoundError:
                # Re-raise project not found error for API layer handling
                raise
            except (EmbeddingModelUnavailableError, EmbeddingConnectionError, EmbeddingError) as exc:
                failed_queries += 1
                last_exception = exc
                logger.warning(
                    f"Knowledge retrieval query '{query_str}' failed for project '{project_id}': {exc}"
                )
            except Exception as exc:
                failed_queries += 1
                last_exception = exc
                logger.warning(
                    f"Knowledge retrieval query '{query_str}' failed unexpectedly for project '{project_id}': {exc}"
                )

        # 6. If all queries failed, return graceful degraded telemetry
        if successful_queries == 0:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            skip_msg = f"embedding_unavailable: {last_exception}" if last_exception else "all_queries_failed"
            return RetrievalExecutionResult(
                items=[],
                references=[],
                telemetry=KnowledgeRetrievalTelemetry(
                    attempted=True,
                    skipped=True,
                    skip_reason=skip_msg,
                    raw_count=0,
                    filtered_count=0,
                    latency_ms=round(latency_ms, 2),
                    query_used=queries[0] if queries else None,
                    queries_attempted=queries,
                    successful_queries=0,
                    failed_queries=failed_queries,
                    results_before_deduplication=0,
                    results_after_deduplication=0,
                    results_after_threshold=0,
                    final_result_count=0,
                    sources_represented=[],
                ),
            )

        results_after_dedup = len(merged_candidates)

        # 7. Filter by relevance threshold
        filtered = [
            c for c in merged_candidates.values()
            if c.effective_score >= min_score
        ]
        results_after_thresh = len(filtered)

        # 8. Deterministic pre-sorting by effective_score descending with stable tie-breakers
        filtered.sort(key=lambda c: (-c.effective_score, c.source_name, c.chunk_index, c.chunk_id))

        # 9. Apply source diversity balancing
        diverse_candidates = self.apply_source_diversity(
            candidates=filtered,
            top_k=k,
            diversity_ratio=div_ratio,
            enabled=use_diversity,
        )

        # 10. Deduplicate content and enforce character budget
        seen_texts: set[str] = set()
        budgeted_items: list[KnowledgeContextItem] = []
        references: list[KnowledgeReference] = []
        current_chars = 0

        for cand in diverse_candidates:
            if len(budgeted_items) >= k:
                break

            normalized_content = cand.content.strip()
            if normalized_content in seen_texts:
                continue
            seen_texts.add(normalized_content)

            remaining_budget = char_budget - current_chars
            if remaining_budget <= 0:
                break

            # If chunk exceeds remaining budget, truncate if meaningful (>100 chars), else stop
            if len(normalized_content) > remaining_budget:
                if remaining_budget >= 100:
                    normalized_content = normalized_content[: remaining_budget - 3].rstrip() + "..."
                else:
                    break

            current_chars += len(normalized_content)

            item = KnowledgeContextItem(
                chunk_id=cand.chunk_id,
                source_id=cand.source_id,
                source_name=cand.source_name,
                source_type=cand.source_type,
                chunk_index=cand.chunk_index,
                content=normalized_content,
                score=cand.effective_score,
                metadata=cand.metadata,
                matched_queries=cand.matched_queries,
            )
            budgeted_items.append(item)

            ref = KnowledgeReference(
                chunk_id=cand.chunk_id,
                source_id=cand.source_id,
                source_name=cand.source_name,
                source_type=cand.source_type,
                score=cand.effective_score,
                matched_queries=cand.matched_queries,
            )
            references.append(ref)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        sources_represented = sorted(list({item.source_name for item in budgeted_items}))

        telemetry = KnowledgeRetrievalTelemetry(
            attempted=True,
            skipped=False,
            skip_reason=None,
            raw_count=raw_count_total,
            filtered_count=results_after_thresh,
            latency_ms=round(latency_ms, 2),
            query_used=queries[0] if queries else None,
            queries_attempted=queries,
            successful_queries=successful_queries,
            failed_queries=failed_queries,
            results_before_deduplication=raw_count_total,
            results_after_deduplication=results_after_dedup,
            results_after_threshold=results_after_thresh,
            final_result_count=len(budgeted_items),
            sources_represented=sources_represented,
        )

        return RetrievalExecutionResult(
            items=budgeted_items,
            references=references,
            telemetry=telemetry,
        )
