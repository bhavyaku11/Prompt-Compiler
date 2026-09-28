"""API router for project vector knowledge base indexing, semantic search, and source management."""

import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.embeddings import (
    EmbeddingConnectionError,
    EmbeddingError,
    EmbeddingModelUnavailableError,
    EmbeddingProvider,
    get_embedding_provider,
)
from app.auth import get_current_user
from app.database.models import UserRecord
from app.database.repositories import KnowledgeRepository, ProjectRepository
from app.engine.chunker import TextChunker
from app.engine.document_ingestion import (
    DocumentIngestionError,
    DocumentIngestionService,
    PathSecurityError,
    ProjectRootNotConfiguredError,
)
from app.engine.knowledge_indexer import KnowledgeIndexerService
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.project_memory import ProjectNotFoundError
from app.schemas.knowledge import (
    BatchDocumentIngestionResponse,
    DocumentIngestionResult,
    IngestDirectoryRequest,
    IngestFileRequest,
    KnowledgeIndexRequest,
    KnowledgeIndexResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSourceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/knowledge", tags=["knowledge"])


def get_project_repository() -> ProjectRepository:
    """Dependency provider for ProjectRepository."""
    return ProjectRepository()


def get_knowledge_repository() -> KnowledgeRepository:
    """Dependency provider for KnowledgeRepository."""
    return KnowledgeRepository()


def get_knowledge_indexer(
    project_repo: ProjectRepository = Depends(get_project_repository),
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repository),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> KnowledgeIndexerService:
    """Dependency provider for KnowledgeIndexerService."""
    return KnowledgeIndexerService(
        project_repository=project_repo,
        knowledge_repository=knowledge_repo,
        embedding_provider=embedding_provider,
        chunker=TextChunker(),
    )


def get_document_ingestion_service(
    project_repo: ProjectRepository = Depends(get_project_repository),
    indexer: KnowledgeIndexerService = Depends(get_knowledge_indexer),
) -> DocumentIngestionService:
    """Dependency provider for DocumentIngestionService."""
    return DocumentIngestionService(
        indexer_service=indexer,
        project_repository=project_repo,
    )


def get_knowledge_searcher(
    project_repo: ProjectRepository = Depends(get_project_repository),
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repository),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> KnowledgeSearchService:
    """Dependency provider for KnowledgeSearchService."""
    return KnowledgeSearchService(
        project_repository=project_repo,
        knowledge_repository=knowledge_repo,
        embedding_provider=embedding_provider,
    )


@router.post(
    "/index",
    response_model=KnowledgeIndexResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index document or code snippet into project knowledge base",
)
async def index_knowledge(
    project_id: str,
    request: KnowledgeIndexRequest,
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    indexer: KnowledgeIndexerService = Depends(get_knowledge_indexer),
) -> KnowledgeIndexResponse:
    """Chunk, embed, and store knowledge content in project vector store."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    try:
        return await indexer.index_content(
            project_id=project_id,
            source_type=request.source_type,
            source_name=request.source_name,
            content=request.content,
            metadata=request.metadata,
        )
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
    except EmbeddingModelUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)) from err
    except EmbeddingConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err
    except EmbeddingError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Perform vector semantic search over project knowledge chunks",
)
async def search_knowledge(
    project_id: str,
    request: KnowledgeSearchRequest,
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    searcher: KnowledgeSearchService = Depends(get_knowledge_searcher),
) -> KnowledgeSearchResponse:
    """Execute vector cosine-similarity KNN search scoped to project_id."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    try:
        return await searcher.search(
            project_id=project_id,
            query=request.query,
            top_k=request.top_k,
        )
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
    except EmbeddingModelUnavailableError as err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(err)) from err
    except EmbeddingConnectionError as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err
    except EmbeddingError as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err)) from err


@router.get(
    "/sources",
    response_model=list[KnowledgeSourceResponse],
    status_code=status.HTTP_200_OK,
    summary="List all indexed knowledge sources for a project",
)
def list_knowledge_sources(
    project_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repository),
) -> list[KnowledgeSourceResponse]:
    """Retrieve list of indexed sources belonging to project_id."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    sources = knowledge_repo.list_sources(project_id=project_id, limit=limit, offset=offset, user_id=current_user.id)
    return [
        KnowledgeSourceResponse(
            source_id=s.source_id,
            project_id=s.project_id,
            source_type=s.source_type,
            source_name=s.source_name,
            content_hash=s.content_hash,
            chunk_count=s.chunk_count,
            metadata=s.metadata,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sources
    ]


@router.delete(
    "/sources/{source_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an indexed knowledge source and its vector chunks",
)
def delete_knowledge_source(
    project_id: str,
    source_id: str,
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    knowledge_repo: KnowledgeRepository = Depends(get_knowledge_repository),
) -> dict[str, Any]:
    """Delete knowledge source and all its associated chunks and vector embeddings."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    source = knowledge_repo.get_source(source_id, user_id=current_user.id)
    if source is None or source.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Knowledge source '{source_id}' not found in project '{project_id}'",
        )

    success = knowledge_repo.delete_source(source_id, user_id=current_user.id)
    return {"deleted": success, "source_id": source_id, "project_id": project_id}


@router.post(
    "/ingest/file",
    response_model=DocumentIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="Ingest a single local document file into project knowledge base",
)
async def ingest_file(
    project_id: str,
    request: IngestFileRequest,
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> DocumentIngestionResult:
    """Validate, read, chunk, embed, and index a single supported local document file."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    try:
        return await service.ingest_file_async(
            project_id=project_id,
            file_path_str=request.file_path,
            project_root=request.project_root,
        )
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ProjectRootNotConfiguredError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
    except (DocumentIngestionError, PathSecurityError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.post(
    "/ingest/directory",
    response_model=BatchDocumentIngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Recursively discover and ingest supported documents in a project directory",
)
async def ingest_directory(
    project_id: str,
    request: IngestDirectoryRequest | None = None,
    current_user: UserRecord = Depends(get_current_user),
    project_repo: ProjectRepository = Depends(get_project_repository),
    service: DocumentIngestionService = Depends(get_document_ingestion_service),
) -> BatchDocumentIngestionResponse:
    """Discover, parse, chunk, embed, and index all supported files within project directory."""
    project = project_repo.get(project_id, user_id=current_user.id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    req = request or IngestDirectoryRequest()
    try:
        return await service.ingest_directory_async(
            project_id=project_id,
            directory_path_str=req.directory_path,
            project_root=req.project_root,
            recursive=req.recursive,
        )
    except ProjectNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err)) from err
    except ProjectRootNotConfiguredError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
    except (DocumentIngestionError, PathSecurityError) as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
