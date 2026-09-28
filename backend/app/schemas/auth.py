"""Authentication schemas for Prompt Compiler Clerk identity layer."""

from typing import Any
from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """In-memory representation of a verified Clerk authenticated identity.

    Carried safely through FastAPI dependency injection without persisting to SQLite.
    """

    user_id: str = Field(
        ...,
        description="The verified Clerk user ID extracted from the 'sub' claim.",
    )
    session_id: str | None = Field(
        default=None,
        description="The optional Clerk session ID extracted from the 'sid' claim.",
    )
    claims: dict[str, Any] = Field(
        default_factory=dict,
        description="Full verified JWT claims payload for downstream inspection.",
    )


class AuthMeResponse(BaseModel):
    """Response schema for the protected GET /api/auth/me verification endpoint."""

    user_id: str = Field(
        ...,
        description="The verified Clerk user ID.",
    )


class User(BaseModel):
    """Domain model representing a persistent user identity in SQLite."""

    id: int = Field(..., description="Local user primary key.")
    clerk_user_id: str = Field(..., description="Verified Clerk user identifier.")
    created_at: float = Field(..., description="Creation Unix timestamp.")
    updated_at: float = Field(..., description="Last update Unix timestamp.")
