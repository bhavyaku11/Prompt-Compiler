"""Health check API route module for Prompt Compiler."""

from fastapi import APIRouter
from app.schemas.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Lightweight application-level health check endpoint."""
    return HealthResponse()
