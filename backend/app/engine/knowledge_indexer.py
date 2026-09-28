"""Knowledge indexing service orchestrating normalization, hashing, chunking, embedding, and storage."""

import logging
from typing import Any

from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.database.repositories import KnowledgeRepository, ProjectRepository
from app.engine.chunker import TextChunker, compute_content_hash, normalize_text
from app.engine.project_memory import ProjectNotFoundError
from app.schemas.knowledge import KnowledgeIndexResponse, KnowledgeSource

logger = logging.getLogger(__name__)


class KnowledgeIndexingError(Exception):
    """Raised when knowledge indexing encounters a fatal processing failure."""


class KnowledgeIndexerService:
    """Service handling text normalization, deterministic chunking, embedding, and vector persistence."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        knowledge_repository: KnowledgeRepository,
        embedding_provider: EmbeddingProvider | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self._project_repo = project_repository
        self._knowledge_repo = knowledge_repository
        self._embedding_provider = embedding_provider or get_embedding_provider()
        self._chunker = chunker or TextChunker()

    async def index_content(
        self,
        project_id: str,
        source_type: str,
        source_name: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeIndexResponse:
        """Process, chunk, embed, and index a text document or code snippet into the vector store."""
        # 1. Validate project existence
        project = self._project_repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(f"Project '{project_id}' not found")

        # 2. Normalize content
        normalized = normalize_text(content)
        if not normalized:
            raise ValueError("Content must not be empty or whitespace only")

        # 3. Calculate deterministic content hash
        content_hash = compute_content_hash(normalized)

        # 4. Check for duplicate content in this project to prevent unnecessary embedding computation
        existing_by_hash = self._knowledge_repo.get_source_by_hash(project_id, content_hash)
        if existing_by_hash is not None:
            logger.info(
                f"Source with content hash {content_hash} already exists as '{existing_by_hash.source_name}' in project {project_id}. Skipping re-embedding."
            )
            return KnowledgeIndexResponse(
                project_id=project_id,
                source_id=existing_by_hash.source_id,
                source_name=existing_by_hash.source_name,
                source_type=existing_by_hash.source_type,
                content_hash=content_hash,
                chunk_count=existing_by_hash.chunk_count,
                is_duplicate=True,
                message=f"Source with identical content already indexed as '{existing_by_hash.source_name}'",
            )

        # 5. If source with same name already exists in project, clean up old version before indexing new content
        existing_by_name = self._knowledge_repo.get_source_by_name(project_id, source_name)
        if existing_by_name is not None:
            logger.info(
                f"Source name '{source_name}' exists in project {project_id} with different content hash. Updating source."
            )
            self._knowledge_repo.delete_source(existing_by_name.source_id)

        # 6. Chunk text
        chunks = self._chunker.chunk_text(
            normalized,
            source_name=source_name,
            source_type=source_type,
            base_metadata=metadata,
        )
        if not chunks:
            raise ValueError("No valid chunks could be produced from content")

        # 7. Generate embeddings in batch
        texts_to_embed = [c.content for c in chunks]
        embeddings = await self._embedding_provider.embed_batch(texts_to_embed)

        if len(embeddings) != len(chunks):
            raise KnowledgeIndexingError(
                f"Embedding count ({len(embeddings)}) does not match chunk count ({len(chunks)})"
            )

        # 8. Create source record in database
        source = self._knowledge_repo.create_source(
            project_id=project_id,
            source_type=source_type,
            source_name=source_name,
            content_hash=content_hash,
            metadata=metadata,
        )

        # 9. Store chunks and vector embeddings
        self._knowledge_repo.store_chunks_with_vectors(
            source_id=source.source_id,
            project_id=project_id,
            chunks_data=chunks,
            embeddings=embeddings,
        )

        logger.info(
            f"Successfully indexed source '{source_name}' ({len(chunks)} chunks) into project {project_id}."
        )

        return KnowledgeIndexResponse(
            project_id=project_id,
            source_id=source.source_id,
            source_name=source_name,
            source_type=source_type,
            content_hash=content_hash,
            chunk_count=len(chunks),
            is_duplicate=False,
            message="Content successfully indexed into vector knowledge base",
        )
