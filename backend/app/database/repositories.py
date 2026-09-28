import time
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

from sqlalchemy import delete, desc, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models import (
    CandidateMemoryRecord,
    CompilationRecord,
    InterviewSessionRecord,
    KnowledgeChunkRecord,
    KnowledgeSourceRecord,
    ProjectMemoryRecord,
    ProjectRecord,
    RequirementAnalysisRecord,
    UserRecord,
)
from app.database.session import get_session_factory
from app.schemas.auth import User
from app.schemas.candidate_memory import (
    CandidateMemory,
    CandidateMemoryCreate,
    CandidateMemoryUpdate,
)
from app.schemas.interview import InterviewQuestion
from app.schemas.knowledge import (
    KnowledgeChunk,
    KnowledgeSource,
)
from app.schemas.project import (
    CATEGORY_PRIORITY,
    SOURCE_TRUST_PRIORITY,
    Project,
    ProjectContext,
    ProjectCreate,
    ProjectMemory,
    ProjectMemoryCreate,
    ProjectMemoryUpdate,
    ProjectUpdate,
)


class UserRepository:
    """Repository managing persistent user identities in SQLite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)

    def _to_domain(self, record: UserRecord) -> User:
        """Convert UserRecord to domain User model."""
        return User(
            id=record.id,
            clerk_user_id=record.clerk_user_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get_by_id(self, user_id: int) -> UserRecord | None:
        """Retrieve a user by local integer ID."""
        with self._session_factory() as db:
            stmt = select(UserRecord).where(UserRecord.id == user_id)
            return db.scalars(stmt).first()

    def get_by_clerk_id(self, clerk_user_id: str) -> UserRecord | None:
        """Retrieve a user by Clerk user ID."""
        with self._session_factory() as db:
            stmt = select(UserRecord).where(UserRecord.clerk_user_id == clerk_user_id)
            return db.scalars(stmt).first()

    def get_or_create(self, clerk_user_id: str) -> UserRecord:
        """Concurrency-safe get or create for Clerk user ID."""
        now = time.time()
        with self._session_factory() as db:
            record = db.scalars(
                select(UserRecord).where(UserRecord.clerk_user_id == clerk_user_id)
            ).first()
            if record is not None:
                return record

            try:
                record = UserRecord(
                    clerk_user_id=clerk_user_id,
                    created_at=now,
                    updated_at=now,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                return record
            except IntegrityError:
                db.rollback()
                record = db.scalars(
                    select(UserRecord).where(UserRecord.clerk_user_id == clerk_user_id)
                ).first()
                if record is not None:
                    return record
                raise


class InterviewSessionRepository:
    """Repository managing persistent interview sessions in SQLite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)

    def create(self, session_data: Any, ttl_seconds: float | None = None) -> Any:
        """Alias for save."""
        return self.save(session_data, ttl_seconds)

    def get_by_session_id(self, session_id: str, check_ttl: bool = True) -> Any | None:
        """Alias for get."""
        return self.get(session_id, check_ttl)

    def update(self, session_data: Any, ttl_seconds: float | None = None) -> Any:
        """Alias for save."""
        return self.save(session_data, ttl_seconds)

    def cleanup_expired(self, current_time: float | None = None) -> int:
        """Alias for delete_expired."""
        return self.delete_expired(current_time)

    def _to_record(
        self,
        session_data: Any,
        ttl_seconds: float,
    ) -> InterviewSessionRecord:
        """Convert domain InterviewSession to SQLAlchemy InterviewSessionRecord."""
        current_time = time.time()
        return InterviewSessionRecord(
            session_id=session_data.session_id,
            original_input=session_data.original_input,
            status=session_data.status,
            turn=session_data.turn,
            current_analysis=session_data.current_analysis.model_dump(),
            questions=[q.model_dump() for q in session_data.questions],
            answers=dict(session_data.answers),
            unresolved_topics=list(session_data.unresolved_topics),
            asked_topics=list(session_data.asked_topics),
            project_id=getattr(session_data, "project_id", None),
            user_id=getattr(session_data, "user_id", None),
            target_agent=getattr(session_data, "target_agent", "generic") or "generic",
            enable_knowledge_retrieval=bool(getattr(session_data, "enable_knowledge_retrieval", True)),
            created_at=session_data.created_at,
            updated_at=session_data.updated_at,
            expires_at=session_data.updated_at + ttl_seconds,
        )

    def _to_domain(self, record: InterviewSessionRecord) -> Any:
        """Convert SQLAlchemy InterviewSessionRecord to domain InterviewSession."""
        # Import lazily to avoid circular dependencies
        from app.engine.interviewer import InterviewSession
        from app.engine.requirements import RequirementAnalysis

        return InterviewSession(
            session_id=record.session_id,
            original_input=record.original_input,
            current_analysis=RequirementAnalysis(**record.current_analysis),
            questions=[InterviewQuestion(**q) for q in record.questions],
            answers=dict(record.answers),
            turn=record.turn,
            unresolved_topics=list(record.unresolved_topics),
            asked_topics=list(record.asked_topics),
            project_id=record.project_id,
            user_id=record.user_id,
            target_agent=getattr(record, "target_agent", "generic") or "generic",
            enable_knowledge_retrieval=bool(getattr(record, "enable_knowledge_retrieval", True)),
            status=record.status,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def get(self, session_id: str, check_ttl: bool = True, user_id: int | None = None) -> Any | None:
        """Retrieve an interview session by session_id, returning None if expired or not found."""
        with self._session_factory() as db:
            stmt = select(InterviewSessionRecord).where(InterviewSessionRecord.session_id == session_id)
            if user_id is not None:
                stmt = stmt.where(InterviewSessionRecord.user_id == user_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None

            if check_ttl and time.time() > record.expires_at:
                db.delete(record)
                db.commit()
                return None

            return self._to_domain(record)

    def save(self, session_data: Any, ttl_seconds: float | None = None, user_id: int | None = None) -> Any:
        """Insert or update an interview session in SQLite."""
        ttl = ttl_seconds or settings.interview_session_ttl_seconds
        session_data.updated_at = time.time()
        if user_id is not None:
            session_data.user_id = user_id

        with self._session_factory() as db:
            stmt = select(InterviewSessionRecord).where(InterviewSessionRecord.session_id == session_data.session_id)
            existing = db.scalars(stmt).first()

            if existing is None:
                record = self._to_record(session_data, ttl)
                db.add(record)
            else:
                existing.status = session_data.status
                existing.turn = session_data.turn
                existing.current_analysis = session_data.current_analysis.model_dump()
                existing.questions = [q.model_dump() for q in session_data.questions]
                existing.answers = dict(session_data.answers)
                existing.unresolved_topics = list(session_data.unresolved_topics)
                existing.asked_topics = list(session_data.asked_topics)
                existing.project_id = getattr(session_data, "project_id", None)
                if getattr(session_data, "user_id", None) is not None:
                    existing.user_id = session_data.user_id
                existing.updated_at = session_data.updated_at
                existing.expires_at = session_data.updated_at + ttl

            db.commit()
            return session_data

    def delete(self, session_id: str, user_id: int | None = None) -> bool:
        """Delete an interview session by session_id."""
        with self._session_factory() as db:
            stmt = delete(InterviewSessionRecord).where(InterviewSessionRecord.session_id == session_id)
            if user_id is not None:
                stmt = stmt.where(InterviewSessionRecord.user_id == user_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount > 0

    def delete_expired(self, current_time: float | None = None) -> int:
        """Remove all expired interview sessions from the database."""
        now = current_time or time.time()
        with self._session_factory() as db:
            stmt = delete(InterviewSessionRecord).where(InterviewSessionRecord.expires_at < now)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount


class RequirementAnalysisRepository:
    """Repository managing persistent requirement analysis records."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)

    def save(
        self,
        analysis: RequirementAnalysis,
        original_input: str = "",
        interview_session_id: str | None = None,
    ) -> RequirementAnalysisRecord:
        """Persist a requirement analysis record to SQLite."""
        record = RequirementAnalysisRecord(
            analysis_id=str(uuid.uuid4()),
            interview_session_id=interview_session_id,
            original_input=original_input or analysis.intent,
            intent=analysis.intent,
            task_type=analysis.task_type,
            domain=analysis.domain,
            confirmed_requirements=list(analysis.confirmed_requirements),
            missing_information=list(analysis.missing_information),
            constraints=list(analysis.constraints),
            assumptions=list(analysis.assumptions),
            created_at=time.time(),
            updated_at=time.time(),
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

    def get_by_session_id(self, interview_session_id: str) -> RequirementAnalysis | None:
        """Retrieve the latest requirement analysis for an interview session."""
        with self._session_factory() as db:
            stmt = (
                select(RequirementAnalysisRecord)
                .where(RequirementAnalysisRecord.interview_session_id == interview_session_id)
                .order_by(desc(RequirementAnalysisRecord.id))
            )
            record = db.scalars(stmt).first()
            if record is None:
                return None
            from app.engine.requirements import RequirementAnalysis

            return RequirementAnalysis(
                intent=record.intent,
                task_type=record.task_type,
                domain=record.domain,
                confirmed_requirements=list(record.confirmed_requirements),
                missing_information=list(record.missing_information),
                constraints=list(record.constraints),
                assumptions=list(record.assumptions),
            )


class CompilationRepository:
    """Repository managing persistent compilation records."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)

    def save(
        self,
        input_text: str,
        compiled_prompt: str,
        task_type: str | None = None,
        template_name: str | None = None,
        requirements_summary: dict[str, Any] | None = None,
        validation_summary: dict[str, Any] | None = None,
        refinement_attempts: int = 0,
        interview_session_id: str | None = None,
        project_id: str | None = None,
        user_id: int | None = None,
        target_agent: str = "generic",
        knowledge_references: list[dict[str, Any]] | None = None,
    ) -> CompilationRecord:
        """Persist a compilation record to SQLite."""
        record = CompilationRecord(
            compilation_id=str(uuid.uuid4()),
            interview_session_id=interview_session_id,
            project_id=project_id,
            user_id=user_id,
            target_agent=target_agent,
            input_text=input_text,
            compiled_prompt=compiled_prompt,
            task_type=task_type,
            template_name=template_name,
            requirements_summary=requirements_summary,
            validation_summary=validation_summary,
            refinement_attempts=refinement_attempts,
            knowledge_references=knowledge_references,
            created_at=time.time(),
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

    def get_by_id(self, identifier: str | int, user_id: int | None = None) -> CompilationRecord | None:
        """Retrieve a compilation record by integer id or string compilation_id."""
        with self._session_factory() as db:
            if isinstance(identifier, int):
                stmt = select(CompilationRecord).where(CompilationRecord.id == identifier)
            elif str(identifier).isdigit():
                stmt = select(CompilationRecord).where(
                    (CompilationRecord.id == int(identifier)) | (CompilationRecord.compilation_id == str(identifier))
                )
            else:
                stmt = select(CompilationRecord).where(CompilationRecord.compilation_id == str(identifier))
            if user_id is not None:
                stmt = stmt.where(CompilationRecord.user_id == user_id)
            return db.scalars(stmt).first()

    def get_by_session_id(self, interview_session_id: str, user_id: int | None = None) -> CompilationRecord | None:
        """Retrieve the compilation record for an interview session."""
        with self._session_factory() as db:
            stmt = (
                select(CompilationRecord)
                .where(CompilationRecord.interview_session_id == interview_session_id)
            )
            if user_id is not None:
                stmt = stmt.where(CompilationRecord.user_id == user_id)
            stmt = stmt.order_by(desc(CompilationRecord.id))
            return db.scalars(stmt).first()

    def list_recent(self, limit: int = 20, user_id: int | None = None) -> list[CompilationRecord]:
        """List recent compilation records ordered by newest first."""
        with self._session_factory() as db:
            stmt = select(CompilationRecord)
            if user_id is not None:
                stmt = stmt.where(CompilationRecord.user_id == user_id)
            stmt = stmt.order_by(desc(CompilationRecord.id)).limit(limit)
            return list(db.scalars(stmt).all())

    def list_by_project(self, project_id: str, limit: int = 100, user_id: int | None = None) -> list[CompilationRecord]:
        """List compilation records for a specific project ordered by newest first."""
        with self._session_factory() as db:
            stmt = (
                select(CompilationRecord)
                .where(CompilationRecord.project_id == project_id)
            )
            if user_id is not None:
                stmt = stmt.where(CompilationRecord.user_id == user_id)
            stmt = stmt.order_by(desc(CompilationRecord.id)).limit(limit)
            return list(db.scalars(stmt).all())


class ProjectRepository:
    """Repository managing persistent development projects in SQLite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)

    def _to_domain(self, record: ProjectRecord) -> Project:
        """Convert ProjectRecord ORM model to domain Project schema."""
        return Project(
            project_id=record.project_id,
            name=record.name,
            description=record.description,
            root_path=record.root_path,
            user_id=record.user_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def create(
        self,
        project_data: ProjectCreate,
        project_id: str | None = None,
        user_id: int | None = None,
    ) -> Project:
        """Persist a new project to SQLite."""
        pid = project_id or str(uuid.uuid4())
        now = time.time()
        record = ProjectRecord(
            project_id=pid,
            name=project_data.name,
            description=project_data.description,
            root_path=project_data.root_path,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def get(self, project_id: str, user_id: int | None = None) -> Project | None:
        """Retrieve a project by project_id, optionally filtered by user ownership."""
        with self._session_factory() as db:
            stmt = select(ProjectRecord).where(ProjectRecord.project_id == project_id)
            if user_id is not None:
                stmt = stmt.where(ProjectRecord.user_id == user_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._to_domain(record)

    def get_by_name(self, name: str, user_id: int | None = None) -> Project | None:
        """Retrieve a project by name, optionally filtered by user ownership."""
        with self._session_factory() as db:
            stmt = select(ProjectRecord).where(ProjectRecord.name == name)
            if user_id is not None:
                stmt = stmt.where(ProjectRecord.user_id == user_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._to_domain(record)

    def update(
        self,
        project_id: str,
        update_data: ProjectUpdate,
        user_id: int | None = None,
    ) -> Project | None:
        """Update an existing project, validating user ownership if provided."""
        with self._session_factory() as db:
            stmt = select(ProjectRecord).where(ProjectRecord.project_id == project_id)
            if user_id is not None:
                stmt = stmt.where(ProjectRecord.user_id == user_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None

            if update_data.name is not None:
                record.name = update_data.name
            if update_data.description is not None:
                record.description = update_data.description
            if update_data.root_path is not None:
                record.root_path = update_data.root_path.strip() if update_data.root_path.strip() else None
            record.updated_at = time.time()

            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def delete(self, project_id: str, user_id: int | None = None) -> bool:
        """Delete a project, associated memories, candidate memories, and knowledge base."""
        # Ownership check
        if user_id is not None:
            existing = self.get(project_id, user_id=user_id)
            if existing is None:
                return False

        with self._session_factory() as db:
            # Delete associated knowledge chunks and vectors
            try:
                chunk_ids_stmt = select(KnowledgeChunkRecord.chunk_id).where(KnowledgeChunkRecord.project_id == project_id)
                chunk_ids = db.scalars(chunk_ids_stmt).all()
                if chunk_ids:
                    for cid in chunk_ids:
                        db.execute(text("DELETE FROM vec_chunks WHERE chunk_id = :cid"), {"cid": cid})
                db.execute(delete(KnowledgeChunkRecord).where(KnowledgeChunkRecord.project_id == project_id))
                db.execute(delete(KnowledgeSourceRecord).where(KnowledgeSourceRecord.project_id == project_id))
            except Exception:
                pass

            # Delete associated candidate memories
            cand_stmt = delete(CandidateMemoryRecord).where(CandidateMemoryRecord.project_id == project_id)
            db.execute(cand_stmt)

            # Delete associated memories
            mem_stmt = delete(ProjectMemoryRecord).where(ProjectMemoryRecord.project_id == project_id)
            db.execute(mem_stmt)

            proj_stmt = delete(ProjectRecord).where(ProjectRecord.project_id == project_id)
            if user_id is not None:
                proj_stmt = proj_stmt.where(ProjectRecord.user_id == user_id)
            result = db.execute(proj_stmt)
            db.commit()
            return result.rowcount > 0

    def list_projects(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[Project]:
        """List all projects ordered by newest updated first, optionally filtered by user."""
        with self._session_factory() as db:
            stmt = select(ProjectRecord)
            if user_id is not None:
                stmt = stmt.where(ProjectRecord.user_id == user_id)
            stmt = stmt.order_by(desc(ProjectRecord.updated_at)).offset(offset).limit(limit)
            records = db.scalars(stmt).all()
            return [self._to_domain(r) for r in records]


class ProjectMemoryRepository:
    """Repository managing persistent project memory items in SQLite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)
        self._project_repo = project_repository or ProjectRepository(session_factory=self._session_factory)

    def _to_domain(self, record: ProjectMemoryRecord) -> ProjectMemory:
        """Convert ProjectMemoryRecord ORM model to domain ProjectMemory schema."""
        return ProjectMemory(
            memory_id=record.memory_id,
            project_id=record.project_id,
            category=record.category,
            content=record.content,
            source=record.source,
            confidence=record.confidence,
            status=record.status,
            metadata=dict(record.metadata_json or {}),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def create(
        self,
        project_id: str,
        memory_data: ProjectMemoryCreate,
        memory_id: str | None = None,
    ) -> ProjectMemory:
        """Persist a new memory item for a project."""
        mid = memory_id or str(uuid.uuid4())
        now = time.time()
        cat_val = memory_data.category.value if hasattr(memory_data.category, "value") else str(memory_data.category)
        src_val = memory_data.source.value if hasattr(memory_data.source, "value") else str(memory_data.source)
        st_val = memory_data.status.value if hasattr(memory_data.status, "value") else str(memory_data.status)

        record = ProjectMemoryRecord(
            memory_id=mid,
            project_id=project_id,
            category=cat_val,
            content=memory_data.content,
            source=src_val,
            confidence=memory_data.confidence,
            status=st_val,
            metadata_json=memory_data.metadata or {},
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def get(self, memory_id: str, user_id: int | None = None) -> ProjectMemory | None:
        """Retrieve a memory item by memory_id, optionally verifying user ownership via project."""
        with self._session_factory() as db:
            if user_id is not None:
                stmt = (
                    select(ProjectMemoryRecord)
                    .join(ProjectRecord, ProjectRecord.project_id == ProjectMemoryRecord.project_id)
                    .where(ProjectMemoryRecord.memory_id == memory_id, ProjectRecord.user_id == user_id)
                )
            else:
                stmt = select(ProjectMemoryRecord).where(ProjectMemoryRecord.memory_id == memory_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._to_domain(record)

    def update(
        self,
        memory_id: str,
        update_data: ProjectMemoryUpdate,
        user_id: int | None = None,
    ) -> ProjectMemory | None:
        """Update an existing memory item with optional user ownership check."""
        if user_id is not None:
            existing_mem = self.get(memory_id, user_id=user_id)
            if existing_mem is None:
                return None

        with self._session_factory() as db:
            stmt = select(ProjectMemoryRecord).where(ProjectMemoryRecord.memory_id == memory_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None

            if update_data.category is not None:
                record.category = (
                    update_data.category.value
                    if hasattr(update_data.category, "value")
                    else str(update_data.category)
                )
            if update_data.content is not None:
                record.content = update_data.content
            if update_data.source is not None:
                record.source = (
                    update_data.source.value
                    if hasattr(update_data.source, "value")
                    else str(update_data.source)
                )
            if update_data.confidence is not None:
                record.confidence = update_data.confidence
            if update_data.status is not None:
                record.status = (
                    update_data.status.value
                    if hasattr(update_data.status, "value")
                    else str(update_data.status)
                )
            if update_data.metadata is not None:
                record.metadata_json = dict(update_data.metadata)
            record.updated_at = time.time()

            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def delete(self, memory_id: str, user_id: int | None = None) -> bool:
        """Delete a memory item by memory_id with optional user ownership check."""
        if user_id is not None:
            existing_mem = self.get(memory_id, user_id=user_id)
            if existing_mem is None:
                return False

        with self._session_factory() as db:
            stmt = delete(ProjectMemoryRecord).where(ProjectMemoryRecord.memory_id == memory_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount > 0

    def list_by_project(
        self,
        project_id: str,
        category: str | None = None,
        source: str | None = None,
        status: str | None = "active",
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[ProjectMemory]:
        """List memory items for a project with optional filtering and ownership check."""
        if user_id is not None:
            proj = self._project_repo.get(project_id, user_id=user_id)
            if proj is None:
                return []

        with self._session_factory() as db:
            stmt = select(ProjectMemoryRecord).where(ProjectMemoryRecord.project_id == project_id)
            if category is not None:
                stmt = stmt.where(ProjectMemoryRecord.category == category)
            if source is not None:
                stmt = stmt.where(ProjectMemoryRecord.source == source)
            if status is not None:
                stmt = stmt.where(ProjectMemoryRecord.status == status)

            stmt = stmt.order_by(ProjectMemoryRecord.id.asc()).offset(offset).limit(limit)
            records = db.scalars(stmt).all()
            return [self._to_domain(r) for r in records]

    def get_project_context(
        self,
        project_id: str,
        status_filter: str | None = "active",
        user_id: int | None = None,
    ) -> ProjectContext | None:
        """Retrieve aggregated project context with strictly deterministic ordering."""
        project = self._project_repo.get(project_id, user_id=user_id)
        if project is None:
            return None

        with self._session_factory() as db:
            stmt = select(ProjectMemoryRecord).where(ProjectMemoryRecord.project_id == project_id)
            if status_filter is not None:
                stmt = stmt.where(ProjectMemoryRecord.status == status_filter)
            records = db.scalars(stmt).all()

        # Convert to domain
        domain_memories = [self._to_domain(r) for r in records]

        # Deterministic sorting helper
        def sort_key(m: ProjectMemory) -> tuple[int, int, float, str]:
            # 1. Category rank
            cat_rank = CATEGORY_PRIORITY.index(m.category) if m.category in CATEGORY_PRIORITY else len(CATEGORY_PRIORITY)
            # 2. Source trust rank
            trust_rank = SOURCE_TRUST_PRIORITY.index(m.source) if m.source in SOURCE_TRUST_PRIORITY else len(SOURCE_TRUST_PRIORITY)
            # 3. Created at timestamp
            # 4. Tie-breaker memory_id
            return (cat_rank, trust_rank, m.created_at, m.memory_id)

        sorted_memories = sorted(domain_memories, key=sort_key)

        # Categorize
        categorized: dict[str, list[ProjectMemory]] = {}
        for m in sorted_memories:
            categorized.setdefault(m.category, []).append(m)

        # Flattened summaries for fast prompt context injection
        active_constraints = [
            m.content
            for m in sorted_memories
            if m.category == "constraint" and m.status == "active"
        ]
        technologies = [
            m.content
            for m in sorted_memories
            if m.category in {"technology", "backend", "frontend", "database"} and m.status == "active"
        ]
        coding_rules = [
            m.content
            for m in sorted_memories
            if m.category == "coding_rule" and m.status == "active"
        ]

        return ProjectContext(
            project=project,
            memories=sorted_memories,
            categorized_memories=categorized,
            active_constraints=active_constraints,
            technologies=technologies,
            coding_rules=coding_rules,
            retrieved_at=time.time(),
        )


class CandidateMemoryRepository:
    """Repository managing persistent candidate memory proposals in SQLite (Task 18)."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)
        self._project_repo = project_repository or ProjectRepository(session_factory=self._session_factory)

    def _to_domain(self, record: CandidateMemoryRecord) -> CandidateMemory:
        """Convert CandidateMemoryRecord ORM model to domain CandidateMemory schema."""
        return CandidateMemory(
            candidate_id=record.candidate_id,
            project_id=record.project_id,
            category=record.category,
            content=record.content,
            source=record.source,
            confidence=record.confidence,
            status=record.status,
            evidence=record.evidence or "",
            conflicting_memory_id=record.conflicting_memory_id,
            conflicting_content=record.conflicting_content,
            metadata=dict(record.metadata_json or {}),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def create(
        self,
        project_id: str,
        candidate_data: CandidateMemoryCreate,
        candidate_id: str | None = None,
    ) -> CandidateMemory:
        """Persist a new candidate memory proposal for a project."""
        cid = candidate_id or str(uuid.uuid4())
        now = time.time()
        cat_val = candidate_data.category.value if hasattr(candidate_data.category, "value") else str(candidate_data.category)
        src_val = candidate_data.source.value if hasattr(candidate_data.source, "value") else str(candidate_data.source)
        st_val = candidate_data.status.value if hasattr(candidate_data.status, "value") else str(candidate_data.status)

        record = CandidateMemoryRecord(
            candidate_id=cid,
            project_id=project_id,
            category=cat_val,
            content=candidate_data.content,
            source=src_val,
            confidence=candidate_data.confidence,
            status=st_val,
            evidence=candidate_data.evidence or "",
            conflicting_memory_id=candidate_data.conflicting_memory_id,
            conflicting_content=candidate_data.conflicting_content,
            metadata_json=candidate_data.metadata or {},
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def get(self, candidate_id: str, user_id: int | None = None) -> CandidateMemory | None:
        """Retrieve a candidate memory item by candidate_id, optionally verifying ownership."""
        with self._session_factory() as db:
            if user_id is not None:
                stmt = (
                    select(CandidateMemoryRecord)
                    .join(ProjectRecord, ProjectRecord.project_id == CandidateMemoryRecord.project_id)
                    .where(CandidateMemoryRecord.candidate_id == candidate_id, ProjectRecord.user_id == user_id)
                )
            else:
                stmt = select(CandidateMemoryRecord).where(CandidateMemoryRecord.candidate_id == candidate_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._to_domain(record)

    def update(
        self,
        candidate_id: str,
        update_data: CandidateMemoryUpdate,
        user_id: int | None = None,
    ) -> CandidateMemory | None:
        """Update an existing candidate memory item with optional ownership check."""
        if user_id is not None:
            existing = self.get(candidate_id, user_id=user_id)
            if existing is None:
                return None

        with self._session_factory() as db:
            stmt = select(CandidateMemoryRecord).where(CandidateMemoryRecord.candidate_id == candidate_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None

            if update_data.category is not None:
                record.category = (
                    update_data.category.value
                    if hasattr(update_data.category, "value")
                    else str(update_data.category)
                )
            if update_data.content is not None:
                record.content = update_data.content
            if update_data.status is not None:
                record.status = (
                    update_data.status.value
                    if hasattr(update_data.status, "value")
                    else str(update_data.status)
                )
            if update_data.confidence is not None:
                record.confidence = update_data.confidence
            if update_data.evidence is not None:
                record.evidence = update_data.evidence
            if update_data.conflicting_memory_id is not None:
                record.conflicting_memory_id = update_data.conflicting_memory_id
            if update_data.conflicting_content is not None:
                record.conflicting_content = update_data.conflicting_content
            if update_data.metadata is not None:
                record.metadata_json = dict(update_data.metadata)
            record.updated_at = time.time()

            db.commit()
            db.refresh(record)
            return self._to_domain(record)

    def delete(self, candidate_id: str, user_id: int | None = None) -> bool:
        """Delete a candidate memory item with optional ownership check."""
        if user_id is not None:
            existing = self.get(candidate_id, user_id=user_id)
            if existing is None:
                return False

        with self._session_factory() as db:
            stmt = delete(CandidateMemoryRecord).where(CandidateMemoryRecord.candidate_id == candidate_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount > 0

    def list_by_project(
        self,
        project_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[CandidateMemory]:
        """List candidate memory items for a project ordered by newest first with optional ownership check."""
        if user_id is not None:
            proj = self._project_repo.get(project_id, user_id=user_id)
            if proj is None:
                return []

        with self._session_factory() as db:
            stmt = select(CandidateMemoryRecord).where(CandidateMemoryRecord.project_id == project_id)
            if status is not None:
                st_val = status.value if hasattr(status, "value") else str(status)
                stmt = stmt.where(CandidateMemoryRecord.status == st_val)
            stmt = stmt.order_by(desc(CandidateMemoryRecord.created_at)).offset(offset).limit(limit)
            records = db.scalars(stmt).all()
            return [self._to_domain(r) for r in records]

    def delete_by_project(self, project_id: str, user_id: int | None = None) -> int:
        """Delete all candidate memories belonging to a project."""
        if user_id is not None:
            proj = self._project_repo.get(project_id, user_id=user_id)
            if proj is None:
                return 0

        with self._session_factory() as db:
            stmt = delete(CandidateMemoryRecord).where(CandidateMemoryRecord.project_id == project_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount


class KnowledgeRepository:
    """Repository managing knowledge sources, chunks, and vector similarity in SQLite."""

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        database_url: str | None = None,
        project_repository: ProjectRepository | None = None,
    ) -> None:
        if session_factory is not None:
            self._session_factory = session_factory
        else:
            self._session_factory = get_session_factory(database_url)
        self._project_repo = project_repository or ProjectRepository(session_factory=self._session_factory)

    def _source_to_domain(self, record: KnowledgeSourceRecord) -> KnowledgeSource:
        """Convert KnowledgeSourceRecord to domain schema."""
        return KnowledgeSource(
            source_id=record.source_id,
            project_id=record.project_id,
            source_type=record.source_type,
            source_name=record.source_name,
            content_hash=record.content_hash,
            chunk_count=record.chunk_count,
            metadata=dict(record.metadata_json or {}),
            created_at=datetime.fromtimestamp(record.created_at, tz=timezone.utc),
            updated_at=datetime.fromtimestamp(record.updated_at, tz=timezone.utc),
        )

    def _chunk_to_domain(self, record: KnowledgeChunkRecord) -> KnowledgeChunk:
        """Convert KnowledgeChunkRecord to domain schema."""
        return KnowledgeChunk(
            chunk_id=record.chunk_id,
            project_id=record.project_id,
            source_id=record.source_id,
            chunk_index=record.chunk_index,
            content=record.content,
            content_hash=record.content_hash,
            metadata=dict(record.metadata_json or {}),
            created_at=datetime.fromtimestamp(record.created_at, tz=timezone.utc),
        )

    def create_source(
        self,
        project_id: str,
        source_type: str,
        source_name: str,
        content_hash: str,
        metadata: dict[str, Any] | None = None,
        source_id: str | None = None,
    ) -> KnowledgeSource:
        """Persist a new knowledge source entry."""
        sid = source_id or str(uuid.uuid4())
        now = time.time()
        record = KnowledgeSourceRecord(
            source_id=sid,
            project_id=project_id,
            source_type=source_type,
            source_name=source_name,
            content_hash=content_hash,
            chunk_count=0,
            metadata_json=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        with self._session_factory() as db:
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._source_to_domain(record)

    def get_source(self, source_id: str, user_id: int | None = None) -> KnowledgeSource | None:
        """Retrieve a knowledge source by ID, optionally filtered by user ownership."""
        with self._session_factory() as db:
            if user_id is not None:
                stmt = (
                    select(KnowledgeSourceRecord)
                    .join(ProjectRecord, ProjectRecord.project_id == KnowledgeSourceRecord.project_id)
                    .where(KnowledgeSourceRecord.source_id == source_id, ProjectRecord.user_id == user_id)
                )
            else:
                stmt = select(KnowledgeSourceRecord).where(KnowledgeSourceRecord.source_id == source_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._source_to_domain(record)

    def get_source_by_hash(self, project_id: str, content_hash: str) -> KnowledgeSource | None:
        """Retrieve a knowledge source by its deterministic content hash within a project."""
        with self._session_factory() as db:
            stmt = select(KnowledgeSourceRecord).where(
                KnowledgeSourceRecord.project_id == project_id,
                KnowledgeSourceRecord.content_hash == content_hash,
            )
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._source_to_domain(record)

    def get_source_by_name(self, project_id: str, source_name: str) -> KnowledgeSource | None:
        """Retrieve a knowledge source by source_name within a project."""
        with self._session_factory() as db:
            stmt = select(KnowledgeSourceRecord).where(
                KnowledgeSourceRecord.project_id == project_id,
                KnowledgeSourceRecord.source_name == source_name,
            )
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._source_to_domain(record)

    def list_sources(
        self,
        project_id: str,
        limit: int = 100,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[KnowledgeSource]:
        """List knowledge sources for a project ordered newest first, with optional user ownership check."""
        if user_id is not None:
            proj = self._project_repo.get(project_id, user_id=user_id)
            if proj is None:
                return []

        with self._session_factory() as db:
            stmt = (
                select(KnowledgeSourceRecord)
                .where(KnowledgeSourceRecord.project_id == project_id)
                .order_by(desc(KnowledgeSourceRecord.created_at))
                .offset(offset)
                .limit(limit)
            )
            records = db.scalars(stmt).all()
            return [self._source_to_domain(r) for r in records]

    def delete_source(self, source_id: str, user_id: int | None = None) -> bool:
        """Delete a knowledge source and all its associated chunks and vector embeddings, checking ownership if provided."""
        if user_id is not None:
            existing = self.get_source(source_id, user_id=user_id)
            if existing is None:
                return False

        with self._session_factory() as db:
            # Find chunk IDs to delete from vec_chunks
            chunk_ids_stmt = select(KnowledgeChunkRecord.chunk_id).where(KnowledgeChunkRecord.source_id == source_id)
            chunk_ids = db.scalars(chunk_ids_stmt).all()

            if chunk_ids:
                for cid in chunk_ids:
                    try:
                        db.execute(text("DELETE FROM vec_chunks WHERE chunk_id = :cid"), {"cid": cid})
                    except Exception:
                        pass
                db.execute(delete(KnowledgeChunkRecord).where(KnowledgeChunkRecord.source_id == source_id))

            stmt = delete(KnowledgeSourceRecord).where(KnowledgeSourceRecord.source_id == source_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount > 0

    def delete_by_project(self, project_id: str, user_id: int | None = None) -> int:
        """Delete all sources, chunks, and vector embeddings belonging to a project, checking ownership."""
        if user_id is not None:
            proj = self._project_repo.get(project_id, user_id=user_id)
            if proj is None:
                return 0

        with self._session_factory() as db:
            chunk_ids_stmt = select(KnowledgeChunkRecord.chunk_id).where(KnowledgeChunkRecord.project_id == project_id)
            chunk_ids = db.scalars(chunk_ids_stmt).all()

            if chunk_ids:
                for cid in chunk_ids:
                    try:
                        db.execute(text("DELETE FROM vec_chunks WHERE chunk_id = :cid"), {"cid": cid})
                    except Exception:
                        pass
                db.execute(delete(KnowledgeChunkRecord).where(KnowledgeChunkRecord.project_id == project_id))

            stmt = delete(KnowledgeSourceRecord).where(KnowledgeSourceRecord.project_id == project_id)
            result = db.execute(stmt)
            db.commit()
            return result.rowcount

    def store_chunks_with_vectors(
        self,
        source_id: str,
        project_id: str,
        chunks_data: list[Any],
        embeddings: list[list[float]],
    ) -> list[KnowledgeChunk]:
        """Store chunk records in SQLite and register their vectors in vec_chunks."""
        if len(chunks_data) != len(embeddings):
            raise ValueError("chunks_data and embeddings lists must have the same length")

        records: list[KnowledgeChunkRecord] = []
        now = time.time()

        with self._session_factory() as db:
            for item, emb in zip(chunks_data, embeddings, strict=True):
                cid = str(uuid.uuid4())
                rec = KnowledgeChunkRecord(
                    chunk_id=cid,
                    project_id=project_id,
                    source_id=source_id,
                    chunk_index=item.chunk_index,
                    content=item.content,
                    content_hash=item.content_hash,
                    metadata_json=dict(item.metadata),
                    created_at=now,
                )
                db.add(rec)
                records.append(rec)

                # Insert vector into sqlite-vec virtual table
                if sqlite_vec is not None:
                    try:
                        serialized_vec = sqlite_vec.serialize_float32(emb)
                        db.execute(
                            text("INSERT INTO vec_chunks(chunk_id, embedding) VALUES (:cid, :emb)"),
                            {"cid": cid, "emb": serialized_vec},
                        )
                    except Exception:
                        pass

            # Update chunk_count on source
            source_rec = db.scalars(
                select(KnowledgeSourceRecord).where(KnowledgeSourceRecord.source_id == source_id)
            ).first()
            if source_rec is not None:
                source_rec.chunk_count = len(chunks_data)
                source_rec.updated_at = now

            db.commit()
            for r in records:
                db.refresh(r)

            return [self._chunk_to_domain(r) for r in records]

    def get_chunks_by_source(self, source_id: str) -> list[KnowledgeChunk]:
        """Retrieve all chunks belonging to a source ordered by chunk_index."""
        with self._session_factory() as db:
            stmt = (
                select(KnowledgeChunkRecord)
                .where(KnowledgeChunkRecord.source_id == source_id)
                .order_by(KnowledgeChunkRecord.chunk_index.asc())
            )
            records = db.scalars(stmt).all()
            return [self._chunk_to_domain(r) for r in records]

    def get_chunk(self, chunk_id: str) -> KnowledgeChunk | None:
        """Retrieve a chunk by ID."""
        with self._session_factory() as db:
            stmt = select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.chunk_id == chunk_id)
            record = db.scalars(stmt).first()
            if record is None:
                return None
            return self._chunk_to_domain(record)

    def count_chunks(self, project_id: str) -> int:
        """Count total knowledge chunks for a project."""
        with self._session_factory() as db:
            stmt = select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.project_id == project_id)
            return len(db.scalars(stmt).all())

    def count_sources(self, project_id: str) -> int:
        """Count total knowledge sources for a project."""
        with self._session_factory() as db:
            stmt = select(KnowledgeSourceRecord).where(KnowledgeSourceRecord.project_id == project_id)
            return len(db.scalars(stmt).all())

    def search_similar_chunks(
        self,
        project_id: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search top_k similar chunks for project_id using sqlite-vec KNN matching."""
        if sqlite_vec is None:
            return []

        serialized_query = sqlite_vec.serialize_float32(query_embedding)
        sql = text("""
            SELECT 
                kc.chunk_id,
                kc.project_id,
                kc.source_id,
                kc.chunk_index,
                kc.content,
                kc.content_hash,
                kc.metadata_json,
                ks.source_name,
                ks.source_type,
                vc.distance
            FROM vec_chunks vc
            JOIN knowledge_chunks kc ON kc.chunk_id = vc.chunk_id
            JOIN knowledge_sources ks ON ks.source_id = kc.source_id
            WHERE vc.embedding MATCH :query_vec AND vc.k = :k AND kc.project_id = :project_id
            ORDER BY vc.distance ASC
            LIMIT :limit
        """)

        with self._session_factory() as db:
            try:
                rows = db.execute(
                    sql,
                    {
                        "query_vec": serialized_query,
                        "k": max(top_k * 10, 100),
                        "project_id": project_id,
                        "limit": top_k,
                    },
                ).fetchall()
            except Exception:
                return []

            results: list[dict[str, Any]] = []
            for r in rows:
                dist = float(r[9]) if r[9] is not None else 1.0
                sim_score = max(0.0, min(1.0, 1.0 - dist))
                raw_meta = r[6]
                if isinstance(raw_meta, str):
                    import json
                    try:
                        meta = json.loads(raw_meta)
                    except Exception:
                        meta = {}
                elif isinstance(raw_meta, dict):
                    meta = raw_meta
                else:
                    meta = {}

                results.append({
                    "chunk_id": r[0],
                    "project_id": r[1],
                    "source_id": r[2],
                    "chunk_index": r[3],
                    "content": r[4],
                    "content_hash": r[5],
                    "metadata": meta,
                    "source_name": r[7],
                    "source_type": r[8],
                    "score": round(sim_score, 4),
                    "distance": round(dist, 4),
                })
            return results


