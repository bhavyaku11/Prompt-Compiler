"""Comprehensive unit and API integration tests for vector knowledge base and semantic retrieval (Task 20)."""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.ai.embeddings import (
    EmbeddingConnectionError,
    EmbeddingDimensionMismatchError,
    EmbeddingError,
    EmbeddingModelUnavailableError,
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
    get_embedding_provider,
)
from app.api.knowledge import (
    get_embedding_provider as get_api_embedding_provider,
    get_knowledge_repository,
    get_project_repository,
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
from app.engine.chunker import (
    ChunkItem,
    TextChunker,
    compute_content_hash,
    normalize_text,
)
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectNotFoundError
from app.main import app
from app.schemas.project import ProjectCreate


class TestChunkerAndHashing(unittest.TestCase):
    """Unit tests for text normalization, deterministic hashing, and chunking."""

    def test_normalize_text(self):
        raw = "  Line 1   \r\nLine 2\r\n\r\nLine 3 \x00  "
        normalized = normalize_text(raw)
        self.assertEqual(normalized, "Line 1\nLine 2\n\nLine 3")

    def test_compute_content_hash_deterministic(self):
        t1 = "Hello world\nThis is a test."
        t2 = "Hello world\r\nThis is a test.  "
        # Since normalize_text removes trailing whitespace and CRLF, both produce identical hash
        self.assertEqual(compute_content_hash(t1), compute_content_hash(t2))
        self.assertEqual(len(compute_content_hash(t1)), 64)

    def test_chunk_small_text_produces_single_chunk(self):
        chunker = TextChunker(chunk_size=500, chunk_overlap=100)
        chunks = chunker.chunk_text(
            text="Short documentation snippet",
            source_name="guide.md",
            source_type="documentation",
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_index, 0)
        self.assertEqual(chunks[0].content, "Short documentation snippet")
        self.assertEqual(chunks[0].metadata["source_name"], "guide.md")
        self.assertEqual(chunks[0].metadata["source_type"], "documentation")

    def test_chunk_large_text_with_overlap(self):
        chunker = TextChunker(chunk_size=100, chunk_overlap=30)
        # Create paragraphs
        paragraphs = [f"Paragraph {i}: " + ("word " * 15) for i in range(5)]
        full_text = "\n\n".join(paragraphs)

        chunks = chunker.chunk_text(full_text, source_name="doc.txt")
        self.assertGreater(len(chunks), 1)
        # Ordering must be strictly sequential
        for idx, c in enumerate(chunks):
            self.assertEqual(c.chunk_index, idx)
            self.assertLessEqual(len(c.content), 120)  # bounded by chunk size

    def test_chunk_ordering_is_deterministic(self):
        chunker = TextChunker(chunk_size=80, chunk_overlap=20)
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."
        chunks1 = chunker.chunk_text(text)
        chunks2 = chunker.chunk_text(text)
        self.assertEqual(len(chunks1), len(chunks2))
        for c1, c2 in zip(chunks1, chunks2, strict=True):
            self.assertEqual(c1.chunk_index, c2.chunk_index)
            self.assertEqual(c1.content, c2.content)
            self.assertEqual(c1.content_hash, c2.content_hash)


class TestEmbeddingProvider(unittest.IsolatedAsyncioTestCase):
    """Unit tests for embedding provider abstraction and mock implementation."""

    async def test_mock_embedding_provider_deterministic_unit_vectors(self):
        provider = MockEmbeddingProvider(dimension=768)
        v1 = await provider.embed_text("FastAPI payment gateway")
        v2 = await provider.embed_text("FastAPI payment gateway")
        v3 = await provider.embed_text("Completely unrelated text")

        self.assertEqual(len(v1), 768)
        self.assertEqual(v1, v2)  # Deterministic!
        self.assertNotEqual(v1, v3)  # Different text yields different vector

    async def test_mock_embedding_batch(self):
        provider = MockEmbeddingProvider(dimension=768)
        texts = ["text A", "text B", "text C"]
        embs = await provider.embed_batch(texts)
        self.assertEqual(len(embs), 3)
        self.assertEqual(len(embs[0]), 768)

    async def test_ollama_embedding_provider_error_handling(self):
        mock_client = AsyncMock()
        mock_client.is_closed = False
        # Mock 503 from Ollama
        mock_response = AsyncMock()
        mock_response.status_code = 503
        mock_response.text = '{"error":"This server does not support embeddings"}'
        mock_client.post.return_value = mock_response

        provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
            dimension=768,
            client=mock_client,
        )

        with self.assertRaises(EmbeddingModelUnavailableError):
            await provider.embed_text("test")


class TestKnowledgeRepositoryAndServices(unittest.IsolatedAsyncioTestCase):
    """Integration tests for KnowledgeRepository, IndexerService, and SearchService."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_knowledge.db")
        self.db_url = f"sqlite:///{self.db_path}"

        reset_db_engine()
        init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.knowledge_repo = KnowledgeRepository(database_url=self.db_url)
        self.embedding_provider = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

        self.indexer = KnowledgeIndexerService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.embedding_provider,
        )
        self.searcher = KnowledgeSearchService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.embedding_provider,
        )

        self.proj_a = self.project_repo.create(
            ProjectCreate(name="Payment Microservice", description="Stripe processing")
        )
        self.proj_b = self.project_repo.create(
            ProjectCreate(name="Inventory App", description="Warehouse inventory")
        )

    def tearDown(self):
        reset_db_engine()
        self.temp_dir.cleanup()

    async def test_index_content_creates_source_and_chunks(self):
        content = "# Architecture\nThe backend uses FastAPI with PostgreSQL on Railway."
        res = await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="architecture.md",
            content=content,
        )
        self.assertFalse(res.is_duplicate)
        self.assertGreaterEqual(res.chunk_count, 1)

        sources = self.knowledge_repo.list_sources(self.proj_a.project_id)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_name, "architecture.md")

        chunks = self.knowledge_repo.get_chunks_by_source(sources[0].source_id)
        self.assertEqual(len(chunks), res.chunk_count)
        self.assertIn("FastAPI", chunks[0].content)

    async def test_index_duplicate_content_skips_reembedding(self):
        content = "Identical content repeated twice."
        res1 = await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="text",
            source_name="notes.txt",
            content=content,
        )
        self.assertFalse(res1.is_duplicate)

        # Re-index same content
        res2 = await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="text",
            source_name="notes_copy.txt",
            content=content,
        )
        self.assertTrue(res2.is_duplicate)
        self.assertEqual(res2.source_id, res1.source_id)
        # Total sources in DB should still be 1
        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 1)

    async def test_index_content_updates_existing_source_name(self):
        await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="readme.md",
            content="Version 1",
        )
        res2 = await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="readme.md",
            content="Version 2 updated content",
        )
        self.assertFalse(res2.is_duplicate)
        sources = self.knowledge_repo.list_sources(self.proj_a.project_id)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_id, res2.source_id)

    async def test_search_similar_chunks_returns_ranked_results(self):
        await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="auth.md",
            content="Authentication is implemented using JWT tokens and bcrypt password hashing.",
        )
        await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="db.md",
            content="PostgreSQL database connects via SQLAlchemy connection pooling.",
        )

        # Search for exact query matching auth
        res = await self.searcher.search(
            project_id=self.proj_a.project_id,
            query="Authentication is implemented using JWT tokens and bcrypt password hashing.",
            top_k=2,
        )
        self.assertEqual(len(res.results), 2)
        # First result should have high similarity score
        self.assertGreaterEqual(res.results[0].score, 0.99)
        self.assertEqual(res.results[0].source_name, "auth.md")

    async def test_project_isolation(self):
        # Index document into Project A
        await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="documentation",
            source_name="secret_a.md",
            content="Secret payment API keys and banking secrets.",
        )
        # Index document into Project B
        await self.indexer.index_content(
            project_id=self.proj_b.project_id,
            source_type="documentation",
            source_name="warehouse_b.md",
            content="Forklift inventory locations and warehouse aisles.",
        )

        # Query Project A: should NEVER return Project B
        search_a = await self.searcher.search(
            project_id=self.proj_a.project_id,
            query="Forklift warehouse aisles",
            top_k=10,
        )
        for r in search_a.results:
            self.assertNotEqual(r.source_name, "warehouse_b.md")
            self.assertNotIn("warehouse", r.content.lower())

        # Query Project B: should NEVER return Project A
        search_b = await self.searcher.search(
            project_id=self.proj_b.project_id,
            query="Secret payment API keys",
            top_k=10,
        )
        for r in search_b.results:
            self.assertNotEqual(r.source_name, "secret_a.md")
            self.assertNotIn("banking secrets", r.content.lower())

    async def test_delete_source_removes_chunks_and_vectors(self):
        res = await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="code",
            source_name="router.py",
            content="@router.get('/health')\ndef health(): return {'status': 'ok'}",
        )
        self.assertEqual(self.knowledge_repo.count_chunks(self.proj_a.project_id), 1)

        deleted = self.knowledge_repo.delete_source(res.source_id)
        self.assertTrue(deleted)
        self.assertEqual(self.knowledge_repo.count_chunks(self.proj_a.project_id), 0)
        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 0)

        # Searching should now return 0 results
        search_res = await self.searcher.search(
            project_id=self.proj_a.project_id,
            query="health router",
        )
        self.assertEqual(len(search_res.results), 0)

    async def test_delete_project_cascades_knowledge_base(self):
        await self.indexer.index_content(
            project_id=self.proj_a.project_id,
            source_type="code",
            source_name="app.py",
            content="main entry point",
        )
        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 1)

        # Delete project
        self.project_repo.delete(self.proj_a.project_id)
        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 0)
        self.assertEqual(self.knowledge_repo.count_chunks(self.proj_a.project_id), 0)


class TestKnowledgeAPI(unittest.TestCase):
    """REST API integration tests for /api/projects/{project_id}/knowledge endpoints."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_api_knowledge.db")
        self.db_url = f"sqlite:///{self.db_path}"

        reset_db_engine()
        init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.knowledge_repo = KnowledgeRepository(database_url=self.db_url)
        self.mock_provider = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_knowledge")

        self.project = self.project_repo.create(
            ProjectCreate(name="API Test Project", description="Testing knowledge routes"),
            user_id=self.test_user.id,
        )

        from app.api.compile import get_project_service as get_compile_project_service
        from app.engine.project_memory import ProjectMemoryService
        from app.database.repositories import ProjectMemoryRepository, CandidateMemoryRepository

        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.candidate_repo = CandidateMemoryRepository(database_url=self.db_url)
        self.project_service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
            candidate_repository=self.candidate_repo,
            database_url=self.db_url,
        )

        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_project_repository] = lambda: self.project_repo
        app.dependency_overrides[get_knowledge_repository] = lambda: self.knowledge_repo
        app.dependency_overrides[get_api_embedding_provider] = lambda: self.mock_provider
        app.dependency_overrides[get_compile_project_service] = lambda: self.project_service

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_api_index_and_search_flow(self):
        # 1. Index document
        index_res = self.client.post(
            f"/api/projects/{self.project.project_id}/knowledge/index",
            json={
                "source_type": "documentation",
                "source_name": "deployment.md",
                "content": "Deployments run via Docker Compose on AWS ECS Fargate.",
                "metadata": {"author": "DevOps Team"},
            },
        )
        self.assertEqual(index_res.status_code, 201)
        data = index_res.json()
        self.assertEqual(data["source_name"], "deployment.md")
        self.assertEqual(data["is_duplicate"], False)
        self.assertGreaterEqual(data["chunk_count"], 1)

        # 2. List sources
        sources_res = self.client.get(f"/api/projects/{self.project.project_id}/knowledge/sources")
        self.assertEqual(sources_res.status_code, 200)
        sources = sources_res.json()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["source_name"], "deployment.md")

        # 3. Search knowledge
        search_res = self.client.post(
            f"/api/projects/{self.project.project_id}/knowledge/search",
            json={
                "query": "Docker Compose AWS ECS",
                "top_k": 3,
            },
        )
        self.assertEqual(search_res.status_code, 200)
        search_data = search_res.json()
        self.assertEqual(search_data["project_id"], self.project.project_id)
        self.assertGreaterEqual(len(search_data["results"]), 1)
        self.assertIn("Docker Compose", search_data["results"][0]["content"])

        # 4. Delete source
        del_res = self.client.delete(
            f"/api/projects/{self.project.project_id}/knowledge/sources/{data['source_id']}"
        )
        self.assertEqual(del_res.status_code, 200)
        self.assertTrue(del_res.json()["deleted"])

        # Verify sources list is now empty
        empty_res = self.client.get(f"/api/projects/{self.project.project_id}/knowledge/sources")
        self.assertEqual(len(empty_res.json()), 0)

    def test_api_unknown_project_returns_404(self):
        res = self.client.post(
            "/api/projects/unknown-proj-id/knowledge/index",
            json={
                "source_type": "text",
                "source_name": "test.txt",
                "content": "some text",
            },
        )
        self.assertEqual(res.status_code, 404)

    def test_api_empty_query_rejected_with_422(self):
        res = self.client.post(
            f"/api/projects/{self.project.project_id}/knowledge/search",
            json={"query": "   "},
        )
        self.assertEqual(res.status_code, 422)

    def test_api_invalid_top_k_rejected_with_422(self):
        res = self.client.post(
            f"/api/projects/{self.project.project_id}/knowledge/search",
            json={"query": "test query", "top_k": 999},
        )
        self.assertEqual(res.status_code, 422)

    def test_compilation_pipeline_remains_independent_of_knowledge_base(self):
        """Strict scope boundary test: POST /api/compile must NOT perform automatic RAG."""
        # Index content into the project knowledge base
        self.client.post(
            f"/api/projects/{self.project.project_id}/knowledge/index",
            json={
                "source_type": "documentation",
                "source_name": "internal_guide.md",
                "content": "Secret knowledge snippet that should not leak into basic compilation.",
            },
        )

        # Mock compiler dependencies to assert context without invoking Ollama
        from app.api.compile import get_prompt_critic, get_prompt_generator, get_requirement_engine
        from app.engine.critic import ValidationResult
        from app.engine.generator import PromptGenerationResult
        from app.engine.requirements import RequirementAnalysis

        mock_req = unittest.mock.MagicMock()
        mock_req.analyze_async = AsyncMock(
            return_value=RequirementAnalysis(
                intent="Build ping",
                task_type="build",
                domain="backend",
                confirmed_requirements=["Ping endpoint"],
            )
        )
        app.dependency_overrides[get_requirement_engine] = lambda: mock_req

        mock_generator = unittest.mock.MagicMock()
        mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="# Objective\nCompiled ping output\n",
                template_name="Build Template",
                task_type="build",
            )
        )
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator

        mock_critic = unittest.mock.MagicMock()
        mock_critic.validate_async = AsyncMock(return_value=ValidationResult(overall_valid=True))
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic

        # Call POST /api/compile
        compile_res = self.client.post(
            "/api/compile",
            json={
                "input": "Build a simple ping endpoint",
                "project_id": self.project.project_id,
            },
        )
        self.assertEqual(compile_res.status_code, 200)

        # Verify that prompt generation context does NOT contain knowledge base chunks
        gen_ctx = mock_generator.generate_async.call_args[0][0]
        # Must not contain the indexed internal_guide text
        self.assertNotIn("Secret knowledge snippet", str(gen_ctx.__dict__))
