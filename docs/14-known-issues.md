# Known Issues

> Add verified issues here instead of hiding them in code or final reports.

## Issue Template
```text
ID:
Date discovered:
Area:
Severity:
Description:
Steps to reproduce:
Expected:
Actual:
Root cause:
Workaround:
Fix status:
Related files:
```

## Current Issues

### PC-001
Area:
Model availability

Severity:
Low for current development

Description:
`qwen3:8b` previously failed to pull with `Error: EOF`.

Current workaround:
Use `qwen3:4b`, which successfully downloaded and runs locally.

Status:
Development continues with Qwen3 4B.

Do not claim the 8B issue is resolved unless it is actually retested.

### PC-002
Area:
Vector Knowledge Base / Embeddings

Severity:
Low (Foundation complete; mock provider available for offline testing)

Description:
The local Ollama instance contains generation models (`qwen3:4b`, `qwen3:0.6b`), but neither is an embedding model and the default Ollama instance does not have a dedicated embedding model installed. Running `/api/embed` against `qwen3:4b` returns: `"This server does not support embeddings. Start it with --embeddings"` or model not supported.

Current workaround:
Per Task 20 instructions, the model was not automatically pulled during automated execution to avoid large background downloads. In tests and default local test runs, `MockEmbeddingProvider` is used. For live embedding inference with real vectors against Ollama, users should run `ollama pull nomic-embed-text` (approx. 274 MB, 768 dimensions), which matches the default configuration in `backend/app/config.py`.

Status:
Documented; local embedding provider cleanly handles model absence and raises descriptive errors.

### PC-003
Area:
Local AI Inference / Test Suite Execution

Severity:
Low (Operational guidance for testing)

Description:
When running all 396 tests in a single unbroken test runner process, sequential live Ollama calls with `qwen3:4b` (which produces extended reasoning tokens in Qwen3 thinking mode) can experience latency of 60–180 seconds per request when competing with other local processes or during model swaps. The 394 core unit and mock tests run in ~14 seconds. The 2 live Ollama integration tests take ~15 minutes when run back-to-back with cold caches.

Current workaround:
The 394 unit and integration tests are isolated from Ollama and run in ~14 seconds. The live Ollama integration tests (`test_real_ollama_requirement_extraction`, `test_live_ollama_prompt_generation`, and `test_live_ollama_critic_validation`) can be targeted individually when testing real LLM responses. For fast local desktop compilation, `qwen3:0.6b` runs in 7–12 seconds.

Status:
Documented; test isolation verified and test execution times logged.

### PC-004
Area:
Test Output / Library Warnings

Severity:
Low (Non-blocking informational)

Description:
Running `pytest` produces four deprecation warnings from upstream libraries:
1. `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
2. `StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.`

Current workaround:
None required. These are upstream Starlette/FastAPI library notices that do not affect runtime stability, test validity, or application functionality.

Status:
Documented; non-blocking.

### PC-005
Area:
macOS Application Distribution / Gatekeeper

Severity:
Low (Documented platform limitation for RC)

Description:
Prompt Compiler v0.1.0 application and sidecar binaries are ad-hoc signed (`Signature=adhoc`) without an Apple Developer ID certificate. macOS Gatekeeper on newer systems will display an alert that the developer cannot be verified upon initial double-click.

Current workaround:
Users must right-click `Prompt Compiler.app` in Finder and select "Open", or click "Open Anyway" in macOS System Settings > Privacy & Security.

Status:
Documented as a known limitation in release notes and audit report. Future CI/CD automation can attach Apple Developer signing certificates.



