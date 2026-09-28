"""Clerk authentication foundation for Prompt Compiler FastAPI backend."""

import logging
from typing import Any
from fastapi import Depends, HTTPException, Request, status
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import (
    AuthenticateRequestOptions,
    AuthErrorReason,
    TokenVerificationErrorReason,
)

from app.config import Settings, settings
from app.database.models import UserRecord
from app.database.repositories import UserRepository
from app.schemas.auth import AuthenticatedUser

logger = logging.getLogger(__name__)


def _map_auth_error_reason(reason: Any) -> str:
    """Map Clerk SDK failure reasons to safe, user-facing error messages.

    Ensures no tokens, secrets, or internal stack traces are returned to clients.
    """
    if reason == AuthErrorReason.SESSION_TOKEN_MISSING:
        return "Authentication required: Session token is missing."
    elif reason == TokenVerificationErrorReason.TOKEN_EXPIRED:
        return "Authentication failed: Session token has expired."
    elif reason == TokenVerificationErrorReason.TOKEN_INVALID_AUTHORIZED_PARTIES:
        return "Authentication failed: Invalid authorized party."
    elif reason == TokenVerificationErrorReason.TOKEN_INVALID_SIGNATURE:
        return "Authentication failed: Invalid token signature."
    elif reason in (
        TokenVerificationErrorReason.TOKEN_INVALID,
        TokenVerificationErrorReason.INVALID_TOKEN_TYPE,
        TokenVerificationErrorReason.TOKEN_NOT_ACTIVE_YET,
        TokenVerificationErrorReason.TOKEN_IAT_IN_THE_FUTURE,
        TokenVerificationErrorReason.TOKEN_INVALID_AUDIENCE,
        AuthErrorReason.TOKEN_TYPE_NOT_SUPPORTED,
    ):
        return "Authentication failed: Invalid session token."
    elif reason == TokenVerificationErrorReason.SECRET_KEY_MISSING:
        return "Authentication service configuration error."
    return "Authentication failed: Could not verify session token."


class ClerkAuthService:
    """Service encapsulating Clerk session token authentication."""

    def __init__(
        self,
        settings_instance: Settings | None = None,
        clerk_client: Clerk | None = None,
    ) -> None:
        self.settings = settings_instance or settings
        self._clerk_client = clerk_client

    @property
    def clerk_client(self) -> Clerk:
        """Lazily initialize and return the official Clerk SDK client instance."""
        if self._clerk_client is None:
            secret = self.settings.clerk_secret_key or ""
            self._clerk_client = Clerk(bearer_auth=secret)
        return self._clerk_client

    def get_authenticate_options(self) -> AuthenticateRequestOptions:
        """Build AuthenticateRequestOptions from current application settings."""
        authorized_parties = self.settings.clerk_authorized_parties
        return AuthenticateRequestOptions(
            secret_key=self.settings.clerk_secret_key,
            jwt_key=self.settings.clerk_jwt_key,
            authorized_parties=authorized_parties if authorized_parties else None,
        )

    def authenticate_request(self, request: Request) -> AuthenticatedUser:
        """Verify the Clerk session token on an incoming HTTP request.

        Raises:
            HTTPException(500): When Clerk configuration is missing.
            HTTPException(401): When authentication fails or token is invalid.
        """
        # 1. Extract Authorization header safely without logging token content
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Missing Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        parts = auth_header.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Malformed Authorization header. Expected 'Bearer <token>'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 2. Configuration check
        if not self.settings.is_clerk_configured:
            logger.error("Clerk authentication is not configured: missing CLERK_SECRET_KEY or CLERK_JWT_KEY.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service configuration error.",
            )

        # 3. Verify token with official Clerk SDK
        options = self.get_authenticate_options()
        try:
            state = self.clerk_client.authenticate_request(request, options)
        except Exception as exc:
            logger.warning(
                "Clerk authenticate_request encountered an unexpected exception: %s",
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: Unable to verify session token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        if not state.is_authenticated:
            reason = state.reason
            safe_detail = _map_auth_error_reason(reason)
            logger.info(
                "Clerk session verification failed with reason: %s",
                getattr(reason, "name", str(reason)),
            )

            # Special case: missing secret key is a server configuration issue
            if reason == TokenVerificationErrorReason.SECRET_KEY_MISSING:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Authentication service configuration error.",
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=safe_detail,
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 4. Extract verified claims
        payload = state.payload or {}
        user_id = payload.get("sub")
        if not user_id or not isinstance(user_id, str):
            logger.warning("Clerk token verified successfully but 'sub' claim is missing or invalid.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed: Token missing valid subject claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        session_id = payload.get("sid")
        if session_id is not None and not isinstance(session_id, str):
            session_id = None

        return AuthenticatedUser(
            user_id=user_id,
            session_id=session_id,
            claims=payload,
        )


# Default singleton instance
auth_service = ClerkAuthService()
_user_repository: UserRepository | None = None


def get_user_repository() -> UserRepository:
    """Dependency provider for UserRepository singleton."""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository()
    return _user_repository


def require_authenticated_user(request: Request) -> AuthenticatedUser:
    """FastAPI dependency to enforce Clerk session authentication and return the verified identity."""
    return auth_service.authenticate_request(request)


def get_current_user(
    auth_user: AuthenticatedUser = Depends(require_authenticated_user),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserRecord:
    """FastAPI dependency to resolve or auto-provision the persistent local User from verified Clerk authentication."""
    return user_repo.get_or_create(auth_user.user_id)
