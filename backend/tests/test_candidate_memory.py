"""Tests for Candidate Project Memory Extraction and Confirmation Workflow (Task 18).

Tests cover:
1. Explicit technology statement produces a candidate.
2. Explicit architecture decision produces a candidate.
3. Explicit coding rule produces a candidate.
4. Explicit constraint produces a candidate.
5. Temporary information is not unnecessarily proposed (transient errors, debugging, casual chat).
6. User-confirmed information gets correct source attribution (user_confirmed / extracted_from_user_input).
7. Generated assumptions are not treated as user-confirmed.
8. Confidence is bounded correctly (between 0.0 and 1.0).
9. Evidence is concise and present.
10. Duplicate memory detection works (detects existing active memory, marks duplicate, prevents duplicate creation).
11. Conflict detection works (detects conflicting stack choice, marks conflict, references conflicting memory).
12. Candidate approval creates ProjectMemory.
13. Candidate rejection does not create ProjectMemory.
14. Conflict does not automatically overwrite existing memory without explicit supersede directive.
15. Compilation does not automatically write memory or create candidate memories (read-only compile guarantee).
16. ProjectRepository cascade delete removes associated candidate memories.
17. REST API: candidate extraction, listing, retrieval, approval, and rejection endpoints.
18. REST API: invalid project and candidate IDs return HTTP 404.
"""

import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.api.compile import (
    get_compilation_repository,
    get_project_service as get_compile_project_service,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)
from app.api.projects import get_project_service
from app.database.repositories import (
    CandidateMemoryRepository,
    CompilationRepository,
    ProjectMemoryRepository,
    ProjectRepository,
)
from app.database.session import init_db, reset_db_engine
from app.engine.critic import PromptCritic, ValidationResult
from app.engine.generator import PromptGenerationResult, PromptGenerator
from app.engine.memory_extractor import CandidateMemoryExtractor, is_transient_or_ephemeral
from app.engine.project_memory import (
    CandidateNotFoundError,
    InvalidCandidateActionError,
    ProjectMemoryService,
    ProjectNotFoundError,
)
from app.engine.requirements import RequirementAnalysis, RequirementEngine
from app.main import app
from app.schemas.candidate_memory import (
    CandidateApprovalRequest,
    CandidateMemory,
    CandidateMemoryCreate,
    CandidateStatus,
)
from app.schemas.project import MemoryCategory, MemorySource, MemoryStatus
from app.templates.selector import TemplateSelector


class TestCandidateMemoryUnit(unittest.TestCase):
    """Unit tests for CandidateMemoryExtractor and ProjectMemoryService candidate workflow."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_candidate_unit.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.candidate_repo = CandidateMemoryRepository(database_url=self.db_url)
        self.extractor = CandidateMemoryExtractor()

        self.service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
            candidate_repository=self.candidate_repo,
            extractor=self.extractor,
            database_url=self.db_url,
        )

        self.project = self.service.create_project(
            name="E-Commerce Backend",
            description="Microservices API for store",
        )
        self.project_id = self.project.project_id

    def tearDown(self) -> None:
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_01_explicit_technology_statement_produces_candidate(self) -> None:
        """Requirement 1: Explicit technology statement produces a candidate."""
        user_input = "We will use FastAPI for the backend and PostgreSQL as our database."
        candidates = self.service.extract_candidates(self.project_id, user_input)

        self.assertGreaterEqual(len(candidates), 2)
        categories = {c.category for c in candidates}
        self.assertIn("backend", categories)
        self.assertIn("database", categories)

        backend_cand = next(c for c in candidates if c.category == "backend")
        self.assertIn("FastAPI", backend_cand.content)
        self.assertEqual(backend_cand.status, CandidateStatus.PENDING.value)

    def test_02_explicit_architecture_decision_produces_candidate(self) -> None:
        """Requirement 2: Explicit architecture decision produces a candidate."""
        user_input = "We want to use microservices architecture for this project."
        candidates = self.service.extract_candidates(self.project_id, user_input)

        self.assertTrue(any(c.category == "architecture" for c in candidates))
        arch_cand = next(c for c in candidates if c.category == "architecture")
        self.assertIn("microservices", arch_cand.content.lower())
        self.assertEqual(arch_cand.status, CandidateStatus.PENDING.value)

    def test_03_explicit_coding_rule_produces_candidate(self) -> None:
        """Requirement 3: Explicit coding rule produces a candidate."""
        user_input = "All API endpoints must have comprehensive type hints and docstrings."
        candidates = self.service.extract_candidates(self.project_id, user_input)

        self.assertTrue(any(c.category == "coding_rule" for c in candidates))
        rule_cand = next(c for c in candidates if c.category == "coding_rule")
        self.assertIn("type hints", rule_cand.content)
        self.assertEqual(rule_cand.status, CandidateStatus.PENDING.value)

    def test_04_explicit_constraint_produces_candidate(self) -> None:
        """Requirement 4: Explicit constraint produces a candidate."""
        user_input = "Do not modify the existing authentication flow and leave token validation untouched."
        candidates = self.service.extract_candidates(self.project_id, user_input)

        self.assertTrue(any(c.category == "constraint" for c in candidates))
        constraint_cand = next(c for c in candidates if c.category == "constraint")
        self.assertIn("authentication", constraint_cand.content.lower())
        self.assertEqual(constraint_cand.status, CandidateStatus.PENDING.value)

    def test_05_temporary_information_not_proposed(self) -> None:
        """Requirement 5: Temporary debugging, one-off commands, and casual chat are rejected."""
        transient_inputs = [
            "print(error_message) to console.log",
            "fix typo on line 42",
            "run pytest",
            "hello can you help me with this",
            "make this button blue",
            "error 500 nullpointer exception in logs",
        ]
        for text in transient_inputs:
            self.assertTrue(is_transient_or_ephemeral(text), f"Expected '{text}' to be transient!")
            candidates = self.service.extract_candidates(self.project_id, text)
            self.assertEqual(
                len(candidates),
                0,
                f"Expected 0 candidates for transient input '{text}', got {len(candidates)}",
            )

    def test_06_source_attribution_for_user_and_requirements(self) -> None:
        """Requirement 6: User-confirmed vs extracted from input source attribution."""
        # Direct user input -> USER_CONFIRMED
        cands_user = self.service.extract_candidates(self.project_id, "Use FastAPI for the backend")
        self.assertEqual(cands_user[0].source, MemorySource.USER_CONFIRMED.value)

        # Confirmed requirements parameter -> EXTRACTED_FROM_USER_INPUT
        cands_req = self.service.extract_candidates(
            self.project_id,
            user_input="Build order service",
            confirmed_requirements=["Database target is Redis"],
        )
        redis_cand = next((c for c in cands_req if "Redis" in c.content), None)
        self.assertIsNotNone(redis_cand)
        self.assertEqual(redis_cand.source, MemorySource.EXTRACTED_FROM_USER_INPUT.value)

    def test_07_generated_assumptions_not_treated_as_user_confirmed(self) -> None:
        """Requirement 7: Generated assumptions preserve GENERATED_ASSUMPTION source."""
        # Direct schema creation with assumption source
        cand = self.candidate_repo.create(
            self.project_id,
            CandidateMemoryCreate(
                category="database",
                content="Assume database is SQLite for dev",
                source=MemorySource.GENERATED_ASSUMPTION.value,
                confidence=0.5,
            ),
        )
        self.assertEqual(cand.source, MemorySource.GENERATED_ASSUMPTION.value)
        self.assertNotEqual(cand.source, MemorySource.USER_CONFIRMED.value)

    def test_08_confidence_is_bounded_correctly(self) -> None:
        """Requirement 8: Confidence is bounded between 0.0 and 1.0."""
        cands = self.service.extract_candidates(self.project_id, "Deploy on Railway")
        for c in cands:
            self.assertGreaterEqual(c.confidence, 0.0)
            self.assertLessEqual(c.confidence, 1.0)
            # High extraction fidelity for explicit direct statement
            self.assertGreaterEqual(c.confidence, 0.9)

        # Schema rejects invalid confidence
        with self.assertRaises(ValueError):
            CandidateMemoryCreate(
                category="technology",
                content="Tech",
                confidence=1.5,
            )

    def test_09_evidence_is_concise_and_present(self) -> None:
        """Requirement 9: Evidence is concise and user-readable."""
        cands = self.service.extract_candidates(self.project_id, "Use FastAPI for the backend")
        backend_cand = cands[0]
        self.assertTrue(len(backend_cand.evidence) > 0)
        self.assertIn("User explicitly stated", backend_cand.evidence)
        self.assertLess(len(backend_cand.evidence), 200)

    def test_10_duplicate_memory_detection(self) -> None:
        """Requirement 10: Duplicate memory detection marks candidate as DUPLICATE and prevents double creation."""
        # Add active project memory
        self.service.add_memory(
            project_id=self.project_id,
            category="backend",
            content="Backend uses FastAPI",
        )

        # Extract candidates with same technology
        cands = self.service.extract_candidates(
            self.project_id,
            "We should use FastAPI for the backend.",
        )
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].status, CandidateStatus.DUPLICATE.value)
        self.assertIn("Duplicate of existing memory", cands[0].evidence)

        # Approving duplicate raises InvalidCandidateActionError
        with self.assertRaises(InvalidCandidateActionError):
            self.service.approve_candidate(cands[0].candidate_id)

    def test_11_conflict_detection(self) -> None:
        """Requirement 11: Conflict detection marks candidate as CONFLICT and references conflicting memory."""
        # Add active memory: Frontend is React
        react_mem = self.service.add_memory(
            project_id=self.project_id,
            category="frontend",
            content="Frontend uses React",
        )

        # User interaction proposing Vue
        cands = self.service.extract_candidates(
            self.project_id,
            "Use Vue for the frontend instead.",
        )
        self.assertEqual(len(cands), 1)
        vue_cand = cands[0]
        self.assertEqual(vue_cand.status, CandidateStatus.CONFLICT.value)
        self.assertEqual(vue_cand.conflicting_memory_id, react_mem.memory_id)
        self.assertIn("React", vue_cand.conflicting_content or "")

    def test_12_candidate_approval_creates_project_memory(self) -> None:
        """Requirement 12: Candidate approval creates persistent ProjectMemory record."""
        cands = self.service.extract_candidates(self.project_id, "Deploy on Railway")
        deploy_cand = cands[0]
        self.assertEqual(deploy_cand.status, CandidateStatus.PENDING.value)

        # Memory count before approval
        memories_before = self.service.list_memories(self.project_id)
        self.assertEqual(len(memories_before), 0)

        # Approve candidate
        resp = self.service.approve_candidate(deploy_cand.candidate_id)
        self.assertEqual(resp.candidate.status, CandidateStatus.APPROVED.value)
        self.assertIsNotNone(resp.created_memory_id)

        # Verify persistent ProjectMemory was created
        memories_after = self.service.list_memories(self.project_id)
        self.assertEqual(len(memories_after), 1)
        self.assertEqual(memories_after[0].memory_id, resp.created_memory_id)
        self.assertIn("Railway", memories_after[0].content)

    def test_13_candidate_rejection_does_not_create_project_memory(self) -> None:
        """Requirement 13: Candidate rejection does not create ProjectMemory."""
        cands = self.service.extract_candidates(self.project_id, "Use FastAPI for the backend")
        cand = cands[0]

        rejected = self.service.reject_candidate(cand.candidate_id, reason="Changed mind")
        self.assertEqual(rejected.status, CandidateStatus.REJECTED.value)
        self.assertEqual(rejected.metadata.get("rejection_reason"), "Changed mind")

        # Confirm 0 ProjectMemories created
        memories = self.service.list_memories(self.project_id)
        self.assertEqual(len(memories), 0)

    def test_14_conflict_does_not_automatically_overwrite_memory(self) -> None:
        """Requirement 14: Conflict does not overwrite memory without explicit supersede_conflicting=True."""
        # Existing memory: React
        react_mem = self.service.add_memory(
            project_id=self.project_id,
            category="frontend",
            content="Frontend uses React",
        )

        cands = self.service.extract_candidates(self.project_id, "Use Vue for the frontend")
        vue_cand = cands[0]
        self.assertEqual(vue_cand.status, CandidateStatus.CONFLICT.value)

        # Approve with supersede_conflicting=False (keeps existing memory active)
        resp_keep = self.service.approve_candidate(vue_cand.candidate_id, supersede_conflicting=False)
        self.assertIsNone(resp_keep.superseded_memory_id)

        # React memory is still active
        refreshed_react = self.service.get_memory(react_mem.memory_id)
        self.assertEqual(refreshed_react.status, MemoryStatus.ACTIVE.value)

        # Now test approval with supersede_conflicting=True on a second conflict candidate
        cands2 = self.service.extract_candidates(self.project_id, "Use Svelte for the frontend")
        svelte_cand = cands2[0]
        resp_supersede = self.service.approve_candidate(svelte_cand.candidate_id, supersede_conflicting=True)

        self.assertIsNotNone(resp_supersede.superseded_memory_id)
        superseded_mem = self.service.get_memory(resp_supersede.superseded_memory_id)
        self.assertEqual(superseded_mem.status, MemoryStatus.SUPERSEDED.value)

    def test_15_project_delete_cascades_to_candidates(self) -> None:
        """Requirement 16: Project deletion removes associated candidate memories."""
        self.service.extract_candidates(self.project_id, "Deploy on Railway")
        candidates = self.service.list_candidates(self.project_id)
        self.assertGreater(len(candidates), 0)

        # Delete project
        self.service.delete_project(self.project_id)

        # Candidates should be deleted
        remaining = self.candidate_repo.list_by_project(self.project_id)
        self.assertEqual(len(remaining), 0)


class TestCandidateMemoryAPI(unittest.TestCase):
    """API integration tests for Candidate Memory REST endpoints."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_candidate_api.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)

        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.candidate_repo = CandidateMemoryRepository(database_url=self.db_url)
        self.compilation_repo = CompilationRepository(database_url=self.db_url)
        self.service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
            candidate_repository=self.candidate_repo,
            database_url=self.db_url,
        )

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_cand_mem")
        app.dependency_overrides[get_current_user] = lambda: self.test_user

        self.project = self.service.create_project(
            name="Fintech Platform",
            description="Trading and account ledger system",
            user_id=self.test_user.id,
        )
        self.project_id = self.project.project_id

        self.client = TestClient(app)
        app.dependency_overrides[get_project_service] = lambda: self.service
        app.dependency_overrides[get_compile_project_service] = lambda: self.service
        app.dependency_overrides[get_compilation_repository] = lambda: self.compilation_repo

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_16_extract_and_list_candidate_endpoints(self) -> None:
        """Requirement 17: Extract and list candidate memories via REST API."""
        # 1. Extract candidates
        resp = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates",
            json={
                "input": "Use FastAPI for the backend and PostgreSQL as our database.",
                "confirmed_requirements": ["All API endpoints must require authentication"],
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 2)

        # 2. List candidates
        list_resp = self.client.get(f"/api/projects/{self.project_id}/memory-candidates")
        self.assertEqual(list_resp.status_code, 200)
        cands = list_resp.json()
        self.assertEqual(len(cands), len(data))

        # 3. Filter by status
        pending_resp = self.client.get(f"/api/projects/{self.project_id}/memory-candidates?status=pending")
        self.assertEqual(pending_resp.status_code, 200)
        self.assertTrue(all(c["status"] == "pending" for c in pending_resp.json()))

    def test_17_approve_and_reject_candidate_endpoints(self) -> None:
        """Requirement 17: Approve and reject candidate memories via REST API."""
        # Extract 2 candidates
        extract_resp = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates",
            json={"input": "Use FastAPI for the backend and Railway for deployment."},
        )
        self.assertEqual(extract_resp.status_code, 201)
        cands = extract_resp.json()
        self.assertGreaterEqual(len(cands), 2)

        cand_to_approve = cands[0]
        cand_to_reject = cands[1]

        # Approve first candidate
        approve_resp = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates/{cand_to_approve['candidate_id']}/approve",
            json={"supersede_conflicting": False},
        )
        self.assertEqual(approve_resp.status_code, 200)
        app_data = approve_resp.json()
        self.assertEqual(app_data["candidate"]["status"], "approved")
        self.assertIsNotNone(app_data["created_memory_id"])

        # Reject second candidate
        reject_resp = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates/{cand_to_reject['candidate_id']}/reject",
            json={"reason": "Decided on a different hosting platform"},
        )
        self.assertEqual(reject_resp.status_code, 200)
        rej_data = reject_resp.json()
        self.assertEqual(rej_data["status"], "rejected")

        # Verify only 1 persistent ProjectMemory exists
        mem_resp = self.client.get(f"/api/projects/{self.project_id}/memories")
        self.assertEqual(mem_resp.status_code, 200)
        self.assertEqual(len(mem_resp.json()), 1)
        self.assertEqual(mem_resp.json()[0]["memory_id"], app_data["created_memory_id"])

    def test_18_invalid_project_and_candidate_ids_return_404(self) -> None:
        """Requirement 18: Invalid IDs return HTTP 404."""
        # Nonexistent project
        resp1 = self.client.post(
            "/api/projects/nonexistent-id/memory-candidates",
            json={"input": "Use FastAPI"},
        )
        self.assertEqual(resp1.status_code, 404)

        resp2 = self.client.get("/api/projects/nonexistent-id/memory-candidates")
        self.assertEqual(resp2.status_code, 404)

        # Nonexistent candidate
        resp3 = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates/nonexistent-cand/approve",
            json={},
        )
        self.assertEqual(resp3.status_code, 404)

        resp4 = self.client.post(
            f"/api/projects/{self.project_id}/memory-candidates/nonexistent-cand/reject",
            json={},
        )
        self.assertEqual(resp4.status_code, 404)

    def test_19_compilation_does_not_automatically_write_memory(self) -> None:
        """Requirement 15: POST /api/compile with project_id remains strictly read-only."""
        # Pre-seed 1 active memory
        self.service.add_memory(
            project_id=self.project_id,
            category="backend",
            content="FastAPI backend framework",
        )

        # Mock compiler stages to prevent live Ollama network call
        mock_analysis = RequirementAnalysis(
            intent="Add user login",
            task_type="build",
            domain="web",
            confirmed_requirements=["JWT authentication", "Use SQLite for sessions"],
            missing_information=[],
            constraints=[],
            assumptions=[],
        )
        mock_req_engine = RequirementEngine()
        mock_req_engine.analyze_async = AsyncMock(return_value=mock_analysis)

        mock_gen_result = PromptGenerationResult(
            final_prompt="Compiled implementation prompt for JWT login.",
            template_name="Build Template",
            task_type="build",
        )
        mock_generator = PromptGenerator()
        mock_generator.generate_async = AsyncMock(return_value=mock_gen_result.final_prompt)
        mock_generator.create_context = PromptGenerator().create_context

        mock_critic = PromptCritic()
        mock_critic.validate_async = AsyncMock(
            return_value=ValidationResult(overall_valid=True, quality_score=1.0, issues=[])
        )

        from app.engine.refiner import RefinementResult

        mock_refiner = get_prompt_refiner()
        mock_refiner.run_loop_async = AsyncMock(
            return_value=RefinementResult(
                final_prompt=mock_gen_result.final_prompt,
                validation_result=ValidationResult(overall_valid=True, quality_score=1.0, issues=[]),
                refinement_attempts=0,
                task_type="build",
                template_name="Build Template",
                converged=True,
                history=[],
            )
        )

        app.dependency_overrides[get_requirement_engine] = lambda: mock_req_engine
        app.dependency_overrides[get_prompt_generator] = lambda: mock_generator
        app.dependency_overrides[get_prompt_critic] = lambda: mock_critic
        app.dependency_overrides[get_prompt_refiner] = lambda: mock_refiner

        # Execute compilation with project_id
        resp = self.client.post(
            "/api/compile",
            json={
                "input": "Add user login using OAuth2 and use Redis for caching.",
                "project_id": self.project_id,
            },
        )
        self.assertEqual(resp.status_code, 200)

        # Verify ZERO automatic candidate memories were created
        candidates = self.service.list_candidates(self.project_id)
        self.assertEqual(
            len(candidates),
            0,
            f"Expected 0 candidate memories from compile, got {len(candidates)}",
        )

        # Verify ZERO automatic ProjectMemories were created (count remains 1)
        memories = self.service.list_memories(self.project_id)
        self.assertEqual(
            len(memories),
            1,
            f"Expected 1 project memory (unchanged), got {len(memories)}",
        )
