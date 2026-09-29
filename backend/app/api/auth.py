"""Authentication API route module for Prompt Compiler.

Provides:
- GET /api/auth/me: Returns verified Clerk user identity.
- POST /api/auth/open-browser: Launches Google Chrome (or system default browser) with external URL.
- GET /api/auth/google-start: Loopback web page initiating Google OAuth in Chrome with oidcPrompt: select_account.
- GET /api/auth/sso-callback: Loopback web page completing Clerk OAuth in Chrome and recording desktop session.
- POST /api/auth/desktop-session: Validates and caches Clerk session token for desktop app consumption.
- GET /api/auth/desktop-session: Polls current desktop session status.
- DELETE /api/auth/desktop-session: Clears cached desktop session.
"""

import base64
import json
import logging
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from starlette.datastructures import Headers

from app.auth import auth_service, get_current_user, get_user_repository
from app.config import settings
from app.database.models import UserRecord
from app.schemas.auth import (
    AuthMeResponse,
    DesktopSessionPayload,
    DesktopSessionResponse,
    OpenBrowserPayload,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# In-memory desktop session state
_desktop_session_lock = threading.Lock()
_active_desktop_session: dict[str, Any] | None = None
_SESSION_TTL_SECONDS: float = 600.0  # 10 minutes


def _get_clerk_frontend_api(publishable_key: str) -> str:
    """Extract frontend API domain from Clerk publishable key."""
    try:
        parts = publishable_key.split("_", 2)
        raw = parts[-1]
        decoded = base64.b64decode(raw + "==").decode("utf-8").rstrip("$")
        return decoded
    except Exception:
        return "model-cobra-7086.clerk.accounts.dev"


def _extract_sid_from_token(token: str) -> str | None:
    """Extract session ID (sid claim) from unverified JWT token."""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            data = json.loads(base64.urlsafe_b64decode(payload_b64))
            return data.get("sid")
    except Exception:
        pass
    return None


class _MockStarletteRequest:
    """Lightweight request adapter matching Starlette Request interface for ClerkAuthService."""

    def __init__(self, token: str):
        self.headers = Headers({"authorization": f"Bearer {token}"})


@router.get("/api/auth/me", response_model=AuthMeResponse)
async def get_me(
    current_user: UserRecord = Depends(get_current_user),
) -> AuthMeResponse:
    """Return the verified identity of the currently authenticated Clerk user."""
    return AuthMeResponse(user_id=current_user.clerk_user_id)


@router.post("/api/auth/open-browser")
async def open_external_browser(payload: OpenBrowserPayload) -> dict[str, Any]:
    """Launch Google Chrome (or default system browser on macOS/other platforms) with the target URL."""
    url = payload.url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL scheme. Only http:// and https:// URLs are allowed.",
        )

    opened = False
    if sys.platform == "darwin":
        # On macOS, attempt to open in Google Chrome first as requested
        try:
            res = subprocess.run(
                ["open", "-a", "Google Chrome", url],
                capture_output=True,
                timeout=5,
            )
            if res.returncode == 0:
                opened = True
        except Exception as exc:
            logger.debug("Failed opening with 'open -a Google Chrome': %s", exc)

        if not opened:
            # Fallback to system default browser
            try:
                res = subprocess.run(["open", url], capture_output=True, timeout=5)
                opened = res.returncode == 0
            except Exception as exc:
                logger.warning("Failed opening default browser on macOS: %s", exc)
    else:
        try:
            opened = webbrowser.open(url)
        except Exception as exc:
            logger.warning("Failed opening browser via webbrowser.open: %s", exc)

    return {"status": "ok", "opened": opened, "url": url}


@router.post("/api/auth/desktop-session", response_model=DesktopSessionResponse)
async def set_desktop_session(payload: DesktopSessionPayload) -> DesktopSessionResponse:
    """Verify and store an active session token established via external browser OAuth."""
    token = payload.token.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session token cannot be empty.",
        )

    # 1. Cryptographically verify the session token with ClerkAuthService
    mock_req = _MockStarletteRequest(token)
    try:
        auth_user = auth_service.authenticate_request(mock_req)  # type: ignore[arg-type]
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Token verification failed during desktop-session sync: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token.",
        ) from None

    # 2. Provision or retrieve user record in local database
    user_repo = get_user_repository()
    user_repo.get_or_create(auth_user.user_id)

    # 3. Store active desktop session
    global _active_desktop_session
    with _desktop_session_lock:
        _active_desktop_session = {
            "token": token,
            "user_id": auth_user.user_id,
            "email": payload.email or "",
            "first_name": payload.first_name or "",
            "last_name": payload.last_name or "",
            "image_url": payload.image_url or "",
            "created_at": time.time(),
        }

    return DesktopSessionResponse(
        authenticated=True,
        token=_active_desktop_session["token"],
        user_id=_active_desktop_session["user_id"],
        email=_active_desktop_session["email"],
        first_name=_active_desktop_session["first_name"],
        last_name=_active_desktop_session["last_name"],
        image_url=_active_desktop_session.get("image_url") or None,
    )


@router.get("/api/auth/desktop-session", response_model=DesktopSessionResponse)
async def get_desktop_session() -> DesktopSessionResponse:
    """Query currently established desktop session (polled by the desktop app)."""
    with _desktop_session_lock:
        if _active_desktop_session:
            age = time.time() - _active_desktop_session.get("created_at", 0)
            if age <= _SESSION_TTL_SECONDS:
                return DesktopSessionResponse(
                    authenticated=True,
                    token=_active_desktop_session["token"],
                    user_id=_active_desktop_session["user_id"],
                    email=_active_desktop_session["email"],
                    first_name=_active_desktop_session["first_name"],
                    last_name=_active_desktop_session["last_name"],
                    image_url=_active_desktop_session.get("image_url") or None,
                )

    return DesktopSessionResponse(authenticated=False)


@router.delete("/api/auth/desktop-session")
async def clear_desktop_session() -> dict[str, str]:
    """Clear established desktop session and revoke active Clerk session upon sign out."""
    global _active_desktop_session
    token_to_revoke = None
    with _desktop_session_lock:
        if _active_desktop_session:
            token_to_revoke = _active_desktop_session.get("token")
        _active_desktop_session = None

    if token_to_revoke:
        sid = _extract_sid_from_token(token_to_revoke)
        if sid and settings.clerk_secret_key:
            try:
                auth_service.clerk_client.sessions.revoke(session_id=sid)
                logger.info("Successfully revoked Clerk session %s on desktop sign-out", sid)
            except Exception as exc:
                logger.debug("Clerk session revocation notice: %s", exc)

    return {"status": "ok"}


@router.get("/api/auth/google-start", response_class=HTMLResponse)
async def google_start() -> HTMLResponse:
    """Serve external browser initiation page that triggers Clerk Google OAuth with account selection."""
    pub_key = settings.clerk_publishable_key or "pk_test_bW9kZWwtY29icmEtNzA4Ni5jbGVyay5hY2NvdW50cy5kZXYk"
    fapi_domain = _get_clerk_frontend_api(pub_key)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Prompt Compiler — Sign in with Google</title>
  <script
    async
    crossorigin="anonymous"
    data-clerk-publishable-key="{pub_key}"
    src="https://{fapi_domain}/npm/@clerk/clerk-js@6/dist/clerk.browser.js"
    type="text/javascript">
  </script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #090a0f;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }}
    .auth-card {{
      background: #111420;
      border: 1px solid #1e2538;
      border-radius: 24px;
      padding: 40px 32px;
      text-align: center;
      max-width: 440px;
      width: 100%;
      box-shadow: 0 24px 48px rgba(0,0,0,0.6), 0 0 1px rgba(255,255,255,0.1);
    }}
    .spinner-ring {{
      display: inline-block;
      width: 48px;
      height: 48px;
      border: 3.5px solid rgba(255, 255, 255, 0.08);
      border-top-color: #6366f1;
      border-radius: 50%;
      animation: spin 0.75s cubic-bezier(0.4, 0, 0.2, 1) infinite;
      margin-bottom: 24px;
    }}
    .icon-container {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: rgba(34, 197, 94, 0.12);
      border: 1px solid rgba(34, 197, 94, 0.3);
      color: #22c55e;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      margin: 0 auto 20px;
      box-shadow: 0 0 24px rgba(34, 197, 94, 0.2);
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 10px;
      color: #ffffff;
    }}
    p {{
      font-size: 13.5px;
      color: #94a3b8;
      line-height: 1.55;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 9999px;
      background: rgba(99, 102, 241, 0.12);
      border: 1px solid rgba(99, 102, 241, 0.25);
      font-size: 11px;
      color: #a5b4fc;
      margin-top: 20px;
      font-mono: monospace;
    }}
    .close-btn {{
      display: inline-block;
      margin-top: 20px;
      padding: 10px 24px;
      background: #6366f1;
      color: #ffffff;
      border: none;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s ease;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }}
    .close-btn:hover {{ opacity: 0.9; }}
  </style>
</head>
<body>
  <div class="auth-card" id="card">
    <div class="spinner-ring" id="spinner"></div>
    <h1 id="title">Connecting to Google</h1>
    <p id="status-text">Redirecting to Google account selection... Please choose your Gmail account.</p>
    <div class="badge" id="badge">Google OAuth &bull; Prompt Compiler Desktop</div>
  </div>

  <script>
    window.addEventListener('load', async () => {{
      const statusEl = document.getElementById('status-text');
      try {{
        const clerk = window.Clerk;
        if (!clerk) {{
          throw new Error('Clerk SDK script could not be loaded.');
        }}

        const allowedOrigins = [
          window.location.origin,
          'http://localhost:*',
          'https://localhost:*',
          'http://127.0.0.1:*',
          'https://127.0.0.1:*',
          'tauri://localhost',
          'https://tauri.localhost'
        ];

        await clerk.load({{
          allowedRedirectOrigins: allowedOrigins
        }});

        // If an existing session is active in this browser from a previous login,
        // sign out first so that Google prompts account selection and the user can freely choose or switch accounts.
        if (clerk.session) {{
          try {{
            await clerk.signOut(() => {{}});
          }} catch (signOutErr) {{
            console.debug('Clerk signOut notice before account switch:', signOutErr);
          }}
        }}

        const callbackUrl = window.location.origin + '/api/auth/sso-callback';

        // 3. Trigger Google OAuth redirect with oidcPrompt: select_account and explicit allowed redirect URL
        try {{
          await clerk.client.signIn.authenticateWithRedirect({{
            strategy: 'oauth_google',
            redirectUrl: callbackUrl,
            redirectUrlComplete: callbackUrl,
            oidcPrompt: 'select_account'
          }});
        }} catch (signInErr) {{
          console.debug('SignIn authenticateWithRedirect failed, trying SignUp:', signInErr);
          await clerk.client.signUp.authenticateWithRedirect({{
            strategy: 'oauth_google',
            redirectUrl: callbackUrl,
            redirectUrlComplete: callbackUrl,
            oidcPrompt: 'select_account'
          }});
        }}
      }} catch (err) {{
        console.error('Google OAuth initialization error:', err);
        statusEl.innerText = 'Unable to launch Google authentication: ' + (err.message || err);
      }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@router.get("/api/auth/sso-callback", response_class=HTMLResponse)
async def sso_callback() -> HTMLResponse:
    """Serve external browser callback page that finalizes OAuth and sends session to desktop app."""
    pub_key = settings.clerk_publishable_key or "pk_test_bW9kZWwtY29icmEtNzA4Ni5jbGVyay5hY2NvdW50cy5kZXYk"
    fapi_domain = _get_clerk_frontend_api(pub_key)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Prompt Compiler — Sign In Complete</title>
  <script
    async
    crossorigin="anonymous"
    data-clerk-publishable-key="{pub_key}"
    src="https://{fapi_domain}/npm/@clerk/clerk-js@6/dist/clerk.browser.js"
    type="text/javascript">
  </script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #090a0f;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }}
    .auth-card {{
      background: #111420;
      border: 1px solid #1e2538;
      border-radius: 24px;
      padding: 44px 32px;
      text-align: center;
      max-width: 440px;
      width: 100%;
      box-shadow: 0 24px 48px rgba(0,0,0,0.6), 0 0 1px rgba(255,255,255,0.1);
    }}
    .icon-container {{
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: rgba(34, 197, 94, 0.12);
      border: 1px solid rgba(34, 197, 94, 0.3);
      color: #22c55e;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 28px;
      margin: 0 auto 20px;
      box-shadow: 0 0 24px rgba(34, 197, 94, 0.2);
    }}
    .spinner-ring {{
      display: inline-block;
      width: 44px;
      height: 44px;
      border: 3.5px solid rgba(255, 255, 255, 0.08);
      border-top-color: #6366f1;
      border-radius: 50%;
      animation: spin 0.75s cubic-bezier(0.4, 0, 0.2, 1) infinite;
      margin-bottom: 20px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-bottom: 10px;
      color: #ffffff;
    }}
    p {{
      font-size: 13.5px;
      color: #94a3b8;
      line-height: 1.55;
      margin-bottom: 24px;
    }}
    .close-btn {{
      display: inline-block;
      padding: 10px 24px;
      background: #6366f1;
      color: #ffffff;
      border: none;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity 0.15s ease;
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }}
    .close-btn:hover {{
      opacity: 0.9;
    }}
  </style>
</head>
<body>
  <div class="auth-card" id="card">
    <div class="spinner-ring" id="spinner"></div>
    <h1 id="title">Completing Sign-In...</h1>
    <p id="status-text">Verifying credentials and syncing session with Prompt Compiler...</p>
  </div>

  <script>
    async function syncSessionAndDisplay(clerk) {{
      const card = document.getElementById('card');
      const statusEl = document.getElementById('status-text');

      if (!clerk.session) {{
        statusEl.innerText = 'Authentication callback completed without an active session.';
        return false;
      }}

      const token = await clerk.session.getToken();
      const userId = clerk.user ? clerk.user.id : null;
      const email = clerk.user && clerk.user.primaryEmailAddress ? clerk.user.primaryEmailAddress.emailAddress : '';
      const firstName = clerk.user ? clerk.user.firstName : '';
      const lastName = clerk.user ? clerk.user.lastName : '';
      const imageUrl = clerk.user && clerk.user.imageUrl ? clerk.user.imageUrl : '';

      const postRes = await fetch('/api/auth/desktop-session', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          token: token,
          user_id: userId,
          email: email,
          first_name: firstName,
          last_name: lastName,
          image_url: imageUrl
        }})
      }});

      if (postRes.ok) {{
        const displayName = firstName || (email ? email.split('@')[0] : 'Developer');
        card.innerHTML = `
          <div class="icon-container">&check;</div>
          <h1>Authentication Successful!</h1>
          <p>Welcome, <strong>${{displayName}}</strong>!<br>Your Google session is securely connected to Prompt Compiler.<br>You can close this tab and return to the application.</p>
          <button class="close-btn" onclick="window.close()">Close Window</button>
        `;
        setTimeout(() => {{
          try {{ window.close(); }} catch (e) {{}}
        }}, 2200);
        return true;
      }} else {{
        const errData = await postRes.json().catch(() => ({{}}));
        statusEl.innerText = 'Failed to sync session: ' + (errData.detail || 'Server error.');
        return false;
      }}
    }}

    window.addEventListener('load', async () => {{
      const statusEl = document.getElementById('status-text');
      try {{
        const clerk = window.Clerk;
        if (!clerk) {{
          throw new Error('Clerk SDK script not available.');
        }}

        const allowedOrigins = [
          window.location.origin,
          'http://localhost:*',
          'https://localhost:*',
          'http://127.0.0.1:*',
          'https://127.0.0.1:*',
          'tauri://localhost',
          'https://tauri.localhost'
        ];

        await clerk.load({{
          allowedRedirectOrigins: allowedOrigins
        }});

        try {{
          await clerk.handleRedirectCallback({{
            navigate: () => {{}}
          }});
        }} catch (cbErr) {{
          console.debug('handleRedirectCallback notice:', cbErr);
        }}

        await syncSessionAndDisplay(clerk);
      }} catch (err) {{
        console.error('SSO Callback error:', err);
        statusEl.innerText = 'Authentication error: ' + (err.message || err);
      }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

