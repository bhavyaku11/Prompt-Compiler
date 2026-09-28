from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.compile import router as compile_router
from app.api.health import router as health_router
from app.api.interview import router as interview_router
from app.api.knowledge import router as knowledge_router
from app.api.projects import router as projects_router
from app.api.runtime import router as runtime_router
from app.config import settings
from app.database.session import init_db
from app.schemas.api import RootResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# The Tauri webview loads from http://localhost:5173 (Vite dev) or
# tauri://localhost / http://tauri.localhost (production). Both origins make
# cross-origin requests to the FastAPI sidecar, which runs on a different
# port (e.g. 127.0.0.1:18000). Without CORSMiddleware every OPTIONS preflight
# returns 405 and the browser blocks the request — causing the frontend to
# report "Engine Stopped" even when the sidecar is healthy.
#
# allow_credentials=True is required because every authenticated request
# carries an "Authorization: Bearer <token>" header. When credentials are
# enabled, allow_origins MUST be an explicit list, never ["*"].
#
# The allowed origins are derived from CLERK_AUTHORIZED_PARTIES, which
# already contains the three trusted origins for this project:
#   http://localhost:5173  — Vite dev server (tauri dev mode)
#   tauri://localhost      — Tauri production webview on macOS
#   http://tauri.localhost — Tauri production webview on Windows/Linux
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.clerk_authorized_parties,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# Register route modules
app.include_router(health_router)
app.include_router(runtime_router)
app.include_router(auth_router)
app.include_router(compile_router)
app.include_router(interview_router)
app.include_router(projects_router)
app.include_router(knowledge_router)


@app.get("/", response_model=RootResponse)
async def get_root() -> RootResponse:
    """Return basic application metadata and running status."""
    return RootResponse(
        name=settings.app_name,
        version=settings.app_version,
        status="running",
    )
