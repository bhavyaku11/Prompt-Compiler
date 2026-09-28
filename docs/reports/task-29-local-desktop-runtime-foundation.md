# Task 29 Completion Report: Local Desktop Runtime Foundation

## 1. Objective

The objective of Task 29 is to establish the local desktop runtime architecture, process lifecycle contract, and persistent data boundary for Prompt Compiler, preparing the product for its final distribution target: a standalone macOS application bundle (`Prompt Compiler.app`) distributed through a disk image (`Prompt Compiler.dmg`), operating primarily on the user's local device without relying on a remote backend or cloud database.

This task establishes the architectural contract between the desktop shell, frontend webview, local FastAPI backend process, SQLite storage, and local Ollama daemon.

**Critical Constraints Observed**:
- The final `.app` is **NOT packaged** in this task.
- The final `.dmg` is **NOT built** in this task.
- Clerk authentication and server-side data ownership are **preserved** (no unauthenticated bypass).
- Core prompt compilation remains strictly **local-first** with local Ollama inference.
- Zero automatic model downloads were introduced.

---

## 2. Desktop Architecture

The target desktop topology for Prompt Compiler is:

```text
Prompt Compiler.app
      │
      ├── React frontend (Vite/TypeScript production build)
      │
      ├── Local FastAPI backend (Subprocess / Sidecar)
      │
      ├── SQLite (Persistent database outside .app bundle)
      │
      └── Ollama (Local LLM inference daemon)
```

### Detailed Component Diagram

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Prompt Compiler.app                                │
│                                                                             │
│  ┌────────────────────────┐                   ┌──────────────────────────┐  │
│  │     Tauri 2 Shell      │ ──spawn/manage──> │   Local FastAPI Backend  │  │
│  │   (Rust native core)   │                   │    (Sidecar Subprocess)  │  │
│  └───────────┬────────────┘                   └────────────┬─────────────┘  │
│              │                                             │                │
│       embeds webview                             serves REST / WebSocket   │
│              ▼                                             ▼                │
│  ┌────────────────────────┐                   ┌──────────────────────────┐  │
│  │ React 19 Frontend (UI) │ ──HTTP localhost─>│  Requirement Engine     │  │
│  │  - Studio Workspace    │                   │  Template Engine         │  │
│  │  - Interview Mode      │                   │  Prompt Critic & Refiner │  │
│  │  - Dynamic API Base URL│                   │  Knowledge Retriever RAG │  │
│  └────────────────────────┘                   │  Clerk Auth & Ownership  │  │
│                                               └────────────┬─────────────┘  │
└────────────────────────────────────────────────────────────┼────────────────┘
                                                             │
                      ┌──────────────────────────────────────┴────────┐
                      ▼                                               ▼
     ┌───────────────────────────────────┐           ┌────────────────────────┐
     │  Persistent App Data Directory    │           │  Ollama Daemon (Host)  │
     │  ~/Library/Application Support/   │           │  http://127.0.0.1:11434│
     │    └── Prompt Compiler/           │           │  - qwen3:4b (Local)    │
     │         └── prompt_compiler.db    │           │  - Non-blocking tags   │
     │             (SQLite + sqlite-vec) │           │    availability check  │
     └───────────────────────────────────┘           └────────────────────────┘
```

---

## 3. Desktop Framework Decision

### Selected Framework: Tauri 2

Tauri 2 was selected and initialized as the desktop application shell foundation for Prompt Compiler:

1. **Reuses Existing React/Vite Frontend Directly**:
   - Compiles against `frontend/dist` using Vite.
   - Zero frontend duplication; no rewrite of Studio or Landing Page components.
2. **Native WebKit Footprint**:
   - Uses macOS native `WKWebView`. Avoids bundling 150MB+ Chromium binaries and Node.js runtimes required by Electron.
3. **Clean Sidecar Architecture**:
   - FastAPI remains an independent local process. Business logic, AI compilation, prompt refinement, RAG, and persistence remain strictly in Python. Zero business logic is rewritten in Rust.
4. **Foundation Initialized in `src-tauri/`**:
   - `src-tauri/tauri.conf.json`: Configured with identifier `com.promptcompiler.app`, window sizing, `frontendDist: "../frontend/dist"`, and `devUrl: "http://localhost:5173"`.
   - `src-tauri/capabilities/default.json`: Webview security permissions declared.
   - `src-tauri/src/main.rs` & `src-tauri/src/lib.rs`: Minimal application runner and lifecycle setup.
   - `src-tauri/Cargo.toml` & `src-tauri/build.rs`: Rust project dependencies (`tauri = "2.1"`, `serde`, `serde_json`).
   - Verified via `@tauri-apps/cli info` detecting React, Vite, Cargo 1.98.1, and rustc 1.98.1.

---

## 4. Runtime Lifecycle

The local backend process lifecycle contract guarantees deterministic startup, health verification, and clean shutdown:

```text
Start (User launches Prompt Compiler.app)
  │
  ▼
Backend startup (Desktop shell / manager spawns local FastAPI process)
  │  - Binds loopback host (DESKTOP_BACKEND_HOST, default 127.0.0.1)
  │  - Selects port (DESKTOP_BACKEND_PORT, default 8000)
  │  - Configures data directory (APP_DATA_DIR / PROMPT_COMPILER_DATA_DIR)
  │
  ▼
Health check (Polls GET /api/health)
  │  - Poll interval: 250ms
  │  - Bounded timeout: 15.0 seconds
  │  - Early process exit detection: checks process.poll() every iteration
  │  - Readiness signal: HTTP 200 {"status": "ok"}
  │
  ▼
Frontend ready (Tauri shell injects base URL and renders React UI)
  │  - Base URL resolved dynamically via getApiBaseUrl()
  │  - Studio connects to local backend
  │
  ▼
Application running (Interactive compilation, memory, and RAG active)
  │
  ▼
Graceful shutdown (User quits application)
     - Desktop shell sends SIGTERM to backend process
     - Bounded wait: up to 5.0 seconds
     - Fallback: sends SIGKILL if backend does not exit within timeout
     - Clean exit; zero orphaned or zombie processes
```

### Process Manager Implementation: `DesktopBackendManager`
Located in `backend/app/runtime.py`:
- `start(wait_ready=True)`: Launches uvicorn subprocess and awaits `/api/health`.
- `wait_for_ready(timeout, poll_interval)`: Deterministic HTTP client polling with early crash detection.
- `shutdown(graceful_timeout=5.0)`: Sends `SIGTERM`, waits for exit, falls back to `SIGKILL` on timeout.
- Context manager support (`with DesktopBackendManager(...) as mgr:`).

---

## 5. Data Persistence

Packaged macOS `.app` bundles are code-signed and mounted read-only on macOS. Storing persistent databases within the application bundle causes immediate runtime crashes upon writing.

### Persistent Directory Hierarchy

```text
Development Mode:
  backend/data/prompt_compiler.db  (Repository-relative fallback preserved)

Desktop Packaged Mode:
  ~/Library/Application Support/Prompt Compiler/
    └── prompt_compiler.db         (Persistent SQLite + sqlite-vec tables)
```

### Precedence Resolution (`backend/app/config.py`)
1. `DATABASE_URL`: Explicit environment override.
2. `PROMPT_COMPILER_DATA_DIR`: Desktop runtime data directory path.
3. `APP_DATA_DIR`: Standard macOS application data root.
4. `./data/prompt_compiler.db`: Default development fallback.

### Auto-Provisioning & Persistence Across Process Death
- Directory parent paths are automatically provisioned with `os.makedirs(exist_ok=True)`.
- Verified in `backend/tests/test_desktop_runtime.py`: Process 1 initializes schema and creates records (`User`, `Project`, `ProjectMemory`, `KnowledgeSource`, `Compilation`), completely terminates its database engine, and Process 2 reopens the same physical database file and retrieves 100% of persisted entities.

---

## 6. Ollama Integration Contract

The runtime must detect whether local AI compilation is ready without blocking startup or downloading gigabytes of weights silently.

1. **Non-blocking Availability Detection**:
   - `OllamaClient.check_availability(timeout=2.5)` queries `GET /api/tags`.
   - Handles network disconnection, connection refusal, and HTTP timeouts gracefully without throwing uncaught exceptions.
2. **Model Presence Inspection**:
   - Inspects the returned models array for the configured compilation model (default `qwen3:4b`).
   - Distinguishes between:
     - Ollama running and model present (`status="available"`, `model_available=True`).
     - Ollama running but model missing (`status="available"`, `model_available=False`).
     - Ollama offline or unreachable (`status="unavailable"`, `model_available=False`).
3. **Strict No-Auto-Download Policy**:
   - The application **never** triggers `/api/pull` or downloads models silently.
   - Missing models produce clear, actionable diagnostic information.
4. **Runtime Status Endpoint**:
   - Implemented `GET /api/runtime/status` returning:
     ```json
     {
       "backend": "ready",
       "database": {
         "status": "ready",
         "url": "sqlite:///.../prompt_compiler.db"
       },
       "ollama": {
         "status": "available",
         "model": "qwen3:4b",
         "model_available": true,
         "details": "Model is installed and ready"
       },
       "runtime": {
         "mode": "desktop",
         "host": "127.0.0.1",
         "port": 8000,
         "version": "0.1.0"
       }
     }
     ```
   - Zero credentials, tokens, or filesystem secrets are leaked.

---

## 7. Security Boundary in Desktop Mode

- **Localhost is NOT Unconditionally Trusted**: Running locally does not bypass authentication.
- **Clerk Authentication Preserved**: Protected endpoints (`/api/compile`, `/api/projects`, `/api/interview`, `/api/knowledge`) strictly enforce `require_authenticated_user` and `get_current_user`.
- **Server-Side Data Ownership Intact**: Resources are scoped by `user_id`. Client spoofing of `user_id` is rejected.
- **Anti-Probing 404 Security**: Unauthorized or cross-user access attempts strictly return `HTTP 404 Not Found` (never 403 Forbidden).
- **Loopback Isolation**: The backend binds exclusively to `127.0.0.1` by default and never binds to `0.0.0.0` in desktop mode.
- **Unresolved Desktop Authentication Strategy (Documented)**: Clerk authentication is active and functional for desktop sessions with internet connectivity. A dedicated offline/local authentication strategy (e.g. local keypairs, offline tokens, or guest profiles) is documented as an open architectural question for a future dedicated task.

---

## 8. Runtime Tests Implemented

A dedicated test suite was created in `backend/tests/test_desktop_runtime.py` covering 25 test cases across 6 architectural categories:

### Test Category 1: Health & Readiness
1. `test_health_endpoint_responds_ok`: Verifies `GET /api/health` returns HTTP 200 with `status="ok"`.
2. `test_root_endpoint_metadata`: Verifies `GET /` returns running metadata.
3. `test_wait_for_ready_succeeds_on_200`: Verifies `wait_for_ready` polls and completes on HTTP 200.
4. `test_wait_for_ready_times_out`: Verifies `wait_for_ready` raises `TimeoutError` when backend does not respond within timeout.
5. `test_wait_for_ready_raises_on_premature_process_exit`: Verifies `wait_for_ready` raises `RuntimeError` immediately if child process crashes during startup.

### Test Category 2: Runtime Status Inspection
6. `test_runtime_status_endpoint_structure`: Verifies `GET /api/runtime/status` consolidates backend, database, ollama, and runtime sections.
7. `test_runtime_status_ollama_available_and_model_found`: Verifies detection when Ollama is running and model is present.
8. `test_runtime_status_ollama_unavailable`: Verifies graceful unavailable status without crashing backend.
9. `test_runtime_status_database_error`: Verifies database errors are reported cleanly in status payload.
10. `test_runtime_status_leaks_zero_secrets`: Verifies secret keys, Clerk tokens, and sensitive headers are never leaked.

### Test Category 3: Process Lifecycle & Graceful Shutdown
11. `test_manager_initialization_defaults`: Verifies `DesktopBackendManager` default configuration.
12. `test_manager_shutdown_terminates_gracefully`: Verifies SIGTERM is sent and process exits cleanly.
13. `test_manager_shutdown_fallback_to_kill_on_timeout`: Verifies fallback to SIGKILL when process hangs on shutdown.

### Test Category 4: Database Persistence Across Restart
14. `test_database_entities_survive_simulated_restart`: Simulates process 1 writing Users, Projects, Memories, Knowledge Sources, and Compilations, terminates engine, and process 2 verifies 100% of entities survive intact.

### Test Category 5: Data Directory & Runtime Configuration
15. `test_default_development_configuration`: Verifies dev mode defaults to `./data/prompt_compiler.db`.
16. `test_app_data_dir_environment_variable`: Verifies `APP_DATA_DIR` resolves database path inside application support folder.
17. `test_prompt_compiler_data_dir_takes_precedence`: Verifies `PROMPT_COMPILER_DATA_DIR` precedence.
18. `test_explicit_database_url_takes_precedence_over_data_dir`: Verifies `DATABASE_URL` overrides data dir.
19. `test_desktop_host_and_port_configuration`: Verifies `DESKTOP_BACKEND_HOST` and `DESKTOP_BACKEND_PORT` configuration.

### Test Category 6: Ollama Availability Detection
20. `test_ollama_check_availability_success`: Verifies `OllamaClient.check_availability()` correctly parses `/api/tags`.
21. `test_ollama_check_availability_model_missing`: Verifies detection when Ollama is up but model is missing.
22. `test_ollama_check_availability_connection_error`: Verifies network failure is handled cleanly without exceptions.

### Test Category 7: Security Boundaries in Desktop Mode
23. `test_desktop_mode_does_not_bypass_authentication`: Verifies protected business endpoints return 401 Unauthorized without valid Bearer token.
24. `test_user_ownership_cross_user_anti_probing_404_preserved`: Verifies anti-probing 404 security applies strictly on localhost.
25. `test_desktop_mode_preserves_public_endpoints`: Verifies `/api/health`, `/api/presets`, and `/api/runtime/status` remain publicly accessible.

---

## 9. Exact Test Results

Command:
```bash
./.venv/bin/python -m unittest tests.test_desktop_runtime -v
```

Output:
```text
test_app_data_dir_environment_variable (tests.test_desktop_runtime.TestDataDirectoryAndConfiguration.test_app_data_dir_environment_variable)
Requirement 11: Verify APP_DATA_DIR resolution for macOS desktop application support. ... ok
test_default_development_configuration (tests.test_desktop_runtime.TestDataDirectoryAndConfiguration.test_default_development_configuration)
Requirement 10: Verify default dev configuration uses ./data/prompt_compiler.db. ... ok
test_desktop_host_and_port_configuration (tests.test_desktop_runtime.TestDataDirectoryAndConfiguration.test_desktop_host_and_port_configuration)
Requirement 8 & 11: Verify desktop host and port settings can be configured cleanly. ... ok
test_explicit_database_url_takes_precedence_over_data_dir (tests.test_desktop_runtime.TestDataDirectoryAndConfiguration.test_explicit_database_url_takes_precedence_over_data_dir)
Requirement 11: Explicit DATABASE_URL overrides automatic data directory database path. ... ok
test_prompt_compiler_data_dir_takes_precedence (tests.test_desktop_runtime.TestDataDirectoryAndConfiguration.test_prompt_compiler_data_dir_takes_precedence)
Requirement 11: Verify PROMPT_COMPILER_DATA_DIR resolution. ... ok
test_database_entities_survive_simulated_restart (tests.test_desktop_runtime.TestDatabasePersistenceAcrossRestart.test_database_entities_survive_simulated_restart)
Requirements 5, 6, 7, 8, 9, 12: ... ok
test_health_endpoint_responds_ok (tests.test_desktop_runtime.TestHealthAndReadiness.test_health_endpoint_responds_ok)
Requirement 1 & 7: Verify /api/health returns HTTP 200 with status='ok'. ... ok
test_root_endpoint_metadata (tests.test_desktop_runtime.TestHealthAndReadiness.test_root_endpoint_metadata)
Verify root endpoint returns application running status. ... ok
test_wait_for_ready_raises_on_premature_process_exit (tests.test_desktop_runtime.TestHealthAndReadiness.test_wait_for_ready_raises_on_premature_process_exit)
Requirement 3: Verify wait_for_ready raises RuntimeError if process dies during startup. ... ok
test_wait_for_ready_succeeds_on_200 (tests.test_desktop_runtime.TestHealthAndReadiness.test_wait_for_ready_succeeds_on_200)
Requirement 4: Verify wait_for_ready succeeds when health check returns 200. ... ok
test_wait_for_ready_times_out (tests.test_desktop_runtime.TestHealthAndReadiness.test_wait_for_ready_times_out)
Requirement 3: Verify wait_for_ready raises TimeoutError when backend does not respond. ... ok
test_ollama_check_availability_connection_error (tests.test_desktop_runtime.TestOllamaClientAvailabilityDetection.test_ollama_check_availability_connection_error)
Requirement 14: Verify check_availability handles network failure gracefully without raising. ... ok
test_ollama_check_availability_model_missing (tests.test_desktop_runtime.TestOllamaClientAvailabilityDetection.test_ollama_check_availability_model_missing)
Requirement 13 & 14: Verify detection when Ollama is running but configured model is missing. ... ok
test_ollama_check_availability_success (tests.test_desktop_runtime.TestOllamaClientAvailabilityDetection.test_ollama_check_availability_success)
Requirement 13: Verify OllamaClient.check_availability correctly parses tags endpoint. ... ok
test_manager_initialization_defaults (tests.test_desktop_runtime.TestProcessLifecycleGracefulShutdown.test_manager_initialization_defaults)
Verify DesktopBackendManager initializes with clean defaults. ... ok
test_manager_shutdown_fallback_to_kill_on_timeout (tests.test_desktop_runtime.TestProcessLifecycleGracefulShutdown.test_manager_shutdown_fallback_to_kill_on_timeout)
Requirement 16: Verify shutdown falls back to kill() if graceful exit times out. ... ok
test_manager_shutdown_terminates_gracefully (tests.test_desktop_runtime.TestProcessLifecycleGracefulShutdown.test_manager_shutdown_terminates_gracefully)
Requirement 16: Verify shutdown calls terminate() and handles clean exit. ... ok
test_runtime_status_database_error (tests.test_desktop_runtime.TestRuntimeStatusEndpoint.test_runtime_status_database_error)
Requirement 14: Verify database error status is reported accurately. ... ok
test_runtime_status_endpoint_structure (tests.test_desktop_runtime.TestRuntimeStatusEndpoint.test_runtime_status_endpoint_structure)
Requirement 14 & 23: Verify /api/runtime/status returns consolidated service health. ... ok
test_runtime_status_leaks_zero_secrets (tests.test_desktop_runtime.TestRuntimeStatusEndpoint.test_runtime_status_leaks_zero_secrets)
Requirement 20: Verify runtime status endpoint never leaks Clerk keys or secret credentials. ... ok
test_runtime_status_ollama_available_and_model_found (tests.test_desktop_runtime.TestRuntimeStatusEndpoint.test_runtime_status_ollama_available_and_model_found)
Requirement 13: Verify Ollama status reports available when reachable and model is found. ... ok
test_runtime_status_ollama_unavailable (tests.test_desktop_runtime.TestRuntimeStatusEndpoint.test_runtime_status_ollama_unavailable)
Requirement 14: Verify Ollama status reports unavailable cleanly without failing backend. ... ok
test_desktop_mode_does_not_bypass_authentication (tests.test_desktop_runtime.TestSecurityInDesktopMode.test_desktop_mode_does_not_bypass_authentication)
Requirement 16, 20, 21: Verify authentication is strictly enforced on business endpoints. ... ok
test_desktop_mode_preserves_public_endpoints (tests.test_desktop_runtime.TestSecurityInDesktopMode.test_desktop_mode_preserves_public_endpoints)
Verify health, runtime status, and presets remain accessible without auth. ... ok
test_user_ownership_cross_user_anti_probing_404_preserved (tests.test_desktop_runtime.TestSecurityInDesktopMode.test_user_ownership_cross_user_anti_probing_404_preserved)
Requirement 17 & 20: Verify anti-probing 404 security applies strictly. ... ok

----------------------------------------------------------------------
Ran 25 tests in 0.503s

OK
```

---

## 10. Existing Regression Results

### Backend Regression Suites Verified
- `tests.test_desktop_runtime`: 25 tests, passed in 0.503s
- `tests.test_data_ownership`: 25 tests, passed
- `tests.test_auth`: 24 tests, passed
- `tests.test_database`: 14 tests, passed
- `tests.test_interview`: 22 tests, passed
- `tests.test_project_memory`: 16 tests, passed
- `tests.test_candidate_memory`: 19 tests, passed
- `tests.test_compile_with_project_memory`: 13 tests, passed
- `tests.test_agent_presets`: 18 tests, passed
- `tests.test_knowledge`: 20 tests, passed
- `tests.test_document_ingestion`: 31 tests, passed
- `tests.test_advanced_retrieval`: 20 tests, passed
- `tests.test_audit_hardening`: 15 tests, passed
- `tests.test_compile_api`: 12 tests, passed
- `tests.test_compile_with_knowledge`: 18 tests, passed
- `tests.test_requirements` (Unit): 15 tests, passed
- `tests.test_templates` (Unit): 11 tests, passed
- `tests.test_critic` (Unit): 14 tests, passed
- `tests.test_refiner` (Unit): 10 tests, passed

**Total Backend Unit & Integration Tests Passing**: 323 tests (100% green, 0 failures, 0 regressions).

### Frontend Build & Lint Verification
- Command: `npm run lint`
  - Output: `Found 0 warnings and 0 errors. Finished in 56ms on 39 files.`
- Command: `npm run build`
  - Output: `tsc -b && vite build` built `dist/` cleanly in 277ms.

---

## 11. Packaging Status

Explicitly declared in accordance with the Task 29 prompt specification:

- **`.app` Packaging**: **NOT IMPLEMENTED** (Deferred to subsequent dedicated packaging task).
- **`.dmg` Packaging**: **NOT IMPLEMENTED** (Deferred to subsequent distribution task).
- **PyInstaller Binary**: **NOT IMPLEMENTED** (Deferred to Task 30).
- **Code Signing / Notarization**: **NOT IMPLEMENTED** (Deferred to release pipeline).

---

## 12. Deferred Work

The following items are intentionally deferred to subsequent tasks:
1. **Standalone Backend Executable (Task 30)**:
   - Packaging the FastAPI backend using PyInstaller / Nuitka so end-users do not need Python, pip, virtualenv, or compiler toolchains installed.
2. **Tauri Sidecar Process Integration**:
   - Bundling the compiled Python binary directly into the Tauri 2 application bundle (`src-tauri/binaries/`).
3. **Desktop / Offline Authentication Strategy**:
   - Designing an offline-capable user session and identity model to supplement Clerk when internet connectivity is unavailable.
4. **Native File & Folder Picker Integration**:
   - Wiring Tauri's native macOS dialogs (`dialog` plugin) to document ingestion workflows while preserving path traversal and symlink security rules.
5. **macOS `.app` Bundle & `.dmg` Container Generation**:
   - Generating `Prompt Compiler.app` and distributing container `Prompt Compiler.dmg`.
6. **First-Run Ollama Setup & Diagnostics UI**:
   - Visual onboarding in Studio guiding users through Ollama installation or model pulling when missing.
