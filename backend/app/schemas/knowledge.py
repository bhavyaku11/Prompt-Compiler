"""Domain schemas for vector knowledge base and semantic retrieval."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(str, Enum):
    """Supported source types for vector knowledge base indexing."""

    DOCUMENTATION = "documentation"
    TEXT = "text"
    CODE = "code"


SUPPORTED_SOURCE_TYPES = {t.value for t in SourceType}


class KnowledgeSource(BaseModel):
    """Domain model for an indexed knowledge document or snippet source."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    project_id: str
    source_type: str = "documentation"
    source_name: str
    content_hash: str
    chunk_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeChunk(BaseModel):
    """Domain model for a single chunk of indexed knowledge text with vector reference."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    project_id: str
    source_id: str
    chunk_index: int
    content: str
    content_hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeIndexRequest(BaseModel):
    """Request payload for indexing text content into project vector knowledge base."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(default="documentation", description="Source category (documentation, text, code)")
    source_name: str = Field(..., min_length=1, max_length=255, description="Human-readable name or filename of the source")
    content: str = Field(..., min_length=1, description="Raw text content to chunk, embed, and index")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Optional extra metadata for the source")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, val: str) -> str:
        normalized = val.strip().lower()
        if normalized not in SUPPORTED_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported source_type '{val}'. Must be one of: {sorted(SUPPORTED_SOURCE_TYPES)}"
            )
        return normalized

    @field_validator("source_name")
    @classmethod
    def validate_source_name(cls, val: str) -> str:
        normalized = val.strip()
        if not normalized:
            raise ValueError("source_name must not be empty or whitespace only")
        return normalized

    @field_validator("content")
    @classmethod
    def validate_content(cls, val: str) -> str:
        if not val.strip():
            raise ValueError("content must not be empty or whitespace only")
        return val


class KnowledgeIndexResponse(BaseModel):
    """Response returned after indexing a knowledge source."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    source_id: str
    source_name: str
    source_type: str
    content_hash: str
    chunk_count: int
    is_duplicate: bool = False
    message: str = "Content successfully indexed into vector knowledge base"


class KnowledgeSearchRequest(BaseModel):
    """Request payload for querying project knowledge base via vector similarity."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, description="Natural-language or code query string")
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum number of relevant chunks to return")

    @field_validator("query")
    @classmethod
    def validate_query(cls, val: str) -> str:
        normalized = val.strip()
        if not normalized:
            raise ValueError("query must not be empty or whitespace only")
        return normalized


class KnowledgeSearchResult(BaseModel):
    """Individual retrieved knowledge chunk with similarity score and origin metadata."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    source_name: str
    source_type: str
    chunk_index: int
    content: str
    score: float = Field(..., description="Cosine similarity score bounded between 0.0 and 1.0 (higher = more similar)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    """Response payload containing ranked semantic search results scoped to a project."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    query: str
    top_k: int
    metric: str = "cosine_similarity"
    total_results: int
    results: list[KnowledgeSearchResult] = Field(default_factory=list)


class KnowledgeSourceResponse(BaseModel):
    """Response schema for listing knowledge sources."""

    model_config = ConfigDict(from_attributes=True)

    source_id: str
    project_id: str
    source_type: str
    source_name: str
    content_hash: str
    chunk_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class KnowledgeContextItem(BaseModel):
    """Contextual representation of a retrieved knowledge chunk for prompt generation."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    source_id: str
    source_name: str
    source_type: str
    chunk_index: int
    content: str
    score: float = Field(..., description="Cosine similarity relevance score (0.0 to 1.0)")
    metadata: dict[str, Any] = Field(default_factory=dict)
    matched_queries: list[str] = Field(default_factory=list, description="List of search queries that retrieved this chunk")


class IngestionStatus(str, Enum):
    """Status outcomes for an individual document ingestion attempt."""

    INDEXED = "indexed"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    FAILED = "failed"


class DocumentIngestionResult(BaseModel):
    """Structured result of ingesting an individual document file."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Original path or filename requested.")
    relative_path: str = Field(..., description="Project-relative path used as the canonical source name.")
    source_type: str | None = Field(default=None, description="Inferred source type ('documentation', 'text', 'code').")
    status: str = Field(..., description="Ingestion status: 'indexed', 'unchanged', 'skipped', or 'failed'.")
    source_id: str | None = Field(default=None, description="UUID of the indexed knowledge source record.")
    chunk_count: int = Field(default=0, description="Number of chunks produced and indexed.")
    content_hash: str | None = Field(default=None, description="SHA-256 hash of normalized content.")
    error: str | None = Field(default=None, description="Reason or error description if skipped or failed.")


class BatchDocumentIngestionResponse(BaseModel):
    """Summary of batch document ingestion for a project directory or file set."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total: int = Field(..., description="Total number of candidate files inspected.")
    indexed: int = Field(default=0, description="Count of newly indexed files.")
    unchanged: int = Field(default=0, description="Count of unchanged files (skipped re-embedding).")
    skipped: int = Field(default=0, description="Count of skipped files (unsupported type, size limit).")
    failed: int = Field(default=0, description="Count of failed files (invalid JSON, decode error).")
    results: list[DocumentIngestionResult] = Field(default_factory=list, description="Per-file detailed results.")


class IngestFileRequest(BaseModel):
    """Request payload for ingesting a single file into project knowledge base."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="Path to file to ingest (relative to project root or within project root).")
    project_root: str | None = Field(default=None, description="Optional project root path override if not configured on project.")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, val: str) -> str:
        normalized = val.strip()
        if not normalized:
            raise ValueError("file_path must not be empty or whitespace only.")
        return normalized


class IngestDirectoryRequest(BaseModel):
    """Request payload for ingesting supported files in a directory."""

    model_config = ConfigDict(extra="forbid")

    directory_path: str | None = Field(default=None, description="Optional sub-directory path to ingest (relative to project root).")
    project_root: str | None = Field(default=None, description="Optional project root path override if not configured on project.")
    recursive: bool = Field(default=True, description="Whether to recursively discover supported files in subdirectories.")

