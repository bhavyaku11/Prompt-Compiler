"""Project Memory Service layer for managing long-term development context."""

import asyncio
import time
import uuid
from typing import Any

from app.database.repositories import (
    CandidateMemoryRepository,
    ProjectMemoryRepository,
    ProjectRepository,
)
from app.engine.memory_extractor import CandidateMemoryExtractor
from app.schemas.candidate_memory import (
    CandidateApprovalResponse,
    CandidateMemory,
    CandidateMemoryCreate,
    CandidateMemoryUpdate,
    CandidateStatus,
)
from app.schemas.project import (
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


class ProjectMemoryError(Exception):
    """Base exception for all project memory operations."""


class ProjectNotFoundError(ProjectMemoryError):
    """Raised when an operation targets a nonexistent project_id."""


class MemoryNotFoundError(ProjectMemoryError):
    """Raised when an operation targets a nonexistent memory_id."""


class InvalidProjectMemoryError(ProjectMemoryError):
    """Raised when memory content or metadata violates validation constraints."""


class CandidateNotFoundError(ProjectMemoryError):
    """Raised when an operation targets a nonexistent candidate_id."""


class InvalidCandidateActionError(ProjectMemoryError):
    """Raised when an operation on a candidate memory violates workflow rules."""


class ProjectMemoryService:
    """Service providing high-level operations for projects, long-term memory, and candidate proposals."""

    def __init__(
        self,
        project_repository: ProjectRepository | None = None,
        memory_repository: ProjectMemoryRepository | None = None,
        candidate_repository: CandidateMemoryRepository | None = None,
        extractor: CandidateMemoryExtractor | None = None,
        database_url: str | None = None,
    ) -> None:
        self._project_repo = project_repository or ProjectRepository(database_url=database_url)
        self._memory_repo = memory_repository or ProjectMemoryRepository(
            database_url=database_url,
            project_repository=self._project_repo,
        )
        self._candidate_repo = candidate_repository or CandidateMemoryRepository(
            database_url=database_url,
        )
        self._extractor = extractor or CandidateMemoryExtractor()


    # -------------------------------------------------------------------------
    # Synchronous Project Methods
    # -------------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str = "",
        root_path: str | None = None,
        user_id: int | None = None,
    ) -> Project:
        """Create and persist a new project."""
        create_schema = ProjectCreate(name=name, description=description, root_path=root_path)
        return self._project_repo.create(create_schema, user_id=user_id)

    def get_project(self, project_id: str, user_id: int | None = None) -> Project:
        """Retrieve a project by ID, raising ProjectNotFoundError if missing or not owned."""
        project = self._project_repo.get(project_id, user_id=user_id)
        if project is None:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found.")
        return project

    def get_project_by_name(self, name: str, user_id: int | None = None) -> Project | None:
        """Retrieve a project by name, optionally filtered by user."""
        return self._project_repo.get_by_name(name, user_id=user_id)

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        root_path: str | None = None,
        user_id: int | None = None,
    ) -> Project:
        """Update an existing project."""
        update_schema = ProjectUpdate(name=name, description=description, root_path=root_path)
        updated = self._project_repo.update(project_id, update_schema, user_id=user_id)
        if updated is None:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found.")
        return updated

    def delete_project(self, project_id: str, user_id: int | None = None) -> bool:
        """Delete a project and all associated memories."""
        deleted = self._project_repo.delete(project_id, user_id=user_id)
        if not deleted:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found.")
        return True

    def list_projects(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[Project]:
        """List all development projects."""
        return self._project_repo.list_projects(limit=limit, offset=offset, user_id=user_id)

    # -------------------------------------------------------------------------
    # Synchronous Memory Methods
    # -------------------------------------------------------------------------

    def add_memory(
        self,
        project_id: str,
        category: MemoryCategory | str,
        content: str,
        source: MemorySource | str = MemorySource.USER_CONFIRMED,
        confidence: float = 1.0,
        status: MemoryStatus | str = MemoryStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> ProjectMemory:
        """Add a memory item to a project after verifying project existence and ownership."""
        # Ensure project exists and belongs to user_id
        self.get_project(project_id, user_id=user_id)

        try:
            memory_data = ProjectMemoryCreate(
                category=category,
                content=content,
                source=source,
                confidence=confidence,
                status=status,
                metadata=metadata or {},
            )
        except Exception as exc:
            raise InvalidProjectMemoryError(f"Invalid project memory: {exc}") from exc

        return self._memory_repo.create(project_id, memory_data)

    def get_memory(self, memory_id: str, user_id: int | None = None) -> ProjectMemory:
        """Retrieve a memory item by ID, raising MemoryNotFoundError if missing or not owned."""
        memory = self._memory_repo.get(memory_id, user_id=user_id)
        if memory is None:
            raise MemoryNotFoundError(f"Memory item with ID '{memory_id}' not found.")
        return memory

    def update_memory(
        self,
        memory_id: str,
        category: MemoryCategory | str | None = None,
        content: str | None = None,
        source: MemorySource | str | None = None,
        confidence: float | None = None,
        status: MemoryStatus | str | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> ProjectMemory:
        """Update an existing memory item."""
        try:
            update_data = ProjectMemoryUpdate(
                category=category,
                content=content,
                source=source,
                confidence=confidence,
                status=status,
                metadata=metadata,
            )
        except Exception as exc:
            raise InvalidProjectMemoryError(f"Invalid project memory update: {exc}") from exc

        updated = self._memory_repo.update(memory_id, update_data, user_id=user_id)
        if updated is None:
            raise MemoryNotFoundError(f"Memory item with ID '{memory_id}' not found.")
        return updated

    def delete_memory(self, memory_id: str, user_id: int | None = None) -> bool:
        """Delete a memory item."""
        deleted = self._memory_repo.delete(memory_id, user_id=user_id)
        if not deleted:
            raise MemoryNotFoundError(f"Memory item with ID '{memory_id}' not found.")
        return True

    def list_memories(
        self,
        project_id: str,
        category: str | None = None,
        source: str | None = None,
        status: str | None = "active",
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[ProjectMemory]:
        """List memory items for a project."""
        # Ensure project exists and belongs to user_id
        self.get_project(project_id, user_id=user_id)
        return self._memory_repo.list_by_project(
            project_id=project_id,
            category=category,
            source=source,
            status=status,
            limit=limit,
            offset=offset,
            user_id=user_id,
        )

    def get_project_context(
        self,
        project_id: str,
        status_filter: str | None = "active",
        user_id: int | None = None,
    ) -> ProjectContext:
        """Retrieve aggregated project context with strictly deterministic ordering."""
        # Ensure project exists and belongs to user_id
        self.get_project(project_id, user_id=user_id)
        context = self._memory_repo.get_project_context(project_id, status_filter=status_filter, user_id=user_id)
        if context is None:
            raise ProjectNotFoundError(f"Project with ID '{project_id}' not found.")
        return context

    # -------------------------------------------------------------------------
    # Asynchronous Wrappers for FastAPI Event Loop Safety
    # -------------------------------------------------------------------------

    async def create_project_async(
        self,
        name: str,
        description: str = "",
        root_path: str | None = None,
        user_id: int | None = None,
    ) -> Project:
        """Asynchronously create a project."""
        return await asyncio.to_thread(self.create_project, name, description, root_path, user_id)

    async def get_project_async(self, project_id: str, user_id: int | None = None) -> Project:
        """Asynchronously retrieve a project."""
        return await asyncio.to_thread(self.get_project, project_id, user_id)

    async def update_project_async(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        root_path: str | None = None,
        user_id: int | None = None,
    ) -> Project:
        """Asynchronously update a project."""
        return await asyncio.to_thread(self.update_project, project_id, name, description, root_path, user_id)

    async def add_memory_async(
        self,
        project_id: str,
        category: MemoryCategory | str,
        content: str,
        source: MemorySource | str = MemorySource.USER_CONFIRMED,
        confidence: float = 1.0,
        status: MemoryStatus | str = MemoryStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> ProjectMemory:
        """Asynchronously add a memory item to a project."""
        return await asyncio.to_thread(
            self.add_memory,
            project_id,
            category,
            content,
            source,
            confidence,
            status,
            metadata,
            user_id,
        )

    async def delete_project_async(self, project_id: str, user_id: int | None = None) -> bool:
        """Asynchronously delete a project and all associated memories, candidates, and knowledge."""
        self.get_project(project_id, user_id=user_id)
        return await asyncio.to_thread(self.delete_project, project_id, user_id)

    async def get_memory_async(self, memory_id: str, user_id: int | None = None) -> ProjectMemory:
        """Asynchronously retrieve a project memory item."""
        return await asyncio.to_thread(self.get_memory, memory_id, user_id)

    async def update_memory_async(
        self,
        memory_id: str,
        category: MemoryCategory | str | None = None,
        content: str | None = None,
        source: MemorySource | str | None = None,
        confidence: float | None = None,
        status: MemoryStatus | str | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> ProjectMemory:
        """Asynchronously update a project memory item."""
        return await asyncio.to_thread(
            self.update_memory,
            memory_id,
            category,
            content,
            source,
            confidence,
            status,
            metadata,
            user_id,
        )

    async def delete_memory_async(self, memory_id: str, user_id: int | None = None) -> bool:
        """Asynchronously delete a project memory item."""
        self.get_memory(memory_id, user_id=user_id)
        return await asyncio.to_thread(self.delete_memory, memory_id, user_id)

    async def get_project_context_async(
        self,
        project_id: str,
        status_filter: str | None = "active",
        user_id: int | None = None,
    ) -> ProjectContext:
        """Asynchronously retrieve deterministic project context."""
        return await asyncio.to_thread(self.get_project_context, project_id, status_filter, user_id)

    # -------------------------------------------------------------------------
    # Synchronous Candidate Memory Methods (Task 18)
    # -------------------------------------------------------------------------

    def extract_candidates(
        self,
        project_id: str,
        user_input: str,
        confirmed_requirements: list[str] | None = None,
        persist_candidates: bool = True,
        user_id: int | None = None,
    ) -> list[CandidateMemory]:
        """Extract candidate memories for a project and optionally persist them.

        Args:
            project_id: UUID of the project.
            user_input: User message or instruction text.
            confirmed_requirements: Optional list of confirmed requirement statements.
            persist_candidates: If True, saves candidates to SQLite with pending/duplicate/conflict status.
            user_id: Optional local user ID for ownership validation.

        Returns:
            List of CandidateMemory objects.
        """
        # Ensure project exists and belongs to user
        project = self.get_project(project_id, user_id=user_id)
        project_context = self.get_project_context(project_id, user_id=user_id)

        # Extract proposals with deduplication & conflict detection
        proposals = self._extractor.extract_candidates(
            user_input=user_input,
            confirmed_requirements=confirmed_requirements,
            project_context=project_context,
        )

        if not persist_candidates:
            now = time.time()
            return [
                CandidateMemory(
                    candidate_id=str(uuid.uuid4()),
                    project_id=project_id,
                    category=p.category,
                    content=p.content,
                    source=p.source,
                    confidence=p.confidence,
                    status=p.status,
                    evidence=p.evidence,
                    conflicting_memory_id=p.conflicting_memory_id,
                    conflicting_content=p.conflicting_content,
                    metadata=p.metadata,
                    created_at=now,
                    updated_at=now,
                )
                for p in proposals
            ]

        persisted: list[CandidateMemory] = []
        for prop in proposals:
            record = self._candidate_repo.create(project_id, prop)
            persisted.append(record)

        return persisted

    def get_candidate(self, candidate_id: str, user_id: int | None = None) -> CandidateMemory:
        """Retrieve a candidate memory item by candidate_id, raising CandidateNotFoundError if missing or not owned."""
        candidate = self._candidate_repo.get(candidate_id, user_id=user_id)
        if candidate is None:
            raise CandidateNotFoundError(f"Candidate memory with ID '{candidate_id}' not found.")
        return candidate

    def list_candidates(
        self,
        project_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[CandidateMemory]:
        """List candidate memory proposals for a project."""
        self.get_project(project_id, user_id=user_id)
        return self._candidate_repo.list_by_project(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
            user_id=user_id,
        )

    def approve_candidate(
        self,
        candidate_id: str,
        supersede_conflicting: bool = False,
        custom_content: str | None = None,
        user_id: int | None = None,
    ) -> CandidateApprovalResponse:
        """Approve a candidate memory proposal and persist it as an active ProjectMemory.

        Args:
            candidate_id: UUID of the candidate memory to approve.
            supersede_conflicting: If True and candidate has a conflict, supersede the conflicting existing memory.
            custom_content: Optional edited content to save as memory instead of candidate.content.
            user_id: Optional local user ID for ownership validation.

        Returns:
            CandidateApprovalResponse containing updated candidate, created memory, and supersede details.
        """
        candidate = self.get_candidate(candidate_id, user_id=user_id)

        if candidate.status == CandidateStatus.APPROVED.value:
            return CandidateApprovalResponse(
                candidate=candidate,
                created_memory_id=candidate.metadata.get("created_memory_id"),
                message="Candidate memory was already approved.",
            )

        if candidate.status == CandidateStatus.DUPLICATE.value:
            raise InvalidCandidateActionError(
                f"Cannot approve duplicate candidate '{candidate.content}'. An identical active memory already exists."
            )

        final_content = (custom_content or candidate.content).strip()
        superseded_id: str | None = None

        # If candidate has conflict and user opted to supersede
        if candidate.status == CandidateStatus.CONFLICT.value and candidate.conflicting_memory_id:
            if supersede_conflicting:
                try:
                    self.update_memory(
                        memory_id=candidate.conflicting_memory_id,
                        status=MemoryStatus.SUPERSEDED.value,
                        user_id=user_id,
                    )
                    superseded_id = candidate.conflicting_memory_id
                except MemoryNotFoundError:
                    pass

        # Create the persistent ProjectMemory
        created_memory = self.add_memory(
            project_id=candidate.project_id,
            category=candidate.category,
            content=final_content,
            source=candidate.source,
            confidence=candidate.confidence,
            status=MemoryStatus.ACTIVE.value,
            metadata={
                "from_candidate_id": candidate.candidate_id,
                "evidence": candidate.evidence,
                "superseded_memory_id": superseded_id,
            },
            user_id=user_id,
        )

        # Transition candidate status to approved
        updated_candidate = self._candidate_repo.update(
            candidate_id,
            CandidateMemoryUpdate(
                status=CandidateStatus.APPROVED.value,
                content=final_content,
                metadata={
                    **candidate.metadata,
                    "created_memory_id": created_memory.memory_id,
                    "superseded_memory_id": superseded_id,
                },
            ),
            user_id=user_id,
        )

        return CandidateApprovalResponse(
            candidate=updated_candidate or candidate,
            created_memory_id=created_memory.memory_id,
            superseded_memory_id=superseded_id,
            message="Candidate successfully approved and persisted to project memory.",
        )

    def reject_candidate(
        self,
        candidate_id: str,
        reason: str | None = None,
        user_id: int | None = None,
    ) -> CandidateMemory:
        """Reject a candidate memory without creating persistent ProjectMemory."""
        candidate = self.get_candidate(candidate_id, user_id=user_id)

        meta = dict(candidate.metadata)
        if reason:
            meta["rejection_reason"] = reason

        updated = self._candidate_repo.update(
            candidate_id,
            CandidateMemoryUpdate(
                status=CandidateStatus.REJECTED.value,
                metadata=meta,
            ),
            user_id=user_id,
        )
        if updated is None:
            raise CandidateNotFoundError(f"Candidate memory '{candidate_id}' not found.")
        return updated

    def delete_candidate(self, candidate_id: str, user_id: int | None = None) -> bool:
        """Delete a candidate memory proposal record."""
        return self._candidate_repo.delete(candidate_id, user_id=user_id)

    # -------------------------------------------------------------------------
    # Asynchronous Candidate Wrappers
    # -------------------------------------------------------------------------

    async def extract_candidates_async(
        self,
        project_id: str,
        user_input: str,
        confirmed_requirements: list[str] | None = None,
        persist_candidates: bool = True,
        user_id: int | None = None,
    ) -> list[CandidateMemory]:
        """Asynchronously extract candidate memories for a project."""
        return await asyncio.to_thread(
            self.extract_candidates,
            project_id,
            user_input,
            confirmed_requirements,
            persist_candidates,
            user_id,
        )

    async def get_candidate_async(self, candidate_id: str, user_id: int | None = None) -> CandidateMemory:
        """Asynchronously retrieve a candidate memory."""
        return await asyncio.to_thread(self.get_candidate, candidate_id, user_id)

    async def list_candidates_async(
        self,
        project_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[CandidateMemory]:
        """Asynchronously list candidate memories for a project."""
        return await asyncio.to_thread(
            self.list_candidates,
            project_id,
            status,
            limit,
            offset,
            user_id,
        )

    async def approve_candidate_async(
        self,
        candidate_id: str,
        supersede_conflicting: bool = False,
        custom_content: str | None = None,
        user_id: int | None = None,
    ) -> CandidateApprovalResponse:
        """Asynchronously approve a candidate memory."""
        return await asyncio.to_thread(
            self.approve_candidate,
            candidate_id,
            supersede_conflicting,
            custom_content,
            user_id,
        )

    async def reject_candidate_async(
        self,
        candidate_id: str,
        reason: str | None = None,
        user_id: int | None = None,
    ) -> CandidateMemory:
        """Asynchronously reject a candidate memory."""
        return await asyncio.to_thread(
            self.reject_candidate,
            candidate_id,
            reason,
            user_id,
        )

    async def delete_candidate_async(self, candidate_id: str, user_id: int | None = None) -> bool:
        """Asynchronously delete a candidate memory proposal."""
        return await asyncio.to_thread(self.delete_candidate, candidate_id, user_id)

