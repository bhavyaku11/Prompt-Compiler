# Risk Register

## Risk Template
```text
Risk:
Probability:
Impact:
Early warning:
Mitigation:
Owner:
Status:
```

## Initial Risks

- Local model quality may be insufficient for complex requirement analysis.
- Model may invent requirements if orchestration is weak (Mitigated: Strict extraction boundaries in `RequirementEngine` and anti-hallucination suppression in `PromptCritic`).
- Prompt quality may vary across task types (Mitigated: Task-specific templates in `backend/app/templates/` and automated refinement loop `PromptRefiner`).
- Context/memory may retrieve irrelevant information (Mitigated: Multi-query synthesis, cosine relevance threshold 0.5, and task-aware source weighting in `KnowledgeRetriever`).
- Large local models may exceed available hardware resources (Mitigated: Standardized on quantized local Qwen3 4B; unit tests completely isolated from live inference).
- Model downloads may fail or consume significant disk space (Mitigated: Model downloads are user-managed via Ollama; no automated heavy downloads).
- Vision processing may require a larger model and more memory (Mitigated: Vision processing kept strictly out of scope for Phase 1).
- Scope creep may make the compiler unnecessarily complex (Mitigated: Strict phased architecture; frontend and cloud features barred from backend tasks).
- Agent-specific prompt formats may become stale (Mitigated: Centralized `AgentPresetRegistry` with deterministic semantic preservation rules).
- Sensitive project context may be exposed if memory boundaries are poorly designed (Mitigated by Task 25: Verified strict project-isolated vector search, cascading project deletion across all SQLite tables, and path containment validation).
- Evaluation without a fixed test set may make improvements subjective (Mitigated by Task 24: Deterministic Quality Evaluation & Regression Benchmark Suite established in `backend/app/benchmark/`).
- Multi-user data leakage or cross-user ID enumeration (Mitigated by Task 28: Enforced server-side UserRecord ownership across all models/endpoints, anti-probing 404 responses on unauthorized resource access, and total client payload user_id rejection).
- Fixed port collision on local user desktop machine (Mitigated by Task 29: Configurable `DESKTOP_BACKEND_HOST` and `DESKTOP_BACKEND_PORT` with loopback binding, avoiding hard-coded port collision assumptions).
- Packaged macOS application attempting to write to read-only bundle directory (Mitigated by Task 29: `APP_DATA_DIR` and `PROMPT_COMPILER_DATA_DIR` abstraction resolving persistent SQLite storage outside the bundle to `~/Library/Application Support/Prompt Compiler/`, with auto-provisioning).
- Orphaned or zombie backend sidecar processes upon application exit (Mitigated by Task 29: `DesktopBackendManager` process lifecycle with graceful SIGTERM termination and bounded 5.0s timeout fallback to SIGKILL).
- Application hanging indefinitely if Ollama daemon is stopped or model is missing (Mitigated by Task 29: Non-blocking `OllamaClient.check_availability()` with 2.5s timeout querying `/api/tags`, reporting structured status via `GET /api/runtime/status` with zero automated downloads).
- Dynamic native libraries (`vec0.dylib`, `sqlean`) failing to load inside frozen PyInstaller bundle (Mitigated by Task 30: Explicitly declared `vec0.dylib` in both `binaries` and `datas` under `sqlite_vec/` in `PromptCompilerBackend.spec`; verified SQLite extension loading and table creation in `backend/tests/test_standalone_executable.py`).
- Initial cold-start delay from macOS Gatekeeper / XProtect static binary security scan on unsigned binaries (Mitigated by Task 30: Documented 10-15s first-launch scan latency; configured 25s test readiness timeout; documented requirement for code signing in Task 32).
- Accidental secret leakage or build-time credential embedding into compiled binary artifact (Mitigated by Task 30: Excluded `.env`, test fixtures, and local caches in `PromptCompilerBackend.spec`; automated `test_no_embedded_secrets` strings audit asserting absence of sensitive key patterns in binary).
- Tauri app shell attempting to connect to hardcoded port instead of dynamic sidecar port (Mitigated by Task 31: Tauri bridge queries Rust backend via `get_backend_port` IPC command, resolving dynamic port written by sidecar at runtime).
- macOS Gatekeeper blocking execution of ad-hoc signed `.app` and `.dmg` on unmanaged machines (Mitigated by Tasks 32 & 35: Documented ad-hoc signing status `Signature=adhoc` in `docs/14-known-issues.md` PC-005, added right-click Open user instructions; documented Apple Developer ID signing/notarization prerequisite for external commercial distribution).
- Desktop app hanging or crashing if Ollama is not running or crashes mid-compilation (Mitigated by Task 34: Decoupled Ollama status polling with 2.5s non-blocking timeout, Studio notification banner indicating Ollama offline, and safe error message propagation without crash).
- Unintended inclusion of private keys, Clerk secret keys, or test databases in production DMG installer (Mitigated by Tasks 35 & 36: Comprehensive artifact inspection; 0 `.env` files, 0 `.pem`/`.key` files, and 0 dev `.db` files packaged in `/Applications/Prompt Compiler.app` or `.dmg`; verified `CLERK_SECRET_KEY` is None in desktop mode).
- Cross-user data leakage or permission bypass across app restarts (Mitigated by Task 36: Automated audit suite verified strict `user_id` scoping in SQLite, anti-probing 404 responses for foreign resources, and zero cross-project chunk retrieval in vector store).
- Uncontrolled disk usage from local vector embeddings and compilation history (Mitigated by Task 36: Verified SQLite WAL vacuuming, bounded chunk sizes `DOCUMENT_MAX_FILE_SIZE_BYTES=1048576`, and automated cascading cleanup upon project deletion).

## Release Candidate Risk Assessment & Status Summary

| Risk Description | Probability | Impact | Mitigation Strategy | Owner | Post-Task 36 Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Unsigned / Ad-hoc DMG Distribution** | High | Medium | App is ad-hoc signed for local developer use; Gatekeeper override documented in README and Release Notes. Apple Developer ID notarization pipeline scoped for enterprise release. | Build / Release | **Accepted with Documentation (PC-005)** |
| **Ollama Dependency & Local LLM Availability** | Medium | High | Decoupled health polling (`GET /api/runtime/status`), non-blocking 2.5s timeout, clear UI status pills ("Offline"), and zero automated model downloads. | Runtime Engine | **Mitigated** |
| **Sensitive Secret Leakage in Desktop Artifacts** | Low | Critical | Strict packaging exclude lists in PyInstaller spec and Tauri config; offline Clerk RSA public key validation; verified 0 embedded secrets in .app and .dmg. | Security / Packaging | **Mitigated** |
| **Sidecar Process Leaks / Zombie Backend** | Low | High | Tauri Rust process lifecycle hooks terminate sidecar with SIGTERM/SIGKILL fallback on window close; clean termination verified in audit. | Desktop Architecture | **Mitigated** |
| **Database Corruption / Read-Only App Bundle Writes** | Low | Critical | SQLite storage relocated to user Application Support (`~/Library/Application Support/com.promptcompiler.app/prompt_compiler.db`) outside read-only app bundle. | Storage Engine | **Mitigated** |
| **Starlette / Pydantic Deprecation Warnings in Dependencies** | Low | Low | Upstream Starlette `upload_protocol` and `repr` warnings logged in test runs; verified zero functional impact on API routing or compilation performance. | Backend Team | **Accepted (PC-004)** |
