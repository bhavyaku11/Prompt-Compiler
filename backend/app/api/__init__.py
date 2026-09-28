"""FastAPI route modules."""

from app.api.compile import router as compile_router
from app.api.health import router as health_router
from app.api.interview import router as interview_router
from app.api.projects import router as projects_router

__all__ = [
    "compile_router",
    "health_router",
    "interview_router",
    "projects_router",
]

