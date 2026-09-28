"""Database engine, session factory, and initialization for Prompt Compiler."""

import os
import sys
import time
from collections.abc import Generator
from typing import Any
from urllib.parse import urlparse

# Ensure SQLite supports extension loading via sqlean if available
try:
    import sqlean
    sys.modules["sqlite3"] = sqlean
except ImportError:
    pass

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _ensure_sqlite_directory(db_url: str) -> None:
    """Ensure the directory for a file-based SQLite database exists."""
    if not db_url.startswith("sqlite:"):
        return

    # Skip in-memory sqlite
    if ":memory:" in db_url or db_url == "sqlite://":
        return

    # Strip sqlite:/// prefix
    path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if path:
        dir_path = os.path.dirname(path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)


def get_engine(
    database_url: str | None = None,
    echo: bool | None = None,
) -> Engine:
    """Create or return the global SQLAlchemy engine instance."""
    global _engine
    target_url = database_url or settings.database_url
    target_echo = echo if echo is not None else settings.database_echo

    if _engine is None or database_url is not None:
        _ensure_sqlite_directory(target_url)

        connect_args: dict[str, Any] = {}
        extra_kwargs: dict[str, Any] = {}
        if target_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            if ":memory:" in target_url:
                from sqlalchemy.pool import StaticPool
                extra_kwargs["poolclass"] = StaticPool
            else:
                from sqlalchemy.pool import NullPool
                extra_kwargs["poolclass"] = NullPool

        engine = create_engine(
            target_url,
            echo=target_echo,
            connect_args=connect_args,
            **extra_kwargs,
        )

        if target_url.startswith("sqlite"):
            # Register sqlite-vec loader on connection
            @event.listens_for(engine, "connect")
            def _load_sqlite_vec(dbapi_connection: Any, connection_record: Any) -> None:
                if sqlite_vec is not None and hasattr(dbapi_connection, "enable_load_extension"):
                    try:
                        dbapi_connection.enable_load_extension(True)
                        sqlite_vec.load(dbapi_connection)
                        dbapi_connection.enable_load_extension(False)
                    except Exception:
                        pass

            # Enable WAL mode for file-based SQLite
            if ":memory:" not in target_url:
                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.close()

        # Ensure standard database tables exist
        Base.metadata.create_all(bind=engine)

        # Create sqlite-vec virtual table for vector knowledge chunk indexing
        if target_url.startswith("sqlite"):
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                            chunk_id text primary key,
                            embedding float[{settings.EMBEDDING_DIMENSION}] distance_metric=cosine
                        );
                    """))
            except Exception:
                pass

        # Migrate existing SQLite databases if project_id, target_agent, knowledge_references, or enable_knowledge_retrieval column is missing
        if target_url.startswith("sqlite"):
            try:
                with engine.connect() as conn:
                    for table in ("interview_sessions", "compilations"):
                        res = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                        cols = [r[1] for r in res]
                        if cols and "project_id" not in cols:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN project_id VARCHAR(64)"))
                            conn.commit()
                        if cols and "target_agent" not in cols:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN target_agent VARCHAR(32) DEFAULT 'generic'"))
                            conn.commit()
                    # Compilation-specific columns
                    res = conn.execute(text("PRAGMA table_info(compilations)")).fetchall()
                    cols = [r[1] for r in res]
                    if cols and "knowledge_references" not in cols:
                        conn.execute(text("ALTER TABLE compilations ADD COLUMN knowledge_references JSON"))
                        conn.commit()
                    # Interview-specific columns
                    res = conn.execute(text("PRAGMA table_info(interview_sessions)")).fetchall()
                    cols = [r[1] for r in res]
                    if cols and "enable_knowledge_retrieval" not in cols:
                        conn.execute(text("ALTER TABLE interview_sessions ADD COLUMN enable_knowledge_retrieval BOOLEAN DEFAULT 1"))
                        conn.commit()
                    # Projects-specific columns
                    res = conn.execute(text("PRAGMA table_info(projects)")).fetchall()
                    cols = [r[1] for r in res]
                    if cols and "root_path" not in cols:
                        conn.execute(text("ALTER TABLE projects ADD COLUMN root_path VARCHAR(512)"))
                        conn.commit()

                    # Task 28: Ensure deterministic legacy user exists in users table
                    res = conn.execute(text("SELECT id FROM users WHERE clerk_user_id = 'legacy_local_user'")).fetchone()
                    if not res:
                        now = time.time()
                        conn.execute(
                            text("INSERT INTO users (clerk_user_id, created_at, updated_at) VALUES ('legacy_local_user', :now, :now)"),
                            {"now": now},
                        )
                        conn.commit()
                        res = conn.execute(text("SELECT id FROM users WHERE clerk_user_id = 'legacy_local_user'")).fetchone()
                    legacy_user_id = res[0] if res else 1

                    # Task 28: Add user_id column to projects, compilations, and interview_sessions if missing
                    for table in ("projects", "compilations", "interview_sessions"):
                        res = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
                        cols = [r[1] for r in res]
                        if cols and "user_id" not in cols:
                            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)"))
                            conn.commit()
                        # Safely assign existing unowned legacy records to legacy_local_user
                        conn.execute(
                            text(f"UPDATE {table} SET user_id = :legacy_id WHERE user_id IS NULL"),
                            {"legacy_id": legacy_user_id},
                        )
                        conn.commit()
            except Exception:
                pass


        if database_url is None:
            _engine = engine
        return engine

    return _engine


def get_session_factory(engine: Engine | str | None = None) -> sessionmaker[Session]:
    """Create or return the sessionmaker factory."""
    global _session_factory
    if isinstance(engine, str):
        active_engine = get_engine(database_url=engine)
        return sessionmaker(autocommit=False, autoflush=False, bind=active_engine)
    if _session_factory is None or engine is not None:
        active_engine = engine or get_engine()
        factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=active_engine,
        )
        if engine is None:
            _session_factory = factory
        return factory
    return _session_factory


def init_db(engine: Engine | str | None = None) -> Engine:
    """Initialize database tables using declarative metadata."""
    if isinstance(engine, str):
        active_engine = get_engine(database_url=engine)
    elif engine is not None:
        active_engine = engine
    else:
        active_engine = get_engine()
    Base.metadata.create_all(bind=active_engine)

    try:
        with active_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                    chunk_id text primary key,
                    embedding float[{settings.EMBEDDING_DIMENSION}] distance_metric=cosine
                );
            """))
    except Exception:
        pass

    return active_engine


def reset_db_engine() -> None:
    """Reset the global engine and sessionmaker (used for test isolation)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a managed database session with commit/rollback/close."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
