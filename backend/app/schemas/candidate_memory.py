"""Candidate Project Memory domain schemas for Prompt Compiler (Task 18).

Represents temporary, unconfirmed memory proposals extracted from user interactions.
Candidate memories must be explicitly reviewed and approved before becoming persistent ProjectMemory records.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.project import MemoryCategory, MemorySource


class CandidateStatus(str, Enum):
    """Lifecycle status for an unconfirmed candidate memory."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


class CandidateMemoryCreate(BaseModel):
    """Schema for creating a new candidate memory proposal."""

    category: MemoryCategory | str = Field(
        ...,
        description="Structured category of the memory item.",
    )
    content: str = Field(
        ...,
        description="Text content of the proposed memory item.",
        min_length=1,
    )
    source: MemorySource | str = Field(
        default=MemorySource.EXTRACTED_FROM_USER_INPUT,
        description="Origin attribution and trust level.",
    )
    confidence: float = Field(
        default=0.9,
        description="Extraction confidence metric between 0.0 and 1.0 (not business importance).",
        ge=0.0,
        le=1.0,
    )
    status: CandidateStatus | str = Field(
        default=CandidateStatus.PENDING,
        description="Review status: pending, approved, rejected, duplicate, or conflict.",
    )
    evidence: str = Field(
        default="",
        description="Concise user-readable explanation or quote justifying the candidate proposal.",
    )
    conflicting_memory_id: str | None = Field(
        default=None,
        description="UUID of conflicting active ProjectMemory if status is conflict.",
    )
    conflicting_content: str | None = Field(
        default=None,
        description="Content of the conflicting existing memory for user inspection.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Contextual metadata dictionary.",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: MemoryCategory | str) -> str:
        cat_str = value.value if isinstance(value, MemoryCategory) else str(value).strip().lower()
        valid = {c.value for c in MemoryCategory}
        if cat_str not in valid:
            raise ValueError(f"Invalid category '{value}'. Allowed categories: {sorted(valid)}")
        return cat_str

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Candidate memory content cannot be empty or contain only whitespace.")
        return stripped

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: MemorySource | str) -> str:
        src_str = value.value if isinstance(value, MemorySource) else str(value).strip().lower()
        valid = {s.value for s in MemorySource}
        if src_str not in valid:
            raise ValueError(f"Invalid source '{value}'. Allowed sources: {sorted(valid)}")
        return src_str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: CandidateStatus | str) -> str:
        st_str = value.value if isinstance(value, CandidateStatus) else str(value).strip().lower()
        valid = {s.value for s in CandidateStatus}
        if st_str not in valid:
            raise ValueError(f"Invalid candidate status '{value}'. Allowed statuses: {sorted(valid)}")
        return st_str


class CandidateMemoryUpdate(BaseModel):
    """Schema for updating an existing candidate memory record."""

    content: str | None = None
    category: MemoryCategory | str | None = None
    status: CandidateStatus | str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence: str | None = None
    conflicting_memory_id: str | None = None
    conflicting_content: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("category")
    @classmethod
    def validate_category_if_present(cls, value: MemoryCategory | str | None) -> str | None:
        if value is None:
            return None
        cat_str = value.value if isinstance(value, MemoryCategory) else str(value).strip().lower()
        valid = {c.value for c in MemoryCategory}
        if cat_str not in valid:
            raise ValueError(f"Invalid category '{value}'. Allowed categories: {sorted(valid)}")
        return cat_str

    @field_validator("content")
    @classmethod
    def validate_content_if_present(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Candidate memory content cannot be empty or contain only whitespace.")
        return stripped

    @field_validator("status")
    @classmethod
    def validate_status_if_present(cls, value: CandidateStatus | str | None) -> str | None:
        if value is None:
            return None
        st_str = value.value if isinstance(value, CandidateStatus) else str(value).strip().lower()
        valid = {s.value for s in CandidateStatus}
        if st_str not in valid:
            raise ValueError(f"Invalid candidate status '{value}'. Allowed statuses: {sorted(valid)}")
        return st_str


class CandidateMemory(BaseModel):
    """Domain model representing an unconfirmed candidate memory proposal."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(..., description="Unique UUID identifying this candidate memory.")
    project_id: str = Field(..., description="UUID of the associated project.")
    category: str = Field(..., description="Categorization tag.")
    content: str = Field(..., description="Proposed memory statement or fact.")
    source: str = Field(
        default=MemorySource.EXTRACTED_FROM_USER_INPUT.value,
        description="Attribution source.",
    )
    confidence: float = Field(
        default=0.9,
        description="Extraction confidence metric between 0.0 and 1.0 (extraction fidelity, not importance).",
    )
    status: str = Field(
        default=CandidateStatus.PENDING.value,
        description="Review status: 'pending', 'approved', 'rejected', 'duplicate', 'conflict'.",
    )
    evidence: str = Field(
        default="",
        description="Concise user-readable explanation or quote justifying the candidate proposal.",
    )
    conflicting_memory_id: str | None = Field(
        default=None,
        description="UUID of conflicting active ProjectMemory if status is conflict.",
    )
    conflicting_content: str | None = Field(
        default=None,
        description="Content of the conflicting existing memory for user inspection.",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary.")
    created_at: float = Field(..., description="Creation Unix timestamp.")
    updated_at: float = Field(..., description="Update Unix timestamp.")


class ExtractCandidatesRequest(BaseModel):
    """Request payload to extract candidate memories from interaction text."""

    input: str = Field(
        ...,
        description="User interaction text, request, or instruction to extract memories from.",
        min_length=1,
    )
    confirmed_requirements: list[str] = Field(
        default_factory=list,
        description="Optional confirmed requirements from compiler analysis.",
    )

    @field_validator("input")
    @classmethod
    def validate_input_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Input text cannot be empty or contain only whitespace.")
        return stripped


class CandidateApprovalRequest(BaseModel):
    """Request options when approving a candidate memory."""

    supersede_conflicting: bool = Field(
        default=False,
        description="If True and candidate has a conflict, mark the conflicting existing memory as superseded.",
    )
    custom_content: str | None = Field(
        default=None,
        description="Optional edited content to save as persistent ProjectMemory instead of candidate.content.",
    )


class CandidateApprovalResponse(BaseModel):
    """Response payload when a candidate memory is approved and persisted."""

    candidate: CandidateMemory = Field(..., description="Updated candidate memory record with approved status.")
    created_memory_id: str | None = Field(
        default=None,
        description="UUID of the newly created persistent ProjectMemory.",
    )
    superseded_memory_id: str | None = Field(
        default=None,
        description="UUID of the existing memory that was superseded, if applicable.",
    )
    message: str = Field(
        default="Candidate approved and persisted to project memory.",
        description="Status description.",
    )


class CandidateRejectionRequest(BaseModel):
    """Request options when rejecting a candidate memory."""

    reason: str | None = Field(
        default=None,
        description="Optional user reason for rejecting this candidate proposal.",
    )
