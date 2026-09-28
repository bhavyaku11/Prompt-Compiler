"""Authentication API route module for Prompt Compiler."""

from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.database.models import UserRecord
from app.schemas.auth import AuthMeResponse

router = APIRouter(tags=["auth"])


@router.get("/api/auth/me", response_model=AuthMeResponse)
async def get_me(
    current_user: UserRecord = Depends(get_current_user),
) -> AuthMeResponse:
    """Return the verified identity of the currently authenticated Clerk user."""
    return AuthMeResponse(user_id=current_user.clerk_user_id)
