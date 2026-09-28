# Release Checklist

## Core Product
- [x] Quick Refine works end-to-end — PASS: Verified live compilation across all 5 agent presets (`generic`, `cursor`, `claude_code`, `cline`, `windsurf`) in Task 36 audit suite (`scratch/audit_suite.py`). Compilations completed in 7–12s with full requirement preservation.
- [x] Prompt Interview works when explicitly selected — PASS: Verified multi-turn interview workflow (Session `dd54803c-ef32-4771-95e4-0eee04829089`). Start, answer submission, turn progression, and final compilation (`compile_from_interview`) verified end-to-end.
- [x] Requirement extraction validated — PASS: `RequirementEngine` successfully extracts structured requirements, intent, constraints, domain, and task type. Verified in unit and live Ollama tests.
- [x] Missing-information detection validated — PASS: Material unresolved topics (deployment, database, auth, styling) detected and surfaced in `RequirementAnalysis.missing_information`.
- [x] Safe-default handling validated — PASS: Reasonable defaults applied without inventing technological specifications; assumptions explicitly separated from confirmed requirements.
- [x] Prompt validation works — PASS: `PromptCritic` validates structural integrity, constraint compliance, and requirement preservation with deterministic and LLM-assisted checks.
- [x] Prompt analysis works — PASS: `RequirementAnalysis` domain schema validated with Pydantic; verified in API responses and persistence tables.
- [x] Templates work — PASS: `TemplateSelector` selects correct templates for all 5 task types (`build`, `modify`, `debug`, `explain`, `analyze`).
- [x] Project context works — PASS: `ProjectContext` deterministic ordering verified; precedence hierarchy strictly enforced (User Requirements > Project Memory > Knowledge Evidence > Extracted Context > Defaults > Assumptions).
- [x] Target-agent formatting works — PASS: `AgentFormatter` preserves 100% of confirmed requirements while tailoring syntax and directives for Generic, Cursor, Claude Code, Cline, and Windsurf.

## Technical
- [x] Local Ollama setup verified — PASS: Ollama daemon verified running at `http://127.0.0.1:11434` with `qwen3:0.6b` (desktop default) and `qwen3:4b` (evaluation model).
- [x] Model availability check works — PASS: Non-blocking availability checks verified via `GET /api/runtime/status` and `OllamaClient.check_availability`.
- [x] API validation works — PASS: Pydantic request validation returns HTTP 422 for malformed payloads; empty inputs strictly rejected.
- [x] Ollama errors handled — PASS: Explicit exception hierarchy (`OllamaConnectionError`, `OllamaTimeoutError`, `OllamaHTTPError`, `OllamaResponseError`) cleanly caught and mapped to HTTP status codes.
- [x] No secrets committed — PASS: Exhaustive scan of repository, DMG image, and `.app` bundle confirms 0 private keys, 0 `.env` files, 0 dev databases. `CLERK_SECRET_KEY` is None in desktop mode.
- [x] No fake fallback output — PASS: Zero hardcoded fake LLM fallbacks; real Ollama inference or explicit errors returned.
- [x] Regression tests pass — PASS: Full test suite passes: 396/396 backend tests, 7/7 frontend automated tests, oxlint clean (0 errors, 0 warnings), TypeScript build clean, Vite production build clean, Tauri cargo check clean.
- [x] Evaluation dataset reviewed — PASS: Task 24 benchmark suite (10 cases, 50 evaluations) passing with 0 regressions against `baseline.json`.
- [x] Backend Clerk JWT authentication verified — PASS: Verified offline RSA cryptographic signature verification using bundled public key (`DEFAULT_CLERK_JWT_KEY`). Protected endpoints return 401 with `WWW-Authenticate: Bearer` on missing/invalid tokens.
- [x] User identity persistence and legacy backfill verified — PASS: Verified `users` table persistence, `UserRecord` mapping, and `legacy_local_user` (id=1) migration.
- [x] Cross-user data isolation and anti-probing 404 security verified — PASS: Unauthorized cross-user requests return HTTP 404 Not Found (never 403 Forbidden) to eliminate resource enumeration.
- [x] Desktop backend process lifecycle and health readiness contract verified — PASS: Tauri managed sidecar spawns autonomously on dynamic port (e.g. 18000), readiness verified via `GET /api/health`, clean shutdown verified.
- [x] Persistent data directory abstraction (APP_DATA_DIR) verified outside .app bundle — PASS: Stores database at `~/Library/Application Support/com.promptcompiler.app/prompt_compiler.db`; persists across app terminations and restarts.
- [x] Frontend dynamic API base URL abstraction verified — PASS: Consumes `window.__PROMPT_COMPILER_API_BASE__` set by Tauri shell with Vite dev proxy fallback.

## UX
- [x] Loading state (Studio & Landing Page) — PASS: Honest indeterminate pipeline indicator reflecting real API Promise lifecycle; buttons disabled during processing.
- [x] Error state (Studio & Landing Page) — PASS: User-friendly error banners with actionable detail and Retry triggers; `prompt-compiler:auth-required` event triggers session banner.
- [x] Empty state — PASS: Clean empty composer view with 5 quick action chips; empty project memory and knowledge states clearly communicated.
- [x] Copy prompt action — PASS: One-click clipboard copy on `CompiledPromptCard` with instant visual checkmark feedback.
- [x] Edit prompt action — PASS: Editable textarea in composer; copy-to-edit support.
- [x] Regenerate action — PASS: Re-compile action supported with updated options or presets.
- [x] Interview mode is optional — PASS: Opt-in toggle on Composer; defaults to false (Quick Refine mode).
- [x] Responsive behavior where applicable — PASS: Fluid Studio layout with collapsible sidebar and auto-resizing textarea (~80px to ~220px).

## Packaging
- [x] Desktop shell foundation created (Tauri 2 shell in src-tauri/) — PASS: Tauri 2 desktop shell configured in `src-tauri/tauri.conf.json` with macOS minimum version 11.0.
- [x] Backend starts and stops cleanly via DesktopBackendManager — PASS: Sidecar lifecycle verified in both standalone tests and live `.app` execution.
- [x] Backend readiness check via GET /api/health verified — PASS: Readiness polling succeeds within 1-2s of launch.
- [x] Ollama reachability and model availability handled without auto-downloads — PASS: Graceful UI indicator surfaces Ollama status without attempting background model downloads.
- [x] macOS .app packaged — PASS: Verified production bundle `Prompt Compiler.app` (44.86 MiB) at `src-tauri/target/release/bundle/macos/Prompt Compiler.app` and `/Applications/Prompt Compiler.app`.
- [x] macOS .dmg created — PASS: Verified production disk image `Prompt Compiler_0.1.0_aarch64.dmg` (35.15 MiB) at `src-tauri/target/release/bundle/dmg/Prompt Compiler_0.1.0_aarch64.dmg`.
- [x] Backend bundled as standalone executable (no system Python) — PASS: Standalone PyInstaller executable (27.6 MB) bundled in `Contents/MacOS/prompt-compiler-backend`. Runs with 0 system Python or pip dependencies.
- [x] Dedicated backend packaging spec (PromptCompilerBackend.spec) and build script (scripts/build_backend.py) created — PASS: Reproducible build automation verified.
- [x] Standalone executable verified on macOS Apple Silicon arm64 (8/8 standalone tests pass) — PASS: Dedicated test suite `backend/tests/test_standalone_executable.py` passes 8/8 tests.
- [x] Backend integrated into Tauri sidecars directory — PASS: Synchronized to `src-tauri/binaries/prompt-compiler-backend-aarch64-apple-darwin`.
- [x] User does not need Terminal for normal use — PASS: End users launch `Prompt Compiler.app` directly from Finder or Applications; backend sidecar spawns silently in background with zero terminal windows or CLI interaction required.
