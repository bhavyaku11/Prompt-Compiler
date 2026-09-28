"""Schemas for desktop and backend runtime status."""

from pydantic import BaseModel, Field


class OllamaStatus(BaseModel):
    """Status details for local Ollama inference service."""

    status: str = Field(..., description="Service status: 'available' or 'unavailable'")
    model: str = Field(..., description="Configured model identifier")
    model_available: bool = Field(..., description="Whether the configured model is installed locally")
    details: str | None = Field(default=None, description="Diagnostic details or error message")


class DatabaseStatus(BaseModel):
    """Status details for local SQLite database connectivity."""

    status: str = Field(..., description="Database status: 'ready' or 'error'")
    details: str | None = Field(default=None, description="Diagnostic details or error message")


class RuntimeInfo(BaseModel):
    """Metadata regarding current runtime environment."""

    mode: str = Field(..., description="Runtime mode: 'development' or 'desktop'")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    host: str = Field(..., description="Bound backend host")
    port: int = Field(..., description="Bound backend port")
    data_dir: str | None = Field(default=None, description="Configured persistent data directory")


class RuntimeStatusResponse(BaseModel):
    """Consolidated runtime readiness and status response."""

    backend: str = Field(default="ready", description="Backend process status: 'ready'")
    database: DatabaseStatus = Field(..., description="Database status")
    ollama: OllamaStatus = Field(..., description="Local Ollama service status")
    runtime: RuntimeInfo = Field(..., description="Runtime environment information")
