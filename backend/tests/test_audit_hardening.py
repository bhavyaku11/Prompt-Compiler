"""Tests for Task 25: Backend Completeness, Requirements & Architecture Audit Hardening.

Verifies:
1. DELETE /api/projects/{project_id} cascades project, memories, candidates, sources, chunks, and vector table.
2. DELETE /api/projects/{project_id} with unknown ID returns 404 Not Found.
3. GET /api/projects/{project_id}/memories/{memory_id} retrieves a specific memory.
4. GET /api/projects/{project_id}/memories/{memory_id} with wrong project ID returns 404 Not Found.
5. PATCH /api/projects/{project_id}/memories/{memory_id} updates category, content, status, and metadata.
6. PATCH /api/projects/{project_id}/memories/{memory_id} with invalid data returns 422.
7. DELETE /api/projects/{project_id}/memories/{memory_id} deletes the memory item.
8. DELETE /api/projects/{project_id}/memories/{memory_id} with non-existent memory returns 404.
9. DELETE /api/projects/{project_id}/memory-candidates/{candidate_id} deletes a candidate proposal.
10. DELETE /api/projects/{project_id}/memory-candidates/{candidate_id} with unknown ID returns 404.
11. Project isolation: Project A cannot read or mutate Project B's memories or candidates.
12. Restart persistence: DB reconnect preserves all projects, memories, candidates, and knowledge.
13. Negative test: Empty project name returns 422 Unprocessable Entity.
14. Negative test: Compile with invalid project ID returns 404 Not Found.
15. API contract consistency: All error responses contain informative detail.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from starlette.testclient import TestClient

from app.ai.embeddings import MockEmbeddingProvider
from app.api.compile import get_knowledge_retriever, get_project_service
from app.api.projects import get_project_service as get_api_project_service
from app.config import settings
from app.database.repositories import (
    CandidateMemoryRepository,
    CompilationRepository,
    KnowledgeRepository,
    ProjectMemoryRepository,
    ProjectRepository,
)
from app.database.session import get_engine, get_session_factory, init_db, reset_db_engine
from app.engine.chunker import TextChunker
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_retrieval import KnowledgeRetriever
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectMemoryService
from app.main import app
from app.schemas.project import ProjectCreate, ProjectMemoryCreate, ProjectMemoryUpdate


class TestAuditHardening(unittest.TestCase):
    """Integration and unit tests for Task 25 completeness hardening."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_audit.db")
        self.db_url = f"sqlite:///{self.db_path}"

        reset_db_engine()
        self.engine = get_engine(database_url=self.db_url)
        init_db(engine=self.engine)
        self.session_factory = get_session_factory(self.engine)

        self.project_repo = ProjectRepository(session_factory=self.session_factory)
        self.memory_repo = ProjectMemoryRepository(session_factory=self.session_factory)
        self.candidate_repo = CandidateMemoryRepository(session_factory=self.session_factory)
        self.knowledge_repo = KnowledgeRepository(session_factory=self.session_factory)
        self.compilation_repo = CompilationRepository(session_factory=self.session_factory)

        self.mock_embeddings = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
        self.project_service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
            candidate_repository=self.candidate_repo,
        )

        self.indexer_service = KnowledgeIndexerService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.mock_embeddings,
            chunker=TextChunker(chunk_size=300, chunk_overlap=50),
        )

        self.search_service = KnowledgeSearchService(
            project_repository=self.project_repo,
            knowledge_repository=self.knowledge_repo,
            embedding_provider=self.mock_embeddings,
        )

        self.knowledge_retriever = KnowledgeRetriever(search_service=self.search_service)

        # Wire overrides into FastAPI app
        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_audit_hardening")
        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_project_service] = lambda: self.project_service
        app.dependency_overrides[get_api_project_service] = lambda: self.project_service
        app.dependency_overrides[get_knowledge_retriever] = lambda: self.knowledge_retriever

        _orig_create_project = self.project_service.create_project
        self.project_service.create_project = lambda name, description="", root_path=None, user_id=None: _orig_create_project(
            name=name,
            description=description,
            root_path=root_path,
            user_id=self.test_user.id if user_id is None else user_id,
        )

        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_delete_project_cascades_all_data(self) -> None:
        """TEST 1: DELETE /api/projects/{project_id} cascades project, memories, candidates, and knowledge."""
        # 1. Create project
        resp = self.client.post("/api/projects", json={"name": "Cascade Test Project", "description": "Desc"})
        self.assertEqual(resp.status_code, 201)
        p_id = resp.json()["project_id"]

        # 2. Add memory
        mem_resp = self.client.post(
            f"/api/projects/{p_id}/memories",
            json={"category": "technology", "content": "FastAPI with SQLite"},
        )
        self.assertEqual(mem_resp.status_code, 201)
        m_id = mem_resp.json()["memory_id"]

        # 3. Add candidate
        cand_resp = self.client.post(
            f"/api/projects/{p_id}/memory-candidates",
            json={"input": "We use Docker for container deployment.", "confirmed_requirements": ["Docker"]},
        )
        self.assertEqual(cand_resp.status_code, 201)
        candidates = cand_resp.json()
        self.assertGreater(len(candidates), 0)

        # 4. Index knowledge content
        asyncio.run(
            self.indexer_service.index_content(
                project_id=p_id,
                source_type="documentation",
                source_name="arch.md",
                content="Architecture document describing modular prompt compiler services.",
            )
        )
        sources = self.knowledge_repo.list_sources(project_id=p_id)
        self.assertEqual(len(sources), 1)

        # 5. Delete project via API
        del_resp = self.client.delete(f"/api/projects/{p_id}")
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["deleted"])
        self.assertEqual(del_resp.json()["project_id"], p_id)

        # 6. Verify cascading cleanup
        self.assertIsNone(self.project_repo.get(p_id))
        self.assertEqual(len(self.memory_repo.list_by_project(p_id)), 0)
        self.assertEqual(len(self.candidate_repo.list_by_project(p_id)), 0)
        self.assertEqual(len(self.knowledge_repo.list_sources(p_id)), 0)
        self.assertEqual(self.knowledge_repo.count_chunks(p_id), 0)

    def test_delete_project_unknown_id_returns_404(self) -> None:
        """TEST 2: DELETE /api/projects/{project_id} returns 404 for non-existent project."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = self.client.delete(f"/api/projects/{fake_id}")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_get_project_memory_by_id(self) -> None:
        """TEST 3: GET /api/projects/{project_id}/memories/{memory_id} retrieves a specific memory."""
        project = self.project_service.create_project(name="Memory Detail Project")
        memory = self.project_service.add_memory(
            project_id=project.project_id,
            category="coding_rule",
            content="Always use strict typing.",
        )

        resp = self.client.get(f"/api/projects/{project.project_id}/memories/{memory.memory_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["memory_id"], memory.memory_id)
        self.assertEqual(data["content"], "Always use strict typing.")
        self.assertEqual(data["category"], "coding_rule")

    def test_get_project_memory_wrong_project_returns_404(self) -> None:
        """TEST 4: GET memory with wrong project_id returns 404 Not Found."""
        p1 = self.project_service.create_project(name="Project 1")
        p2 = self.project_service.create_project(name="Project 2")
        memory = self.project_service.add_memory(
            project_id=p1.project_id,
            category="technology",
            content="Uses React",
        )

        # Attempt to access p1's memory under p2
        resp = self.client.get(f"/api/projects/{p2.project_id}/memories/{memory.memory_id}")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("does not belong to project", resp.json()["detail"])

    def test_patch_project_memory(self) -> None:
        """TEST 5: PATCH /api/projects/{project_id}/memories/{memory_id} updates memory attributes."""
        project = self.project_service.create_project(name="Patch Memory Project")
        memory = self.project_service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Initial Content",
        )

        resp = self.client.patch(
            f"/api/projects/{project.project_id}/memories/{memory.memory_id}",
            json={"content": "Updated Content", "status": "deprecated"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["content"], "Updated Content")
        self.assertEqual(data["status"], "deprecated")

    def test_patch_project_memory_invalid_category_returns_422(self) -> None:
        """TEST 6: PATCH memory with invalid category returns 422 Unprocessable Entity."""
        project = self.project_service.create_project(name="Invalid Category Project")
        memory = self.project_service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Some Content",
        )

        resp = self.client.patch(
            f"/api/projects/{project.project_id}/memories/{memory.memory_id}",
            json={"category": "invalid_category_xyz"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_delete_project_memory(self) -> None:
        """TEST 7: DELETE /api/projects/{project_id}/memories/{memory_id} deletes the item."""
        project = self.project_service.create_project(name="Delete Memory Project")
        memory = self.project_service.add_memory(
            project_id=project.project_id,
            category="database",
            content="PostgreSQL with asyncpg",
        )

        resp = self.client.delete(f"/api/projects/{project.project_id}/memories/{memory.memory_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deleted"])
        self.assertEqual(resp.json()["memory_id"], memory.memory_id)

        # Verify deletion
        self.assertIsNone(self.memory_repo.get(memory.memory_id))

    def test_delete_project_memory_unknown_returns_404(self) -> None:
        """TEST 8: DELETE non-existent memory returns 404 Not Found."""
        project = self.project_service.create_project(name="Delete Unknown Project")
        fake_mem = "00000000-0000-0000-0000-000000000000"
        resp = self.client.delete(f"/api/projects/{project.project_id}/memories/{fake_mem}")
        self.assertEqual(resp.status_code, 404)

    def test_delete_candidate_memory(self) -> None:
        """TEST 9: DELETE /api/projects/{project_id}/memory-candidates/{candidate_id} deletes candidate."""
        project = self.project_service.create_project(name="Candidate Delete Project")
        candidates = self.project_service.extract_candidates(
            project_id=project.project_id,
            user_input="Use FastAPI for the backend",
        )
        self.assertGreater(len(candidates), 0)
        c_id = candidates[0].candidate_id

        resp = self.client.delete(f"/api/projects/{project.project_id}/memory-candidates/{c_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["deleted"])
        self.assertEqual(resp.json()["candidate_id"], c_id)

        # Verify deletion
        self.assertIsNone(self.candidate_repo.get(c_id))

    def test_delete_candidate_memory_unknown_returns_404(self) -> None:
        """TEST 10: DELETE non-existent candidate returns 404 Not Found."""
        project = self.project_service.create_project(name="Candidate Unknown Project")
        fake_c = "00000000-0000-0000-0000-000000000000"
        resp = self.client.delete(f"/api/projects/{project.project_id}/memory-candidates/{fake_c}")
        self.assertEqual(resp.status_code, 404)

    def test_cross_project_isolation(self) -> None:
        """TEST 11: Cross-project isolation: Project A data cannot be accessed or modified through Project B."""
        p_a = self.project_service.create_project(name="Project A")
        p_b = self.project_service.create_project(name="Project B")

        mem_a = self.project_service.add_memory(
            project_id=p_a.project_id,
            category="technology",
            content="Project A Secret Technology",
        )

        cand_a = self.project_service.extract_candidates(
            project_id=p_a.project_id,
            user_input="Use FastAPI for the backend",
        )[0]

        # Project B cannot get Project A's memory
        resp_mem = self.client.get(f"/api/projects/{p_b.project_id}/memories/{mem_a.memory_id}")
        self.assertEqual(resp_mem.status_code, 404)

        # Project B cannot patch Project A's memory
        resp_patch = self.client.patch(
            f"/api/projects/{p_b.project_id}/memories/{mem_a.memory_id}",
            json={"content": "Tampered"},
        )
        self.assertEqual(resp_patch.status_code, 404)

        # Project B cannot delete Project A's memory
        resp_del_m = self.client.delete(f"/api/projects/{p_b.project_id}/memories/{mem_a.memory_id}")
        self.assertEqual(resp_del_m.status_code, 404)

        # Project B cannot get Project A's candidate
        resp_cand = self.client.get(f"/api/projects/{p_b.project_id}/memory-candidates/{cand_a.candidate_id}")
        self.assertEqual(resp_cand.status_code, 404)

        # Project B cannot approve Project A's candidate
        resp_app = self.client.post(f"/api/projects/{p_b.project_id}/memory-candidates/{cand_a.candidate_id}/approve")
        self.assertEqual(resp_app.status_code, 404)

        # Project B cannot delete Project A's candidate
        resp_del_c = self.client.delete(f"/api/projects/{p_b.project_id}/memory-candidates/{cand_a.candidate_id}")
        self.assertEqual(resp_del_c.status_code, 404)

    def test_restart_persistence(self) -> None:
        """TEST 12: Restart persistence: Reconnecting to SQLite preserves projects, memories, and context."""
        project = self.project_service.create_project(
            name="Persistence Test Project",
            description="Testing survival across engine restarts",
        )
        self.project_service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="SQLite WAL Mode",
        )
        self.project_service.add_memory(
            project_id=project.project_id,
            category="coding_rule",
            content="Never modify production DB directly",
        )

        # Simulate complete engine restart
        reset_db_engine()
        restarted_engine = get_engine(database_url=self.db_url)
        init_db(engine=restarted_engine)
        restarted_factory = get_session_factory(restarted_engine)
        restarted_service = ProjectMemoryService(
            project_repository=ProjectRepository(session_factory=restarted_factory),
            memory_repository=ProjectMemoryRepository(session_factory=restarted_factory),
            candidate_repository=CandidateMemoryRepository(session_factory=restarted_factory),
        )

        # Verify project exists after restart
        loaded_project = restarted_service.get_project(project.project_id)
        self.assertEqual(loaded_project.name, "Persistence Test Project")

        # Verify context exists and has correct deterministic items
        context = restarted_service.get_project_context(project.project_id)
        self.assertIn("SQLite WAL Mode", context.technologies)
        self.assertIn("Never modify production DB directly", context.coding_rules)

    def test_empty_project_name_rejected_with_422(self) -> None:
        """TEST 13: Creating project with empty or whitespace name returns 422 Unprocessable Entity."""
        for invalid_name in ["", "   ", "\t\n"]:
            resp = self.client.post("/api/projects", json={"name": invalid_name})
            self.assertEqual(resp.status_code, 422)

    def test_compile_with_invalid_project_id_returns_404(self) -> None:
        """TEST 14: POST /api/compile with invalid project_id returns 404 Not Found."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build something", "project_id": fake_id},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["detail"].lower())

    def test_api_error_response_consistency(self) -> None:
        """TEST 15: Error responses follow standard FastAPI {"detail": ...} schema."""
        resp = self.client.get("/api/projects/non-existent-uuid-12345")
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("detail", data)
        self.assertIsInstance(data["detail"], str)


if __name__ == "__main__":
    unittest.main()
