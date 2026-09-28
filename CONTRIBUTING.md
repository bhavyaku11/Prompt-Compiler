# Contributing to Prompt Compiler

Thank you for your interest in contributing to Prompt Compiler! Prompt Compiler is a local-first desktop application designed to compile unstructured human requirements into precise, context-aware, implementation-ready prompts for AI coding agents.

---

## Code of Conduct & Principles

When contributing, please adhere to the core architectural principles of the project:

1. **Local-First**: The core compiler pipeline, persistence layer, and inference engine must function locally without requiring cloud AI APIs or proprietary subscription services.
2. **Deterministic Architecture**: Guardrails around LLM inference (precedence hierarchies, anti-hallucination critic, schema validation, agent formatters) are deterministic and testable.
3. **No Fabricated Requirements**: Never allow the compiler to invent unstated technical requirements. Unknowns must remain explicitly declared.
4. **Zero-Secret Invariant**: Production client bundles and desktop artifacts must never embed private keys, server secrets, or credentials.
5. **Verified Verification**: Every change must be verified by automated tests. Do not claim behavior that has not been empirically verified.

---

## Development Setup

### Prerequisites

- **macOS**: Sonoma 14+ or Sequoia 15+ on Apple Silicon (`arm64`)
- **Node.js**: v20.x or higher, with `npm` 10+
- **Python**: 3.12+ (Python 3.14 used for official builds)
- **Rust**: 1.80+ (`rustup toolchain install stable`)
- **Ollama**: Locally installed and running on `http://127.0.0.1:11434`
  ```bash
  ollama pull qwen3:0.6b
  # Optional higher-accuracy model:
  ollama pull qwen3:4b
  ```

### 1. Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Start the backend in development mode:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup

In another terminal:
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The frontend will be available at `http://localhost:5173` with API requests proxied to `127.0.0.1:8000`.

### 3. Tauri Desktop Development

To launch the full Tauri desktop shell in development:
```bash
# In the repository root:
npm install
npm run tauri dev
```

---

## Testing & Quality Assurance

All pull requests must pass the automated test suites and linters:

### Backend Test Suite
```bash
cd backend
source .venv/bin/activate
# Run isolated unit and integration test suite (~14s)
pytest tests/ -q

# Run benchmark regression evaluations
python -m app.benchmark.runner --compare
```

### Frontend Linters & Build
```bash
cd frontend
npx oxlint --deny-warnings src/
npm run build
node tests/auth_client_test.mjs
node tests/tauri_bridge_test.mjs
```

### Desktop Binary Verification
```bash
python3 scripts/build_backend.py
```

---

## Pull Request Guidelines

1. **Focus**: Keep PRs focused on a single bug fix, performance optimization, or enhancement.
2. **Branching**: Create a feature branch off `main` (e.g., `fix/ollama-timeout`, `feat/custom-preset`).
3. **Commit Messages**: Use clean conventional commits (e.g., `fix: ...`, `feat: ...`, `docs: ...`, `test: ...`).
4. **Documentation**: Update corresponding files in `docs/` if modifying APIs, configuration, or runtime contracts.
5. **No Secrets**: Double-check that no `.env`, `.pem`, `.key`, or database files are committed.
