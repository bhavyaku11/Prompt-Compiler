# TRD — Technical Requirements Document

## 1. Technical Goal
Build a modular local-first prompt compilation engine that can later be packaged as a macOS application.

## 2. Initial Stack
- Language: Python
- Backend: FastAPI
- HTTP client: httpx
- Validation: Pydantic
- Environment configuration: python-dotenv
- Local model runtime: Ollama
- Initial model: Qwen3 4B
- Initial database: none
- Initial storage: local filesystem only where required

## 3. Local Services
### FastAPI
Default development address:
`http://127.0.0.1:8000`

### Ollama
Default local address:
`http://127.0.0.1:11434`

### Model
`qwen3:4b`

## 4. Architectural Layers
- API layer
- Requirement analysis layer
- Prompt construction layer
- AI/provider layer
- Validation layer
- Template layer
- Context/memory layer (later)
- Input extraction layer (later)

## 5. Provider Abstraction
The application should isolate model-provider communication behind a small interface so Ollama can later be replaced or supplemented without rewriting the compiler.

## 6. Reliability Requirements
- Ollama unavailable must produce a clear error.
- Invalid model responses must be detected.
- No silent fallback to fabricated output.
- Request timeouts must be configured.
- Validation failures must be observable.
- Partial or unsupported input must be reported honestly.

## 7. Security Requirements
- No API keys in source control.
- Do not log private user content unnecessarily.
- Do not expose local service credentials if introduced later.
- Validate uploaded files and URLs when those features are added.
- Keep project memory scoped and inspectable.

## 8. Testing Requirements
- Unit tests for requirement parsing and validation.
- API tests.
- Ollama integration tests.
- Prompt quality evaluation set.
- Regression tests for previously fixed compiler failures.

## 9. Packaging Direction
Final target is a macOS application. The packaged application should manage or launch required local services without requiring the end user to manually operate Terminal.

## 10. Change Rule
Inspect existing code and documentation before architectural changes. Any change to the approved architecture must be explicitly justified and recorded.
