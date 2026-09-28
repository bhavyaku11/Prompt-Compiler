# Task 33 — Desktop Authentication, Session & Offline Strategy Report

## 1. Executive Summary & Objective
The objective of Task 33 was to implement and verify the desktop authentication, session, and offline strategy for the Prompt Compiler macOS desktop application. The application integrates:
- Tauri 2 desktop shell (`src-tauri/`)
- React 19 / Vite frontend (`frontend/`)
- Local standalone FastAPI sidecar (`backend/`) on `127.0.0.1:18000` (or dynamically allocated port)
- Clerk user authentication & Clerk Device Trust
- Authoritative backend data ownership (`backend/app/database/`)
- Local SQLite persistence and local vector search (`sqlite-vec`)
- Local Ollama AI generation and native macOS filesystem project ingestion

Task 33 ensures that authentication behavior is correct, secure, and predictable in the desktop environment, especially when network connectivity transitions between online and offline, without weakening backend security or creating fake local bypasses.

---

## 2. Current Auth Architecture

### 2.1 Principle of Authoritative Backend Verification
Prompt Compiler operates under a strict Zero Trust model between the frontend webview and the local engine:
- The frontend client is treated as an untrusted client environment.
- The desktop client distribution does **not** package or expose `CLERK_SECRET_KEY`.
- All protected backend operations (project creation, listing, updating, prompt compilation, document ingestion, project memory, interview sessions) require an authenticated Clerk JWT session token.
- Unauthenticated requests or requests with invalid/expired tokens return `HTTP 401 Unauthorized`.
- The user's identity is derived strictly from verified JWT claims (`sub` / `user_id`). Client-supplied user identity parameters are rejected or ignored.

### 2.2 Token Transport & Propagation
Previously, `frontend/src/api/client.ts` did not attach the `Authorization: Bearer <token>` header to requests made by `fetchApi`. In Task 33:
- Introduced a dynamic token provider mechanism via `setAuthTokenGetter(getter: () => Promise<string | null>)` in `client.ts`.
- Integrated `AuthTokenSync` in `App.tsx` directly under `<ClerkProvider>`, registering Clerk's `useAuth().getToken` with the API client.
- Fallback check checks `window.Clerk?.session?.getToken()` if the registered getter is temporarily unavailable.
- In `fetchApi`, every outgoing HTTP request to the backend engine automatically attaches `Authorization: Bearer <token>` when a valid token is present.
- If the backend returns `401 Unauthorized`, `fetchApi` translates the raw error into a user-friendly message (`"Authentication session expired or invalid. Please sign in to continue."`) and dispatches a custom browser event `prompt-compiler:auth-required`.

### 2.3 Cryptographic Offline Signature Verification
Because desktop environments cannot safely embed `CLERK_SECRET_KEY`, the local FastAPI sidecar verifies JWT tokens using Clerk's RSA public key (`CLERK_JWT_KEY`):
- Retrieved the public RSA key for the Clerk development instance (`model-cobra-7086.clerk.accounts.dev`) and embedded it into `backend/app/config.py` as `DEFAULT_CLERK_JWT_KEY`.
- `Settings.CLERK_JWT_KEY` defaults to `os.getenv("CLERK_JWT_KEY", DEFAULT_CLERK_JWT_KEY)`.
- When verifying tokens in `backend/app/api/auth.py`, the backend calls:
  ```python
  AuthenticateRequestOptions(
      jwt_key=settings.clerk_jwt_key,
      authorized_parties=settings.clerk_authorized_parties_list,
  )
  ```
- Because the RSA public key is present locally, the Clerk Python SDK mathematically validates the signature, issuer, expiry (`exp`), and audience without requiring any outbound network calls to Clerk servers.

---

## 3. Clerk Session Mechanism & Maintenance

### 3.1 Session Token Lifecycle
- Clerk issues short-lived JWT tokens (typically 60 seconds) backed by a long-lived session cookie or refresh token managed in the frontend webview's persistent web storage.
- The Clerk frontend SDK automatically refreshes the short-lived session token in the background while network connectivity is active.
- When `fetchApi` invokes `getToken()`, Clerk yields the latest cached or freshly refreshed JWT.

### 3.2 Offline Token Availability
- If internet connectivity drops while a session is active, Clerk continues to provide the unexpired JWT from its in-memory cache until the token's `exp` timestamp is reached.
- During this window, local operations (querying SQLite, RAG retrieval, running Ollama generation, folder ingestion) continue uninterrupted because the backend sidecar verifies the token signature entirely offline using `CLERK_JWT_KEY`.
- Once the short-lived token expires and cannot be refreshed due to network unavailability, subsequent protected backend calls receive `HTTP 401 Unauthorized`.
- The frontend catches this 401, dispatches `prompt-compiler:auth-required`, and displays a non-destructive session banner prompting the user to reconnect once online.

---

## 4. Device Trust Compatibility
Task 31 established robust support for Clerk Device Trust (`needs_client_trust`, secondary verification factors, SMS/email codes, resend countdowns, and cancellation). Task 33 completely preserves this functionality:
- `frontend/src/components/auth/auth-switch.tsx` handles `status === "needs_client_trust"` and directs the user to the Device Verification workflow.
- Secondary factors (`phone_code`, `email_code`) and resend timers remain fully functional.
- The Device Trust flow interacts exclusively with Clerk's frontend authentication endpoints. The backend sidecar remains neutral, accepting the resulting JWT once Device Trust verification completes.
- Network loss during a Device Trust challenge correctly transitions to the offline error boundary with a "Retry Connection" action.

---

## 5. Desktop Session Behavior & Status Semantics

### 5.1 Three Distinct States Decoupled
A primary defect in earlier versions was confusing Local Engine Health with Internet Connectivity (e.g., mislabeling the application as "Offline" when the local engine was 100% operational). Task 33 strictly separates three independent states:

1. **Local Engine Status (FastAPI Sidecar)**:
   - Evaluated by pinging `GET /api/health` on `127.0.0.1:18000`.
   - **Local Engine Ready**: Displayed with an Emerald green pulsing dot when the sidecar is responsive.
   - **Engine Stopped / Connecting**: Displayed with a Rose red icon if the sidecar fails to respond.

2. **Network & Clerk Connectivity**:
   - Evaluated via `window.navigator.onLine` and `online`/`offline` window events.
   - Indicates whether the client can communicate with Clerk and external services.

3. **Authenticated User Session**:
   - Evaluated via Clerk's `isSignedIn` and `user` state.
   - **Account Connected**: User is signed in and online.
   - **Account Offline**: User was signed in, but the network connection is currently offline. The user's active project data remains visible, and local operations succeed while the token remains valid.
   - **Sign In Required**: No user session exists. Protected operations are disabled.

### 5.2 Studio TopBar Implementation
In `frontend/src/components/studio/TopBar.tsx`:
- The Local Engine status badge and the Account/Network status badge are rendered side-by-side as separate, dedicated pills.
- The Engine badge never displays "Offline" when `health?.status === "ok"`.
- The user profile dropdown indicates `"Authenticated via Clerk"` when online, or `"Local Session (Offline)"` when working disconnected.

---

## 6. Restart Behavior & Survival

### 6.1 Application Restart While Online
- Tauri shell boots the sidecar binary (`prompt-compiler-backend-aarch64-apple-darwin`).
- The frontend webview initializes Clerk from persistent webview storage (`IndexedDB` / `localStorage`).
- Clerk restores the session, requests a fresh token, and `AuthTokenSync` registers the getter.
- The Studio immediately loads the user's projects and state.

### 6.2 Application Restart While Offline
- If the application is launched without an internet connection:
  - The sidecar starts successfully, creates/migrates the local SQLite database, and serves `GET /api/health` with `status: ok`.
  - The Clerk JavaScript SDK cannot reach `*.clerk.accounts.dev` to validate the session.
  - In `frontend/src/views/StudioView.tsx` and `AuthView.tsx`, an `isLoaded` timeout (6 seconds) prevents indefinite loading spinners and displays a clean offline message:
    > *"Network Connection Unavailable. Prompt Compiler requires an active connection to verify your Clerk account upon initial startup."*
  - As soon as the network interface reconnects (`online` event), Clerk initializes automatically without requiring an app relaunch.

---

## 7. Security Boundaries & Invariants Preserved
Task 33 adhered strictly to core architectural security boundaries:
1. **No Fake Local Auth**: No mock authentication bypasses were introduced in the backend. Unauthenticated calls to `/api/projects` or `/api/compile` strictly return `401 Unauthorized`.
2. **No Embedded Secrets**: `CLERK_SECRET_KEY` is not bundled into the desktop app or sidecar binary. Only the public verification key (`CLERK_JWT_KEY`) is configured.
3. **Backend Remains Authoritative**: Data ownership cannot be spoofed by sending arbitrary client headers. All database operations filter strictly by the verified JWT `sub`.
4. **Authorized Parties**: Requests from Tauri webviews (`tauri://localhost`, `http://tauri.localhost`, `http://localhost:5173`) are explicitly authorized in `CLERK_AUTHORIZED_PARTIES`.

---

## 8. Automated Test Matrix

### 8.1 Backend Tests (`backend/tests/test_auth.py`)
Added `TestDesktopAuthSessionOfflineStrategy` containing 5 new tests:
- `test_default_jwt_key_preconfigured`: Verifies `DEFAULT_CLERK_JWT_KEY` is formatted and loaded into `settings.clerk_jwt_key`.
- `test_local_offline_token_verification_no_network`: Monkey-patches socket connections to forbid outbound network calls, signs a JWT using the matching test private RSA key, and verifies the backend validates the token and extracts `user_id` without network access.
- `test_expired_token_returns_401_session_expired`: Confirms tokens with an expired `exp` timestamp are rejected with `401 Unauthorized`.
- `test_tampered_token_rejected_locally`: Modifies the JWT payload and confirms the cryptographic signature check rejects it immediately.
- `test_tauri_authorized_party_accepted`: Verifies that tokens with `azp: "tauri://localhost"` or `"http://tauri.localhost"` are accepted.

### 8.2 Frontend Tests (`frontend/tests/auth_client_test.mjs`)
Added 4 automated unit tests:
- `setAuthTokenGetter registers and clears token provider`: Verified registration and unregistration.
- `fetchApi automatically attaches Bearer token from token getter`: Verified HTTP `Authorization` header injection.
- `fetchApi does not attach Authorization when unauthenticated`: Verified clean behavior when signed out.
- `fetchApi dispatches prompt-compiler:auth-required on HTTP 401`: Verified browser event notification for expired sessions.

### 8.3 Regression Verification
- **Backend Test Suite**: 98 passed tests across `test_auth.py`, `test_data_ownership.py`, `test_desktop_runtime.py`, `test_filesystem_integration.py`, and `test_standalone_executable.py`.
- **Frontend Linter (`oxlint`)**: 0 errors.
- **Frontend Typecheck & Build (`tsc -b && vite build`)**: Clean build in under 500ms.
- **Tauri Rust Check (`cargo check`)**: Clean check in under 4 seconds.

---

## 9. Tauri Runtime Verification
Verified in live Tauri development runtime:
1. Sidecar starts on `127.0.0.1:18000` with SQLite database initialized.
2. `GET /api/health` returns `200 OK` (`status: "ok"`).
3. `GET /api/runtime/status` returns `200 OK` (`desktop_mode: true`).
4. `GET /api/auth/me` returns `401 Unauthorized` when unauthenticated.
5. `GET /api/auth/me` with invalid bearer token returns `401 Unauthorized`.
6. UI renders distinct status indicators for "Local Engine Ready" and "Account Connected" / "Account Offline".

---

## 10. Known Limitations & Next Steps
- **Initial Offline Startup**: Clerk SDK requires network access at least once on cold launch to retrieve the initial session keys. Subsequent restarts within the browser cache TTL can restore cached sessions.
- **Session Duration Offline**: Once a short-lived token expires offline (default ~60 seconds), write operations requiring backend authentication will be rejected until the client reconnects to the internet to allow Clerk to refresh the token. Future tasks may explore longer token TTLs or local offline caching policies if desired.
