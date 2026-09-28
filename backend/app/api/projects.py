"""Minimal API endpoints for Project Memory and development context management."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import get_current_user
from app.database.models import UserRecord
from app.engine.project_memory import (
    CandidateNotFoundError,
    InvalidCandidateActionError,
    InvalidProjectMemoryError,
    MemoryNotFoundError,
    ProjectMemoryService,
    ProjectNotFoundError,
)
from app.schemas.candidate_memory import (
    CandidateApprovalRequest,
    CandidateApprovalResponse,
    CandidateMemory,
    CandidateRejectionRequest,
    ExtractCandidatesRequest,
)
from app.schemas.project import (
    Project,
    ProjectContext,
    ProjectCreate,
    ProjectMemory,
    ProjectMemoryCreate,
    ProjectMemoryUpdate,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

_project_memory_service: ProjectMemoryService | None = None


def get_project_service() -> ProjectMemoryService:
    """Dependency provider for ProjectMemoryService with singleton reuse."""
    global _project_memory_service
    if _project_memory_service is None:
        _project_memory_service = ProjectMemoryService()
    return _project_memory_service


@router.post(
    "",
    response_model=Project,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new development project",
)
async def create_project(
    request: ProjectCreate,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> Project:
    """Create a new project context for long-term prompt compilation."""
    try:
        return await service.create_project_async(
            name=request.name,
            description=request.description,
            root_path=request.root_path,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create project: {exc}",
        ) from exc


@router.get(
    "",
    response_model=list[Project],
    summary="List development projects",
)
async def list_projects(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> list[Project]:
    """Retrieve a list of development projects owned by the authenticated user."""
    return service.list_projects(limit=limit, offset=offset, user_id=current_user.id)


@router.get(
    "/{project_id}",
    response_model=Project,
    summary="Get project by ID",
)
async def get_project(
    project_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> Project:
    """Retrieve project metadata by project_id."""
    try:
        return await service.get_project_async(project_id, user_id=current_user.id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{project_id}",
    response_model=Project,
    summary="Update project metadata",
)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> Project:
    """Update project name, description, or root_path."""
    try:
        return await service.update_project_async(
            project_id=project_id,
            name=request.name,
            description=request.description,
            root_path=request.root_path,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update project: {exc}",
        ) from exc


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a project and all associated data",
)
async def delete_project(
    project_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> dict[str, Any]:
    """Delete a project along with its memories, candidates, and vector knowledge base."""
    try:
        success = await service.delete_project_async(project_id, user_id=current_user.id)
        return {"deleted": success, "project_id": project_id}
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/memories",
    response_model=ProjectMemory,
    status_code=status.HTTP_201_CREATED,
    summary="Add a memory item to a project",
)
async def add_project_memory(
    project_id: str,
    request: ProjectMemoryCreate,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> ProjectMemory:
    """Add a structured memory or context statement to a project."""
    try:
        return await service.add_memory_async(
            project_id=project_id,
            category=request.category,
            content=request.content,
            source=request.source,
            confidence=request.confidence,
            status=request.status,
            metadata=request.metadata,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidProjectMemoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/memories",
    response_model=list[ProjectMemory],
    summary="List memories for a project",
)
async def list_project_memories(
    project_id: str,
    category: str | None = Query(default=None),
    source: str | None = Query(default=None),
    status_filter: str | None = Query(default="active", alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> list[ProjectMemory]:
    """Retrieve memory items belonging to a project."""
    try:
        return service.list_memories(
            project_id=project_id,
            category=category,
            source=source,
            status=status_filter,
            limit=limit,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/memories/{memory_id}",
    response_model=ProjectMemory,
    summary="Get memory item by ID",
)
async def get_project_memory(
    project_id: str,
    memory_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> ProjectMemory:
    """Retrieve a specific memory item belonging to a project."""
    try:
        await service.get_project_async(project_id, user_id=current_user.id)
        memory = await service.get_memory_async(memory_id, user_id=current_user.id)
        if memory.project_id != project_id:
            raise MemoryNotFoundError(f"Memory item '{memory_id}' does not belong to project '{project_id}'.")
        return memory
    except (ProjectNotFoundError, MemoryNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{project_id}/memories/{memory_id}",
    response_model=ProjectMemory,
    summary="Update a project memory item",
)
async def update_project_memory(
    project_id: str,
    memory_id: str,
    request: ProjectMemoryUpdate,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> ProjectMemory:
    """Update category, content, status, confidence, or metadata of a memory item."""
    try:
        await service.get_project_async(project_id, user_id=current_user.id)
        memory = await service.get_memory_async(memory_id, user_id=current_user.id)
        if memory.project_id != project_id:
            raise MemoryNotFoundError(f"Memory item '{memory_id}' does not belong to project '{project_id}'.")
        return await service.update_memory_async(
            memory_id=memory_id,
            category=request.category,
            content=request.content,
            source=request.source,
            confidence=request.confidence,
            status=request.status,
            metadata=request.metadata,
            user_id=current_user.id,
        )
    except (ProjectNotFoundError, MemoryNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidProjectMemoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{project_id}/memories/{memory_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a project memory item",
)
async def delete_project_memory(
    project_id: str,
    memory_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> dict[str, Any]:
    """Delete a specific project memory item."""
    try:
        await service.get_project_async(project_id, user_id=current_user.id)
        memory = await service.get_memory_async(memory_id, user_id=current_user.id)
        if memory.project_id != project_id:
            raise MemoryNotFoundError(f"Memory item '{memory_id}' does not belong to project '{project_id}'.")
        success = await service.delete_memory_async(memory_id, user_id=current_user.id)
        return {"deleted": success, "project_id": project_id, "memory_id": memory_id}
    except (ProjectNotFoundError, MemoryNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/context",
    response_model=ProjectContext,
    summary="Get aggregated project context",
)
async def get_project_context(
    project_id: str,
    status_filter: str | None = Query(default="active", alias="status"),
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> ProjectContext:
    """Retrieve aggregated, deterministically-sorted project context."""
    try:
        return await service.get_project_context_async(
            project_id=project_id,
            status_filter=status_filter,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# -----------------------------------------------------------------------------
# Candidate Memory Endpoints (Task 18)
# -----------------------------------------------------------------------------


@router.post(
    "/{project_id}/memory-candidates",
    response_model=list[CandidateMemory],
    status_code=status.HTTP_201_CREATED,
    summary="Extract candidate memories from interaction data",
)
async def extract_memory_candidates(
    project_id: str,
    request: ExtractCandidatesRequest,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> list[CandidateMemory]:
    """Extract candidate project memory proposals from interaction text and confirmed requirements.

    Candidate memories represent proposed long-term project knowledge and are NOT automatically
    saved as active ProjectMemory until explicitly confirmed by the user.
    """
    try:
        return await service.extract_candidates_async(
            project_id=project_id,
            user_input=request.input,
            confirmed_requirements=request.confirmed_requirements,
            persist_candidates=True,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract candidate memories: {exc}",
        ) from exc


@router.get(
    "/{project_id}/memory-candidates",
    response_model=list[CandidateMemory],
    summary="List candidate memories for a project",
)
async def list_memory_candidates(
    project_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> list[CandidateMemory]:
    """Retrieve proposed candidate memories for a project, optionally filtered by status."""
    try:
        return await service.list_candidates_async(
            project_id=project_id,
            status=status_filter,
            limit=limit,
            offset=offset,
            user_id=current_user.id,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{project_id}/memory-candidates/{candidate_id}",
    response_model=CandidateMemory,
    summary="Get candidate memory by ID",
)
async def get_memory_candidate(
    project_id: str,
    candidate_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> CandidateMemory:
    """Retrieve details of a specific candidate memory proposal."""
    try:
        # Verify project exists and belongs to current_user
        await service.get_project_async(project_id, user_id=current_user.id)
        candidate = await service.get_candidate_async(candidate_id, user_id=current_user.id)
        if candidate.project_id != project_id:
            raise CandidateNotFoundError(f"Candidate memory '{candidate_id}' does not belong to project '{project_id}'.")
        return candidate
    except (ProjectNotFoundError, CandidateNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/memory-candidates/{candidate_id}/approve",
    response_model=CandidateApprovalResponse,
    summary="Approve candidate memory proposal",
)
async def approve_memory_candidate(
    project_id: str,
    candidate_id: str,
    request: CandidateApprovalRequest | None = None,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> CandidateApprovalResponse:
    """Approve an unconfirmed candidate memory, persisting it as an active ProjectMemory.

    If the candidate had a conflict and supersede_conflicting=True was supplied,
    the conflicting existing memory is marked as superseded.
    """
    try:
        # Verify project exists and belongs to current_user
        await service.get_project_async(project_id, user_id=current_user.id)
        candidate = await service.get_candidate_async(candidate_id, user_id=current_user.id)
        if candidate.project_id != project_id:
            raise CandidateNotFoundError(f"Candidate memory '{candidate_id}' does not belong to project '{project_id}'.")

        req = request or CandidateApprovalRequest()
        return await service.approve_candidate_async(
            candidate_id=candidate_id,
            supersede_conflicting=req.supersede_conflicting,
            custom_content=req.custom_content,
            user_id=current_user.id,
        )
    except (ProjectNotFoundError, CandidateNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidCandidateActionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidProjectMemoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post(
    "/{project_id}/memory-candidates/{candidate_id}/reject",
    response_model=CandidateMemory,
    summary="Reject candidate memory proposal",
)
async def reject_memory_candidate(
    project_id: str,
    candidate_id: str,
    request: CandidateRejectionRequest | None = None,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> CandidateMemory:
    """Reject an unconfirmed candidate memory proposal without persisting it as ProjectMemory."""
    try:
        # Verify project exists and belongs to current_user
        await service.get_project_async(project_id, user_id=current_user.id)
        candidate = await service.get_candidate_async(candidate_id, user_id=current_user.id)
        if candidate.project_id != project_id:
            raise CandidateNotFoundError(f"Candidate memory '{candidate_id}' does not belong to project '{project_id}'.")

        reason = request.reason if request else None
        return await service.reject_candidate_async(
            candidate_id=candidate_id,
            reason=reason,
            user_id=current_user.id,
        )
    except (ProjectNotFoundError, CandidateNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{project_id}/memory-candidates/{candidate_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a candidate memory proposal",
)
async def delete_memory_candidate(
    project_id: str,
    candidate_id: str,
    current_user: UserRecord = Depends(get_current_user),
    service: ProjectMemoryService = Depends(get_project_service),
) -> dict[str, Any]:
    """Delete a specific candidate memory proposal record."""
    try:
        await service.get_project_async(project_id, user_id=current_user.id)
        candidate = await service.get_candidate_async(candidate_id, user_id=current_user.id)
        if candidate.project_id != project_id:
            raise CandidateNotFoundError(f"Candidate memory '{candidate_id}' does not belong to project '{project_id}'.")
        success = await service.delete_candidate_async(candidate_id, user_id=current_user.id)
        return {"deleted": success, "project_id": project_id, "candidate_id": candidate_id}
    except (ProjectNotFoundError, CandidateNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
