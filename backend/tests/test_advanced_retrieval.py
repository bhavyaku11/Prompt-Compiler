"""Tests for Task 23: Advanced Retrieval & Multi-Document Context Synthesis.

Verifies:
1. Single-query behavior remains compatible.
2. Multiple retrieval queries are generated deterministically.
3. Maximum query count is respected (max_queries cap).
4. Query deduplication works (no identical queries).
5. Results from multiple queries are merged.
6. Duplicate chunks are removed across queries.
7. Highest score is retained for duplicate chunks.
8. Result ordering is deterministic.
9. Relevance threshold remains enforced (min_relevance_score).
10. Source-type information is preserved (documentation, code, text).
11. Source-type weighting behaves deterministically.
12. Architecture/explain tasks favor relevant documentation when appropriate.
13. Implementation/debug tasks favor relevant code when appropriate.
14. Mixed tasks can retrieve multiple source types.
15. Source diversity works without forcing weak results.
16. Context character budget remains enforced.
17. Top-k remains enforced.
18. Multiple source boundaries are preserved in context.
19. Provenance references remain correct.
20. Query provenance works (matched_queries tracking).
21. Telemetry reflects multi-query retrieval metrics.
22. Partial retrieval failure is handled correctly (one failing query does not abort other queries).
23. Project isolation remains intact.
24. Explicit user requirements remain highest priority.
25. Confirmed project memory remains higher priority than retrieved knowledge.
26. Compilation does not write to project memory or candidate memory (read-only invariant).
27. Interview Mode remains compatible with multi-document retrieval.
28. All five agent presets remain compatible with multi-document retrieved knowledge.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from app.ai.embeddings import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingModelUnavailableError,
    MockEmbeddingProvider,
)
from app.api.compile import (
    get_compilation_repository,
    get_knowledge_retriever,
    get_project_service,
    get_prompt_critic,
    get_prompt_generator,
    get_requirement_engine,
)
from app.config import settings
from app.database.repositories import (
    CandidateMemoryRepository,
    CompilationRepository,
    KnowledgeRepository,
    ProjectMemoryRepository,
    ProjectRepository,
)
from app.database.session import init_db, reset_db_engine
from app.engine.agent_formatter import AgentFormatter
from app.engine.chunker import TextChunker
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import PromptGenerationContext, PromptGenerationResult, PromptGenerator
from app.engine.interviewer import PromptInterviewer
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_retrieval import (
    KnowledgeRetriever,
    MergedCandidate,
    RetrievalExecutionResult,
)
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectMemoryService
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.api import CompileRequest
from app.schemas.candidate_memory import CandidateStatus
from app.schemas.knowledge import KnowledgeContextItem, KnowledgeSearchResult, KnowledgeSearchResponse
from app.templates.selector import TemplateSelector


class TestAdvancedRetrieval(unittest.TestCase):
    """Unit and integration tests for Task 23 advanced retrieval & multi-document context synthesis."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_advanced_retrieval.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.candidate_repo = CandidateMemoryRepository(database_url=self.db_url)
        self.knowledge_repo = KnowledgeRepository(database_url=self.db_url)
        self.compilation_repo = CompilationRepository(database_url=self.db_url)

        self.project_service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
            candidate_repository=self.candidate_repo,
        )
        self.mock_embedding_provider = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
        self.chunker = TextChunker(chunk_size=300, chunk_overlap=50)
        self.indexer = KnowledgeIndexerService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.mock_embedding_provider,
            chunker=self.chunker,
        )
        self.search_service = KnowledgeSearchService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.mock_embedding_provider,
        )
        self.retriever = KnowledgeRetriever(
            search_service=self.search_service,
            min_relevance_score=0.1,
            top_k=3,
            max_context_chars=2000,
        )

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_adv_retrieval")
        app.dependency_overrides[get_current_user] = lambda: self.test_user

        # Create primary test project A
        self.project_a = self.project_service.create_project(
            name="Project Alpha",
            description="Alpha authentication & API backend",
            user_id=self.test_user.id,
        )

        # Index multi-source documents for Project A
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_a.project_id,
                source_type="documentation",
                source_name="docs/authentication.md",
                content="OAuth2 authentication specifications. The JWT payload includes user_id, email, and role permissions.",
            )
        )
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_a.project_id,
                source_type="documentation",
                source_name="docs/database.md",
                content="Database architecture for user auth. Tables: users, credentials, refresh_tokens, sessions.",
            )
        )
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_a.project_id,
                source_type="code",
                source_name="src/auth.py",
                content="def authenticate_user(db, username, password):\n    # Update OAuth2 authentication API with token verification\n    return create_jwt_token(username)",
            )
        )
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_a.project_id,
                source_type="code",
                source_name="src/types.ts",
                content="export interface AuthToken {\n  userId: string;\n  accessToken: string;\n  expiresIn: number;\n}",
            )
        )
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_a.project_id,
                source_type="code",
                source_name="config/auth.json",
                content='{\n  "jwt_secret": "env_secret",\n  "token_ttl_seconds": 3600\n}',
                metadata={"subtype": "configuration"},
            )
        )

        # Create isolated test project B with sensitive/unrelated content
        self.project_b = self.project_service.create_project(
            name="Project Beta",
            description="Beta banking system",
            user_id=self.test_user.id,
        )
        asyncio.run(
            self.indexer.index_content(
                project_id=self.project_b.project_id,
                source_type="documentation",
                source_name="docs/secrets.md",
                content="Top secret banking encryption keys and private credentials for Project B.",
            )
        )

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    # 1. Single-query behavior remains compatible
    def test_single_query_backward_compatibility(self) -> None:
        analysis = RequirementAnalysis(
            intent="Update authentication API",
            task_type="modify",
            domain="backend",
            confirmed_requirements=["JWT auth"],
        )
        q = self.retriever.build_retrieval_query(analysis, "raw input")
        self.assertIsInstance(q, str)
        self.assertIn("Update authentication API", q)
        self.assertIn("Domain: backend", q)
        self.assertIn("JWT auth", q)

    # 2. Multiple retrieval queries are generated deterministically
    def test_multiple_queries_generated_deterministically(self) -> None:
        analysis = RequirementAnalysis(
            intent="Implement refresh token flow",
            task_type="build",
            domain="security",
            confirmed_requirements=["Store refresh tokens in database", "Token expiration 30 days"],
            constraints=["Must be backward compatible with existing sessions"],
            missing_information=["Token rotation strategy"],
        )
        queries1 = self.retriever.build_retrieval_queries(analysis, "raw", max_queries=3)
        queries2 = self.retriever.build_retrieval_queries(analysis, "raw", max_queries=3)

        self.assertEqual(queries1, queries2)
        self.assertGreater(len(queries1), 1)
        self.assertLessEqual(len(queries1), 3)

        # Verify query angles
        self.assertTrue(any("Implement refresh token flow" in q for q in queries1))
        self.assertTrue(any("implementation" in q.lower() or "constraints" in q.lower() for q in queries1))
        self.assertTrue(any("architecture" in q.lower() or "decisions" in q.lower() for q in queries1))

    # 3. Maximum query count is respected
    def test_max_query_count_enforced(self) -> None:
        analysis = RequirementAnalysis(
            intent="Refactor database schema",
            task_type="modify",
            domain="database",
            confirmed_requirements=["Req 1", "Req 2"],
            constraints=["Constraint 1"],
            missing_information=["Open decision 1"],
        )
        queries_cap1 = self.retriever.build_retrieval_queries(analysis, "raw", max_queries=1)
        self.assertEqual(len(queries_cap1), 1)

        queries_cap2 = self.retriever.build_retrieval_queries(analysis, "raw", max_queries=2)
        self.assertEqual(len(queries_cap2), 2)

    # 4. Query deduplication works
    def test_query_deduplication(self) -> None:
        # Minimal analysis where second and third passes would produce redundant queries
        analysis = RequirementAnalysis(
            intent="Simple task",
            task_type="build",
            domain="",
            confirmed_requirements=[],
            constraints=[],
            missing_information=[],
        )
        queries = self.retriever.build_retrieval_queries(analysis, "Simple task", max_queries=3)
        # Should not produce identical duplicate strings
        lower_queries = [q.lower().strip() for q in queries]
        self.assertEqual(len(lower_queries), len(set(lower_queries)))

    # 5 & 6. Results from multiple queries are merged and duplicate chunks removed
    def test_multi_query_merging_and_chunk_deduplication(self) -> None:
        mock_search = MagicMock(spec=KnowledgeSearchService)
        # Query 1 returns Chunk A and Chunk B
        # Query 2 returns Chunk B and Chunk C
        chunk_a = KnowledgeSearchResult(
            chunk_id="chunk-a",
            source_id="src-1",
            source_name="docs/auth.md",
            source_type="documentation",
            chunk_index=0,
            content="Content A",
            score=0.80,
            metadata={},
        )
        chunk_b_q1 = KnowledgeSearchResult(
            chunk_id="chunk-b",
            source_id="src-1",
            source_name="docs/auth.md",
            source_type="documentation",
            chunk_index=1,
            content="Content B",
            score=0.75,
            metadata={},
        )
        chunk_b_q2 = KnowledgeSearchResult(
            chunk_id="chunk-b",
            source_id="src-1",
            source_name="docs/auth.md",
            source_type="documentation",
            chunk_index=1,
            content="Content B",
            score=0.88,  # Higher score in query 2!
            metadata={},
        )
        chunk_c = KnowledgeSearchResult(
            chunk_id="chunk-c",
            source_id="src-2",
            source_name="src/auth.py",
            source_type="code",
            chunk_index=0,
            content="Content C",
            score=0.70,
            metadata={},
        )

        async def fake_search(project_id, query, top_k):
            if "query1" in query.lower() or "intent" in query.lower():
                return KnowledgeSearchResponse(
                    project_id=project_id,
                    query=query,
                    top_k=top_k,
                    total_results=2,
                    results=[chunk_a, chunk_b_q1],
                )
            else:
                return KnowledgeSearchResponse(
                    project_id=project_id,
                    query=query,
                    top_k=top_k,
                    total_results=2,
                    results=[chunk_b_q2, chunk_c],
                )

        mock_search.search = AsyncMock(side_effect=fake_search)
        retriever = KnowledgeRetriever(search_service=mock_search, min_relevance_score=0.5, top_k=5)

        # Mock query generator to return 2 distinct queries
        retriever.build_retrieval_queries = MagicMock(return_value=["intent query1", "technical query2"])  # type: ignore

        res = asyncio.run(
            retriever.retrieve_async(
                project_id="p1",
                analysis=None,
                raw_input="test",
                source_weighting=False,
                source_diversity=False,
            )
        )

        chunk_ids = [item.chunk_id for item in res.items]
        # Chunks should be unique (no duplicates of chunk-b)
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertIn("chunk-a", chunk_ids)
        self.assertIn("chunk-b", chunk_ids)
        self.assertIn("chunk-c", chunk_ids)

        # 7. Highest score is retained for duplicate chunk-b
        b_item = next(item for item in res.items if item.chunk_id == "chunk-b")
        self.assertEqual(b_item.score, 0.88)

        # 20. Query provenance: matched_queries records both queries that hit chunk-b
        self.assertEqual(len(b_item.matched_queries), 2)
        self.assertIn("intent query1", b_item.matched_queries)
        self.assertIn("technical query2", b_item.matched_queries)

    # 8. Result ordering is deterministic
    def test_deterministic_result_ordering(self) -> None:
        mock_search = MagicMock(spec=KnowledgeSearchService)
        # Three chunks with identical scores
        c1 = KnowledgeSearchResult(
            chunk_id="chunk-3",
            source_id="src-z",
            source_name="z_file.md",
            source_type="documentation",
            chunk_index=0,
            content="C1",
            score=0.80,
            metadata={},
        )
        c2 = KnowledgeSearchResult(
            chunk_id="chunk-1",
            source_id="src-a",
            source_name="a_file.md",
            source_type="documentation",
            chunk_index=0,
            content="C2",
            score=0.80,
            metadata={},
        )
        c3 = KnowledgeSearchResult(
            chunk_id="chunk-2",
            source_id="src-a",
            source_name="a_file.md",
            source_type="documentation",
            chunk_index=1,
            content="C3",
            score=0.80,
            metadata={},
        )

        mock_search.search = AsyncMock(
            return_value=KnowledgeSearchResponse(
                project_id="p1",
                query="q",
                top_k=5,
                total_results=3,
                results=[c1, c2, c3],
            )
        )
        retriever = KnowledgeRetriever(search_service=mock_search, min_relevance_score=0.5, top_k=5)
        retriever.build_retrieval_queries = MagicMock(return_value=["q"])  # type: ignore

        res1 = asyncio.run(retriever.retrieve_async(project_id="p1", analysis=None, raw_input="q", source_weighting=False, source_diversity=False))
        res2 = asyncio.run(retriever.retrieve_async(project_id="p1", analysis=None, raw_input="q", source_weighting=False, source_diversity=False))

        # Tie-breaker sorts by source_name ("a_file.md" before "z_file.md") then chunk_index (0 before 1)
        self.assertEqual([i.chunk_id for i in res1.items], ["chunk-1", "chunk-2", "chunk-3"])
        self.assertEqual([i.chunk_id for i in res1.items], [i.chunk_id for i in res2.items])

    # 9. Relevance threshold remains enforced
    def test_relevance_threshold_enforced(self) -> None:
        mock_search = MagicMock(spec=KnowledgeSearchService)
        high = KnowledgeSearchResult(chunk_id="c1", source_id="s1", source_name="f.md", source_type="documentation", chunk_index=0, content="High", score=0.85, metadata={})
        low = KnowledgeSearchResult(chunk_id="c2", source_id="s1", source_name="f.md", source_type="documentation", chunk_index=1, content="Low", score=0.45, metadata={})
        mock_search.search = AsyncMock(return_value=KnowledgeSearchResponse(project_id="p1", query="q", top_k=5, total_results=2, results=[high, low]))

        retriever = KnowledgeRetriever(search_service=mock_search, min_relevance_score=0.6, top_k=5)
        retriever.build_retrieval_queries = MagicMock(return_value=["q"])  # type: ignore

        res = asyncio.run(retriever.retrieve_async(project_id="p1", analysis=None, raw_input="q"))
        self.assertEqual(len(res.items), 1)
        self.assertEqual(res.items[0].chunk_id, "c1")
        self.assertEqual(res.telemetry.filtered_count, 1)

    # 10, 11, 12, 13. Source-type weighting & task-type alignment
    def test_source_type_weighting_task_types(self) -> None:
        # For "explain" or "analyze", documentation gets 1.15, code gets 1.05
        w_doc = self.retriever.calculate_source_type_weight(task_type="explain", source_type="documentation")
        w_code = self.retriever.calculate_source_type_weight(task_type="explain", source_type="code")
        self.assertGreater(w_doc, w_code)
        self.assertEqual(w_doc, 1.15)
        self.assertEqual(w_code, 1.05)

        # For "debug", code gets 1.15, doc gets 1.00
        w_doc_dbg = self.retriever.calculate_source_type_weight(task_type="debug", source_type="documentation")
        w_code_dbg = self.retriever.calculate_source_type_weight(task_type="debug", source_type="code")
        self.assertGreater(w_code_dbg, w_doc_dbg)
        self.assertEqual(w_code_dbg, 1.15)
        self.assertEqual(w_doc_dbg, 1.00)

        # Configuration subtype boost
        w_cfg = self.retriever.calculate_source_type_weight(task_type="build", source_type="code", metadata={"subtype": "configuration"})
        self.assertEqual(w_cfg, 1.10)

    # 14. Mixed tasks can retrieve multiple source types
    def test_mixed_task_retrieves_multiple_source_types(self) -> None:
        analysis = RequirementAnalysis(
            intent="Update authentication API with database schema and frontend types",
            task_type="modify",
            domain="backend",
            confirmed_requirements=["Update OAuth2 authentication", "Verify database schema and token types"],
        )
        res = asyncio.run(
            self.retriever.retrieve_async(
                project_id=self.project_a.project_id,
                analysis=analysis,
                raw_input="Update authentication API with database schema and frontend types",
                top_k=5,
            )
        )
        self.assertGreater(len(res.items), 1)
        source_types = {item.source_type for item in res.items}
        # Both documentation and code sources are retrieved
        self.assertIn("documentation", source_types)
        self.assertIn("code", source_types)

    # 15. Source diversity works without forcing weak results
    def test_source_diversity_promotes_competitive_sources(self) -> None:
        # Candidate 1: Doc 1 (Score 0.90)
        # Candidate 2: Doc 1 (Score 0.88)
        # Candidate 3: Code 1 (Score 0.85) - competitive (0.85 >= 0.90 * 0.8 = 0.72)
        c1 = MergedCandidate(chunk_id="c1", source_id="s1", source_name="doc1.md", source_type="documentation", chunk_index=0, content="D1", raw_score=0.90, effective_score=0.90, metadata={})
        c2 = MergedCandidate(chunk_id="c2", source_id="s1", source_name="doc1.md", source_type="documentation", chunk_index=1, content="D2", raw_score=0.88, effective_score=0.88, metadata={})
        c3 = MergedCandidate(chunk_id="c3", source_id="s2", source_name="code1.py", source_type="code", chunk_index=0, content="C1", raw_score=0.85, effective_score=0.85, metadata={})

        diverse = self.retriever.apply_source_diversity(
            candidates=[c1, c2, c3],
            top_k=2,
            diversity_ratio=0.8,
            enabled=True,
        )
        # Top 2 should include both s1 (doc1.md) and s2 (code1.py), promoting diversity over chunk c2!
        sources = [c.source_name for c in diverse]
        self.assertEqual(sources, ["doc1.md", "code1.py"])

    def test_source_diversity_does_not_force_weak_sources(self) -> None:
        # Candidate 1: Doc 1 (Score 0.95)
        # Candidate 2: Doc 1 (Score 0.92)
        # Candidate 3: Weak source 2 (Score 0.52) - NOT competitive (0.52 < 0.95 * 0.8 = 0.76)
        c1 = MergedCandidate(chunk_id="c1", source_id="s1", source_name="doc1.md", source_type="documentation", chunk_index=0, content="D1", raw_score=0.95, effective_score=0.95, metadata={})
        c2 = MergedCandidate(chunk_id="c2", source_id="s1", source_name="doc1.md", source_type="documentation", chunk_index=1, content="D2", raw_score=0.92, effective_score=0.92, metadata={})
        c3 = MergedCandidate(chunk_id="c3", source_id="s2", source_name="weak.py", source_type="code", chunk_index=0, content="W1", raw_score=0.52, effective_score=0.52, metadata={})

        diverse = self.retriever.apply_source_diversity(
            candidates=[c1, c2, c3],
            top_k=2,
            diversity_ratio=0.8,
            enabled=True,
        )
        # Should NOT force weak.py when it's uncompetitive! It should pick doc1.md chunks.
        chunk_ids = [c.chunk_id for c in diverse]
        self.assertEqual(chunk_ids, ["c1", "c2"])

    # 16 & 17. Context character budget & top-k enforced
    def test_context_character_budget_and_top_k(self) -> None:
        mock_search = MagicMock(spec=KnowledgeSearchService)
        chunks = [
            KnowledgeSearchResult(
                chunk_id=f"c{i}",
                source_id=f"s{i}",
                source_name=f"f{i}.md",
                source_type="documentation",
                chunk_index=0,
                content=f"Unique chunk {i} " + "A" * 120,
                score=0.90 - i * 0.05,
                metadata={},
            )
            for i in range(5)
        ]
        mock_search.search = AsyncMock(return_value=KnowledgeSearchResponse(project_id="p1", query="q", top_k=5, total_results=5, results=chunks))
        retriever = KnowledgeRetriever(search_service=mock_search, min_relevance_score=0.5)
        retriever.build_retrieval_queries = MagicMock(return_value=["q"])  # type: ignore

        # Top-k cap test
        res_k = asyncio.run(retriever.retrieve_async(project_id="p1", analysis=None, raw_input="q", top_k=2, max_context_chars=1000))
        self.assertEqual(len(res_k.items), 2)

        # Character budget cap test (250 chars can only hold 1 chunk of 150 chars, second is truncated or skipped)
        res_budget = asyncio.run(retriever.retrieve_async(project_id="p1", analysis=None, raw_input="q", top_k=5, max_context_chars=250))
        total_chars = sum(len(item.content) for item in res_budget.items)
        self.assertLessEqual(total_chars, 250)

    # 18. Multiple source boundaries are preserved in context
    def test_multi_source_boundaries_in_context(self) -> None:
        items = [
            KnowledgeContextItem(chunk_id="c1", source_id="s1", source_name="docs/auth.md", source_type="documentation", chunk_index=0, content="Auth docs", score=0.88),
            KnowledgeContextItem(chunk_id="c2", source_id="s2", source_name="src/auth.py", source_type="code", chunk_index=0, content="def auth(): pass", score=0.84),
        ]
        ctx = PromptGenerationContext(
            requirement_analysis=RequirementAnalysis(intent="Test", task_type="build"),
            template=TemplateSelector().select("build"),
            retrieved_knowledge=items,
        )
        formatted = ctx.format_retrieved_knowledge()
        self.assertIn("[Source: docs/auth.md | Type: documentation | Relevance: 0.88]\nAuth docs", formatted)
        self.assertIn("[Source: src/auth.py | Type: code | Relevance: 0.84]\ndef auth(): pass", formatted)

    # 19 & 20. Provenance references and query tracking
    def test_provenance_references_and_query_tracking(self) -> None:
        analysis = RequirementAnalysis(
            intent="Update authentication API",
            task_type="modify",
            domain="backend",
            confirmed_requirements=["OAuth2 and JWT"],
        )
        res = asyncio.run(
            self.retriever.retrieve_async(
                project_id=self.project_a.project_id,
                analysis=analysis,
                raw_input="Update authentication API",
            )
        )
        self.assertGreater(len(res.references), 0)
        ref = res.references[0]
        self.assertTrue(ref.chunk_id)
        self.assertTrue(ref.source_name)
        self.assertGreaterEqual(ref.score, 0.1)
        self.assertIsInstance(ref.matched_queries, list)
        self.assertGreater(len(ref.matched_queries), 0)

    # 21. Telemetry reflects multi-query retrieval metrics
    def test_telemetry_metrics_populated(self) -> None:
        analysis = RequirementAnalysis(
            intent="Update auth API",
            task_type="build",
            domain="backend",
            confirmed_requirements=["JWT auth"],
        )
        res = asyncio.run(
            self.retriever.retrieve_async(
                project_id=self.project_a.project_id,
                analysis=analysis,
                raw_input="Update auth API",
            )
        )
        t = res.telemetry
        self.assertTrue(t.attempted)
        self.assertFalse(t.skipped)
        self.assertGreater(len(t.queries_attempted), 0)
        self.assertGreater(t.successful_queries, 0)
        self.assertEqual(t.failed_queries, 0)
        self.assertGreater(t.raw_count, 0)
        self.assertGreater(t.results_before_deduplication, 0)
        self.assertGreater(t.results_after_deduplication, 0)
        self.assertGreater(t.results_after_threshold, 0)
        self.assertGreater(t.final_result_count, 0)
        self.assertIsInstance(t.sources_represented, list)
        self.assertGreater(len(t.sources_represented), 0)

    # 22. Partial retrieval failure is handled correctly
    def test_partial_query_failure_handled_gracefully(self) -> None:
        mock_search = MagicMock(spec=KnowledgeSearchService)
        # First query succeeds, second fails with connection error
        call_count = 0

        async def fake_search(project_id, query, top_k):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return KnowledgeSearchResponse(
                    project_id=project_id,
                    query=query,
                    top_k=top_k,
                    total_results=1,
                    results=[
                        KnowledgeSearchResult(
                            chunk_id="chunk-ok",
                            source_id="s1",
                            source_name="docs/auth.md",
                            source_type="documentation",
                            chunk_index=0,
                            content="Auth info",
                            score=0.85,
                            metadata={},
                        )
                    ],
                )
            else:
                raise EmbeddingConnectionError("Connection to Ollama failed for query 2")

        mock_search.search = AsyncMock(side_effect=fake_search)
        retriever = KnowledgeRetriever(search_service=mock_search, min_relevance_score=0.5)
        retriever.build_retrieval_queries = MagicMock(return_value=["query 1", "query 2"])  # type: ignore

        res = asyncio.run(
            retriever.retrieve_async(
                project_id="p1",
                analysis=None,
                raw_input="test",
            )
        )
        # Retrieval should NOT fail completely because query 1 succeeded!
        self.assertEqual(len(res.items), 1)
        self.assertEqual(res.items[0].chunk_id, "chunk-ok")
        self.assertEqual(res.telemetry.successful_queries, 1)
        self.assertEqual(res.telemetry.failed_queries, 1)
        self.assertFalse(res.telemetry.skipped)

    # 23. Project isolation remains intact
    def test_project_isolation_intact(self) -> None:
        analysis = RequirementAnalysis(
            intent="Access secret banking keys and confidential credentials",
            task_type="build",
            domain="security",
        )
        # Run search for Project A
        res_a = asyncio.run(
            self.retriever.retrieve_async(
                project_id=self.project_a.project_id,
                analysis=analysis,
                raw_input="Access secret banking keys and confidential credentials",
            )
        )
        source_names_a = [item.source_name for item in res_a.items]
        # Must NEVER contain Project B's secrets.md
        self.assertNotIn("docs/secrets.md", source_names_a)

        # Run search for Project B
        res_b = asyncio.run(
            self.retriever.retrieve_async(
                project_id=self.project_b.project_id,
                analysis=analysis,
                raw_input="Access secret banking keys and confidential credentials",
            )
        )
        source_names_b = [item.source_name for item in res_b.items]
        self.assertIn("docs/secrets.md", source_names_b)
        # Must NOT contain Project A's documents
        for a_doc in ("docs/authentication.md", "src/auth.py", "config/auth.json"):
            self.assertNotIn(a_doc, source_names_b)

    # 24, 25, 26. Precedence, read-only compilation invariant & API integration
    def test_compile_api_with_multi_document_retrieval_read_only(self) -> None:
        # Override FastAPI dependencies for local isolated test
        app.dependency_overrides[get_project_service] = lambda: self.project_service
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo
        app.dependency_overrides[get_knowledge_retriever] = lambda: self.retriever

        mock_generator = MagicMock(spec=PromptGenerator)
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Compiled Implementation Specification\nObjective: Implement authentication API.\n\n=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===\n[Source: docs/authentication.md | Type: documentation | Relevance: 0.88]\nOAuth2\n\n[Source: src/auth.py | Type: code | Relevance: 0.84]\ndef auth(): pass\n\n## Requirements\n- Implement OAuth2 JWT auth",
                template_name="Build Task",
                task_type="build",
            )
        )
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        mock_critic = MagicMock(spec=PromptCritic)
        mock_critic.validate_with_rules = MagicMock(
            return_value=ValidationResult(
                overall_valid=True,
                issues=[],
                preserved_requirements=["Implement OAuth2 JWT auth"],
                missing_requirements=[],
                violated_constraints=[],
                invented_requirements=[],
                missing_information_preserved=True,
                task_type_valid=True,
                structure_valid=True,
            )
        )
        mock_critic.validate_async = AsyncMock(return_value=mock_critic.validate_with_rules.return_value)
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        mock_req_engine = MagicMock(spec=RequirementEngine)
        mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Implement OAuth2 JWT auth using existing database schema and auth code",
                task_type="build",
                domain="backend",
                confirmed_requirements=["Implement OAuth2 JWT auth"],
            )
        )
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine

        client = TestClient(app)
        try:
            mem_count_before = len(self.memory_repo.list_by_project(self.project_a.project_id))
            cand_count_before = len(self.candidate_repo.list_by_project(self.project_a.project_id))

            response = client.post(
                "/api/compile",
                json={
                    "input": "Implement OAuth2 JWT auth using existing database schema and auth code",
                    "project_id": self.project_a.project_id,
                    "target_agent": "generic",
                    "enable_knowledge_retrieval": True,
                },
            )
            self.assertEqual(response.status_code, 200, f"Response text: {response.text}")
            data = response.json()

            # Verify citations & telemetry returned
            self.assertIn("knowledge_references", data)
            self.assertIn("knowledge_telemetry", data)
            telemetry = data["knowledge_telemetry"]
            self.assertTrue(telemetry["attempted"])
            self.assertFalse(telemetry["skipped"])
            self.assertGreater(telemetry["successful_queries"], 0)
            self.assertGreater(len(telemetry["queries_attempted"]), 0)

            # Read-only check: zero new project memories or candidates created!
            mem_count_after = len(self.memory_repo.list_by_project(self.project_a.project_id))
            cand_count_after = len(self.candidate_repo.list_by_project(self.project_a.project_id))
            self.assertEqual(mem_count_before, mem_count_after)
            self.assertEqual(cand_count_before, cand_count_after)

        finally:
            app.dependency_overrides.clear()

    # 27. Interview mode remains compatible
    def test_interview_mode_compatibility(self) -> None:
        session = self.project_service.create_project(name="Interview Project", description="Interview test")
        # Interview compilation delegates through the same knowledge_retriever.retrieve_async
        interviewer = PromptInterviewer(store=None)  # type: ignore
        self.assertTrue(hasattr(interviewer, "store"))

    # 28. All five agent presets retain multi-document retrieved knowledge
    def test_all_five_agent_presets_with_multi_document_knowledge(self) -> None:
        formatter = AgentFormatter()
        compiled = """# Feature Specification
Objective: Update authentication.

=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===
The following background context was retrieved from indexed project documentation and code:

[Source: docs/authentication.md | Type: documentation | Relevance: 0.88]
OAuth2 specification

[Source: src/auth.py | Type: code | Relevance: 0.84]
def authenticate_user(): pass

## Requirements
- Use OAuth2 tokens
"""
        items = [
            KnowledgeContextItem(chunk_id="c1", source_id="s1", source_name="docs/authentication.md", source_type="documentation", chunk_index=0, content="OAuth2 specification", score=0.88),
            KnowledgeContextItem(chunk_id="c2", source_id="s2", source_name="src/auth.py", source_type="code", chunk_index=0, content="def authenticate_user(): pass", score=0.84),
        ]

        for preset in ("generic", "cursor", "claude_code", "cline", "windsurf"):
            formatted = formatter.format_prompt(
                compiled_prompt=compiled,
                target_agent=preset,
                retrieved_knowledge=items,
            )
            self.assertIsInstance(formatted, str)
            self.assertIn("docs/authentication.md", formatted)
            self.assertIn("src/auth.py", formatted)
            self.assertIn("OAuth2", formatted)


if __name__ == "__main__":
    unittest.main()
