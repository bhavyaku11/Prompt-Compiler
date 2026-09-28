"""Comprehensive unit and API integration tests for document ingestion and file parsing foundation (Task 22)."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from app.ai.embeddings import MockEmbeddingProvider
from app.api.knowledge import (
    get_embedding_provider as get_api_embedding_provider,
    get_knowledge_repository,
    get_project_repository,
)
from app.config import settings
from app.database.repositories import KnowledgeRepository, ProjectRepository
from app.database.session import init_db, reset_db_engine
from app.engine.document_ingestion import (
    DEFAULT_EXCLUDED_DIRECTORIES,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DocumentIngestionError,
    DocumentIngestionService,
    PathSecurityError,
    ProjectRootNotConfiguredError,
    SUPPORTED_EXTENSIONS,
    discover_supported_files,
    read_and_normalize_content,
    resolve_project_root,
    validate_path_safety,
)
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_search import KnowledgeSearchService
from app.main import app
from app.schemas.knowledge import IngestionStatus
from app.schemas.project import ProjectCreate


class TestDocumentDiscoveryAndParsingUnits(unittest.TestCase):
    """Unit tests for path validation, discovery, and file content parsing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Supported extension detection
    def test_supported_extensions(self):
        expected = {".md", ".txt", ".py", ".ts", ".json"}
        self.assertEqual(set(SUPPORTED_EXTENSIONS.keys()), expected)
        self.assertEqual(SUPPORTED_EXTENSIONS[".md"], "documentation")
        self.assertEqual(SUPPORTED_EXTENSIONS[".txt"], "text")
        self.assertEqual(SUPPORTED_EXTENSIONS[".py"], "code")
        self.assertEqual(SUPPORTED_EXTENSIONS[".ts"], "code")
        self.assertEqual(SUPPORTED_EXTENSIONS[".json"], "code")

    # 2. Unsupported extension rejection
    def test_unsupported_extensions_rejected(self):
        unsupported_files = ["doc.pdf", "image.png", "archive.zip", "data.docx", "binary.exe"]
        for fname in unsupported_files:
            p = self.root_path / fname
            p.write_bytes(b"content")
            with self.assertRaises(ValueError) as ctx:
                read_and_normalize_content(p)
            self.assertIn("UNSUPPORTED_FILE_TYPE", str(ctx.exception))

    # 3. Deterministic file discovery & sorting
    def test_deterministic_file_discovery_sorting(self):
        # Create files in arbitrary order
        (self.root_path / "z_last.md").write_text("# Z", encoding="utf-8")
        (self.root_path / "a_first.py").write_text("print('a')", encoding="utf-8")
        (self.root_path / "m_middle.json").write_text('{"m": 1}', encoding="utf-8")

        discovered = discover_supported_files(self.root_path, self.root_path, recursive=False)
        names = [p.name for p in discovered]
        self.assertEqual(names, ["a_first.py", "m_middle.json", "z_last.md"])

    # 4. Recursive directory discovery
    def test_recursive_directory_discovery(self):
        sub_dir = self.root_path / "src" / "utils"
        sub_dir.mkdir(parents=True)
        (sub_dir / "helper.ts").write_text("export const x = 1;", encoding="utf-8")
        (self.root_path / "README.md").write_text("# Main", encoding="utf-8")

        discovered = discover_supported_files(self.root_path, self.root_path, recursive=True)
        rel_paths = [str(p.relative_to(self.root_path)) for p in discovered]
        self.assertEqual(rel_paths, ["README.md", "src/utils/helper.ts"])

    # 5. Default excluded directories
    def test_default_excluded_directories(self):
        # Create git and node_modules folders
        git_dir = self.root_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.txt").write_text("git config", encoding="utf-8")

        nm_dir = self.root_path / "node_modules" / "pkg"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.ts").write_text("export const nm = true;", encoding="utf-8")

        pycache_dir = self.root_path / "__pycache__"
        pycache_dir.mkdir()
        (pycache_dir / "test.py").write_text("cache", encoding="utf-8")

        valid_file = self.root_path / "valid.py"
        valid_file.write_text("x = 1", encoding="utf-8")

        discovered = discover_supported_files(self.root_path, self.root_path, recursive=True)
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].name, "valid.py")

    # 6. UTF-8 reading
    def test_utf8_reading(self):
        f = self.root_path / "unicode.txt"
        f.write_text("Testing UTF-8 characters: ñ, ü, 🚀, 日本語", encoding="utf-8")
        content, source_type, meta = read_and_normalize_content(f)
        self.assertIn("🚀", content)
        self.assertIn("日本語", content)
        self.assertEqual(source_type, "text")

    # 7. UTF-8 BOM handling
    def test_utf8_bom_handling(self):
        f = self.root_path / "bom.txt"
        bom_bytes = b"\xef\xbb\xbfHello with BOM"
        f.write_bytes(bom_bytes)
        content, _, _ = read_and_normalize_content(f)
        self.assertEqual(content, "Hello with BOM")
        self.assertFalse(content.startswith("\ufeff"))

    # 8. Newline normalization
    def test_newline_normalization(self):
        f = self.root_path / "crlf.md"
        f.write_bytes(b"# Header\r\nLine 1\rLine 2\r\nLine 3\n")
        content, _, _ = read_and_normalize_content(f)
        self.assertEqual(content, "# Header\nLine 1\nLine 2\nLine 3\n")

    # 9. Markdown preservation
    def test_markdown_preservation(self):
        f = self.root_path / "doc.md"
        md_text = (
            "# Architecture\n\n"
            "## Database\n"
            "- SQLite with WAL\n"
            "- Vector extension\n\n"
            "```python\n"
            "def query():\n"
            "    pass\n"
            "```\n\n"
            "Refer to [link](http://localhost)."
        )
        f.write_text(md_text, encoding="utf-8")
        content, source_type, _ = read_and_normalize_content(f)
        self.assertEqual(content, md_text)
        self.assertEqual(source_type, "documentation")

    # 10. Python source ingestion
    def test_python_source_ingestion(self):
        f = self.root_path / "service.py"
        py_code = (
            '"""Module docstring."""\n'
            "import os\n\n"
            "class DataService:\n"
            "    def fetch(self) -> int:\n"
            "        # Return constant\n"
            "        return 42\n"
        )
        f.write_text(py_code, encoding="utf-8")
        content, source_type, meta = read_and_normalize_content(f)
        self.assertEqual(content, py_code)
        self.assertEqual(source_type, "code")
        self.assertEqual(meta["extension"], ".py")

    # 11. TypeScript source ingestion
    def test_typescript_source_ingestion(self):
        f = self.root_path / "types.ts"
        ts_code = (
            "export interface User {\n"
            "  id: string;\n"
            "  name: string;\n"
            "}\n\n"
            "export function formatUser(u: User): string {\n"
            "  return u.name;\n"
            "}\n"
        )
        f.write_text(ts_code, encoding="utf-8")
        content, source_type, meta = read_and_normalize_content(f)
        self.assertEqual(content, ts_code)
        self.assertEqual(source_type, "code")
        self.assertEqual(meta["extension"], ".ts")

    # 12. Valid JSON ingestion & 13. Deterministic JSON normalization
    def test_valid_json_ingestion_and_normalization(self):
        f = self.root_path / "config.json"
        raw_json = '{\n  "zebra": 1,\n  "alpha": 2,\n  "nested": {"z": 9, "a": 8}\n}'
        f.write_text(raw_json, encoding="utf-8")
        content, source_type, meta = read_and_normalize_content(f)
        parsed = json.loads(content)
        self.assertEqual(parsed["zebra"], 1)
        self.assertEqual(parsed["alpha"], 2)
        # Check keys are sorted deterministically
        lines = content.splitlines()
        alpha_idx = next(i for i, l in enumerate(lines) if '"alpha"' in l)
        zebra_idx = next(i for i, l in enumerate(lines) if '"zebra"' in l)
        self.assertLess(alpha_idx, zebra_idx)
        self.assertEqual(source_type, "code")
        self.assertEqual(meta["subtype"], "configuration")

    # 14. Invalid JSON rejection
    def test_invalid_json_rejection(self):
        f = self.root_path / "invalid.json"
        f.write_text('{"broken": json without quotes', encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            read_and_normalize_content(f)
        self.assertIn("INVALID_JSON", str(ctx.exception))

    # 17. Path traversal rejection
    def test_path_traversal_rejection(self):
        with self.assertRaises(PathSecurityError):
            validate_path_safety("../outside.txt", self.root_path)

        with self.assertRaises(PathSecurityError):
            validate_path_safety("docs/../../outside.txt", self.root_path)

    # 18. Absolute path outside project root rejection
    def test_absolute_path_outside_project_root_rejection(self):
        with self.assertRaises(PathSecurityError):
            validate_path_safety("/tmp/private_key.pem", self.root_path)

    # 19. Symlink escape rejection
    def test_symlink_escape_rejection(self):
        outside_dir = tempfile.TemporaryDirectory()
        try:
            outside_file = Path(outside_dir.name) / "secret.txt"
            outside_file.write_text("confidential", encoding="utf-8")

            symlink_path = self.root_path / "leak_symlink.txt"
            try:
                os.symlink(outside_file, symlink_path)
            except OSError:
                # If OS prohibits symlink creation in environment, skip gracefully
                return

            with self.assertRaises(PathSecurityError):
                validate_path_safety("leak_symlink.txt", self.root_path)
        finally:
            outside_dir.cleanup()

    # 20. Maximum file-size enforcement
    def test_max_file_size_enforcement(self):
        f = self.root_path / "large.txt"
        f.write_text("A" * 200, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            read_and_normalize_content(f, max_file_size_bytes=100)
        self.assertIn("FILE_TOO_LARGE", str(ctx.exception))


class TestDocumentIngestionServiceIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for DocumentIngestionService with SQLite repository and indexer."""

    def setUp(self):
        self.temp_db_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_db_dir.name, "test_ingestion.db")
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

        self.ingestion_service = DocumentIngestionService(
            indexer_service=self.indexer,
            project_repository=self.project_repo,
            max_file_size_bytes=10000,
        )

        # Create project root directory
        self.project_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.project_dir.name).resolve()

        # Create project with root_path configured
        self.proj_a = self.project_repo.create(
            ProjectCreate(
                name="Project A",
                description="Test project for ingestion",
                root_path=str(self.root_path),
            )
        )

    def tearDown(self):
        self.temp_db_dir.cleanup()
        self.project_dir.cleanup()

    # 15. Missing file handling
    async def test_missing_file_handling(self):
        res = await self.ingestion_service.ingest_file_async(
            self.proj_a.project_id,
            "nonexistent.md",
        )
        self.assertEqual(res.status, IngestionStatus.FAILED.value)
        self.assertIn("FILE_NOT_FOUND", res.error)

    # 16. Directory path handling when file expected
    async def test_directory_path_handling(self):
        sub_dir = self.root_path / "sub_folder"
        sub_dir.mkdir()
        res = await self.ingestion_service.ingest_file_async(
            self.proj_a.project_id,
            "sub_folder",
        )
        self.assertEqual(res.status, IngestionStatus.FAILED.value)
        self.assertIn("EXPECTED_FILE", res.error)

    # 23. Source metadata is correct & 24. Relative paths stored correctly
    async def test_ingest_single_file_metadata_and_relative_path(self):
        docs_dir = self.root_path / "docs"
        docs_dir.mkdir()
        readme = docs_dir / "architecture.md"
        readme.write_text("# High Level Architecture\nUsing SQLite-vec.", encoding="utf-8")

        res = await self.ingestion_service.ingest_file_async(
            self.proj_a.project_id,
            "docs/architecture.md",
        )
        self.assertEqual(res.status, IngestionStatus.INDEXED.value)
        self.assertEqual(res.relative_path, "docs/architecture.md")
        self.assertEqual(res.source_type, "documentation")
        self.assertGreater(res.chunk_count, 0)
        self.assertIsNotNone(res.content_hash)
        self.assertIsNotNone(res.source_id)

        # Verify source in repository
        source = self.knowledge_repo.get_source(res.source_id)
        self.assertIsNotNone(source)
        self.assertEqual(source.source_name, "docs/architecture.md")
        self.assertEqual(source.metadata["relative_path"], "docs/architecture.md")
        self.assertEqual(source.metadata["extension"], ".md")

    # 21. One failed file does not abort batch ingestion & 22. Batch result counts correct
    async def test_batch_ingestion_with_mixed_outcomes(self):
        # 1 valid md
        (self.root_path / "guide.md").write_text("# Setup guide", encoding="utf-8")
        # 1 valid py
        (self.root_path / "app.py").write_text("def run(): pass", encoding="utf-8")
        # 1 invalid json
        (self.root_path / "bad.json").write_text("invalid json {", encoding="utf-8")
        # 1 unsupported file
        (self.root_path / "test.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        batch = await self.ingestion_service.ingest_directory_async(
            self.proj_a.project_id,
        )
        # Total discovered should be 3 (valid md, valid py, bad json - png not in discovered since ext is excluded)
        self.assertEqual(batch.total, 3)
        self.assertEqual(batch.indexed, 2)
        self.assertEqual(batch.failed, 1)
        self.assertEqual(batch.unchanged, 0)

        bad_res = next(r for r in batch.results if r.relative_path == "bad.json")
        self.assertEqual(bad_res.status, IngestionStatus.FAILED.value)
        self.assertIn("INVALID_JSON", bad_res.error)

    # 27. Duplicate/unchanged files do not create unnecessary records
    async def test_duplicate_unchanged_files(self):
        f = self.root_path / "notes.txt"
        f.write_text("Consistent notes content", encoding="utf-8")

        res1 = await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "notes.txt")
        self.assertEqual(res1.status, IngestionStatus.INDEXED.value)

        # Ingest again without changes
        res2 = await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "notes.txt")
        self.assertEqual(res2.status, IngestionStatus.UNCHANGED.value)
        self.assertEqual(res2.source_id, res1.source_id)

    # 28. Changed files are re-indexed
    async def test_changed_file_reindexing(self):
        f = self.root_path / "version.md"
        f.write_text("# Version 1", encoding="utf-8")
        res1 = await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "version.md")
        self.assertEqual(res1.status, IngestionStatus.INDEXED.value)

        # Modify file
        f.write_text("# Version 2 with new details", encoding="utf-8")
        res2 = await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "version.md")
        self.assertEqual(res2.status, IngestionStatus.INDEXED.value)
        self.assertNotEqual(res1.content_hash, res2.content_hash)

        # Total sources for proj_a should still be 1
        sources = self.knowledge_repo.list_sources(self.proj_a.project_id)
        self.assertEqual(len(sources), 1)

    # 29. Project isolation remains intact
    async def test_project_isolation_in_ingestion(self):
        proj_b = self.project_repo.create(
            ProjectCreate(name="Project B", description="Isolated project")
        )
        (self.root_path / "secret.md").write_text("Project A proprietary algorithm", encoding="utf-8")
        await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "secret.md")

        # Search in Project B should return zero results
        search_b = await self.searcher.search(
            project_id=proj_b.project_id,
            query="proprietary algorithm",
            top_k=5,
        )
        self.assertEqual(len(search_b.results), 0)

        # Search in Project A returns the chunk
        search_a = await self.searcher.search(
            project_id=self.proj_a.project_id,
            query="proprietary algorithm",
            top_k=5,
        )
        self.assertEqual(len(search_a.results), 1)
        self.assertEqual(search_a.results[0].source_name, "secret.md")

    # 30. Project deletion still cascades correctly
    async def test_project_deletion_cascades_ingested_sources(self):
        (self.root_path / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        await self.ingestion_service.ingest_file_async(self.proj_a.project_id, "data.json")

        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 1)
        self.project_repo.delete(self.proj_a.project_id)
        self.assertEqual(self.knowledge_repo.count_sources(self.proj_a.project_id), 0)


class TestDocumentIngestionAPI(unittest.TestCase):
    """API endpoint integration tests for document ingestion."""

    def setUp(self):
        self.temp_db_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_db_dir.name, "test_api_ingest.db")
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

        # Create temporary project filesystem root
        self.project_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.project_dir.name).resolve()

        from app.auth import get_current_user
        from app.database.models import UserRecord

        self.test_user = UserRecord(id=1, clerk_user_id="user_test_doc_ingest")

        self.proj = self.project_repo.create(
            ProjectCreate(
                name="API Ingestion Project",
                description="Testing ingest endpoints",
                root_path=str(self.root_path),
            ),
            user_id=self.test_user.id,
        )

        app.dependency_overrides[get_current_user] = lambda: self.test_user
        app.dependency_overrides[get_project_repository] = lambda: self.project_repo
        app.dependency_overrides[get_knowledge_repository] = lambda: self.knowledge_repo
        app.dependency_overrides[get_api_embedding_provider] = lambda: self.embedding_provider
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.temp_db_dir.cleanup()
        self.project_dir.cleanup()

    def test_ingest_single_file_endpoint(self):
        (self.root_path / "hello.py").write_text("print('hello')", encoding="utf-8")

        response = self.client.post(
            f"/api/projects/{self.proj.project_id}/knowledge/ingest/file",
            json={"file_path": "hello.py"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "indexed")
        self.assertEqual(data["relative_path"], "hello.py")
        self.assertEqual(data["source_type"], "code")
        self.assertGreater(data["chunk_count"], 0)

    def test_ingest_directory_endpoint(self):
        (self.root_path / "README.md").write_text("# Overview", encoding="utf-8")
        src_dir = self.root_path / "src"
        src_dir.mkdir()
        (src_dir / "app.ts").write_text("export const app = 1;", encoding="utf-8")

        response = self.client.post(
            f"/api/projects/{self.proj.project_id}/knowledge/ingest/directory",
            json={"recursive": True},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["indexed"], 2)
        self.assertEqual(data["failed"], 0)

    # 26. Existing text indexing endpoint remains compatible
    def test_existing_text_indexing_endpoint_compatibility(self):
        payload = {
            "source_type": "text",
            "source_name": "manual_snippet.txt",
            "content": "Manually posted snippet content.",
        }
        response = self.client.post(
            f"/api/projects/{self.proj.project_id}/knowledge/index",
            json=payload,
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["source_name"], "manual_snippet.txt")
        self.assertFalse(data["is_duplicate"])

    def test_ingest_file_project_not_found(self):
        response = self.client.post(
            "/api/projects/unknown-proj-id/knowledge/ingest/file",
            json={"file_path": "some.md"},
        )
        self.assertEqual(response.status_code, 404)

    def test_ingest_file_unconfigured_root_without_override(self):
        proj_no_root = self.project_repo.create(
            ProjectCreate(name="No Root", description="No root path"),
            user_id=self.test_user.id,
        )
        response = self.client.post(
            f"/api/projects/{proj_no_root.project_id}/knowledge/ingest/file",
            json={"file_path": "some.md"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("root", response.json()["detail"].lower())

    def test_ingest_file_path_traversal_returns_failed_status(self):
        response = self.client.post(
            f"/api/projects/{self.proj.project_id}/knowledge/ingest/file",
            json={"file_path": "../secrets.txt"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "failed")
        self.assertIn("PATH_OUTSIDE_PROJECT", data["error"])


if __name__ == "__main__":
    unittest.main()
