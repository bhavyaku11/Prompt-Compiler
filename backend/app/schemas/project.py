"""Project and Project Memory domain schemas for Prompt Compiler."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryCategory(str, Enum):
    """Categorization for project memory items."""

    PROJECT_DESCRIPTION = "project_description"
    TECHNOLOGY = "technology"
    ARCHITECTURE = "architecture"
    CONSTRAINT = "constraint"
    PREFERENCE = "preference"
    REQUIREMENT = "requirement"
    CODING_RULE = "coding_rule"
    DEPLOYMENT = "deployment"
    DATABASE = "database"
    FRONTEND = "frontend"
    BACKEND = "backend"
    OTHER = "other"


class MemorySource(str, Enum):
    """Origin and trust attribution for memory content."""

    USER_CONFIRMED = "user_confirmed"
    EXTRACTED_FROM_USER_INPUT = "extracted_from_user_input"
    GENERATED_ASSUMPTION = "generated_assumption"
    SYSTEM_DEFINED = "system_defined"


class MemoryStatus(str, Enum):
    """Lifecycle status for a memory item."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


# Canonical category ordering for deterministic presentation and sorting
CATEGORY_PRIORITY: list[str] = [
    MemoryCategory.PROJECT_DESCRIPTION.value,
    MemoryCategory.ARCHITECTURE.value,
    MemoryCategory.TECHNOLOGY.value,
    MemoryCategory.BACKEND.value,
    MemoryCategory.FRONTEND.value,
    MemoryCategory.DATABASE.value,
    MemoryCategory.DEPLOYMENT.value,
    MemoryCategory.REQUIREMENT.value,
    MemoryCategory.CONSTRAINT.value,
    MemoryCategory.CODING_RULE.value,
    MemoryCategory.PREFERENCE.value,
    MemoryCategory.OTHER.value,
]

# Source trust ranking for deterministic prioritization (lower index = higher trust)
SOURCE_TRUST_PRIORITY: list[str] = [
    MemorySource.USER_CONFIRMED.value,
    MemorySource.EXTRACTED_FROM_USER_INPUT.value,
    MemorySource.SYSTEM_DEFINED.value,
    MemorySource.GENERATED_ASSUMPTION.value,
]


class ProjectCreate(BaseModel):
    """Schema for creating a new project."""

    name: str = Field(..., description="Human-readable project name.", min_length=1, max_length=128)
    description: str = Field(default="", description="Detailed project description or purpose.")
    root_path: str | None = Field(default=None, description="Optional local filesystem root directory path for the project.")

    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Project name cannot be empty or contain only whitespace.")
        return stripped


class ProjectUpdate(BaseModel):
    """Schema for updating an existing project."""

    name: str | None = Field(default=None, description="Updated project name.", min_length=1, max_length=128)
    description: str | None = Field(default=None, description="Updated project description.")
    root_path: str | None = Field(default=None, description="Optional updated local filesystem root directory path.")

    @field_validator("name")
    @classmethod
    def validate_name_if_present(cls, value: str | None) -> str | None:
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise ValueError("Project name cannot be empty or contain only whitespace.")
            return stripped
        return value


class Project(BaseModel):
    """Domain model representing a persistent development project."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str = Field(..., description="Unique UUID identifying the project.")
    name: str = Field(..., description="Project name.")
    description: str = Field(default="", description="Project description.")
    root_path: str | None = Field(default=None, description="Configured local filesystem root directory path.")
    user_id: int | None = Field(default=None, description="Owner local user ID.")
    created_at: float = Field(..., description="Creation Unix timestamp.")
    updated_at: float = Field(..., description="Last update Unix timestamp.")


class ProjectMemoryCreate(BaseModel):
    """Schema for creating a project memory item."""

    category: MemoryCategory | str = Field(
        ...,
        description="Structured category of the memory item.",
    )
    content: str = Field(
        ...,
        description="Text content of the memory item (e.g. 'Uses FastAPI with SQLAlchemy').",
        min_length=1,
    )
    source: MemorySource | str = Field(
        default=MemorySource.USER_CONFIRMED,
        description="Attribution source and trust level.",
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score between 0.0 and 1.0.",
        ge=0.0,
        le=1.0,
    )
    status: MemoryStatus | str = Field(
        default=MemoryStatus.ACTIVE,
        description="Lifecycle status: 'active', 'deprecated', or 'superseded'.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary contextual metadata.",
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
            raise ValueError("Memory content cannot be empty or contain only whitespace.")
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
    def validate_status(cls, value: MemoryStatus | str) -> str:
        st_str = value.value if isinstance(value, MemoryStatus) else str(value).strip().lower()
        valid = {s.value for s in MemoryStatus}
        if st_str not in valid:
            raise ValueError(f"Invalid status '{value}'. Allowed statuses: {sorted(valid)}")
        return st_str


class ProjectMemoryUpdate(BaseModel):
    """Schema for updating an existing project memory item."""

    category: MemoryCategory | str | None = None
    content: str | None = None
    source: MemorySource | str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: MemoryStatus | str | None = None
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
            raise ValueError("Memory content cannot be empty or contain only whitespace.")
        return stripped

    @field_validator("source")
    @classmethod
    def validate_source_if_present(cls, value: MemorySource | str | None) -> str | None:
        if value is None:
            return None
        src_str = value.value if isinstance(value, MemorySource) else str(value).strip().lower()
        valid = {s.value for s in MemorySource}
        if src_str not in valid:
            raise ValueError(f"Invalid source '{value}'. Allowed sources: {sorted(valid)}")
        return src_str

    @field_validator("status")
    @classmethod
    def validate_status_if_present(cls, value: MemoryStatus | str | None) -> str | None:
        if value is None:
            return None
        st_str = value.value if isinstance(value, MemoryStatus) else str(value).strip().lower()
        valid = {s.value for s in MemoryStatus}
        if st_str not in valid:
            raise ValueError(f"Invalid status '{value}'. Allowed statuses: {sorted(valid)}")
        return st_str


class ProjectMemory(BaseModel):
    """Domain model representing a persistent project memory record."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: str = Field(..., description="Unique UUID identifying this memory record.")
    project_id: str = Field(..., description="UUID of the associated project.")
    category: str = Field(..., description="Categorization tag.")
    content: str = Field(..., description="Memory statement or fact.")
    source: str = Field(default=MemorySource.USER_CONFIRMED.value, description="Attribution source.")
    confidence: float = Field(default=1.0, description="Confidence metric.")
    status: str = Field(default=MemoryStatus.ACTIVE.value, description="Status ('active', 'deprecated', 'superseded').")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary.")
    created_at: float = Field(..., description="Creation Unix timestamp.")
    updated_at: float = Field(..., description="Update Unix timestamp.")


class ProjectContext(BaseModel):
    """Aggregated, deterministic project context for downstream prompt compilation."""

    project: Project = Field(..., description="Associated project entity.")
    memories: list[ProjectMemory] = Field(
        default_factory=list,
        description="All relevant memory records sorted deterministically.",
    )
    categorized_memories: dict[str, list[ProjectMemory]] = Field(
        default_factory=dict,
        description="Memory items grouped by category.",
    )
    active_constraints: list[str] = Field(
        default_factory=list,
        description="Flattened list of active constraints.",
    )
    technologies: list[str] = Field(
        default_factory=list,
        description="Flattened list of active technologies/stack elements.",
    )
    coding_rules: list[str] = Field(
        default_factory=list,
        description="Flattened list of active coding rules/standards.",
    )
    retrieved_at: float = Field(
        default_factory=time.time,
        description="Unix timestamp when this context view was computed.",
    )

    def to_context_string(self) -> str:
        """Render a deterministic, human-readable context summary for prompt builders."""
        lines: list[str] = [f"PROJECT: {self.project.name}"]
        if self.project.description:
            lines.append(f"DESCRIPTION: {self.project.description}")

        if self.technologies:
            lines.append("\nTECHNOLOGIES:")
            for tech in self.technologies:
                lines.append(f"- {tech}")

        if self.active_constraints:
            lines.append("\nCONSTRAINTS:")
            for constraint in self.active_constraints:
                lines.append(f"- {constraint}")

        if self.coding_rules:
            lines.append("\nCODING RULES:")
            for rule in self.coding_rules:
                lines.append(f"- {rule}")

        # Other categories
        other_cats = [
            cat
            for cat in CATEGORY_PRIORITY
            if cat not in {"technology", "constraint", "coding_rule", "project_description"}
            and cat in self.categorized_memories
            and self.categorized_memories[cat]
        ]
        for cat in other_cats:
            items = self.categorized_memories[cat]
            lines.append(f"\n{cat.upper()}:")
            for item in items:
                trust_note = f" (assumption)" if item.source == MemorySource.GENERATED_ASSUMPTION.value else ""
                lines.append(f"- {item.content}{trust_note}")

        return "\n".join(lines)
