"""Tests for Task 21: Integrating Semantic Retrieval into the Prompt Compiler Pipeline.

Verifies:
1. Compilation without project_id does not retrieve knowledge.
2. Compilation with project_id retrieves relevant knowledge chunks.
3. Empty knowledge base does not break compilation.
4. Retrieved knowledge appears in PromptGenerationContext and banner.
5. Retrieved knowledge is clearly separated from explicit requirements.
6. Explicit user requirements remain higher priority than retrieved knowledge.
7. Confirmed project memory remains higher priority than retrieved knowledge.
8. Relevance threshold removes low-score results.
9. Top-k and character context budget are respected.
10. Retrieval references are returned correctly in CompileResponse.
11. No knowledge references are returned when retrieval is skipped or disabled.
12. Retrieval failure (embedding error) follows defined graceful error handling.
13. Existing compile API behavior remains compatible.
14. Interview compilation incorporates project knowledge.
15. Downstream agent-specific formatting presets retain retrieved knowledge.
16. Compilation is read-only (zero writes to project memories or candidate memories).
17. Strict project isolation is maintained (Project A never retrieves Project B knowledge).
18. Retrieval query builder creates compact deterministic queries.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from app.ai.embeddings import (
    EmbeddingConnectionError,
    EmbeddingProvider,
    MockEmbeddingProvider,
    get_embedding_provider,
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
from app.engine.chunker import TextChunker
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import (
    PromptGenerationResult,
    PromptGenerator,
)
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_retrieval import KnowledgeRetriever, RetrievalExecutionResult
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectMemoryService
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.knowledge import KnowledgeSearchResult, KnowledgeSearchResponse


class TestCompileWithKnowledge(unittest.TestCase):
    """Integration and unit tests for semantic retrieval in the compilation pipeline."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_compile_knowledge.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)

        # Repositories bound to test database
        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.candidate_repo = CandidateMemoryRepository(database_url=self.db_url)
        self.knowledge_repo = KnowledgeRepository(database_url=self.db_url)
        self.compilation_repo = CompilationRepository(database_url=self.db_url)

        # Services
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
        # In test mode with MockEmbeddingProvider, threshold 0.1 allows token-matched mock embeddings to pass
        self.knowledge_retriever = KnowledgeRetriever(
            search_service=self.search_service,
            min_relevance_score=0.1,
        )

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_compile_knowledge")

        # Create Primary Test Project A
        self.project_a = self.project_service.create_project(
            name="E-Commerce Backend",
            description="Online store API",
            user_id=self.test_user.id,
        )
        self.project_a_id = self.project_a.project_id

        # Add explicit confirmed project memory to Project A
        self.project_service.add_memory(
            project_id=self.project_a_id,
            category="technology",
            content="FastAPI with PostgreSQL and SQLAlchemy",
            confidence=1.0,
            user_id=self.test_user.id,
        )
        self.project_service.add_memory(
            project_id=self.project_a_id,
            category="constraint",
            content="All API endpoints must require OAuth2 bearer token authentication",
            confidence=1.0,
            user_id=self.test_user.id,
        )

        # Create Secondary Test Project B for isolation testing
        self.project_b = self.project_service.create_project(
            name="Analytics Platform",
            description="Internal metric pipeline",
            user_id=self.test_user.id,
        )
        self.project_b_id = self.project_b.project_id

        # Setup TestClient with FastAPI dependency overrides
        self.client = TestClient(app)
        app.dependency_overrides.clear()
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_project_service] = lambda: self.project_service
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo
        app.dependency_overrides[get_embedding_provider] = lambda: self.mock_embedding_provider
        app.dependency_overrides[get_knowledge_retriever] = lambda: self.knowledge_retriever

        # Setup fast, deterministic mock generator, critic, and req engine by default
        self.mock_critic = MagicMock(spec=PromptCritic)
        self.mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True, issues=[])
        )
        self.mock_generator = MagicMock(spec=PromptGenerator)

        async def _default_fake_generate(analysis, project_context=None, retrieved_knowledge=None, **kwargs):
            parts = [f"# Objective\n{analysis.intent}\n"]
            if project_context:
                parts.insert(0, f"=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===\n{project_context.to_context_string()}\n\n")
            if retrieved_knowledge:
                lines = []
                for item in retrieved_knowledge:
                    lines.append(f"[Source: {item.source_name} | Score: {item.score}]\n{item.content}")
                parts.insert(1, f"=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===\n" + "\n\n".join(lines) + "\n\n")
            return PromptGenerationResult(
                final_prompt="".join(parts),
                template_name="Build Template",
                task_type=analysis.task_type,
            )

        self.mock_generator.generate_async = AsyncMock(side_effect=_default_fake_generate)

        self.mock_req_engine = MagicMock(spec=RequirementEngine)

        async def _default_fake_analyze(user_input, project_context=None):
            return RequirementAnalysis(
                intent=user_input,
                task_type="build",
                domain="software",
                confirmed_requirements=[user_input],
                project_context_summary=project_context.to_context_string() if project_context else None,
            )

        self.mock_req_engine.analyze_async = AsyncMock(side_effect=_default_fake_analyze)

        app.dependency_overrides[get_prompt_generator] = lambda: self.mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: self.mock_critic
        app.dependency_overrides[get_requirement_engine] = lambda: self.mock_req_engine

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _index_doc(self, project_id: str, title: str, content: str) -> None:
        """Synchronously index a knowledge source for testing."""
        asyncio.run(
            self.indexer.index_content(
                project_id=project_id,
                source_type="documentation",
                source_name=title,
                content=content,
            )
        )

    # -------------------------------------------------------------------------
    # Tests
    # -------------------------------------------------------------------------

    def test_01_compilation_without_project_id_skips_retrieval(self) -> None:
        """1. Compilation without project_id does not retrieve knowledge."""
        resp = self.client.post("/api/compile", json={"input": "Build a markdown parser"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data["project_id"])
        self.assertEqual(data["knowledge_references"], [])
        self.assertIsNotNone(data["knowledge_telemetry"])
        self.assertTrue(data["knowledge_telemetry"]["skipped"])
        self.assertEqual(data["knowledge_telemetry"]["skip_reason"], "no_project_id")

    def test_02_compilation_with_project_id_retrieves_knowledge(self) -> None:
        """2. Compilation with project_id retrieves relevant knowledge chunks."""
        self._index_doc(
            project_id=self.project_a_id,
            title="payment_architecture.md",
            content="The payment service integrates with Stripe via webhooks using idempotent event processing.",
        )

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "The payment service integrates with Stripe via webhooks using idempotent event processing.",
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_id"], self.project_a_id)
        self.assertGreater(len(data["knowledge_references"]), 0)
        first_ref = data["knowledge_references"][0]
        self.assertEqual(first_ref["source_name"], "payment_architecture.md")
        self.assertGreaterEqual(first_ref["score"], 0.0)

        # Verify telemetry
        telem = data["knowledge_telemetry"]
        self.assertIsNotNone(telem)
        self.assertTrue(telem["attempted"])
        self.assertFalse(telem["skipped"])
        self.assertGreater(telem["raw_count"], 0)

    def test_03_empty_knowledge_base_does_not_break_compilation(self) -> None:
        """3. Empty knowledge base does not break compilation."""
        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Build user profile page",
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["project_id"], self.project_a_id)
        self.assertEqual(data["knowledge_references"], [])
        self.assertEqual(data["knowledge_telemetry"]["raw_count"], 0)
        self.assertEqual(data["knowledge_telemetry"]["filtered_count"], 0)

    def test_04_retrieved_knowledge_appears_in_prompt_context(self) -> None:
        """4. Retrieved knowledge appears in PromptGenerationContext and banner."""
        content = "Redis is used for caching session tokens with a 15-minute TTL."
        self._index_doc(
            project_id=self.project_a_id,
            title="cache_policy.md",
            content=content,
        )

        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        result_prompt = resp.json()["result"]
        # Canonical banner must appear
        self.assertIn("RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE)", result_prompt)
        self.assertIn("cache_policy.md", result_prompt)
        self.assertIn("Redis is used for caching session tokens", result_prompt)

    def test_05_retrieved_knowledge_is_separated_from_explicit_requirements(self) -> None:
        """5. Retrieved knowledge is clearly separated from explicit requirements."""
        content = "Legacy database migration notes: MySQL 5.7 schema was used for order migration before PostgreSQL."
        self._index_doc(
            project_id=self.project_a_id,
            title="legacy_database.md",
            content=content,
        )

        self.mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Migrate order checkout to PostgreSQL",
                task_type="build",
                domain="database",
                confirmed_requirements=["PostgreSQL order migration"],
            )
        )

        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        requirements = data["requirements"]["confirmed_requirements"]
        # MySQL must NOT have leaked into confirmed user requirements
        self.assertNotIn("MySQL", " ".join(requirements))
        self.assertIn("PostgreSQL order migration", requirements)
        # But MySQL should be in retrieved knowledge evidence
        self.assertIn("legacy_database.md", data["result"])

    def test_06_explicit_user_requirements_remain_higher_priority(self) -> None:
        """6. Explicit user requirements remain higher priority than retrieved knowledge."""
        self._index_doc(
            project_id=self.project_a_id,
            title="existing_auth.md",
            content="Our authentication system is currently backed by Supabase Auth.",
        )

        analysis = RequirementAnalysis(
            intent="Build auth using Auth0",
            task_type="build",
            domain="security",
            confirmed_requirements=["Integrate Auth0 authentication"],
            constraints=["Do NOT use Supabase Auth"],
        )
        self.mock_req_engine.analyze_async = AsyncMock(return_value=analysis)

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Build auth using Auth0. Do NOT use Supabase Auth.",
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("Integrate Auth0 authentication", data["requirements"]["confirmed_requirements"])
        self.assertIn("Do NOT use Supabase Auth", data["requirements"]["constraints"])

    def test_07_confirmed_project_memory_takes_precedence_over_retrieved_knowledge(self) -> None:
        """7. Confirmed project memory remains higher priority than retrieved knowledge."""
        self._index_doc(
            project_id=self.project_a_id,
            title="archived_prototype.md",
            content="Initial prototype explored Flask with MongoDB.",
        )

        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Initial prototype explored Flask with MongoDB.",
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        result = resp.json()["result"]
        # Project baseline must show confirmed memory
        self.assertIn("FastAPI with PostgreSQL", result)
        # Prototype info appears only under retrieved evidence
        self.assertIn("archived_prototype.md", result)

    def test_08_relevance_threshold_removes_low_score_results(self) -> None:
        """8. Relevance threshold removes low-score results."""
        mock_search = MagicMock(spec=KnowledgeSearchService)

        high_res = KnowledgeSearchResult(
            chunk_id="chunk-high",
            source_id="src-1",
            source_name="relevant.md",
            source_type="documentation",
            chunk_index=0,
            content="Highly relevant text matching query",
            score=0.88,
        )
        low_res = KnowledgeSearchResult(
            chunk_id="chunk-low",
            source_id="src-2",
            source_name="irrelevant.md",
            source_type="documentation",
            chunk_index=0,
            content="Completely unrelated content",
            score=0.25,
        )
        mock_search.search = AsyncMock(
            return_value=KnowledgeSearchResponse(
                project_id=self.project_a_id,
                query="relevant query",
                top_k=5,
                total_results=2,
                results=[high_res, low_res],
            )
        )

        retriever = KnowledgeRetriever(search_service=mock_search)
        result: RetrievalExecutionResult = asyncio.run(
            retriever.retrieve_async(
                project_id=self.project_a_id,
                analysis=None,
                raw_input="relevant query",
                min_relevance_score=0.60,
            )
        )

        # Only the high-score item should pass the 0.60 threshold
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].chunk_id, "chunk-high")
        self.assertEqual(len(result.references), 1)
        self.assertEqual(result.references[0].chunk_id, "chunk-high")
        self.assertEqual(result.telemetry.raw_count, 2)
        self.assertEqual(result.telemetry.filtered_count, 1)

    def test_09_top_k_and_context_budget_are_respected(self) -> None:
        """9. Top-k/context budget is respected."""
        mock_search = MagicMock(spec=KnowledgeSearchService)

        chunks = [
            KnowledgeSearchResult(
                chunk_id=f"chunk-{i}",
                source_id="src-bulk",
                source_name="bulk.md",
                source_type="documentation",
                chunk_index=i,
                content=f"Important architecture component number {i} with detailed instructions.",
                score=0.90 - (i * 0.05),
            )
            for i in range(5)
        ]
        mock_search.search = AsyncMock(
            return_value=KnowledgeSearchResponse(
                project_id=self.project_a_id,
                query="bulk query",
                top_k=5,
                total_results=5,
                results=chunks,
            )
        )

        retriever = KnowledgeRetriever(search_service=mock_search)

        # Test Top-K constraint = 2
        result_top_k = asyncio.run(
            retriever.retrieve_async(
                project_id=self.project_a_id,
                analysis=None,
                raw_input="bulk query",
                top_k=2,
                min_relevance_score=0.1,
            )
        )
        self.assertEqual(len(result_top_k.items), 2)
        self.assertEqual(len(result_top_k.references), 2)

        # Test Character Budget constraint = 120 chars
        result_budget = asyncio.run(
            retriever.retrieve_async(
                project_id=self.project_a_id,
                analysis=None,
                raw_input="bulk query",
                top_k=5,
                min_relevance_score=0.1,
                max_context_chars=120,
            )
        )
        total_chars = sum(len(item.content) for item in result_budget.items)
        self.assertLessEqual(total_chars, 120)

    def test_10_retrieval_references_are_returned_in_api(self) -> None:
        """10. Retrieval references are returned correctly in CompileResponse."""
        content = "CREATE TABLE inventory (sku VARCHAR(64) PRIMARY KEY, stock INT NOT NULL);"
        self._index_doc(
            project_id=self.project_a_id,
            title="inventory_schema.sql",
            content=content,
        )

        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        refs = resp.json()["knowledge_references"]
        self.assertGreater(len(refs), 0)
        self.assertIn("chunk_id", refs[0])
        self.assertIn("source_id", refs[0])
        self.assertEqual(refs[0]["source_name"], "inventory_schema.sql")
        self.assertEqual(refs[0]["source_type"], "documentation")
        self.assertIsInstance(refs[0]["score"], float)

    def test_11_no_knowledge_references_when_retrieval_disabled(self) -> None:
        """11. No knowledge references are returned when retrieval is disabled."""
        content = "Standard delivery takes 3-5 business days."
        self._index_doc(
            project_id=self.project_a_id,
            title="shipping.md",
            content=content,
        )

        # Explicitly disable retrieval in request
        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
                "enable_knowledge_retrieval": False,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["knowledge_references"], [])
        self.assertTrue(data["knowledge_telemetry"]["skipped"])
        self.assertEqual(data["knowledge_telemetry"]["skip_reason"], "retrieval_disabled")

    def test_12_embedding_failure_follows_graceful_error_handling(self) -> None:
        """12. Retrieval failure follows defined graceful error handling (does not crash compiler)."""
        content = '{"swagger": "2.0"}'
        self._index_doc(
            project_id=self.project_a_id,
            title="api_spec.json",
            content=content,
        )

        failing_provider = MagicMock(spec=EmbeddingProvider)
        failing_provider.embed_text = AsyncMock(
            side_effect=EmbeddingConnectionError("Connection refused to Ollama")
        )
        failing_search = KnowledgeSearchService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=failing_provider,
        )
        app.dependency_overrides[get_knowledge_retriever] = lambda: KnowledgeRetriever(search_service=failing_search)

        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        # Compilation MUST still succeed
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["knowledge_references"], [])
        self.assertTrue(data["knowledge_telemetry"]["skipped"])
        self.assertIn("embedding_unavailable", data["knowledge_telemetry"]["skip_reason"])

    def test_13_existing_compile_api_behavior_remains_compatible(self) -> None:
        """13. Existing compile API behavior remains compatible."""
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build a simple Python CLI application"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("result", data)
        self.assertIn("requirements", data)
        self.assertIn("validation", data)
        self.assertEqual(data["knowledge_references"], [])

    def test_14_interview_compilation_with_knowledge(self) -> None:
        """14. Interview compilation incorporates project knowledge."""
        content = "VAT is calculated dynamically based on the destination country code."
        self._index_doc(
            project_id=self.project_a_id,
            title="tax_rules.md",
            content=content,
        )

        # 1. Start interview with complete info (0 missing info -> ready)
        self.mock_req_engine.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent=content,
                task_type="build",
                domain="finance",
                confirmed_requirements=["VAT calculation"],
                missing_information=[],
            )
        )

        start_resp = self.client.post(
            "/api/interview/start",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(start_resp.status_code, 200)
        session_data = start_resp.json()
        session_id = session_data["session_id"]
        self.assertEqual(session_data["status"], "ready")

        # 2. Compile interview
        compile_resp = self.client.post(f"/api/interview/{session_id}/compile")
        self.assertEqual(compile_resp.status_code, 200)
        data = compile_resp.json()
        self.assertEqual(data["project_id"], self.project_a_id)
        self.assertGreater(len(data["knowledge_references"]), 0)
        self.assertEqual(data["knowledge_references"][0]["source_name"], "tax_rules.md")
        self.assertIn("RETRIEVED PROJECT KNOWLEDGE", data["result"])

    def test_15_agent_specific_formatting_retains_retrieved_knowledge(self) -> None:
        """15. Agent-specific formatting presets retain retrieved knowledge."""
        content = "type Query { getProduct(id: ID!): Product }"
        self._index_doc(
            project_id=self.project_a_id,
            title="graphql_schema.graphql",
            content=content,
        )

        for agent in ("cursor", "claude_code", "cline", "windsurf"):
            resp = self.client.post(
                "/api/compile",
                json={
                    "input": content,
                    "project_id": self.project_a_id,
                    "target_agent": agent,
                },
            )
            self.assertEqual(resp.status_code, 200)
            result = resp.json()["result"]
            # Presets should retain the retrieved evidence in context
            self.assertTrue(
                "graphql_schema.graphql" in result or "getProduct" in result,
                f"Agent {agent} dropped retrieved knowledge content",
            )

    def test_16_compilation_does_not_write_project_memory(self) -> None:
        """16. Compilation is read-only (zero writes to project memories or candidate memories)."""
        content = "Customer accounts can be linked to Stripe customer IDs."
        self._index_doc(
            project_id=self.project_a_id,
            title="notes.txt",
            content=content,
        )

        initial_memories = self.memory_repo.list_by_project(self.project_a_id)
        initial_candidates = self.candidate_repo.list_by_project(self.project_a_id)
        initial_sources = self.knowledge_repo.list_sources(self.project_a_id)

        resp = self.client.post(
            "/api/compile",
            json={
                "input": content,
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)

        # Verify exact counts after compilation
        after_memories = self.memory_repo.list_by_project(self.project_a_id)
        after_candidates = self.candidate_repo.list_by_project(self.project_a_id)
        after_sources = self.knowledge_repo.list_sources(self.project_a_id)

        self.assertEqual(len(initial_memories), len(after_memories))
        self.assertEqual(len(initial_candidates), len(after_candidates))
        self.assertEqual(len(initial_sources), len(after_sources))

    def test_17_project_isolation_remains_intact(self) -> None:
        """17. Project isolation remains intact (Project A never retrieves Project B knowledge)."""
        secret_content = "Project B Secret Internal Metrics Pipeline Token XYZ-99999"
        self._index_doc(
            project_id=self.project_b_id,
            title="project_b_confidential.md",
            content=secret_content,
        )

        # Compile for Project A with a query that could semantically match Project B if unisolated
        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Setup internal metrics pipeline",
                "project_id": self.project_a_id,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Verify Project B knowledge never leaked into Project A's compilation
        self.assertEqual(data["knowledge_references"], [])
        self.assertNotIn("project_b_confidential.md", data["result"])
        self.assertNotIn("XYZ-99999", data["result"])

    def test_18_retrieval_query_builder_determinism(self) -> None:
        """18. KnowledgeRetriever builds compact, deterministic queries."""
        analysis = RequirementAnalysis(
            intent="Build authentication service",
            task_type="build",
            domain="security",
            confirmed_requirements=[
                "Requirement 1: OAuth2",
                "Requirement 2: JWT",
                "Requirement 3: Refresh tokens",
                "Requirement 4: Ignored due to top-3 cap",
            ],
        )
        query = self.knowledge_retriever.build_retrieval_query(analysis, "raw text")
        self.assertIn("Build authentication service", query)
        self.assertIn("Domain: security", query)
        self.assertIn("OAuth2", query)
        self.assertIn("JWT", query)
        self.assertIn("Refresh tokens", query)
        self.assertNotIn("Ignored due to top-3 cap", query)
        self.assertLessEqual(len(query), 500)


if __name__ == "__main__":
    unittest.main()
