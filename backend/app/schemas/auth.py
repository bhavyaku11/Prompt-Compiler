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


class DesktopSessionPayload(BaseModel):
    """Payload sent when recording an established desktop session."""

    token: str = Field(..., description="Verified Clerk session JWT token.")
    user_id: str | None = Field(default=None, description="Clerk user ID.")
    email: str | None = Field(default=None, description="Primary email address.")
    first_name: str | None = Field(default=None, description="First name.")
    last_name: str | None = Field(default=None, description="Last name.")
    image_url: str | None = Field(default=None, description="Profile avatar picture URL.")


class DesktopSessionResponse(BaseModel):
    """Response returned when querying current desktop session status."""

    authenticated: bool = Field(..., description="Whether a valid desktop session is established.")
    token: str | None = Field(default=None, description="Active Clerk session JWT token.")
    user_id: str | None = Field(default=None, description="Clerk user ID.")
    email: str | None = Field(default=None, description="User email address.")
    first_name: str | None = Field(default=None, description="User first name.")
    last_name: str | None = Field(default=None, description="User last name.")
    image_url: str | None = Field(default=None, description="User profile picture URL.")


class OpenBrowserPayload(BaseModel):
    """Payload to request opening an external URL in Google Chrome or system default browser."""

    url: str = Field(..., description="The URL to open.")

