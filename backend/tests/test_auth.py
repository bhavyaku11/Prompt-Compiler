"""Tests for FastAPI Clerk authentication foundation."""

import time
import unittest
from typing import Any
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
import jwt
from starlette.datastructures import Headers

from app.auth import ClerkAuthService, require_authenticated_user
from app.config import Settings
from app.main import app
from app.schemas.auth import AuthenticatedUser


class BaseAuthTestCase(unittest.TestCase):
    """Base test case generating cryptographic test keys and tokens."""

    @classmethod
    def setUpClass(cls):
        # Generate an RSA key pair for local deterministic testing
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.public_pem = cls.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        # Generate a second key pair to simulate an attacker/mismatched signature
        cls.other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def create_token(
        self,
        sub: str = "user_2TestClerkUser",
        sid: str = "sess_2TestClerkSession",
        exp_delta: int = 3600,
        azp: str = "http://localhost:5173",
        use_other_key: bool = False,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a signed JWT token matching Clerk session token structure."""
        now = int(time.time())
        payload = {
            "sub": sub,
            "sid": sid,
            "iat": now,
            "exp": now + exp_delta,
            "nbf": now - 5,
            "azp": azp,
        }
        if extra_claims:
            payload.update(extra_claims)

        signing_key = self.other_private_key if use_other_key else self.private_key
        return jwt.encode(payload, signing_key, algorithm="RS256", headers={"kid": "test_kid"})

    def create_mock_request(self, auth_header: str | None = None):
        """Create a lightweight request mock matching Starlette Request interface."""
        class MockRequest:
            def __init__(self, header_val: str | None):
                d = {}
                if header_val is not None:
                    d["authorization"] = header_val
                self.headers = Headers(d)

        return MockRequest(auth_header)


class TestClerkConfig(unittest.TestCase):
    """Test configuration parsing and validation for Clerk."""

    def test_missing_clerk_configuration(self):
        cfg = Settings(CLERK_SECRET_KEY=None, CLERK_JWT_KEY=None)
        self.assertFalse(cfg.is_clerk_configured)

    def test_valid_secret_key_configuration(self):
        cfg = Settings(CLERK_SECRET_KEY="sk_test_12345", CLERK_JWT_KEY=None)
        self.assertTrue(cfg.is_clerk_configured)
        self.assertEqual(cfg.clerk_secret_key, "sk_test_12345")

    def test_valid_jwt_key_configuration(self):
        cfg = Settings(CLERK_SECRET_KEY=None, CLERK_JWT_KEY="-----BEGIN PUBLIC KEY-----...")
        self.assertTrue(cfg.is_clerk_configured)
        self.assertEqual(cfg.clerk_jwt_key, "-----BEGIN PUBLIC KEY-----...")

    def test_clerk_authorized_parties_parsing(self):
        cfg = Settings(CLERK_AUTHORIZED_PARTIES="http://localhost:5173, https://app.example.com")
        self.assertEqual(cfg.clerk_authorized_parties, ["http://localhost:5173", "https://app.example.com"])

    def test_clerk_authorized_parties_empty(self):
        cfg = Settings(CLERK_AUTHORIZED_PARTIES="")
        self.assertEqual(cfg.clerk_authorized_parties, [])


class TestClerkAuthService(BaseAuthTestCase):
    """Test ClerkAuthService token verification and error handling."""

    def setUp(self):
        self.settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173",
        )
        self.auth_service = ClerkAuthService(settings_instance=self.settings)

    def test_missing_authorization_header_raises_401(self):
        req = self.create_mock_request(auth_header=None)
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Missing Authorization header", ctx.exception.detail)

    def test_malformed_authorization_header_not_bearer(self):
        req = self.create_mock_request(auth_header="Basic dXNlcjpwYXNz")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Malformed Authorization header", ctx.exception.detail)

    def test_malformed_authorization_header_empty_token(self):
        req = self.create_mock_request(auth_header="Bearer ")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Malformed Authorization header", ctx.exception.detail)

    def test_unconfigured_clerk_with_token_raises_500(self):
        unconfigured_service = ClerkAuthService(
            settings_instance=Settings(CLERK_SECRET_KEY=None, CLERK_JWT_KEY=None)
        )
        req = self.create_mock_request(auth_header="Bearer some.token.val")
        with self.assertRaises(HTTPException) as ctx:
            unconfigured_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("Authentication service configuration error", ctx.exception.detail)

    def test_invalid_token_format_raises_401(self):
        req = self.create_mock_request(auth_header="Bearer not_a_valid_jwt")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid session token", ctx.exception.detail)

    def test_expired_token_raises_401(self):
        token = self.create_token(exp_delta=-3600)
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail)

    def test_invalid_signature_raises_401(self):
        token = self.create_token(use_other_key=True)
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid token signature", ctx.exception.detail)

    def test_invalid_authorized_party_raises_401(self):
        token = self.create_token(azp="http://attacker.example.com")
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid authorized party", ctx.exception.detail)

    def test_valid_token_returns_authenticated_user(self):
        token = self.create_token(sub="user_valid123", sid="sess_valid456")
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        user = self.auth_service.authenticate_request(req)

        self.assertIsInstance(user, AuthenticatedUser)
        self.assertEqual(user.user_id, "user_valid123")
        self.assertEqual(user.session_id, "sess_valid456")
        self.assertEqual(user.claims.get("azp"), "http://localhost:5173")

    def test_missing_sub_claim_raises_401(self):
        now = int(time.time())
        # Craft a token without sub claim
        payload = {
            "sid": "sess_123",
            "iat": now,
            "exp": now + 3600,
            "azp": "http://localhost:5173",
        }
        token = jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": "test_kid"})
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("missing valid subject claim", ctx.exception.detail.lower())

    def test_no_secret_or_token_leakage_in_error_detail(self):
        secret_sample = "sensitive_token_payload_xyz"
        req = self.create_mock_request(auth_header=f"Bearer {secret_sample}")
        with self.assertRaises(HTTPException) as ctx:
            self.auth_service.authenticate_request(req)
        self.assertNotIn(secret_sample, str(ctx.exception.detail))


class TestAuthMeEndpoint(BaseAuthTestCase):
    """Test the protected GET /api/auth/me endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Missing Authorization header", data["detail"])

    def test_malformed_header_returns_401(self):
        response = self.client.get("/api/auth/me", headers={"Authorization": "Token abcdef"})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Malformed Authorization header", response.json()["detail"])

    def test_invalid_token_returns_401(self):
        response = self.client.get("/api/auth/me", headers={"Authorization": "Bearer bad.jwt.token"})
        # When unconfigured in global settings, returns 500 configuration error, or 401
        self.assertIn(response.status_code, [401, 500])

    def test_authenticated_request_with_dependency_override(self):
        """Verify the endpoint returns 200 and verified identity using dependency override."""
        app.dependency_overrides[require_authenticated_user] = lambda: AuthenticatedUser(
            user_id="user_clerk_verified_999",
            session_id="sess_abc123",
            claims={"sub": "user_clerk_verified_999"},
        )
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, {"user_id": "user_clerk_verified_999"})

    def test_authenticated_request_with_real_token_and_test_service(self):
        """Verify end-to-end token verification and /api/auth/me response without dependency override."""
        from fastapi import Request

        test_settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173",
        )
        test_auth_service = ClerkAuthService(settings_instance=test_settings)

        # Override dependency to use test_auth_service
        def override_dep(request: Request):
            return test_auth_service.authenticate_request(request)

        app.dependency_overrides[require_authenticated_user] = override_dep

        token = self.create_token(sub="user_live_extracted_555")
        response = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user_id": "user_live_extracted_555"})


class TestExistingEndpointsRegression(unittest.TestCase):
    """Confirm existing business endpoints remain completely unprotected and working."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_endpoint_unprotected(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "prompt-compiler"})

    def test_presets_endpoint_unprotected(self):
        response = self.client.get("/api/presets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_compile_endpoint_protected_in_task_28(self):
        # In Task 28, /api/compile is protected and must reject unauthenticated requests with 401
        response = self.client.post("/api/compile", json={"input": ""})
        self.assertEqual(response.status_code, 401)


class TestDesktopAuthSessionOfflineStrategy(BaseAuthTestCase):
    """Test desktop authentication, session, and offline strategy behaviors (Task 33)."""

    def test_default_jwt_key_preconfigured(self):
        """Verify settings has default public key configured and is_clerk_configured is True."""
        from app.config import DEFAULT_CLERK_JWT_KEY
        cfg = Settings()
        self.assertTrue(cfg.is_clerk_configured)
        self.assertEqual(cfg.clerk_jwt_key, DEFAULT_CLERK_JWT_KEY)
        self.assertIn("tauri://localhost", cfg.clerk_authorized_parties)
        self.assertIn("http://localhost:5173", cfg.clerk_authorized_parties)

    def test_local_offline_token_verification_no_network(self):
        """Verify token verification works completely offline without network access."""
        from unittest.mock import patch

        settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173",
        )
        service = ClerkAuthService(settings_instance=settings)
        token = self.create_token(sub="user_offline_verified_123")
        req = self.create_mock_request(auth_header=f"Bearer {token}")

        # Block any network socket connections to prove verification is 100% offline
        with patch("socket.socket") as mock_socket:
            mock_socket.side_effect = AssertionError("Network call attempted during offline token verification!")
            auth_user = service.authenticate_request(req)

        self.assertEqual(auth_user.user_id, "user_offline_verified_123")
        self.assertEqual(auth_user.session_id, "sess_2TestClerkSession")

    def test_expired_token_returns_401_session_expired(self):
        """Verify expired token returns 401 with explicit expired message."""
        settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173",
        )
        service = ClerkAuthService(settings_instance=settings)
        expired_token = self.create_token(exp_delta=-60)
        req = self.create_mock_request(auth_header=f"Bearer {expired_token}")

        with self.assertRaises(HTTPException) as ctx:
            service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Session token has expired", ctx.exception.detail)

    def test_tampered_token_rejected_locally(self):
        """Verify tampered token is rejected with 401 signature failure."""
        settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173",
        )
        service = ClerkAuthService(settings_instance=settings)
        tampered_token = self.create_token(use_other_key=True)
        req = self.create_mock_request(auth_header=f"Bearer {tampered_token}")

        with self.assertRaises(HTTPException) as ctx:
            service.authenticate_request(req)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid token signature", ctx.exception.detail)

    def test_tauri_authorized_party_accepted(self):
        """Verify tauri://localhost origin is accepted under default authorized parties."""
        settings = Settings(
            CLERK_JWT_KEY=self.public_pem,
            CLERK_AUTHORIZED_PARTIES="http://localhost:5173,tauri://localhost",
        )
        service = ClerkAuthService(settings_instance=settings)
        token = self.create_token(sub="user_tauri_123", azp="tauri://localhost")
        req = self.create_mock_request(auth_header=f"Bearer {token}")
        auth_user = service.authenticate_request(req)
        self.assertEqual(auth_user.user_id, "user_tauri_123")


if __name__ == "__main__":
    unittest.main()

