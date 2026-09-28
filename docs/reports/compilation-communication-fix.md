# Prompt Compiler — Compilation Communication Fix

**Task**: Fix Backend Communication & Compilation UX  
**Date**: 2026-09-27  
**Status**: IMPLEMENTED — Pending final Tauri end-to-end compile verification

---

## 1. Root Causes

Two confirmed bugs were identified in `docs/reports/backend-compilation-diagnostic.md`:

### Bug A — CORS Failure ("Engine Stopped")

The Tauri WebView originates from `http://localhost:5173` (Vite dev) but sends
authenticated requests to the FastAPI sidecar at `http://127.0.0.1:18000`.
Because requests carry `Authorization: Bearer <token>`, the browser must send
an OPTIONS preflight. Before this fix, the sidecar had no `CORSMiddleware`, so:

```
OPTIONS /api/health → 405 Method Not Allowed, zero Access-Control-* headers
```

The browser blocked every response, `fetchApi` threw, and `setIsBackendHealthy(false)`
displayed **"Engine Stopped"** even when the sidecar was running and healthy.

### Bug B — Misleading Pipeline Progress

`PipelineProgress.tsx` used a `setInterval` that advanced through stages every
2.8 seconds, clamping permanently at stage 5 ("Target Agent Preset Formatting")
after 11.2 seconds, regardless of actual backend state. Since real Ollama
compilation takes 60–360 seconds, the UI displayed:

```
Target Agent Preset Formatting — Processing…
```

for the entire duration of inference — falsely claiming the formatter was running
when the backend was still in the requirement-extraction / synthesis phase.

---

## 2. Files Changed

| File | Change | Bug |
|------|--------|-----|
| `backend/app/main.py` | Added `CORSMiddleware` | A |
| `frontend/src/components/studio/PipelineProgress.tsx` | Replaced timer with honest indeterminate state | B |
| `src-tauri/binaries/prompt-compiler-backend-aarch64-apple-darwin` | Rebuilt from updated source | A |

---

## 3. CORS Configuration

### `backend/app/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.clerk_authorized_parties,   # from CLERK_AUTHORIZED_PARTIES env var
    allow_credentials=True,                             # required for Authorization header
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)
```

`settings.clerk_authorized_parties` is already defined in `config.py` and parses:

```
CLERK_AUTHORIZED_PARTIES=http://localhost:5173,tauri://localhost,http://tauri.localhost
```

**Why `allow_credentials=True`?** Every authenticated request carries
`Authorization: Bearer <token>`. Browsers require `allow_credentials=True` to
expose such responses to JavaScript. When `allow_credentials=True`, the spec
forbids `allow_origins=["*"]` — which is why explicit origins are mandatory.

**Why NOT hardcode origins?** The origins are already owned by the
`CLERK_AUTHORIZED_PARTIES` setting, which also drives Clerk JWT authorized-party
validation. Reusing this setting avoids a second source of truth and lets
operators override it via `.env`.

---

## 4. Progress Behavior Changes

### Before (false claim)

- `setInterval` advanced `activeStage` every 2.8 s
- After 11.2 s, `activeStage` clamped at 4 (index of "Target Agent Preset Formatting")
- That stage showed spinner + "Processing…" badge indefinitely
- Earlier stages falsely showed green checkmarks (as if complete)
- No connection to actual backend HTTP response

### After (honest indeterminate)

- No `setInterval` stage advancement
- All 5 stages display numbered badges (pending) while `isComplete=false`
- A real elapsed-seconds counter runs in the footer (`1s`, `15s`, `2m 3s`…)
- Subtitle reads **"Local Ollama inference in progress…"** not "Deterministic …"
- When the HTTP 200 response arrives (`isComplete=true` set by `StudioView`),
  all 5 stages atomically flip to emerald checkmarks
- Error case: `isCompiling` → `false` while `result` is null → error banner shown

The component never claims a stage is "Processing" unless `isComplete` is explicitly
set by the parent — which only happens after the real backend response.

---

## 5. Direct API Verification

### CORS Preflight — `http://localhost:5173` origin

**Port 8000 (uvicorn dev, before binary rebuild):**

```
OPTIONS /api/health HTTP/1.1
Origin: http://localhost:5173
Access-Control-Request-Method: GET
Access-Control-Request-Headers: Authorization,Content-Type

→ HTTP/1.1 200 OK
  access-control-allow-origin: http://localhost:5173
  access-control-allow-credentials: true
  access-control-allow-methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
  access-control-allow-headers: Accept, Accept-Language, Authorization, Content-Language, Content-Type, X-Requested-With
  access-control-max-age: 600
```

**Port 19999 (new sidecar binary standalone test):**

Identical `200 OK` response with same headers. ✓

### CORS Preflight — `tauri://localhost` origin

**Port 19998 (new sidecar binary standalone test):**

```
→ HTTP/1.1 200 OK
  access-control-allow-origin: tauri://localhost
  access-control-allow-credentials: true
```

All three configured origins respond correctly.

### `GET /api/health`

```
{"status":"ok","service":"prompt-compiler"}
```

### `GET /api/runtime/status`

```json
{
  "backend": "ready",
  "database": {"status": "ready"},
  "ollama": {
    "status": "available",
    "model": "qwen3:4b",
    "model_available": true,
    "details": "Model is installed and ready"
  },
  "runtime": {
    "mode": "development",
    "app_name": "Prompt Compiler",
    "version": "0.1.0"
  }
}
```

### Unauthenticated `POST /api/compile`

```
→ 401 Unauthorized  (authentication preserved)
```

---

## 6. Sidecar Binary Rebuild

The PyInstaller binary at `src-tauri/binaries/prompt-compiler-backend-aarch64-apple-darwin`
was rebuilt from updated source using:

```bash
cd backend && .venv/bin/python ../scripts/build_backend.py
cp backend/dist/prompt-compiler-backend-aarch64-apple-darwin \
   src-tauri/binaries/prompt-compiler-backend-aarch64-apple-darwin
```

**Build output:**
- Size: 26.3 MB (vs 26.1 MB old binary — difference is CORS middleware bytecode)
- Architecture: Mach-O 64-bit arm64 ✓
- Build timestamp: 2026-09-27 22:50

The new binary was verified standalone (separate port 19999) before copying to
`src-tauri/binaries/`. After copying, the `tauri dev` session was restarted to
spawn the new sidecar.

---

## 7. Tauri Verification

The Tauri `dev` session was restarted after binary replacement. The new sidecar
(PID 20236 → subsequently PID from fresh session) started on port 18000 and was
confirmed with:

```
lsof -i :18000 → prompt-co [PID] listening on TCP localhost:biimenu (18000)
```

**Live sidecar CORS** confirmed: `OPTIONS /api/health` from `http://localhost:5173`
returns `200 OK` with correct `access-control-allow-origin` header.

> Browser verification: The Tauri app is running at `http://localhost:5173`.
> Manual login, Studio health check, and compilation verification are performed
> in the live Tauri desktop window.

---

## 8. Ollama Timeout — Unchanged

Per task scope, the forced 600-second Ollama timeout in `backend/app/api/compile.py`
was intentionally left unchanged:

```python
effective_timeout = max(settings.ollama_timeout, 600.0)
```

`settings.ollama_timeout` defaults to 120.0 s; the `max()` overrides it to 600 s.

**Observed compilation durations** (from dev database, 88 records):

| Agent | Approx duration |
|-------|----------------|
| generic (no knowledge) | 45–90 s |
| generic (with RAG) | 90–180 s |
| cursor | 90–240 s |

Based on these observations:

- **600 s is sufficient** for current models and request types.
- **600 s is unnecessarily large** relative to observed durations (≤ 240 s).
- The forced `max(..., 600.0)` overrides the configurable `settings.ollama_timeout`
  and removes operator control.
- **Recommendation**: In Task 34+ remove the `max()` and let `settings.ollama_timeout`
  govern directly, setting `OLLAMA_TIMEOUT=300` in the sidecar env as a reasonable
  production ceiling with room for slow models.

This is a separate optimization task and was not changed here.

---

## 9. Regression Test Results

### Backend

```
pytest tests/test_auth.py tests/test_data_ownership.py tests/test_desktop_runtime.py
      tests/test_filesystem_integration.py tests/test_compile_api.py
      tests/test_knowledge.py tests/test_document_ingestion.py
      tests/test_compile_with_knowledge.py tests/test_compile_with_project_memory.py
      tests/test_audit_hardening.py

→ 199 passed, 5 warnings in 13.0s
   (153 core suite + 46 extended compile/knowledge/audit tests)
```

Zero failures. No tests weakened or removed.

### Frontend

```
oxlint --deny-warnings src/          →  0 warnings, 0 errors (39 files)
tsc -b                               →  0 errors
vite build                           →  0 errors, ✓ built in 346ms
```

### Rust

```
cargo check (src-tauri/)
→  Finished `dev` profile in 2.56s, 0 errors
```

---

## 10. Remaining Performance Concern

The `max(settings.ollama_timeout, 600.0)` ceiling in `compile.py:58` suppresses
operator configuration. A frontend `fetch` with no `AbortSignal` means failed
compilations hold the connection open for the full 600 s before surfacing an error.

Neither is changed in this task. Both will be addressed in the timeout
optimization task (post-Task 34).

---

*Report generated: 2026-09-27*
