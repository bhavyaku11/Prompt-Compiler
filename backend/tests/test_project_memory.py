"""Tests for Long-term Project Memory and Context Foundation."""

import os
import tempfile
import time
import unittest
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.api.projects import get_project_service
from app.database.models import ProjectMemoryRecord, ProjectRecord
from app.database.repositories import ProjectMemoryRepository, ProjectRepository
from app.database.session import init_db, reset_db_engine
from app.engine.project_memory import (
    InvalidProjectMemoryError,
    MemoryNotFoundError,
    ProjectMemoryService,
    ProjectNotFoundError,
)
from app.main import app
from app.schemas.project import (
    CATEGORY_PRIORITY,
    SOURCE_TRUST_PRIORITY,
    MemoryCategory,
    MemorySource,
    MemoryStatus,
    Project,
    ProjectContext,
    ProjectCreate,
    ProjectMemory,
    ProjectMemoryCreate,
    ProjectMemoryUpdate,
    ProjectUpdate,
)


class TestProjectMemoryFoundation(unittest.TestCase):
    """Test suite for Project Memory domain models, persistence, repository, and service."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_project_memory.db")
        self.db_url = f"sqlite:///{self.db_path}"
        reset_db_engine()
        self.engine = init_db(self.db_url)
        self.project_repo = ProjectRepository(database_url=self.db_url)
        self.memory_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=self.project_repo)
        self.service = ProjectMemoryService(
            project_repository=self.project_repo,
            memory_repository=self.memory_repo,
        )

    def tearDown(self):
        reset_db_engine()
        self.temp_dir.cleanup()

    def test_01_database_tables_created(self):
        """TEST 1: Verify projects and project_memories tables exist in SQLite."""
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        self.assertIn("projects", tables)
        self.assertIn("project_memories", tables)
        self.assertIn("interview_sessions", tables)
        self.assertIn("requirement_analyses", tables)
        self.assertIn("compilations", tables)

    def test_02_project_creation(self):
        """TEST 2: Project creation persists name, description, and timestamps."""
        project = self.service.create_project(
            name="Smart Home Dashboard",
            description="IoT dashboard application for connected devices.",
        )
        self.assertIsNotNone(project.project_id)
        self.assertEqual(project.name, "Smart Home Dashboard")
        self.assertEqual(project.description, "IoT dashboard application for connected devices.")
        self.assertGreater(project.created_at, 0)
        self.assertGreater(project.updated_at, 0)

    def test_03_project_retrieval(self):
        """TEST 3: Project can be retrieved by ID and by name."""
        created = self.service.create_project(name="Alpha Project", description="Test project")
        fetched_by_id = self.service.get_project(created.project_id)
        self.assertIsNotNone(fetched_by_id)
        self.assertEqual(fetched_by_id.project_id, created.project_id)
        self.assertEqual(fetched_by_id.name, "Alpha Project")

        fetched_by_name = self.service.get_project_by_name("Alpha Project")
        self.assertIsNotNone(fetched_by_name)
        self.assertEqual(fetched_by_name.project_id, created.project_id)

    def test_04_project_update(self):
        """TEST 4: Project name and description can be updated."""
        project = self.service.create_project(name="Old Name", description="Old Desc")
        time.sleep(0.01)
        updated = self.service.update_project(
            project_id=project.project_id,
            name="New Name",
            description="Updated description",
        )
        self.assertEqual(updated.name, "New Name")
        self.assertEqual(updated.description, "Updated description")
        self.assertGreaterEqual(updated.updated_at, project.created_at)

        # Retrieve fresh
        fresh = self.service.get_project(project.project_id)
        self.assertEqual(fresh.name, "New Name")

    def test_05_memory_creation_and_retrieval(self):
        """TEST 5: Memory item is created with category, source, confidence, status, metadata."""
        project = self.service.create_project(name="Memory Test")
        mem = self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.TECHNOLOGY,
            content="Backend built with FastAPI and PostgreSQL",
            source=MemorySource.USER_CONFIRMED,
            confidence=1.0,
            status=MemoryStatus.ACTIVE,
            metadata={"framework_version": "0.115.0"},
        )
        self.assertIsNotNone(mem.memory_id)
        self.assertEqual(mem.project_id, project.project_id)
        self.assertEqual(mem.category, "technology")
        self.assertEqual(mem.content, "Backend built with FastAPI and PostgreSQL")
        self.assertEqual(mem.source, "user_confirmed")
        self.assertEqual(mem.confidence, 1.0)
        self.assertEqual(mem.status, "active")
        self.assertEqual(mem.metadata, {"framework_version": "0.115.0"})

        # Retrieve by ID
        fetched = self.service.get_memory(mem.memory_id)
        self.assertEqual(fetched.memory_id, mem.memory_id)
        self.assertEqual(fetched.content, mem.content)

    def test_06_multiple_memories_belonging_to_one_project(self):
        """TEST 6: Multiple memories can be stored and listed for a single project."""
        project = self.service.create_project(name="Multi Memory Project")
        m1 = self.service.add_memory(
            project_id=project.project_id,
            category="frontend",
            content="React 18 with TypeScript",
        )
        m2 = self.service.add_memory(
            project_id=project.project_id,
            category="backend",
            content="Python 3.12 with FastAPI",
        )
        m3 = self.service.add_memory(
            project_id=project.project_id,
            category="database",
            content="PostgreSQL with SQLAlchemy 2.x",
        )

        memories = self.service.list_memories(project.project_id)
        self.assertEqual(len(memories), 3)
        contents = [m.content for m in memories]
        self.assertIn(m1.content, contents)
        self.assertIn(m2.content, contents)
        self.assertIn(m3.content, contents)

    def test_07_deterministic_project_context_retrieval(self):
        """TEST 7: Project context returns items in strictly deterministic order."""
        project = self.service.create_project(name="Deterministic Context Project")

        # Insert items in arbitrary order across multiple categories and trust levels
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.PREFERENCE,
            content="Prefer Tailwind for styling",
            source=MemorySource.USER_CONFIRMED,
        )
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.CONSTRAINT,
            content="Never modify existing public API routes",
            source=MemorySource.USER_CONFIRMED,
        )
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.ARCHITECTURE,
            content="Clean Hexagonal Architecture",
            source=MemorySource.USER_CONFIRMED,
        )
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.TECHNOLOGY,
            content="FastAPI backend",
            source=MemorySource.USER_CONFIRMED,
        )
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.CODING_RULE,
            content="Strict type annotations on all functions",
            source=MemorySource.USER_CONFIRMED,
        )
        self.service.add_memory(
            project_id=project.project_id,
            category=MemoryCategory.TECHNOLOGY,
            content="Redis caching layer",
            source=MemorySource.GENERATED_ASSUMPTION,  # Lower trust priority than USER_CONFIRMED
        )

        # Retrieve context multiple times and ensure identical ordering
        ctx1 = self.service.get_project_context(project.project_id)
        ctx2 = self.service.get_project_context(project.project_id)

        self.assertEqual(len(ctx1.memories), 6)
        self.assertEqual(len(ctx2.memories), 6)
        self.assertEqual([m.memory_id for m in ctx1.memories], [m.memory_id for m in ctx2.memories])

        # Architecture should precede Technology, which precedes Constraint, which precedes Coding Rule, which precedes Preference
        categories_in_order = [m.category for m in ctx1.memories]
        self.assertEqual(categories_in_order[0], "architecture")
        self.assertEqual(categories_in_order[1], "technology")
        self.assertEqual(categories_in_order[2], "technology")
        self.assertEqual(categories_in_order[3], "constraint")
        self.assertEqual(categories_in_order[4], "coding_rule")
        self.assertEqual(categories_in_order[5], "preference")

        # Within 'technology', USER_CONFIRMED ("FastAPI backend") must precede GENERATED_ASSUMPTION ("Redis caching layer")
        tech_memories = ctx1.categorized_memories["technology"]
        self.assertEqual(tech_memories[0].content, "FastAPI backend")
        self.assertEqual(tech_memories[0].source, "user_confirmed")
        self.assertEqual(tech_memories[1].content, "Redis caching layer")
        self.assertEqual(tech_memories[1].source, "generated_assumption")

        # Check flattened summaries
        self.assertIn("Never modify existing public API routes", ctx1.active_constraints)
        self.assertIn("FastAPI backend", ctx1.technologies)
        self.assertIn("Redis caching layer", ctx1.technologies)
        self.assertIn("Strict type annotations on all functions", ctx1.coding_rules)

    def test_08_memory_source_and_status_preservation(self):
        """TEST 8: Memory source attribution and status (active, deprecated, superseded) are preserved."""
        project = self.service.create_project(name="Source Status Test")

        m_active = self.service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Active Tech: PostgreSQL",
            source=MemorySource.USER_CONFIRMED,
            status=MemoryStatus.ACTIVE,
        )
        m_deprecated = self.service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Old Tech: MongoDB",
            source=MemorySource.SYSTEM_DEFINED,
            status=MemoryStatus.DEPRECATED,
        )
        m_assumption = self.service.add_memory(
            project_id=project.project_id,
            category="architecture",
            content="Assumed: Monolith",
            source=MemorySource.GENERATED_ASSUMPTION,
            status=MemoryStatus.ACTIVE,
        )

        # Context defaults to active only
        ctx = self.service.get_project_context(project.project_id)
        active_ids = [m.memory_id for m in ctx.memories]
        self.assertIn(m_active.memory_id, active_ids)
        self.assertIn(m_assumption.memory_id, active_ids)
        self.assertNotIn(m_deprecated.memory_id, active_ids)

        # Querying with status_filter=None includes deprecated
        all_ctx = self.service.get_project_context(project.project_id, status_filter=None)
        all_ids = [m.memory_id for m in all_ctx.memories]
        self.assertIn(m_deprecated.memory_id, all_ids)

    def test_09_persistence_after_database_session_recreation(self):
        """TEST 9: Project and memories survive engine reset and repository recreation."""
        project = self.service.create_project(
            name="Persistent Project",
            description="Testing survival after engine reset",
        )
        mem = self.service.add_memory(
            project_id=project.project_id,
            category="coding_rule",
            content="Use snake_case for all Python variables",
            source="user_confirmed",
        )

        saved_pid = project.project_id
        saved_mid = mem.memory_id

        # Simulate backend restart: purge in-memory references and reset engine
        reset_db_engine()
        del self.service
        del self.project_repo
        del self.memory_repo
        time.sleep(0.1)

        # Reinstantiate against same SQLite file
        fresh_engine = init_db(self.db_url)
        fresh_p_repo = ProjectRepository(database_url=self.db_url)
        fresh_m_repo = ProjectMemoryRepository(database_url=self.db_url, project_repository=fresh_p_repo)
        fresh_service = ProjectMemoryService(project_repository=fresh_p_repo, memory_repository=fresh_m_repo)

        restored_project = fresh_service.get_project(saved_pid)
        self.assertIsNotNone(restored_project)
        self.assertEqual(restored_project.name, "Persistent Project")

        restored_mem = fresh_service.get_memory(saved_mid)
        self.assertIsNotNone(restored_mem)
        self.assertEqual(restored_mem.content, "Use snake_case for all Python variables")

        restored_ctx = fresh_service.get_project_context(saved_pid)
        self.assertEqual(len(restored_ctx.memories), 1)
        self.assertIn("Use snake_case for all Python variables", restored_ctx.coding_rules)

    def test_10_isolation_between_two_different_projects(self):
        """TEST 10: Memories from Project A never leak into Project B."""
        proj_a = self.service.create_project(name="Project A")
        proj_b = self.service.create_project(name="Project B")

        self.service.add_memory(
            project_id=proj_a.project_id,
            category="technology",
            content="Django framework",
        )
        self.service.add_memory(
            project_id=proj_b.project_id,
            category="technology",
            content="Express.js framework",
        )

        ctx_a = self.service.get_project_context(proj_a.project_id)
        ctx_b = self.service.get_project_context(proj_b.project_id)

        self.assertEqual(len(ctx_a.memories), 1)
        self.assertEqual(ctx_a.memories[0].content, "Django framework")

        self.assertEqual(len(ctx_b.memories), 1)
        self.assertEqual(ctx_b.memories[0].content, "Express.js framework")

    def test_11_invalid_project_references_handled_correctly(self):
        """TEST 11: Accessing or adding memory to nonexistent project raises ProjectNotFoundError."""
        fake_id = str(uuid.uuid4())
        with self.assertRaises(ProjectNotFoundError):
            self.service.get_project(fake_id)

        with self.assertRaises(ProjectNotFoundError):
            self.service.add_memory(
                project_id=fake_id,
                category="technology",
                content="Some tech",
            )

        with self.assertRaises(ProjectNotFoundError):
            self.service.get_project_context(fake_id)

        with self.assertRaises(MemoryNotFoundError):
            self.service.get_memory(str(uuid.uuid4()))

    def test_12_memory_update_and_delete(self):
        """TEST 12: Memory item can be updated and deleted."""
        project = self.service.create_project(name="CRUD Memory Project")
        mem = self.service.add_memory(
            project_id=project.project_id,
            category="preference",
            content="Light mode preferred",
        )
        # Update
        updated = self.service.update_memory(
            memory_id=mem.memory_id,
            content="Dark mode preferred",
            status=MemoryStatus.ACTIVE,
        )
        self.assertEqual(updated.content, "Dark mode preferred")

        # Delete
        deleted = self.service.delete_memory(mem.memory_id)
        self.assertTrue(deleted)

        with self.assertRaises(MemoryNotFoundError):
            self.service.get_memory(mem.memory_id)

    def test_13_project_deletion_cleans_up_memories(self):
        """TEST 13: Deleting a project cascades and removes associated memories."""
        project = self.service.create_project(name="Cascade Delete Project")
        mem = self.service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Rust backend",
        )
        deleted = self.service.delete_project(project.project_id)
        self.assertTrue(deleted)

        with self.assertRaises(ProjectNotFoundError):
            self.service.get_project(project.project_id)

        with self.assertRaises(MemoryNotFoundError):
            self.service.get_memory(mem.memory_id)

    def test_14_schema_validation_checks(self):
        """TEST 14: Invalid categories, sources, or empty names/content raise validation errors."""
        with self.assertRaises(ValueError):
            ProjectCreate(name="   ")

        with self.assertRaises(ValueError):
            ProjectMemoryCreate(
                category="invalid_category_xyz",
                content="Valid content",
            )

        with self.assertRaises(ValueError):
            ProjectMemoryCreate(
                category="technology",
                content="   ",
            )

        with self.assertRaises(ValueError):
            ProjectMemoryCreate(
                category="technology",
                content="Valid content",
                source="unsupported_source",
            )

        with self.assertRaises(ValueError):
            ProjectMemoryCreate(
                category="technology",
                content="Valid content",
                confidence=1.5,  # Out of range 0.0 - 1.0
            )

    def test_15_context_string_formatting(self):
        """TEST 15: ProjectContext.to_context_string() produces expected structured markdown."""
        project = self.service.create_project(
            name="E-Commerce Platform",
            description="Online store for gadgets",
        )
        self.service.add_memory(
            project_id=project.project_id,
            category="technology",
            content="Next.js 14",
            source="user_confirmed",
        )
        self.service.add_memory(
            project_id=project.project_id,
            category="constraint",
            content="Zero client-side analytics trackers",
            source="user_confirmed",
        )
        self.service.add_memory(
            project_id=project.project_id,
            category="database",
            content="Supabase PostgreSQL",
            source="generated_assumption",
        )

        ctx = self.service.get_project_context(project.project_id)
        summary = ctx.to_context_string()

        self.assertIn("PROJECT: E-Commerce Platform", summary)
        self.assertIn("DESCRIPTION: Online store for gadgets", summary)
        self.assertIn("TECHNOLOGIES:\n- Next.js 14", summary)
        self.assertIn("CONSTRAINTS:\n- Zero client-side analytics trackers", summary)
        self.assertIn("DATABASE:\n- Supabase PostgreSQL (assumption)", summary)

    def test_16_fastapi_endpoints_integration(self):
        """TEST 16: Minimal API endpoints work through FastAPI TestClient."""
        from app.auth import get_current_user
        from app.database.models import UserRecord

        test_user = UserRecord(id=1, clerk_user_id="user_test_proj_mem")
        app.dependency_overrides[get_current_user] = lambda: test_user
        try:
            client = TestClient(app)

            # 1. Create project
            resp = client.post("/api/projects", json={"name": "API Test Project", "description": "Created via HTTP"})
            self.assertEqual(resp.status_code, 201)
            proj_data = resp.json()
            pid = proj_data["project_id"]
            self.assertEqual(proj_data["name"], "API Test Project")

            # 2. Get project
            get_resp = client.get(f"/api/projects/{pid}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["name"], "API Test Project")

            # 3. Add memory
            mem_resp = client.post(
                f"/api/projects/{pid}/memories",
                json={
                    "category": "technology",
                    "content": "Vue.js with Pinia",
                    "source": "user_confirmed",
                },
            )
            self.assertEqual(mem_resp.status_code, 201)
            mem_data = mem_resp.json()
            self.assertEqual(mem_data["content"], "Vue.js with Pinia")

            # 4. Get project context
            ctx_resp = client.get(f"/api/projects/{pid}/context")
            self.assertEqual(ctx_resp.status_code, 200)
            ctx_data = ctx_resp.json()
            self.assertEqual(ctx_data["project"]["project_id"], pid)
            self.assertEqual(len(ctx_data["memories"]), 1)
            self.assertEqual(ctx_data["technologies"], ["Vue.js with Pinia"])

            # 5. Nonexistent project returns 404
            nonexistent = str(uuid.uuid4())
            bad_resp = client.get(f"/api/projects/{nonexistent}")
            self.assertEqual(bad_resp.status_code, 404)
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
