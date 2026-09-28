"""Document ingestion and file parsing foundation service for Prompt Compiler."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.config import settings
from app.database.repositories import ProjectRepository
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.project_memory import ProjectNotFoundError
from app.schemas.knowledge import (
    BatchDocumentIngestionResponse,
    DocumentIngestionResult,
    IngestionStatus,
    SourceType,
)

logger = logging.getLogger(__name__)

# Supported file extensions mapped to canonical SourceType values
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".md": SourceType.DOCUMENTATION.value,
    ".txt": SourceType.TEXT.value,
    ".py": SourceType.CODE.value,
    ".ts": SourceType.CODE.value,
    ".json": SourceType.CODE.value,
}

# Directories to exclude automatically during recursive file discovery
DEFAULT_EXCLUDED_DIRECTORIES: set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".next",
    ".nuxt",
    ".idea",
    ".vscode",
    ".turbo",
    ".cache",
}

# Known non-text/database extensions to strictly exclude
DEFAULT_EXCLUDED_EXTENSIONS: set[str] = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".doc",
    ".docx",
}


class DocumentIngestionError(Exception):
    """Base exception for document ingestion failures."""


class ProjectRootNotConfiguredError(DocumentIngestionError):
    """Raised when an ingestion request is made for a project without a valid filesystem root."""


class PathSecurityError(DocumentIngestionError):
    """Raised when a path traverses outside the allowed project root."""


class FileReadError(DocumentIngestionError):
    """Raised when a file cannot be read or decoded."""


def resolve_project_root(project_root: str | Path | None) -> Path:
    """Resolve and validate a project root directory."""
    if not project_root:
        raise ProjectRootNotConfiguredError(
            "Project filesystem root is not configured. Please configure root_path on the project or supply project_root."
        )
    root = Path(project_root).resolve()
    if not root.exists():
        raise ProjectRootNotConfiguredError(f"Project root directory '{root}' does not exist.")
    if not root.is_dir():
        raise ProjectRootNotConfiguredError(f"Project root path '{root}' is not a directory.")
    return root


def validate_path_safety(target_path_str: str, root_path: Path) -> Path:
    """Validate that target_path resolves strictly within root_path without traversal or symlink escape."""
    resolved_root = root_path.resolve()
    raw_path = Path(target_path_str)

    if raw_path.is_absolute():
        resolved_target = raw_path.resolve()
    else:
        resolved_target = (resolved_root / raw_path).resolve()

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise PathSecurityError(
            f"Path '{target_path_str}' escapes allowed project root '{resolved_root}'."
        ) from exc

    return resolved_target


def discover_supported_files(
    directory_path: Path,
    root_path: Path,
    recursive: bool = True,
    excluded_dirs: set[str] | None = None,
) -> list[Path]:
    """Deterministically discover all supported files in a directory."""
    resolved_root = root_path.resolve()
    resolved_dir = directory_path.resolve()
    ignore_dirs = excluded_dirs or DEFAULT_EXCLUDED_DIRECTORIES

    discovered: list[Path] = []

    if recursive:
        for root, dirs, files in os.walk(resolved_dir, topdown=True, followlinks=False):
            # Prune excluded directories in-place (handles both exact names and hidden directories)
            dirs[:] = [
                d for d in dirs
                if d not in ignore_dirs and not d.startswith(".")
            ]

            current_dir_path = Path(root).resolve()
            # Ensure current directory has not escaped root via symlink
            try:
                current_dir_path.relative_to(resolved_root)
            except ValueError:
                continue

            for file_name in files:
                if file_name.startswith("."):
                    continue
                file_path = current_dir_path / file_name
                ext = file_path.suffix.lower()
                if ext in SUPPORTED_EXTENSIONS and ext not in DEFAULT_EXCLUDED_EXTENSIONS:
                    discovered.append(file_path)
    else:
        for entry in resolved_dir.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_file():
                ext = entry.suffix.lower()
                if ext in SUPPORTED_EXTENSIONS and ext not in DEFAULT_EXCLUDED_EXTENSIONS:
                    discovered.append(entry.resolve())

    # Deterministic alphabetical sort by relative path string
    discovered.sort(key=lambda p: str(p.relative_to(resolved_root)).lower())
    return discovered


def read_and_normalize_content(
    file_path: Path,
    max_file_size_bytes: int = 1048576,
) -> tuple[str, str, dict[str, Any]]:
    """Read and normalize content of a supported file.

    Returns:
        tuple[normalized_content, source_type, metadata]
    """
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"UNSUPPORTED_FILE_TYPE: File extension '{ext}' is not supported.")

    # Check file size
    stat_result = file_path.stat()
    if stat_result.st_size > max_file_size_bytes:
        raise ValueError(
            f"FILE_TOO_LARGE: File size ({stat_result.st_size} bytes) exceeds limit of {max_file_size_bytes} bytes."
        )

    # Read bytes and decode UTF-8 with automatic BOM stripping
    try:
        raw_bytes = file_path.read_bytes()
    except PermissionError as err:
        raise PermissionError(f"PERMISSION_DENIED: Cannot read file '{file_path.name}': {err}") from err
    except Exception as err:
        raise FileReadError(f"FILE_READ_ERROR: Error reading '{file_path.name}': {err}") from err

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as err:
        raise ValueError(f"FILE_DECODE_ERROR: File '{file_path.name}' is not valid UTF-8 text.") from err

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    source_type = SUPPORTED_EXTENSIONS[ext]
    metadata: dict[str, Any] = {
        "extension": ext,
        "file_size": stat_result.st_size,
        "source_type": source_type,
    }

    # Format-specific validations and normalizations
    if ext == ".json":
        try:
            parsed_json = json.loads(text)
            # Deterministic serialization with sorted keys
            normalized_text = json.dumps(parsed_json, indent=2, sort_keys=True)
            metadata["subtype"] = "configuration"
            return normalized_text, source_type, metadata
        except Exception as err:
            raise ValueError(f"INVALID_JSON: Malformed JSON content in '{file_path.name}': {err}") from err

    # For .md, .txt, .py, .ts: retain semantic structural text as-is
    return text, source_type, metadata


class DocumentIngestionService:
    """Service orchestrating file discovery, security validation, parsing, and indexer delegation."""

    def __init__(
        self,
        indexer_service: KnowledgeIndexerService,
        project_repository: ProjectRepository,
        max_file_size_bytes: int | None = None,
    ) -> None:
        self._indexer = indexer_service
        self._project_repo = project_repository
        self._max_file_size_bytes = (
            max_file_size_bytes if max_file_size_bytes is not None else settings.document_max_file_size_bytes
        )

    def _get_project_root(self, project_id: str, request_root: str | None = None) -> Path:
        """Resolve project filesystem root from request override or database record."""
        project = self._project_repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found.")

        root_candidate = request_root or project.root_path
        if not root_candidate:
            raise ProjectRootNotConfiguredError(
                f"Project '{project.name}' ({project_id}) has no root_path configured. "
                "Specify project_root in request or update project with a root_path."
            )
        return resolve_project_root(root_candidate)

    async def ingest_file_async(
        self,
        project_id: str,
        file_path_str: str,
        project_root: str | None = None,
    ) -> DocumentIngestionResult:
        """Ingest a single file safely into the project's vector knowledge base."""
        # 1. Resolve project root
        root_path = self._get_project_root(project_id, project_root)

        # 2. Validate path safety
        try:
            resolved_path = validate_path_safety(file_path_str, root_path)
        except PathSecurityError as exc:
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=file_path_str,
                status=IngestionStatus.FAILED.value,
                error=f"PATH_OUTSIDE_PROJECT: {exc}",
            )

        # 3. Check existence and file type
        if not resolved_path.exists():
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=str(resolved_path.relative_to(root_path)),
                status=IngestionStatus.FAILED.value,
                error=f"FILE_NOT_FOUND: File '{file_path_str}' does not exist.",
            )

        if resolved_path.is_dir():
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=str(resolved_path.relative_to(root_path)),
                status=IngestionStatus.FAILED.value,
                error="EXPECTED_FILE: Path points to a directory, not a file.",
            )

        relative_path = str(resolved_path.relative_to(root_path))
        ext = resolved_path.suffix.lower()

        # Check supported extension
        if ext not in SUPPORTED_EXTENSIONS or ext in DEFAULT_EXCLUDED_EXTENSIONS:
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=relative_path,
                source_type=None,
                status=IngestionStatus.SKIPPED.value,
                error=f"UNSUPPORTED_FILE_TYPE: Extension '{ext}' is not supported.",
            )

        # 4. Read and parse content
        try:
            content, source_type, metadata = read_and_normalize_content(
                resolved_path,
                max_file_size_bytes=self._max_file_size_bytes,
            )
        except ValueError as exc:
            err_msg = str(exc)
            status_val = (
                IngestionStatus.SKIPPED.value
                if "FILE_TOO_LARGE" in err_msg or "UNSUPPORTED_FILE_TYPE" in err_msg
                else IngestionStatus.FAILED.value
            )
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=relative_path,
                source_type=SUPPORTED_EXTENSIONS.get(ext),
                status=status_val,
                error=err_msg,
            )
        except Exception as exc:
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=relative_path,
                source_type=SUPPORTED_EXTENSIONS.get(ext),
                status=IngestionStatus.FAILED.value,
                error=f"FILE_READ_ERROR: {exc}",
            )

        # 5. Call KnowledgeIndexerService
        metadata["relative_path"] = relative_path
        try:
            index_res = await self._indexer.index_content(
                project_id=project_id,
                source_type=source_type,
                source_name=relative_path,
                content=content,
                metadata=metadata,
            )
        except Exception as exc:
            return DocumentIngestionResult(
                path=file_path_str,
                relative_path=relative_path,
                source_type=source_type,
                status=IngestionStatus.FAILED.value,
                error=f"INDEXING_ERROR: {exc}",
            )

        status_val = IngestionStatus.UNCHANGED.value if index_res.is_duplicate else IngestionStatus.INDEXED.value

        return DocumentIngestionResult(
            path=file_path_str,
            relative_path=relative_path,
            source_type=source_type,
            status=status_val,
            source_id=index_res.source_id,
            chunk_count=index_res.chunk_count,
            content_hash=index_res.content_hash,
            error=None,
        )

    async def ingest_directory_async(
        self,
        project_id: str,
        directory_path_str: str | None = None,
        project_root: str | None = None,
        recursive: bool = True,
    ) -> BatchDocumentIngestionResponse:
        """Discover and ingest all supported files within a project directory."""
        # 1. Resolve project root
        root_path = self._get_project_root(project_id, project_root)

        # 2. Resolve target directory
        if directory_path_str:
            resolved_target = validate_path_safety(directory_path_str, root_path)
            if not resolved_target.exists():
                raise DocumentIngestionError(f"Directory '{directory_path_str}' does not exist.")
            if not resolved_target.is_dir():
                raise DocumentIngestionError(f"Path '{directory_path_str}' is not a directory.")
        else:
            resolved_target = root_path

        # 3. Discover supported files deterministically
        candidate_files = discover_supported_files(
            directory_path=resolved_target,
            root_path=root_path,
            recursive=recursive,
        )

        results: list[DocumentIngestionResult] = []
        indexed_count = 0
        unchanged_count = 0
        skipped_count = 0
        failed_count = 0

        # 4. Ingest each discovered file
        for file_path in candidate_files:
            rel_path = str(file_path.relative_to(root_path))
            result = await self.ingest_file_async(
                project_id=project_id,
                file_path_str=rel_path,
                project_root=str(root_path),
            )
            results.append(result)

            if result.status == IngestionStatus.INDEXED.value:
                indexed_count += 1
            elif result.status == IngestionStatus.UNCHANGED.value:
                unchanged_count += 1
            elif result.status == IngestionStatus.SKIPPED.value:
                skipped_count += 1
            else:
                failed_count += 1

        return BatchDocumentIngestionResponse(
            project_id=project_id,
            total=len(candidate_files),
            indexed=indexed_count,
            unchanged=unchanged_count,
            skipped=skipped_count,
            failed=failed_count,
            results=results,
        )
