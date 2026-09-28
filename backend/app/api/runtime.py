"""Runtime and service readiness status API router for Prompt Compiler."""

from fastapi import APIRouter
from sqlalchemy import text

from app.ai.ollama import OllamaClient
from app.config import settings
from app.database.session import get_engine
from app.schemas.runtime import (
    DatabaseStatus,
    OllamaStatus,
    RuntimeInfo,
    RuntimeStatusResponse,
)

router = APIRouter(tags=["runtime"])


def _check_database() -> DatabaseStatus:
    """Verify local SQLite database connectivity."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return DatabaseStatus(status="ready")
    except Exception as exc:
        return DatabaseStatus(status="error", details=str(exc))


@router.get("/api/runtime/status", response_model=RuntimeStatusResponse)
async def get_runtime_status() -> RuntimeStatusResponse:
    """Comprehensive runtime readiness status check for desktop shell and frontend.

    Checks:
    - Backend: always 'ready' if this endpoint responds.
    - Database: active connection to local SQLite.
    - Ollama: reachability of local daemon and presence of configured model (non-blocking).
    - Runtime: runtime mode (development vs desktop) and safe metadata.
    """
    db_status = _check_database()

    ollama_client = OllamaClient()
    ollama_info = await ollama_client.check_availability(timeout=2.0)
    ollama_status = OllamaStatus(
        status=ollama_info.get("status", "unavailable"),
        model=ollama_info.get("model", settings.ollama_model),
        model_available=ollama_info.get("model_available", False),
        details=ollama_info.get("details"),
    )

    runtime_info = RuntimeInfo(
        mode="desktop" if settings.desktop_mode else "development",
        app_name=settings.app_name,
        version=settings.app_version,
        host=settings.desktop_backend_host,
        port=settings.desktop_backend_port,
        data_dir=settings.app_data_dir,
    )

    return RuntimeStatusResponse(
        backend="ready",
        database=db_status,
        ollama=ollama_status,
        runtime=runtime_info,
    )
