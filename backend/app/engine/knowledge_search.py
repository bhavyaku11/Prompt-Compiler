"""Semantic search service performing vector similarity retrieval over project knowledge."""

import logging
from typing import Any

from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.config import settings
from app.database.repositories import KnowledgeRepository, ProjectRepository
from app.engine.project_memory import ProjectNotFoundError
from app.schemas.knowledge import KnowledgeSearchResponse, KnowledgeSearchResult

logger = logging.getLogger(__name__)


class KnowledgeSearchService:
    """Service handling query embedding and scoped KNN vector retrieval over project knowledge."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        knowledge_repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._project_repo = project_repository
        self._knowledge_repo = knowledge_repository
        self._embedding_provider = embedding_provider or get_embedding_provider()

    async def search(
        self,
        project_id: str,
        query: str,
        top_k: int | None = None,
    ) -> KnowledgeSearchResponse:
        """Search knowledge base chunks for a specific project by vector cosine similarity."""
        # 1. Validate project existence
        project = self._project_repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

        # 2. Validate query string
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Query must not be empty or whitespace only")

        # 3. Validate top_k
        k = top_k if top_k is not None else settings.KNOWLEDGE_SEARCH_TOP_K
        if not (1 <= k <= 50):
            raise ValueError(f"top_k must be between 1 and 50, got {k}")

        # 4. Generate query embedding vector
        query_embedding = await self._embedding_provider.embed_text(normalized_query)

        # 5. Search similar chunks scoped to project_id
        raw_results = self._knowledge_repo.search_similar_chunks(
            project_id=project_id,
            query_embedding=query_embedding,
            top_k=k,
        )

        # 6. Format search results
        results = [
            KnowledgeSearchResult(
                chunk_id=r["chunk_id"],
                source_id=r["source_id"],
                source_name=r["source_name"],
                source_type=r["source_type"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in raw_results
        ]

        logger.debug(
            f"Query '{normalized_query}' in project {project_id} returned {len(results)} chunks."
        )

        return KnowledgeSearchResponse(
            project_id=project_id,
            query=normalized_query,
            top_k=k,
            metric="cosine_similarity",
            total_results=len(results),
            results=results,
        )
