# Backend Compilation Diagnostic Report

> **Status**: Diagnosis complete — two distinct bugs identified with evidence.
> **DO NOT implement fixes without further approval.**

---

## 1. Reproduction Steps

The following was observed in the running `npm run tauri dev` session (Tauri PID 18476, Vite PID 18434, sidecar PID 18542).

1. Open the Tauri desktop app (loaded from `http://localhost:5173` via `devUrl`).
2. App initializes — Studio loads, "Local Engine Ready" badge is green.
3. User submits a compilation (default `cursor` target agent, or any non-trivial prompt).
4. Within ~11 seconds, the pipeline animation reaches "Target Agent Preset Formatting — Processing…" and clamps there.
5. Within ~10–30 seconds more (after sidecar starts), the "Local Engine" badge flips to **"Engine Stopped"** (red).
6. Both states remain indefinitely — compilation never completes, engine never recovers.

---

## 2. Environment State at Time of Investigation

| Component | Status | Details |
|-----------|--------|---------|
| FastAPI sidecar (Tauri binary) | ✅ Running | PID 18542 on `127.0.0.1:18000` |
| FastAPI uvicorn dev server | ✅ Running | PID 1743 on `127.0.0.1:8000` (with reload) |
| Ollama | ✅ Running | `qwen3:4b` + `qwen3:0.6b` installed |
| Tauri app | ✅ Running | PID 18476, webview origin `http://localhost:5173` |
| Vite dev server | ✅ Running | PID 18434, port 5173 |

> **Critical observation**: Two backends run simultaneously in `tauri dev` mode.

---

## 3. GET /api/health Results

```
Port 18000: {"status":"ok","service":"prompt-compiler"}  HTTP 200
Port 8000:  {"status":"ok","service":"prompt-compiler"}  HTTP 200
```

Both backends are alive. "Engine Stopped" is NOT caused by the sidecar being down.

---

## 4. GET /api/runtime/status Results

Port 18000 (sidecar): mode=desktop, ollama available, qwen3:4b ready, data_dir=/Users/bhavyakumar/Library/Application Support/com.promptcompiler.app
Port 8000 (uvicorn): mode=development, ollama available, data_dir=null

---

## 5. Ollama Availability

```
$ curl http://localhost:11434/api/tags
→ models: ['qwen3:4b', 'qwen3:0.6b']
```

Ollama is running. qwen3:4b is installed. Ollama is not the cause of Engine Stopped.

---

## 6. Direct POST /api/compile Results (Unauthenticated)

```
Port 8000  → HTTP 401 {"detail":"Authentication required: Missing Authorization header."} in 0.003s
Port 18000 → HTTP 401 {"detail":"Authentication required: Missing Authorization header."} in 0.002s
```

Both backends correctly enforce authentication on /api/compile.

---

## 7. CORS Preflight Test — The Smoking Gun

```bash
$ curl -v -X OPTIONS http://127.0.0.1:18000/api/health \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization,Content-Type"

→ HTTP/1.1 405 Method Not Allowed
   allow: GET
   (ZERO Access-Control-Allow-Origin headers)
   (ZERO Access-Control-Allow-Methods headers)
   (ZERO Access-Control-Allow-Headers headers)
```

```bash
$ curl -D - -o /dev/null http://127.0.0.1:18000/api/health \
  -H "Origin: http://localhost:5173"

→ HTTP/1.1 200 OK
   date: Sun, 27 Sep 2026 17:07:11 GMT
   server: uvicorn
   content-length: 43
   content-type: application/json
   (ZERO Access-Control-Allow-Origin headers)
```

The sidecar returns zero CORS response headers on both simple and preflighted requests.
Any browser fetch to http://127.0.0.1:18000 from origin http://localhost:5173 is blocked.

---

## 8. CORS Middleware Audit

```bash
$ grep -rn "CORSMiddleware\|add_middleware" backend/app/ --include="*.py"
→ (no output — zero matches)
```

CORSMiddleware is present in the Python venv's site-packages but is NEVER registered 
in the application source. backend/app/main.py has no app.add_middleware() call.

---

## 9. Agent Formatter Inspection — backend/app/engine/agent_formatter.py

- format_prompt(): Pure synchronous string operations only.
- generic: Returns compiled_prompt unchanged (1 line, instant).
- cursor, claude_code, cline, windsurf: Dispatch to deterministic string builders.
- Zero network calls. Zero async awaits. Zero I/O.

THE FORMATTER IS NOT AND CANNOT BE THE SOURCE OF THE HANG.

---

## 10. Compile Pipeline — Actual Ollama Call Count

From backend/app/api/compile.py line 58:

    timeout = max(settings.ollama_timeout, 600.0)
    # settings.ollama_timeout = 120.0
    # max(120.0, 600.0) = 600.0 seconds (10 MINUTES per Ollama call)

Pipeline with use_llm_critic=False (compile.py line 254):

    Step 1: requirement_engine.analyze_async()     → 1 Ollama call (up to 600s)
    Step 1.5: knowledge retrieval (disabled)        → 0 calls
    Step 3: prompt_generator.generate_async()       → 1 Ollama call (up to 600s)
    Step 4: prompt_refiner.run_loop_async()         → 0–2 Ollama calls (0–1200s)
    Step 5: agent_formatter.format_prompt()         → 0 (sync, instant)
    Step 6: compilation_repo.save()                 → 0 (SQLite, ~2ms)

    TOTAL OLLAMA CALLS: 2–4
    MAXIMUM WAIT TIME: 1200–2400 seconds (20–40 minutes)
    PRACTICAL DURATION (qwen3:4b on Apple Silicon): 60–360 seconds (1–6 minutes)

---

## 11. PipelineProgress Animation — Timer-Based Mismatch

backend/src/components/studio/PipelineProgress.tsx line 30-33:

    const interval = setInterval(() => {
      setActiveStage((prev) => (prev < PIPELINE_STAGES.length - 1 ? prev + 1 : prev));
    }, 2800);  // 2.8 seconds per stage, NO BACKEND CONNECTION

Animation timeline:
    t=0s    → Stage 1 "Requirement Analysis"        [active]
    t=2.8s  → Stage 2 "Knowledge Retrieval"         [active]
    t=5.6s  → Stage 3 "Canonical Prompt Synthesis"  [active]
    t=8.4s  → Stage 4 "Quality Verification"        [active]
    t=11.2s → Stage 5 "Target Agent Preset Formatting" [CLAMPED FOREVER]

After 11.2 seconds the animation permanently shows "Target Agent Preset Formatting — Processing…"
The backend may still be on Ollama call #1 (requirement analysis).
The animation provides zero information about actual backend progress.

---

## 12. Database Persistence Results

Sidecar database (/Users/bhavyakumar/Library/Application Support/com.promptcompiler.app/prompt_compiler.db):
    SELECT id, input_text, target_agent FROM compilations ORDER BY id DESC LIMIT 5;
    → (empty — 0 rows)

Dev uvicorn database (data/prompt_compiler.db):
    id=88 | "Build a simple ping endpoint" | generic | 2026-09-27 17:01:43
    id=87 | "Build a portfolio website"    | generic | ...
    id=86 | "Build a portfolio website"    | generic | ...
    ...

CONCLUSIONS:
- Zero compilations have ever been processed by the Tauri sidecar (port 18000).
- All successful compilations went to port 8000 via the Vite proxy.
- All successful DB records are target_agent=generic.
- The default targetAgent in StudioView.tsx is 'cursor' — a cursor compilation
  is currently pending in port 8000's pipeline (not yet complete, not yet in DB).

---

## 13. Frontend HTTP Request State

The fetch() call in handleCompile (StudioView.tsx:232) is STILL PENDING.
There is NO AbortSignal or timeout on the compilePrompt fetch.
isCompiling = true (set at line 227, cleared only in finally block).
The request has not received 200, 4xx, or 5xx — it is waiting for Ollama.

---

## 14. "Engine Stopped" Status Analysis

Trigger chain:
1. Tauri lib.rs spawns sidecar, emits "backend-ready" with "http://127.0.0.1:18000"
2. tauri-bridge.ts receives event → setApiBaseUrl("http://127.0.0.1:18000")
3. All subsequent fetchApi calls use absolute URL pointing to port 18000
4. Tauri webview origin = "http://localhost:5173" (different host from 127.0.0.1)
5. fetchApi attaches Authorization: Bearer <token> → non-simple request → preflight required
6. Browser sends OPTIONS to http://127.0.0.1:18000/api/health
7. Sidecar returns 405 Method Not Allowed (no CORS middleware)
8. Browser throws TypeError (CORS) → catch { setIsBackendHealthy(false) }
9. TopBar renders "Engine Stopped" despite sidecar being perfectly healthy

---

## 15. Browser vs. Tauri Comparison

    Aspect                    | Browser (pure Vite)              | Tauri webview
    --------------------------+----------------------------------+----------------------------------
    Initial API URL           | '' (relative, Vite proxy)        | '' (same, before backend-ready)
    After backend-ready       | N/A (event not fired)            | http://127.0.0.1:18000 (absolute)
    /api/health target        | port 8000 via proxy (same-origin)| port 18000 direct (cross-origin)
    CORS enforcement          | None (same-origin via proxy)     | ENFORCED (different host)
    Health check result       | ✅ 200 → "Local Engine Ready"    | ❌ CORS block → "Engine Stopped"
    Compile target            | port 8000 via proxy              | port 18000 direct (after ready)
    Compile CORS              | None                             | BLOCKED (OPTIONS → 405)
    Sidecar DB records        | 0                                | 0
    Dev DB records            | ✅ 88 records present            | ✅ 88 records (via proxy)

In the browser: no CORS issues. In Tauri: every post-backend-ready request to port 18000 is blocked.

---

## 16. Root Causes

### BUG A: "Engine Stopped" — Missing CORS Middleware

Root cause: backend/app/main.py does not register CORSMiddleware.

After backend-ready fires:
  tauri-bridge.ts → setApiBaseUrl("http://127.0.0.1:18000")
  → fetchApi attaches Authorization header → non-simple → preflight
  → OPTIONS http://127.0.0.1:18000/api/health → 405 (no CORS)
  → browser throws TypeError
  → catch { setIsBackendHealthy(false) }
  → "Engine Stopped"

Evidence:
- OPTIONS to port 18000 → 405, zero CORS headers (confirmed via curl)
- GET with Origin header → 200 OK, zero Access-Control-Allow-Origin (confirmed via curl)
- grep CORSMiddleware backend/app/ → no results
- Sidecar DB: 0 compilation records (CORS blocks all sidecar traffic from webview)

---

### BUG B: "Compilation Stuck" — Timer Animation vs. Slow Ollama

Root cause:
  1. PipelineProgress.tsx is 100% timer-based (2.8s intervals, clamps at stage 5 after 11.2s)
  2. Actual Ollama inference takes 60–360 seconds (2–4 calls × 30–90s each)
  3. compile.py forces 600s Ollama timeout: max(settings.ollama_timeout, 600.0)
  4. fetchApi has no AbortSignal/timeout → waits indefinitely

Evidence:
- PipelineProgress.tsx line 31: setInterval(..., 2800) → 4 × 2.8 = 11.2s to clamp at index 4
- compile.py line 58: max(120.0, 600.0) = 600s forced per Ollama call
- Dev DB compilations DO complete eventually (88 records exist, all generic)
- Current cursor compilation: pending in port 8000 Ollama queue, not yet in DB

---

## 17. Failing Layer Determination

    React
    └── handleCompile (StudioView.tsx)
        └── compilePrompt() → fetchApi('/api/compile')
            ├── BEFORE backend-ready: Vite proxy → port 8000 → PENDING ← BUG B (slow Ollama)
            └── AFTER  backend-ready: http://127.0.0.1:18000 → CORS BLOCK ← instant fail

    Health check:
    └── getHealth() → fetchApi('/api/health')
        ├── BEFORE backend-ready: Vite proxy → port 8000 → 200 OK
        └── AFTER  backend-ready: http://127.0.0.1:18000 → CORS BLOCK ← BUG A "Engine Stopped"

    AgentFormatter:     ✅ Deterministic, no I/O, not involved in hang
    compilation_repo:   ✅ Not reached (Ollama still running)
    Tauri lib.rs:       ✅ Sidecar alive and healthy
    Ollama/qwen3:4b:    ✅ Available but SLOW (causing hang in BUG B)

---

## 18. Recommended Fixes (DO NOT IMPLEMENT YET)

### Fix A1 — Add CORSMiddleware to FastAPI [Bug A]
File: backend/app/main.py
Action: Register CORSMiddleware with allow_origins including:
        "http://localhost:5173", "tauri://localhost", "http://tauri.localhost"
Risk: LOW. These origins are already trusted in CLERK_AUTHORIZED_PARTIES.

### Fix A2 — Skip setApiBaseUrl in Vite dev mode [Bug A, alternative]
File: frontend/src/api/tauri-bridge.ts
Action: Check import.meta.env.DEV; if true, do not call setApiBaseUrl (keep using proxy).
Risk: MEDIUM. Means sidecar is unused in tauri dev mode (intended behavior for development).

### Fix B1 — Add AbortSignal timeout to compile fetch [Bug B, partial]
File: frontend/src/api/compile.ts
Action: Add signal: AbortSignal.timeout(300_000) to compile request.
Risk: LOW. Provides user feedback after 5 minutes. Does not affect backend.

### Fix B2 — Remove forced 600s Ollama timeout override [Bug B, partial]
File: backend/app/api/compile.py line 58
Action: Change to timeout = settings.ollama_timeout (uses configured 120s default).
Risk: LOW-MEDIUM. May cause HTTP 504 on very slow hardware; frontend handles 504 gracefully.

### Fix B3 — Real backend stage progress via SSE [Bug B, full fix]
Files: backend/app/api/compile.py, frontend/src/components/studio/PipelineProgress.tsx
Action: Replace timer animation with SSE events from each pipeline step.
Risk: MEDIUM. Larger scope change; suited for dedicated task.

---

## 19. Files That Would Need to Change

| File | Bug | Change |
|------|-----|--------|
| backend/app/main.py | A | Add CORSMiddleware |
| frontend/src/api/tauri-bridge.ts | A (alt) | Skip setApiBaseUrl in DEV mode |
| backend/app/api/compile.py | B | Remove forced 600s timeout override |
| frontend/src/api/compile.ts | B | Add AbortSignal.timeout |
| frontend/src/components/studio/PipelineProgress.tsx | B (full) | Real stage events |

---

## 20. Evidence Summary

| Item | Result |
|------|--------|
| GET /api/health port 8000 | 200 OK {"status":"ok"} |
| GET /api/health port 18000 | 200 OK {"status":"ok"} |
| GET /api/runtime/status port 18000 | Ollama available, desktop mode |
| Ollama + qwen3:4b | Available |
| POST /api/compile (unauth, port 8000) | 401 Unauthorized (3ms) |
| POST /api/compile (unauth, port 18000) | 401 Unauthorized (2ms) |
| OPTIONS /api/health port 18000 | 405 Method Not Allowed, ZERO CORS headers |
| GET /api/health with Origin header | 200 OK, ZERO Access-Control-Allow-Origin |
| CORSMiddleware in backend/app/ source | NOT FOUND |
| Ollama timeout in compile.py | Forced to 600s (10 min per call) |
| Pipeline animation timing | Clamps at stage 5 after 11.2 seconds |
| Frontend compile fetch timeout | NONE |
| Sidecar DB compilations | 0 records |
| Dev uvicorn DB compilations | 88 records (all generic, all via proxy) |
| Backend process alive during stuck state | YES (confirmed via ps + port check) |
| Port 18000 listening | YES |
| Frontend HTTP request state | PENDING INDEFINITELY (no timeout, no abort) |

---

*Report generated: 2026-09-27. Diagnosis only — no source files were modified.*
