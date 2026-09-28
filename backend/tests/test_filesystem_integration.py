"""Deterministic tests for Task 32: Native macOS Filesystem & Project Folder Integration.

Verifies:
- Project creation with root_path persistence
- Project update (PATCH) of root_path
- Cross-user isolation on root_path modification and ingestion
- Authoritative backend path safety (traversal, non-existent path, symlinks)
- Directory ingestion integration using project.root_path
- Excluded directories (.git, node_modules, __pycache__) filtering
- Unauthenticated rejection and missing root_path handling
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai.embeddings import MockEmbeddingProvider
from app.api.knowledge import (
    get_document_ingestion_service,
    get_embedding_provider,
    get_knowledge_indexer,
    get_knowledge_repository,
    get_project_repository,
)
from app.api.projects import get_project_service
from app.auth import get_current_user, get_user_repository, require_authenticated_user
from app.config import Settings, settings
from app.database.models import UserRecord
from app.database.repositories import KnowledgeRepository, ProjectRepository, UserRepository
from app.database.session import get_session_factory, init_db, reset_db_engine
from app.engine.document_ingestion import DocumentIngestionService
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.project_memory import ProjectMemoryService
from app.main import app
from app.schemas.auth import AuthenticatedUser


class TestFilesystemIntegration(unittest.TestCase):
    """Integration and security test suite for project folder filesystem integration."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_fs.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.settings_patcher = patch.object(Settings, "DATABASE_URL", self.db_url)
        self.settings_patcher.start()

        reset_db_engine()
        init_db(self.db_url)

        self.session_factory = get_session_factory(self.db_url)
        self.user_repo = UserRepository(session_factory=self.session_factory)
        self.project_repo = ProjectRepository(session_factory=self.session_factory)
        self.knowledge_repo = KnowledgeRepository(session_factory=self.session_factory)

        self.mock_embedding = MockEmbeddingProvider(dimension=settings.EMBEDDING_DIMENSION)
        self.indexer_service = KnowledgeIndexerService(
            knowledge_repository=self.knowledge_repo,
            project_repository=self.project_repo,
            embedding_provider=self.mock_embedding,
        )
        self.ingestion_service = DocumentIngestionService(
            indexer_service=self.indexer_service,
            project_repository=self.project_repo,
        )
        self.project_service = ProjectMemoryService(database_url=self.db_url)

        # Provision two distinct test users
        self.user_a = self.user_repo.get_or_create("clerk_user_A")
        self.user_b = self.user_repo.get_or_create("clerk_user_B")

        # Set up dependency overrides
        app.dependency_overrides[get_user_repository] = lambda: self.user_repo
        app.dependency_overrides[get_project_repository] = lambda: self.project_repo
        app.dependency_overrides[get_knowledge_repository] = lambda: self.knowledge_repo
        app.dependency_overrides[get_embedding_provider] = lambda: self.mock_embedding
        app.dependency_overrides[get_knowledge_indexer] = lambda: self.indexer_service
        app.dependency_overrides[get_document_ingestion_service] = lambda: self.ingestion_service
        app.dependency_overrides[get_project_service] = lambda: self.project_service

        self.set_active_user(self.user_a)
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
    # A. PROJECT CREATION & PERSISTENCE
    # =========================================================================

    def test_create_project_with_root_path(self):
        """Project created with root_path correctly saves and returns it."""
        folder = Path(self.temp_dir.name) / "my_project"
        folder.mkdir()

        res = self.client.post(
            "/api/projects",
            json={
                "name": "Local Desktop App",
                "description": "App connected to local macOS directory",
                "root_path": str(folder),
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["root_path"], str(folder))
        self.assertEqual(data["name"], "Local Desktop App")

        # Verify persistence via GET
        get_res = self.client.get(f"/api/projects/{data['project_id']}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["root_path"], str(folder))

    def test_update_project_root_path(self):
        """Existing project can update root_path via PATCH."""
        folder1 = Path(self.temp_dir.name) / "folder1"
        folder1.mkdir()
        folder2 = Path(self.temp_dir.name) / "folder2"
        folder2.mkdir()

        create_res = self.client.post(
            "/api/projects",
            json={"name": "Initial Project", "root_path": str(folder1)},
        )
        project_id = create_res.json()["project_id"]
        self.assertEqual(create_res.json()["root_path"], str(folder1))

        # Update root_path to folder2
        patch_res = self.client.patch(
            f"/api/projects/{project_id}",
            json={"root_path": str(folder2)},
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["root_path"], str(folder2))

        # Verify via GET
        get_res = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(get_res.json()["root_path"], str(folder2))

    def test_update_project_clear_root_path(self):
        """Existing project can unlink root_path by setting it to None."""
        folder = Path(self.temp_dir.name) / "linked_folder"
        folder.mkdir()

        create_res = self.client.post(
            "/api/projects",
            json={"name": "Unlink Test", "root_path": str(folder)},
        )
        project_id = create_res.json()["project_id"]

        patch_res = self.client.patch(
            f"/api/projects/{project_id}",
            json={"root_path": ""},
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertIsNone(patch_res.json()["root_path"])

    # =========================================================================
    # B. OWNERSHIP & CROSS-USER ISOLATION
    # =========================================================================

    def test_cross_user_cannot_update_project_root_path(self):
        """User B cannot alter or associate folder to User A's project."""
        folder = Path(self.temp_dir.name) / "user_a_folder"
        folder.mkdir()

        self.set_active_user(self.user_a)
        create_res = self.client.post(
            "/api/projects",
            json={"name": "User A Private Project", "root_path": str(folder)},
        )
        project_id = create_res.json()["project_id"]

        # Switch to User B
        self.set_active_user(self.user_b)
        patch_res = self.client.patch(
            f"/api/projects/{project_id}",
            json={"root_path": "/malicious/path"},
        )
        self.assertEqual(patch_res.status_code, 404)

        # Verify User A's project path was not modified
        self.set_active_user(self.user_a)
        get_res = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(get_res.json()["root_path"], str(folder))

    def test_cross_user_cannot_ingest_project_directory(self):
        """User B cannot trigger directory ingestion on User A's project."""
        folder = Path(self.temp_dir.name) / "user_a_ingest"
        folder.mkdir()
        (folder / "README.md").write_text("# Secret Docs", encoding="utf-8")

        self.set_active_user(self.user_a)
        create_res = self.client.post(
            "/api/projects",
            json={"name": "User A Docs", "root_path": str(folder)},
        )
        project_id = create_res.json()["project_id"]

        # User B attempts ingestion
        self.set_active_user(self.user_b)
        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={},
        )
        self.assertEqual(ingest_res.status_code, 404)

    # =========================================================================
    # C. DIRECTORY INGESTION INTEGRATION
    # =========================================================================

    def test_directory_ingestion_with_configured_root_path(self):
        """Directory ingestion automatically uses project.root_path when omitted from request."""
        folder = Path(self.temp_dir.name) / "codebase"
        folder.mkdir()
        (folder / "README.md").write_text("# Overview\nSystem architecture overview.", encoding="utf-8")
        (folder / "main.py").write_text("def run():\n    print('running')", encoding="utf-8")
        (folder / "config.json").write_text('{"env": "production"}', encoding="utf-8")

        self.set_active_user(self.user_a)
        proj_res = self.client.post(
            "/api/projects",
            json={"name": "Full Ingestion Project", "root_path": str(folder)},
        )
        project_id = proj_res.json()["project_id"]

        # Trigger directory ingestion with empty body
        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={},
        )
        self.assertEqual(ingest_res.status_code, 200)
        data = ingest_res.json()
        self.assertEqual(data["project_id"], project_id)
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["indexed"], 3)
        self.assertEqual(data["failed"], 0)

        # Check sources indexed
        sources_res = self.client.get(f"/api/projects/{project_id}/knowledge/sources")
        self.assertEqual(sources_res.status_code, 200)
        source_names = {s["source_name"] for s in sources_res.json()}
        self.assertEqual(source_names, {"README.md", "main.py", "config.json"})

    def test_directory_ingestion_excludes_ignored_directories(self):
        """Directory ingestion ignores .git, node_modules, and __pycache__ within project folder."""
        folder = Path(self.temp_dir.name) / "repo_with_exclusions"
        folder.mkdir()
        (folder / "guide.md").write_text("# Guide", encoding="utf-8")

        git_dir = folder / ".git"
        git_dir.mkdir()
        (git_dir / "config.txt").write_text("git internal", encoding="utf-8")

        nm_dir = folder / "node_modules" / "pkg"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.js").write_text("console.log()", encoding="utf-8")

        pycache_dir = folder / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "cache.py").write_text("# pycache", encoding="utf-8")

        self.set_active_user(self.user_a)
        proj_res = self.client.post(
            "/api/projects",
            json={"name": "Exclusion Project", "root_path": str(folder)},
        )
        project_id = proj_res.json()["project_id"]

        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={"recursive": True},
        )
        self.assertEqual(ingest_res.status_code, 200)
        data = ingest_res.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["indexed"], 1)
        self.assertEqual(data["results"][0]["relative_path"], "guide.md")

    def test_directory_ingestion_missing_root_path_error(self):
        """Calling directory ingestion without project.root_path or override returns 422."""
        self.set_active_user(self.user_a)
        proj_res = self.client.post(
            "/api/projects",
            json={"name": "No Root Project"},
        )
        project_id = proj_res.json()["project_id"]

        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={},
        )
        self.assertEqual(ingest_res.status_code, 422)
        self.assertIn("has no root_path configured", ingest_res.json()["detail"])

    # =========================================================================
    # D. SECURITY & AUTHORITATIVE VALIDATION
    # =========================================================================

    def test_directory_ingestion_path_traversal_rejected(self):
        """Sub-directory path traversal outside project root is rejected."""
        folder = Path(self.temp_dir.name) / "safe_project"
        folder.mkdir()

        self.set_active_user(self.user_a)
        proj_res = self.client.post(
            "/api/projects",
            json={"name": "Traversal Test", "root_path": str(folder)},
        )
        project_id = proj_res.json()["project_id"]

        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={"directory_path": "../../../etc"},
        )
        self.assertEqual(ingest_res.status_code, 400)
        self.assertIn("escapes allowed project root", ingest_res.json()["detail"])

    def test_directory_ingestion_symlink_outside_root_rejected(self):
        """Symlink inside project folder targeting an external file is rejected."""
        proj_folder = Path(self.temp_dir.name) / "project_with_symlink"
        proj_folder.mkdir()

        external_folder = Path(self.temp_dir.name) / "outside_dir"
        external_folder.mkdir()
        secret_file = external_folder / "secret.md"
        secret_file.write_text("# Top Secret Outside Data", encoding="utf-8")

        # Create symlink inside project pointing outside
        symlink_path = proj_folder / "link_to_secret.md"
        symlink_path.symlink_to(secret_file)

        self.set_active_user(self.user_a)
        proj_res = self.client.post(
            "/api/projects",
            json={"name": "Symlink Test", "root_path": str(proj_folder)},
        )
        project_id = proj_res.json()["project_id"]

        ingest_res = self.client.post(
            f"/api/projects/{project_id}/knowledge/ingest/directory",
            json={},
        )
        self.assertEqual(ingest_res.status_code, 200)
        data = ingest_res.json()
        # The symlinked file resolving outside root must fail ingestion
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["indexed"], 0)
        self.assertIn("PATH_OUTSIDE_PROJECT", data["results"][0]["error"])

    def test_unauthenticated_requests_rejected(self):
        """Unauthenticated requests to project and ingestion endpoints return 401."""
        self.set_active_user(None)
        res_post = self.client.post("/api/projects", json={"name": "Anon"})
        self.assertEqual(res_post.status_code, 401)

        res_ingest = self.client.post("/api/projects/some_id/knowledge/ingest/directory", json={})
        self.assertEqual(res_ingest.status_code, 401)
