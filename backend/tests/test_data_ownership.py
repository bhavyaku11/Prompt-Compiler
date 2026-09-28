"""Comprehensive deterministic security and ownership tests for Task 28.

Tests all 38 requirements specified in Task 28:
- User provisioning and uniqueness (Reqs 1-4)
- Project ownership and cross-user isolation (Reqs 5-14)
- Project memory and candidate memory ownership (Reqs 15-19)
- Knowledge ownership and search isolation (Reqs 20-24)
- Compilation ownership and persistence (Reqs 25-28)
- Interview session ownership (Reqs 29-30)
- Authentication enforcement and client-provided ownership rejection (Reqs 31-33)
- Regressions and public endpoints (Reqs 34-38)
- Security test matrix: User A vs User B cross-isolation
"""

import asyncio
import os
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.ai.embeddings import MockEmbeddingProvider, get_embedding_provider
from app.api.compile import (
    get_agent_formatter,
    get_compilation_repository,
    get_knowledge_retriever,
    get_knowledge_search_service,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_interviewer,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)
from app.api.knowledge import (
    get_document_ingestion_service,
    get_knowledge_indexer,
    get_knowledge_repository,
    get_knowledge_searcher,
    get_project_repository,
)
from app.api.projects import get_project_service
from app.auth import get_current_user, get_user_repository, require_authenticated_user
from app.config import Settings, settings
from app.database.models import UserRecord
from app.database.repositories import (
    CompilationRepository,
    InterviewSessionRepository,
    KnowledgeRepository,
    ProjectRepository,
    UserRepository,
)
from app.database.session import get_session_factory, init_db, reset_db_engine
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.interviewer import PromptInterviewer, SqliteInterviewSessionStore
from app.engine.knowledge_retrieval import KnowledgeRetriever, RetrievalExecutionResult
from app.engine.project_memory import ProjectMemoryService
from app.engine.refiner import PromptRefiner, RefinementResult
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.auth import AuthenticatedUser
from app.templates.selector import PromptTemplate, TemplateSelector


class TestDataOwnership(unittest.TestCase):
    """Deterministic security tests for user identity and data ownership."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_ownership.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.settings_patcher = patch.object(Settings, "DATABASE_URL", self.db_url)
        self.settings_patcher.start()

        reset_db_engine()
        init_db(self.db_url)

        self.session_factory = get_session_factory(self.db_url)
        self.user_repo = UserRepository(session_factory=self.session_factory)
        self.project_repo = ProjectRepository(session_factory=self.session_factory)
        self.compilation_repo = CompilationRepository(session_factory=self.session_factory)
        self.interview_repo = InterviewSessionRepository(session_factory=self.session_factory)
        self.knowledge_repo = KnowledgeRepository(session_factory=self.session_factory)

        self.project_service = ProjectMemoryService(database_url=self.db_url)
        self.interview_store = SqliteInterviewSessionStore(database_url=self.db_url)
        self.interviewer = PromptInterviewer(store=self.interview_store)

        # Provision two test users
        self.user_a = self.user_repo.get_or_create("clerk_user_A")
        self.user_b = self.user_repo.get_or_create("clerk_user_B")

        # Mock requirement engine and compiler dependencies so tests don't require external Ollama
        self.mock_req_engine = MagicMock(spec=RequirementEngine)
        self.mock_analysis = RequirementAnalysis(
            intent="Build a web app",
            task_type="build",
            domain="web",
            confirmed_requirements=["Must use React", "Must use Python"],
            missing_information=[],
            constraints=[],
            assumptions=[],
        )
        self.mock_req_engine.analyze_async = AsyncMock(return_value=self.mock_analysis)

        self.mock_generator = MagicMock(spec=PromptGenerator)
        self.mock_generator.generate_async = AsyncMock(
            return_value=PromptGenerationResult(
                final_prompt="Prompt content",
                template_name="build",
                task_type="build",
            )
        )

        mock_critic = MagicMock(spec=PromptCritic)
        mock_validation = ValidationResult(
            overall_valid=True,
            issues=[],
            preserved_requirements=["Must use React", "Must use Python"],
            missing_requirements=[],
            violated_constraints=[],
            invented_requirements=[],
            missing_information_preserved=True,
            task_type_valid=True,
            structure_valid=True,
        )

        self.mock_refiner = MagicMock(spec=PromptRefiner)
        self.mock_refiner.run_loop_async = AsyncMock(
            return_value=RefinementResult(
                final_prompt="Final prompt content",
                validation_result=mock_validation,
                refinement_attempts=0,
                task_type="build",
                template_name="build",
                converged=True,
            )
        )

        # Wire dependency overrides to point to our isolated test sqlite db
        self.mock_embedding_provider = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
        app.dependency_overrides[get_embedding_provider] = lambda: self.mock_embedding_provider
        app.dependency_overrides[get_user_repository] = lambda: self.user_repo
        app.dependency_overrides[get_project_repository] = lambda: self.project_repo
        app.dependency_overrides[get_knowledge_repository] = lambda: self.knowledge_repo
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo
        app.dependency_overrides[get_project_service] = lambda: self.project_service
        app.dependency_overrides[get_prompt_interviewer] = lambda: self.interviewer
        app.dependency_overrides[get_requirement_engine] = lambda: self.mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: self.mock_generator
        app.dependency_overrides[get_prompt_refiner] = lambda: self.mock_refiner

        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.settings_patcher.stop()
        reset_db_engine()
        self.temp_dir.cleanup()

    def set_active_user(self, user: UserRecord | None):
        """Set the active authenticated user for dependency injection."""
        if user is None:
            app.dependency_overrides.pop(require_authenticated_user, None)
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
                user_id=user.clerk_user_id
            )
            app.dependency_overrides[get_current_user] = lambda: user

    # =========================================================================
    # 1. USER PROVISIONING (Reqs 1-4)
    # =========================================================================

    def test_req_1_first_request_creates_local_user(self):
        """1. First authenticated request creates local User."""
        new_clerk_id = "clerk_unique_first_request"
        # Test direct get_or_create
        user = self.user_repo.get_or_create(new_clerk_id)
        self.assertIsNotNone(user)
        self.assertEqual(user.clerk_user_id, new_clerk_id)
        self.assertIsInstance(user.id, int)

        # Test through get_current_user dependency flow
        fresh_clerk_id = "clerk_fresh_via_dependency"
        auth_user = AuthenticatedUser(user_id=fresh_clerk_id)
        resolved_user = get_current_user(auth_user=auth_user, user_repo=self.user_repo)
        self.assertIsNotNone(resolved_user)
        self.assertEqual(resolved_user.clerk_user_id, fresh_clerk_id)

    def test_req_2_second_request_reuses_existing_user(self):
        """2. Second request for same Clerk user reuses existing User."""
        clerk_id = "clerk_reused_user"
        user_1 = self.user_repo.get_or_create(clerk_id)
        user_2 = self.user_repo.get_or_create(clerk_id)
        self.assertEqual(user_1.id, user_2.id)
        self.assertEqual(user_1.clerk_user_id, user_2.clerk_user_id)

    def test_req_3_same_clerk_user_cannot_create_duplicate_user(self):
        """3. Same Clerk user cannot create duplicate User (unique constraint)."""
        clerk_id = "clerk_dup_test"
        self.user_repo.get_or_create(clerk_id)

        # Attempting raw direct insert with same clerk_user_id must raise IntegrityError
        with self.session_factory() as session:
            duplicate = UserRecord(clerk_user_id=clerk_id)
            session.add(duplicate)
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_req_4_concurrent_provisioning_is_protected_by_unique_constraint(self):
        """4. Concurrent provisioning is protected by unique constraint."""
        clerk_id = "clerk_concurrent_user"
        results = []
        errors = []

        def worker():
            try:
                repo = UserRepository(session_factory=self.session_factory)
                user = repo.get_or_create(clerk_id)
                results.append(user.id)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent workers encountered errors: {errors}")
        self.assertEqual(len(results), 5)
        # All workers must resolve to the identical single user ID
        self.assertEqual(len(set(results)), 1)

    # =========================================================================
    # 2. PROJECT OWNERSHIP (Reqs 5-14)
    # =========================================================================

    def test_req_5_6_user_can_create_project(self):
        """5 & 6. User A can create Project A; User B can create Project B."""
        self.set_active_user(self.user_a)
        resp_a = self.client.post("/api/projects", json={"name": "Project Alpha"})
        self.assertEqual(resp_a.status_code, 201)
        project_a_id = resp_a.json()["project_id"]

        self.set_active_user(self.user_b)
        resp_b = self.client.post("/api/projects", json={"name": "Project Beta"})
        self.assertEqual(resp_b.status_code, 201)
        project_b_id = resp_b.json()["project_id"]

        self.assertNotEqual(project_a_id, project_b_id)

    def test_req_7_8_9_project_listing_isolation(self):
        """7, 8, 9. User A sees Project A, does not see Project B; User B sees Project B, not Project A."""
        self.set_active_user(self.user_a)
        resp_a = self.client.post("/api/projects", json={"name": "Alpha-Isolated"})
        id_a = resp_a.json()["project_id"]

        self.set_active_user(self.user_b)
        resp_b = self.client.post("/api/projects", json={"name": "Beta-Isolated"})
        id_b = resp_b.json()["project_id"]

        # Check User A's list
        self.set_active_user(self.user_a)
        list_a = self.client.get("/api/projects").json()
        ids_seen_by_a = [p["project_id"] for p in list_a]
        self.assertIn(id_a, ids_seen_by_a)
        self.assertNotIn(id_b, ids_seen_by_a)

        # Check User B's list
        self.set_active_user(self.user_b)
        list_b = self.client.get("/api/projects").json()
        ids_seen_by_b = [p["project_id"] for p in list_b]
        self.assertIn(id_b, ids_seen_by_b)
        self.assertNotIn(id_a, ids_seen_by_b)

    def test_req_10_11_project_update_cross_user_rejected(self):
        """10 & 11. User A can update Project A; User A cannot update Project B (returns 404)."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Project A to update"}).json()
        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Project B to update"}).json()

        # User A updates Project A -> Success (200)
        self.set_active_user(self.user_a)
        resp = self.client.patch(f"/api/projects/{proj_a['project_id']}", json={"name": "Project A Updated"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Project A Updated")

        # User A attempts to update Project B -> 404 (does not reveal existence)
        resp = self.client.patch(f"/api/projects/{proj_b['project_id']}", json={"name": "Hacked B"})
        self.assertEqual(resp.status_code, 404)

    def test_req_12_13_project_delete_cross_user_rejected(self):
        """12 & 13. User A can delete Project A; User A cannot delete Project B (returns 404)."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Project A to delete"}).json()
        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Project B to delete"}).json()

        # User A attempts to delete Project B -> 404
        self.set_active_user(self.user_a)
        resp = self.client.delete(f"/api/projects/{proj_b['project_id']}")
        self.assertEqual(resp.status_code, 404)

        # User A deletes Project A -> 200
        resp = self.client.delete(f"/api/projects/{proj_a['project_id']}")
        self.assertEqual(resp.status_code, 200)

    def test_req_14_user_cannot_access_other_project_by_id(self):
        """14. User A cannot access Project B by direct ID (returns 404)."""
        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Project B Secret"}).json()

        self.set_active_user(self.user_a)
        resp = self.client.get(f"/api/projects/{proj_b['project_id']}")
        self.assertEqual(resp.status_code, 404)

    # =========================================================================
    # 3. MEMORY OWNERSHIP (Reqs 15-19)
    # =========================================================================

    def test_req_15_16_17_18_memory_ownership_enforced(self):
        """15-18. User A can access/modify/delete memory under Project A; cannot do so under Project B."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Proj A Memory"}).json()
        mem_a_resp = self.client.post(
            f"/api/projects/{proj_a['project_id']}/memories",
            json={"category": "architecture", "content": "FastAPI backend"},
        )
        self.assertEqual(mem_a_resp.status_code, 201)
        mem_a_id = mem_a_resp.json()["memory_id"]

        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Proj B Memory"}).json()
        mem_b_resp = self.client.post(
            f"/api/projects/{proj_b['project_id']}/memories",
            json={"category": "architecture", "content": "Django backend"},
        )
        self.assertEqual(mem_b_resp.status_code, 201)
        mem_b_id = mem_b_resp.json()["memory_id"]

        # User A accesses memory A -> 200
        self.set_active_user(self.user_a)
        resp = self.client.get(f"/api/projects/{proj_a['project_id']}/memories/{mem_a_id}")
        self.assertEqual(resp.status_code, 200)

        # User A attempts to access memory B -> 404
        resp = self.client.get(f"/api/projects/{proj_b['project_id']}/memories/{mem_b_id}")
        self.assertEqual(resp.status_code, 404)

        # User A attempts to modify memory B -> 404
        resp = self.client.patch(
            f"/api/projects/{proj_b['project_id']}/memories/{mem_b_id}",
            json={"content": "Modified Django"},
        )
        self.assertEqual(resp.status_code, 404)

        # User A attempts to delete memory B -> 404
        resp = self.client.delete(f"/api/projects/{proj_b['project_id']}/memories/{mem_b_id}")
        self.assertEqual(resp.status_code, 404)

        # User A deletes memory A -> 200
        resp = self.client.delete(f"/api/projects/{proj_a['project_id']}/memories/{mem_a_id}")
        self.assertEqual(resp.status_code, 200)

    def test_req_19_candidate_memory_ownership_enforced(self):
        """19. Candidate memory ownership is strictly enforced across users."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Proj A Candidate"}).json()

        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Proj B Candidate"}).json()

        # User B extracts candidates
        cand_b_resp = self.client.post(
            f"/api/projects/{proj_b['project_id']}/memory-candidates",
            json={"input": "We must use PostgreSQL database"},
        )
        self.assertEqual(cand_b_resp.status_code, 201)
        candidates = cand_b_resp.json()
        self.assertGreater(len(candidates), 0)
        cand_b_id = candidates[0]["candidate_id"]

        # User A cannot list candidates from Project B -> 404
        self.set_active_user(self.user_a)
        resp = self.client.get(f"/api/projects/{proj_b['project_id']}/memory-candidates")
        self.assertEqual(resp.status_code, 404)

        # User A cannot get candidate from Project B -> 404
        resp = self.client.get(f"/api/projects/{proj_b['project_id']}/memory-candidates/{cand_b_id}")
        self.assertEqual(resp.status_code, 404)

        # User A cannot approve candidate from Project B -> 404
        resp = self.client.post(f"/api/projects/{proj_b['project_id']}/memory-candidates/{cand_b_id}/approve")
        self.assertEqual(resp.status_code, 404)

        # User A cannot reject candidate from Project B -> 404
        resp = self.client.post(f"/api/projects/{proj_b['project_id']}/memory-candidates/{cand_b_id}/reject")
        self.assertEqual(resp.status_code, 404)

        # User A cannot delete candidate from Project B -> 404
        resp = self.client.delete(f"/api/projects/{proj_b['project_id']}/memory-candidates/{cand_b_id}")
        self.assertEqual(resp.status_code, 404)

    # =========================================================================
    # 4. KNOWLEDGE OWNERSHIP (Reqs 20-24)
    # =========================================================================

    def test_req_20_21_22_23_knowledge_ownership_enforced(self):
        """20-23. Knowledge indexing, search, ingestion, and deletion enforce user/project boundary."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Proj A Knowledge"}).json()

        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Proj B Knowledge"}).json()

        # User A cannot search Project B knowledge -> 404
        self.set_active_user(self.user_a)
        resp = self.client.post(
            f"/api/projects/{proj_b['project_id']}/knowledge/search",
            json={"query": "database schema"},
        )
        self.assertEqual(resp.status_code, 404)

        # User A cannot ingest knowledge into Project B -> 404
        resp = self.client.post(
            f"/api/projects/{proj_b['project_id']}/knowledge/index",
            json={"source_name": "spec.md", "source_type": "documentation", "content": "Sample content"},
        )
        self.assertEqual(resp.status_code, 404)

        # User A cannot list knowledge sources for Project B -> 404
        resp = self.client.get(f"/api/projects/{proj_b['project_id']}/knowledge/sources")
        self.assertEqual(resp.status_code, 404)

        # User A cannot delete Project B knowledge source -> 404
        resp = self.client.delete(f"/api/projects/{proj_b['project_id']}/knowledge/sources/nonexistent-source")
        self.assertEqual(resp.status_code, 404)

    def test_req_24_knowledge_retrieval_cannot_cross_user_boundary(self):
        """24. RAG / Knowledge retrieval during compilation cannot cross user boundaries."""
        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "User B Secret Docs"}).json()

        # User A attempts compilation pointing at Project B's ID -> 404
        self.set_active_user(self.user_a)
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build app", "project_id": proj_b["project_id"]},
        )
        self.assertEqual(resp.status_code, 404)

    # =========================================================================
    # 5. COMPILATION OWNERSHIP (Reqs 25-28)
    # =========================================================================

    def test_req_25_26_compilation_project_ownership(self):
        """25 & 26. User A can compile for Project A; User A cannot compile using Project B."""
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Proj A Compile"}).json()

        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Proj B Compile"}).json()

        # User A compiles for Project A -> Success (200)
        self.set_active_user(self.user_a)
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build login screen", "project_id": proj_a["project_id"]},
        )
        self.assertEqual(resp.status_code, 200)

        # User A compiles using Project B -> Rejected (404)
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build login screen", "project_id": proj_b["project_id"]},
        )
        self.assertEqual(resp.status_code, 404)

    def test_req_27_28_compilation_persisted_with_user_id(self):
        """27 & 28. Compilation ownership is persisted correctly and isolated in repository."""
        self.set_active_user(self.user_a)
        resp = self.client.post("/api/compile", json={"input": "Build home page"})
        self.assertEqual(resp.status_code, 200)

        # Verify compilation record in repository is associated with user_a.id
        recent_a = self.compilation_repo.list_recent(limit=10, user_id=self.user_a.id)
        recent_b = self.compilation_repo.list_recent(limit=10, user_id=self.user_b.id)

        self.assertGreater(len(recent_a), 0)
        self.assertTrue(all(c.user_id == self.user_a.id for c in recent_a))
        # User B should not see User A's compilation
        self.assertEqual(len(recent_b), 0)

    # =========================================================================
    # 6. INTERVIEW SESSION OWNERSHIP (Reqs 29-30)
    # =========================================================================

    def test_req_29_30_interview_session_ownership_enforced(self):
        """29 & 30. User A can access own interview session; User A cannot access User B's session."""
        self.set_active_user(self.user_a)
        start_a = self.client.post("/api/interview/start", json={"input": "Build a portal"}).json()
        session_a_id = start_a["session_id"]

        self.set_active_user(self.user_b)
        start_b = self.client.post("/api/interview/start", json={"input": "Build a portal"}).json()
        session_b_id = start_b["session_id"]

        # User A accesses own session -> 200
        self.set_active_user(self.user_a)
        resp = self.client.get(f"/api/interview/{session_a_id}")
        self.assertEqual(resp.status_code, 200)

        # User A attempts to access User B's session -> 404
        resp = self.client.get(f"/api/interview/{session_b_id}")
        self.assertEqual(resp.status_code, 404)

        # User A attempts to answer User B's session -> 404
        resp = self.client.post(
            f"/api/interview/{session_b_id}/answer",
            json={"answers": [{"question_id": "q1", "answer": "Vercel"}]},
        )
        self.assertEqual(resp.status_code, 404)

        # User A attempts to compile User B's session -> 404
        resp = self.client.post(f"/api/interview/{session_b_id}/compile")
        self.assertEqual(resp.status_code, 404)

        # User A attempts to delete User B's session -> 404
        resp = self.client.delete(f"/api/interview/{session_b_id}")
        self.assertEqual(resp.status_code, 404)

        # User A deletes own session -> 200
        resp = self.client.delete(f"/api/interview/{session_a_id}")
        self.assertEqual(resp.status_code, 200)

    # =========================================================================
    # 7. AUTHENTICATION & CLIENT INPUT INTEGRITY (Reqs 31-33)
    # =========================================================================

    def test_req_31_unauthenticated_business_requests_rejected(self):
        """31. Unauthenticated business requests are rejected with 401."""
        self.set_active_user(None)

        endpoints = [
            ("GET", "/api/projects"),
            ("POST", "/api/projects"),
            ("POST", "/api/compile"),
            ("POST", "/api/interview/start"),
            ("GET", "/api/interview/test-session"),
            ("GET", "/api/projects/test-proj/knowledge/sources"),
        ]

        for method, url in endpoints:
            if method == "GET":
                resp = self.client.get(url)
            else:
                resp = self.client.post(url, json={})
            self.assertEqual(
                resp.status_code,
                401,
                f"Expected 401 for unauthenticated {method} {url}, got {resp.status_code}",
            )

    def test_req_32_authenticated_user_identity_from_verified_clerk(self):
        """32. Authenticated user identity comes from verified Clerk identity."""
        self.set_active_user(self.user_a)
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["user_id"], self.user_a.clerk_user_id)

    def test_req_33_client_provided_ownership_cannot_override_identity(self):
        """33. Client-provided user ID cannot override authentication identity."""
        self.set_active_user(self.user_a)
        # Attempt to pass user_id, owner_id, clerk_user_id in payload
        resp = self.client.post(
            "/api/projects",
            json={
                "name": "Spoofed Project",
                "user_id": self.user_b.id,
                "owner_id": self.user_b.id,
                "clerk_user_id": self.user_b.clerk_user_id,
            },
        )
        self.assertEqual(resp.status_code, 201)
        proj_data = resp.json()
        proj_id = proj_data["project_id"]

        # The project must belong to User A, NOT User B
        proj_in_db = self.project_repo.get(proj_id, user_id=self.user_a.id)
        self.assertIsNotNone(proj_in_db)
        self.assertEqual(proj_in_db.user_id, self.user_a.id)

        # User B cannot access it
        self.assertIsNone(self.project_repo.get(proj_id, user_id=self.user_b.id))

    # =========================================================================
    # 8. REGRESSION & PUBLIC ENDPOINTS (Reqs 34-38)
    # =========================================================================

    def test_req_34_health_endpoint_continues_working(self):
        """34. /api/health continues working without authentication."""
        self.set_active_user(None)
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok", "service": "prompt-compiler"})

    def test_req_35_presets_endpoint_continues_working(self):
        """35. /api/presets continues working without authentication."""
        self.set_active_user(None)
        resp = self.client.get("/api/presets")
        self.assertEqual(resp.status_code, 200)
        self.assertIsInstance(resp.json(), list)

    def test_req_36_existing_compiler_behavior_works_for_owner(self):
        """36. Existing compiler behavior still works for authenticated owner."""
        self.set_active_user(self.user_a)
        resp = self.client.post(
            "/api/compile",
            json={"input": "Build an e-commerce checkout flow in TypeScript"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["result"], "Final prompt content")
        self.assertEqual(data["task_type"], "build")

    def test_req_37_existing_rag_behavior_works_for_owner(self):
        """37. Existing RAG behavior still works for authenticated owner."""
        self.set_active_user(self.user_a)
        proj = self.client.post("/api/projects", json={"name": "Owner RAG Proj"}).json()

        # Ingest knowledge into own project
        idx_resp = self.client.post(
            f"/api/projects/{proj['project_id']}/knowledge/index",
            json={
                "source_name": "auth_spec.md",
                "source_type": "documentation",
                "content": "Authentication must use Clerk JWT tokens.",
            },
        )
        self.assertEqual(idx_resp.status_code, 201)

        # Search knowledge in own project
        search_resp = self.client.post(
            f"/api/projects/{proj['project_id']}/knowledge/search",
            json={"query": "Clerk tokens", "top_k": 5},
        )
        self.assertEqual(search_resp.status_code, 200)

    def test_req_38_existing_memory_behavior_works_for_owner(self):
        """38. Existing memory behavior still works for authenticated owner."""
        self.set_active_user(self.user_a)
        proj = self.client.post("/api/projects", json={"name": "Owner Memory Proj"}).json()

        # Add memory
        add_resp = self.client.post(
            f"/api/projects/{proj_id}/memories" if "proj_id" in locals() else f"/api/projects/{proj['project_id']}/memories",
            json={"category": "technology", "content": "FastAPI + React"},
        )
        self.assertEqual(add_resp.status_code, 201)

        # Get context
        ctx_resp = self.client.get(f"/api/projects/{proj['project_id']}/context")
        self.assertEqual(ctx_resp.status_code, 200)
        self.assertIn("FastAPI + React", ctx_resp.json()["technologies"])

    # =========================================================================
    # 9. SECURITY TEST MATRIX
    # =========================================================================

    def test_security_test_matrix_cross_isolation(self):
        """Test complete cross-user security matrix:

                     User A      User B
        Project A      ✓           ✗
        Project B      ✗           ✓
        Memory A       ✓           ✗
        Memory B       ✗           ✓
        Knowledge A    ✓           ✗
        Knowledge B    ✗           ✓
        Compilation A  ✓           ✗
        Compilation B  ✗           ✓
        Interview A    ✓           ✗
        Interview B    ✗           ✓
        """
        # Create resources for User A
        self.set_active_user(self.user_a)
        proj_a = self.client.post("/api/projects", json={"name": "Matrix Project A"}).json()
        mem_a = self.client.post(
            f"/api/projects/{proj_a['project_id']}/memories",
            json={"category": "technology", "content": "Memory A"},
        ).json()
        self.client.post(
            f"/api/projects/{proj_a['project_id']}/knowledge/index",
            json={"source_name": "ka.txt", "source_type": "documentation", "content": "Knowledge A"},
        )
        comp_a = self.client.post(
            "/api/compile",
            json={"input": "Compile A", "project_id": proj_a["project_id"]},
        ).json()
        int_a = self.client.post("/api/interview/start", json={"input": "Interview A"}).json()

        # Create resources for User B
        self.set_active_user(self.user_b)
        proj_b = self.client.post("/api/projects", json={"name": "Matrix Project B"}).json()
        mem_b = self.client.post(
            f"/api/projects/{proj_b['project_id']}/memories",
            json={"category": "technology", "content": "Memory B"},
        ).json()
        self.client.post(
            f"/api/projects/{proj_b['project_id']}/knowledge/index",
            json={"source_name": "kb.txt", "source_type": "documentation", "content": "Knowledge B"},
        )
        comp_b = self.client.post(
            "/api/compile",
            json={"input": "Compile B", "project_id": proj_b["project_id"]},
        ).json()
        int_b = self.client.post("/api/interview/start", json={"input": "Interview B"}).json()

        # --- USER A TESTS ---
        self.set_active_user(self.user_a)

        # Project A: ✓ | Project B: ✗
        self.assertEqual(self.client.get(f"/api/projects/{proj_a['project_id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/projects/{proj_b['project_id']}").status_code, 404)

        # Memory A: ✓ | Memory B: ✗
        self.assertEqual(self.client.get(f"/api/projects/{proj_a['project_id']}/memories/{mem_a['memory_id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/projects/{proj_b['project_id']}/memories/{mem_b['memory_id']}").status_code, 404)

        # Knowledge A: ✓ | Knowledge B: ✗
        self.assertEqual(
            self.client.post(f"/api/projects/{proj_a['project_id']}/knowledge/search", json={"query": "test"}).status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/projects/{proj_b['project_id']}/knowledge/search", json={"query": "test"}).status_code, 404
        )

        # Compilation A: ✓ | Compilation B: ✗ (via repository listing)
        comps_seen_by_a = self.compilation_repo.list_recent(limit=50, user_id=self.user_a.id)
        comps_by_a_projects = [c.project_id for c in comps_seen_by_a]
        self.assertIn(proj_a["project_id"], comps_by_a_projects)
        self.assertNotIn(proj_b["project_id"], comps_by_a_projects)

        # Interview A: ✓ | Interview B: ✗
        self.assertEqual(self.client.get(f"/api/interview/{int_a['session_id']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/interview/{int_b['session_id']}").status_code, 404)

        # --- USER B TESTS ---
        self.set_active_user(self.user_b)

        # Project A: ✗ | Project B: ✓
        self.assertEqual(self.client.get(f"/api/projects/{proj_a['project_id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/projects/{proj_b['project_id']}").status_code, 200)

        # Memory A: ✗ | Memory B: ✓
        self.assertEqual(self.client.get(f"/api/projects/{proj_a['project_id']}/memories/{mem_a['memory_id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/projects/{proj_b['project_id']}/memories/{mem_b['memory_id']}").status_code, 200)

        # Knowledge A: ✗ | Knowledge B: ✓
        self.assertEqual(
            self.client.post(f"/api/projects/{proj_a['project_id']}/knowledge/search", json={"query": "test"}).status_code, 404
        )
        self.assertEqual(
            self.client.post(f"/api/projects/{proj_b['project_id']}/knowledge/search", json={"query": "test"}).status_code, 200
        )

        # Compilation A: ✗ | Compilation B: ✓
        comps_seen_by_b = self.compilation_repo.list_recent(limit=50, user_id=self.user_b.id)
        comps_by_b_projects = [c.project_id for c in comps_seen_by_b]
        self.assertIn(proj_b["project_id"], comps_by_b_projects)
        self.assertNotIn(proj_a["project_id"], comps_by_b_projects)

        # Interview A: ✗ | Interview B: ✓
        self.assertEqual(self.client.get(f"/api/interview/{int_a['session_id']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/interview/{int_b['session_id']}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
