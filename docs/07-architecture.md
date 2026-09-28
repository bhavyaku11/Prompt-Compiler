# Architecture

## Current Development Architecture

```text
User / Frontend
      |
      v
FastAPI Backend
      |
      +--> Requirement Analyzer
      |
      +--> Template Engine
      |
      +--> Prompt Generator
      |
      +--> Prompt Critic / Validator
      |
      v
AI Provider Interface
      |
      v
Ollama
      |
      v
Qwen3 4B
```

## Planned Expanded Architecture

```text
Input Layer
  ├── Text
  ├── Image
  ├── Screenshot
  ├── Sketch
  ├── URL
  └── File
        |
        v
Input Normalizer
        |
        v
Requirement Engine
  ├── Intent
  ├── Known requirements
  ├── Safe defaults
  ├── Missing information
  └── Constraints
        |
        +--> Optional Interview
        |
        v
Template Selector
        |
        v
Context / Memory Retrieval
        |
        v
Prompt Builder
        |
        v
Prompt Critic
        |
        v
Validator
        |
        v
Agent-Specific Formatter
        |
        v
Final Prompt
```

## Principles
- Local-first.
- Provider-independent compiler core.
- Structured intermediate representation.
- Explicit uncertainty.
- No fabricated requirements.
- Small vertical slices.
- Keep frontend concerns out of backend business logic.
- Keep optional AI features replaceable.
- Do not introduce persistent storage before it is needed.

## Project Memory & Context Architecture (Implemented in Tasks 16 & 17)

```text
CompileRequest (optional project_id) / InterviewSession
      │
      ├──> If project_id provided:
      │       │
      │       ▼
      │    ProjectRepository.get(project_id)
      │       │
      │       ▼
      │    ProjectMemoryService.get_project_context(project_id)
      │       │ (Deterministic sort: Category Rank -> Source Trust -> Chronological -> UUID)
      │       ▼
      │    ProjectContext (Technologies, Constraints, Coding Rules, Grouped Memories)
      │       │
      │       ├──> RequirementEngine (Preserves separation: confirmed user input vs project summary)
      │       │
      │       ├──> PromptGenerationContext (Injected as === PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===)
      │       │
      │       ├──> PromptGenerator (Explicit precedence: User Requirements > Project Context)
      │       │
      │       ├──> PromptCritic (Suppresses false positive hallucination warnings for confirmed project stack)
      │       │
      │       └──> CompilationRecord (Persists project_id linkage)
      │
      └──> If project_id omitted:
              │
              ▼
           Standard Compilation Pipeline (Zero project lookup, 100% backward compatible)
```

### Precedence Hierarchy
1. Explicit current user requirements (Highest priority — can override project baseline).
2. Explicit user-confirmed project memory.
3. Extracted project context.
4. System-defined defaults.
5. Generated assumptions (Lowest trust).

### Read-Only Context Guarantee
Compilation reads project memory but NEVER automatically creates or updates memories.

## Candidate Memory Extraction & Confirmation Architecture (Implemented in Task 18)

Memory is long-term project state. Prompt Compiler enforces an explicit verification boundary between unconfirmed candidate extraction and persistent storage:

```text
User Interaction / Requirements
            │
            ▼
   CandidateMemoryExtractor
            │ (Filters debugging, transient commands, casual chat)
            ▼
   Deduplication & Conflict Detection against active ProjectMemory
            │
            ▼
   CandidateMemoryRecord in SQLite (status: pending | duplicate | conflict)
            │
      ┌─────┴─────────────────┐
      │                       │
      ▼                       ▼
POST .../approve        POST .../reject
      │                       │
      ▼                       ▼
Persist ProjectMemory     Zero ProjectMemory created
(status: active)          (candidate status: rejected)
(optional supersede)
```

### Safety & Trust Principles
1. **No Silent Writes**: Candidate extraction NEVER automatically persists to `ProjectMemory`.
2. **Explicit User Approval**: The developer must review candidates and approve them via REST API before memories become permanent.
3. **Source Attribution**:
   - `user_confirmed`: Explicit user statements ("Use FastAPI for backend").
   - `extracted_from_user_input`: Extracted from broader prompt requirements.
   - `generated_assumption`: Unconfirmed inferences; never treated as facts.
4. **Confidence Semantics**: Represents extraction fidelity / certainty (0.0 to 1.0), NOT business priority.
5. **Deduplication**: Exact or overlapping active memories flag the candidate as `duplicate` and prevent duplicate storage.
6. **Conflict Resolution**: Opposing stack choices flag candidate as `conflict` and require explicit user choice (e.g. `supersede_conflicting=True` or keeping both).

## Agent-Specific Formatting Preset Architecture (Implemented in Task 19)

The Prompt Compiler decouples requirement compilation from downstream prompt presentation:

```text
User Input
    │
    ▼
Requirement Engine (Extraction)
    │
    ▼
Project Memory (Persistent Context)
    │
    ▼
Template Selector (build, modify, debug, etc.)
    │
    ▼
Prompt Generator (Ollama / Qwen3 4B)
    │
    ▼
Prompt Critic / Validator
    │
    ▼
Prompt Refiner (Automated Iterative Loop)
    │
    ▼
Agent-Specific Formatter (Deterministic pure-Python layout transformation)
    ├── generic     -> Canonical Prompt Compiler markdown structure
    ├── cursor      -> Optimized for Cursor Composer (Context top, Objectives, Rules)
    ├── claude_code -> Optimized for Claude Code CLI (Role, Task, Steps, Verification)
    ├── cline       -> Optimized for Cline / Roo Code (Task, Context, Requirements, Steps)
    └── windsurf    -> Optimized for Windsurf Cascade (Task, Context, Implementation, Checkpoints)
    │
    ▼
Final Output Prompt
```

### Key Principles & Guarantees
1. **Presentation vs Semantics**: "Agent presets change prompt presentation, not the underlying requirement semantics."
2. **Zero Extra LLM Overhead**: Formatting is 100% deterministic pure-Python string assembly. No additional Ollama or external API calls are made.
3. **Information Preservation**: Confirmed requirements, constraints, open decisions, coding rules, and project context are preserved across all presets.
4. **Context Separation**: The distinction between existing project baseline (`=== PROJECT CONTEXT ===`) and new user requirements is preserved across all presets.
5. **Interview Compatibility**: Multi-turn clarification sessions retain the target agent preset and format accordingly upon final compilation.

## Vector Knowledge Base & Semantic Retrieval Architecture (Implemented in Task 20)

Task 20 introduces the local vector storage and semantic retrieval foundation decoupled from the core compilation pipeline:

```text
Input Document / Code / Text
            │
            ▼
     Text Normalization & Deterministic SHA-256 Hashing
            │ (Detects identical content; avoids redundant embedding)
            ▼
     TextChunker (Paragraph- & line-aware sliding window with overlap)
            │
            ▼
     EmbeddingProvider Abstraction
     ├── OllamaEmbeddingProvider (Local Ollama /api/embed or /api/embeddings)
     └── MockEmbeddingProvider (Deterministic unit testing & offline dev)
            │
            ▼
     KnowledgeRepository in SQLite
     ├── knowledge_sources (source metadata, content hash, chunk counts)
     ├── knowledge_chunks (text chunks, chunk index, parent references)
     └── vec_chunks (sqlite-vec virtual table float[768] with cosine distance)
            │
            ▼
     KnowledgeSearchService (Vector KNN Search)
     └── Strict Project Isolation (JOIN with knowledge_chunks WHERE project_id = :project_id)
```

### Key Architectural Decisions
1. **Local-First SQLite Vector Storage**: Uses `sqlite-vec` (v0.1.9) via `sqlean` extension loading. No external cloud vector database (Pinecone, Weaviate, Supabase) or PostgreSQL server required.
2. **Project Isolation Invariant**: Queries for Project A never retrieve chunks belonging to Project B. Scoped filtering is enforced at the database level.
3. **Deduplication via Hashing**: Re-indexing identical content reuses existing chunks and bypasses expensive embedding computation.
4. **Memory vs Knowledge Base**: Project Memory stores concise, durable facts ("Backend uses FastAPI"); Knowledge Base stores searchable source documents (architecture.md, code snippets).

## Semantic Retrieval Pipeline Integration (Task 21)

Task 21 connects the vector knowledge base into the compilation pipeline:

```text
USER INPUT
    ↓
REQUIREMENT ANALYSIS
    ↓
PROJECT MEMORY CONTEXT
    ↓
SEMANTIC KNOWLEDGE RETRIEVAL (Step 1.5 - KnowledgeRetriever)
    ↓
PROMPT GENERATION CONTEXT (carries retrieved_knowledge: list[KnowledgeContextItem])
    ↓
TEMPLATE SELECTION / INITIAL GENERATION (PromptGenerator)
    ↓
PROMPT CRITIC (Validates against explicit requirements, project context, retrieved evidence)
    ↓
PROMPT REFINER (Automated convergence loop)
    ↓
AGENT FORMATTER (Formats canonical sections + retrieved evidence for target preset)
    ↓
FINAL PROMPT + KNOWLEDGE REFERENCES + TELEMETRY
```

### Precedence Hierarchy (Strictly Enforced)
1. **Explicit Current User Requirements**: Top priority. Overrides all conflicting context.
2. **Explicit Confirmed Project Memory**: Trusted persistent application facts.
3. **Retrieved Project Knowledge**: Background evidence and reference material. Never promoted into confirmed requirements.
4. **Extracted Project Context**: Inferred tech stack and conventions.
5. **System Defaults**: Standard framework conventions.
6. **Generated Assumptions**: Lowest priority fallback.

### Retrieval Pipeline Details
- **Clean Insertion Point**: Executed at Step 1.5 in `/api/compile` and `/api/interview/{session_id}/compile` before prompt generation. Neither PromptGenerator nor AgentFormatter perform independent vector retrieval.
- **Deterministic Query**: Built from `intent + "Domain: " + domain + confirmed_requirements[:3]`, capped at 500 characters. Avoids embedding full templates or noisy prompts.
- **Relevance Threshold**: Configurable via `KNOWLEDGE_MIN_RELEVANCE_SCORE` (default: 0.5). Chunks below threshold are excluded.
- **Context Budgeting**: Configurable `KNOWLEDGE_RETRIEVAL_TOP_K` (default: 3) and `KNOWLEDGE_MAX_CONTEXT_CHARS` (default: 2000). Deduplicates chunks and truncates overflowing items cleanly.
- **Context Presentation**: Labeled explicitly as `=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===` with `[Source: <name> | Score: <score>]`.
- **Provenance Citations**: Returned in `CompileResponse.knowledge_references` and persisted in `compilations.knowledge_references`.
- **Graceful Error Handling**: If local Ollama embedding is unavailable or fails, compilation logs a warning, notes `skipped=True, skip_reason="..."` in `knowledge_telemetry`, and completes prompt compilation normally.
- **Strict Read-Only Compilation**: Compilation never writes to `project_memories`, `candidate_memories`, `knowledge_sources`, or `knowledge_chunks`.

## Document Ingestion & File Parsing Architecture (Task 22)

Task 22 introduces a local document discovery and parsing service feeding directly into the Vector Knowledge Base:

```text
LOCAL PROJECT DIRECTORY
            │
            ▼
DocumentIngestionService
  ├── Resolve & Validate Project Root (ProjectRecord.root_path)
  ├── Security Check: Canonical Path Containment & Symlink Verification
  ├── Deterministic Discovery (os.walk with DEFAULT_EXCLUDED_DIRECTORIES)
  └── Format Validation & Text Normalization
        ├── .md   -> UTF-8, structure preservation (headings, lists, code)
        ├── .txt  -> UTF-8, CRLF newline normalization
        ├── .py   -> UTF-8, static code text preservation
        ├── .ts   -> UTF-8, static TypeScript text preservation
        └── .json -> UTF-8, JSON validation & sorted key serialization
            │
            ▼
KnowledgeIndexerService (Existing)
  ├── Normalization & SHA-256 Content Hash
  ├── Deduplication Check (Unchanged files skip re-embedding)
  ├── TextChunker (Sliding window with paragraph boundaries)
  ├── EmbeddingProvider (Batch embeddings)
  └── KnowledgeRepository (SQLite + sqlite-vec vector store)
```

### Path Security & Project Boundaries
1. **Configured Project Root**: Ingestion operations are anchored to `projects.root_path`. If unconfigured, requests must specify `project_root` or configure the project.
2. **Path Traversal Prevention**: `validate_path_safety` resolves target paths with `pathlib.Path.resolve()` and enforces `resolved_target.relative_to(resolved_root)`. Traversal attempts (e.g. `../`, symlink escapes) are rejected with `PathSecurityError` / HTTP 400.
3. **Excluded Directories**: Automatic exclusion of build artifacts, version control, and cache folders (`.git`, `node_modules`, `__pycache__`, `.venv`, etc.).
4. **Binary & Database Exclusion**: Explicit filtering against non-text and database extensions (`.db`, `.sqlite`, `.exe`, `.png`, `.zip`, etc.).
5. **Safe Batch Ingestion**: Individual file parsing errors (e.g. malformed JSON, decode failure) do not abort the entire batch; outcomes are reported per file in `BatchDocumentIngestionResponse`.

## Advanced Retrieval & Multi-Document Context Synthesis (Task 23)

Task 23 enhances semantic retrieval quality when multiple project sources (e.g. documentation, implementation code, and configuration) are relevant to a user request:

```text
Structured RequirementAnalysis
            │
            ▼
Deterministic Multi-Query Synthesis (Up to KNOWLEDGE_MAX_RETRIEVAL_QUERIES = 3)
  ├── Query 1: Primary intent & high-level domain/requirements
  ├── Query 2: Technical implementation details & explicit constraints
  └── Query 3: Architectural context, design specifications & open decisions
            │
            ▼
Parallel Vector Searches (Scoped to project_id; fault-tolerant across queries)
            │
            ▼
Candidate Merging & Chunk Deduplication
  ├── Deduplicate by chunk_id
  ├── Retain max(query_scores) across matching queries
  └── Preserve query provenance (matched_queries)
            │
            ▼
Source-Type Weighting (TASK_SOURCE_WEIGHTS)
  ├── build:   doc: 1.05, code: 1.05, text: 1.00
  ├── modify:  code: 1.10, doc: 1.05, text: 1.00
  ├── debug:   code: 1.15, doc: 1.00, text: 0.95
  ├── explain: doc: 1.15, code: 1.05, text: 1.00
  └── config:  metadata subtype="configuration" receives 1.10 multiplier
            │
            ▼
Relevance Threshold Filtering (KNOWLEDGE_MIN_RELEVANCE_SCORE)
            │
            ▼
Source Diversity Balancing
  ├── Pick top scoring candidate unconditionally
  ├── Prioritize competitive candidates from unrepresented sources (ratio >= 0.8)
  └── Fill remaining slots up to top_k by score descending
            │
            ▼
Context Budgeting & Formatting
  ├── Top-k limit (KNOWLEDGE_RETRIEVAL_TOP_K)
  └── Character budget with safe boundary truncation (KNOWLEDGE_MAX_CONTEXT_CHARS)
            │
            ▼
PromptGenerationContext (Structured contextual evidence with provenance)
```

### Guarantees & Constraints
1. **Zero Extra LLM Calls**: Multi-query generation is 100% deterministic, deriving compact queries directly from structured `RequirementAnalysis` fields.
2. **Partial Query Failure Resilience**: If one query encounters a connection or embedding error, remaining successful queries still return results.
3. **No Machine Learning Rerankers**: Reranking is deterministic, combining conservative source-type weighting and source diversity heuristics.
4. **Strict Project Isolation**: Every query execution strictly filters on `knowledge_chunks.project_id = :project_id`.
5. **Memory Precedence**: User Requirements > Confirmed Project Memory > Retrieved Knowledge Evidence > Extracted Context > Defaults > Assumptions.

## Backend Authentication Layer (Task 27 — Clerk Integration Foundation)
Task 27 introduces a secure, reusable authentication foundation to the FastAPI backend using Clerk's official Python SDK (`clerk-backend-api`):

```text
React Frontend + Clerk
          │
          ▼
Clerk Session Token
          │
          ▼
HTTP Request Header: Authorization: Bearer <token>
          │
          ▼
FastAPI Dependency (require_authenticated_user / get_current_user)
          │
          ├──> 1. Header Validation: Missing or non-Bearer -> 401 Unauthorized
          │
          ├──> 2. Configuration Check: Missing CLERK_SECRET_KEY / CLERK_JWT_KEY -> 500 Configuration Error
          │
          ├──> 3. Token Verification: clerk_client.authenticate_request()
          │       ├── Networkless local verification via CLERK_JWT_KEY, or
          │       └── JWKS remote verification via CLERK_SECRET_KEY
          │       ├── Authorized party validation (CLERK_AUTHORIZED_PARTIES e.g. http://localhost:5173)
          │       └── Expiration, signature, format validation -> 401 Unauthorized
          │
          └──> 4. Identity Extraction:
                  ├── user_id: Extracted from verified 'sub' claim
                  ├── session_id: Extracted from 'sid' claim
                  └── claims: Complete verified claims payload
                          │
                          ▼
                  AuthenticatedUser (In-memory representation)
                          │
                          ▼
                  Protected Route Handler (e.g. GET /api/auth/me)
```

### Guarantees & Explicit Boundaries
1. **User data ownership is enforced in Task 28.**
2. **Business endpoints protected**: Endpoints (`/api/compile`, `/api/interview/*`, `/api/projects/*`) require verified authentication.
3. **Token Security**: Tokens and secrets are never logged, printed, or leaked in error responses.
4. **Deterministic Error Mapping**: Missing or invalid tokens return clean HTTP 401 Unauthorized responses without exposing internal exception details.

## User Identity & Server-Side Data Ownership Layer (Implemented in Task 28)

Task 28 connects verified Clerk authentication (`AuthenticatedUser.user_id`) to persistent local `UserRecord` identities and enforces strict server-side ownership across all business domains:

```text
Incoming HTTP Request (Authorization: Bearer <clerk_token>)
          │
          ▼
FastAPI Dependency: get_current_user
  ├── 1. require_authenticated_user verifies Clerk JWT token -> AuthenticatedUser(user_id=clerk_sub)
  └── 2. UserRepository.get_or_create(clerk_sub)
          ├── SELECT * FROM users WHERE clerk_user_id = :sub
          └── IF missing: INSERT INTO users (clerk_user_id) -> UserRecord(id, clerk_user_id)
          │
          ▼
UserRecord(id=<int>, clerk_user_id=<str>)
          │
          ▼
Protected Endpoint Handlers & Repositories
  ├── Projects: ProjectRecord.user_id == current_user.id
  ├── Project Memories: Inherited via ProjectRecord.user_id == current_user.id
  ├── Candidate Memories: Inherited via ProjectRecord.user_id == current_user.id
  ├── Knowledge Sources & Chunks: Inherited via ProjectRecord.user_id == current_user.id
  ├── Compilations: CompilationRecord.user_id == current_user.id
  └── Interview Sessions: InterviewSessionRecord.user_id == current_user.id
```

### Security Guarantees & Constraints
1. **Strict Server-Side Identity Authority**: Client-supplied `user_id` in request payloads, JSON bodies, or query parameters is strictly ignored or rejected. The authenticated user identity is derived exclusively from verified Clerk tokens.
2. **Anti-Probing Boundary (404 Not Found)**: Attempting to access, modify, or delete a resource belonging to another user always returns `404 Not Found` (never 403 Forbidden). This completely prevents attackers from enumerating or probing whether a resource ID exists in another account.
3. **Cross-Project & Cross-User Isolation in RAG**: Knowledge indexing, retrieval, search, and directory ingestion strictly require project ownership. A user compiling for Project A cannot access or synthesize knowledge chunks from Project B, even if their own account or another account owns Project B.
4. **Backward Compatibility & Legacy Migration**: Existing records prior to Task 28 are mapped to a deterministic `legacy_local_user` (`id = 1`, `clerk_user_id = "legacy_local_user"`).
5. **Public Endpoint Boundary**: `/api/health`, `/api/runtime/status`, and `/api/presets` remain publicly accessible without authentication.

## Desktop Runtime Foundation & Architecture (Implemented in Task 29)

Task 29 establishes the local desktop runtime architecture and process lifecycle contract required for the eventual standalone macOS `.app` distributed via `.dmg`.

### Target Desktop Topology

```text
Prompt Compiler.app (macOS Application Bundle)
       │
       ├── Tauri 2 Shell (Rust Core)
       │     ├── Application Window & Webview Lifecycle
       │     ├── Local Backend Sidecar Process Management
       │     └── System Shutdown & Intercept Handling
       │
       ├── React + TypeScript Frontend (HTML/JS/CSS Assets)
       │     ├── API Client with Dynamic Base URL Abstraction
       │     ├── Studio UI & Interview Interface
       │     └── Runtime Health & Status Monitoring
       │
       ├── Local FastAPI Backend (Subprocess / Sidecar)
       │     ├── Loopback Binding (127.0.0.1)
       │     ├── Port Negotiation (DESKTOP_BACKEND_PORT / Default 8000)
       │     ├── Clerk Authentication & User Ownership Enforcement
       │     ├── Requirement Engine, Templates, Critic, Refiner
       │     ├── Ingestion & Knowledge Retrieval (RAG)
       │     └── SQLite Data Persistence
       │
       ├── Persistent Application Data Directory (Outside Packaged .app)
       │     ├── macOS: ~/Library/Application Support/Prompt Compiler/
       │     ├── SQLite Database: prompt_compiler.db
       │     └── Future: Knowledge indexes, user configurations
       │
       └── Ollama Local Inference (Local System Daemon)
             ├── Address: http://127.0.0.1:11434
             ├── Default Model: qwen3:4b
             └── Availability Detection (Non-blocking, zero auto-downloads)
```

### Desktop Framework Decision: Tauri 2

Tauri 2 was selected for the Prompt Compiler macOS desktop application shell:
- **Preserves existing React/Vite frontend**: Reuses `frontend/dist` without frontend duplication or rewriting Studio.
- **Lightweight macOS binary footprint**: Utilizes native macOS WebKit (WKWebView), avoiding 150MB+ Chromium bundles associated with Electron.
- **Sidecar architecture**: FastAPI runs as an external local process/sidecar. Business logic is strictly preserved in Python, not moved into Rust.
- **Foundation established**: `src-tauri/` contains minimal declarative configuration (`tauri.conf.json`), capabilities (`capabilities/default.json`), and lifecycle hooks (`src/lib.rs`, `src/main.rs`). Full packaging into `.app` and `.dmg` is deferred to subsequent release tasks.

### Development Mode vs Desktop Mode

| Dimension | Development Mode | Desktop Mode (Prompt Compiler.app) |
| :--- | :--- | :--- |
| **Frontend Server** | Vite Dev Server (`localhost:5173`) | Embedded Webview loading bundled `frontend/dist` |
| **API Base URL** | `/api` (Proxied by Vite to `127.0.0.1:8000`) | Runtime-resolved `http://127.0.0.1:<DESKTOP_BACKEND_PORT>/api` |
| **Backend Process** | Started manually (`uvicorn app.main:app --reload`) | Managed by Tauri shell / `DesktopBackendManager` |
| **Database Location** | `./data/prompt_compiler.db` (repo-relative) | `APP_DATA_DIR/prompt_compiler.db` (`~/Library/Application Support/...`) |
| **Port Binding** | Fixed `8000` default | Dynamic or configurable `DESKTOP_BACKEND_PORT` on `127.0.0.1` |
| **Readiness Signal** | Manual developer readiness | Polling `GET /api/health` with bounded timeout (15s default) |

### Backend Process Lifecycle Contract

```text
User Launches Application
         │
         ▼
Desktop Shell Initializes
         │
         ▼
Spawn Backend Process (FastAPI / Uvicorn Sidecar)
  ├── Host: DESKTOP_BACKEND_HOST (default: 127.0.0.1)
  ├── Port: DESKTOP_BACKEND_PORT (default: 8000)
  └── Data Dir: APP_DATA_DIR / PROMPT_COMPILER_DATA_DIR
         │
         ▼
Poll Health Endpoint (GET /api/health)
  ├── Polling Interval: 250ms
  ├── Timeout: 15 seconds (configurable)
  ├── Early Process Exit Detection (checks process.poll() each cycle)
  └── Success: HTTP 200 {"status": "ok"}
         │
         ▼
Inject Backend Base URL -> Load React Frontend Webview
         │
         ▼
Application Active & Usable
         │
         ▼
User Closes Application Window
         │
         ▼
Graceful Shutdown Request (SIGTERM)
  ├── Timeout: 5.0 seconds
  ├── Wait for clean process termination
  └── Fallback: Force kill (SIGKILL) if process fails to exit cleanly
         │
         ▼
Desktop Shell Exits
```

### Data Directory Abstraction (`APP_DATA_DIR`)

Packaged macOS `.app` bundles are code-signed and read-only. Persistent state cannot be written inside the bundle.
- **Resolution Precedence**:
  1. `DATABASE_URL` (explicit override)
  2. `PROMPT_COMPILER_DATA_DIR`
  3. `APP_DATA_DIR` (standard macOS application data root)
  4. Repository-relative fallback (`./data/prompt_compiler.db` for development mode)
- **Automatic Directory Provisioning**: The backend automatically provisions parent directories (`os.makedirs(exist_ok=True)`) before initializing SQLite.
- **Persistence Across Restarts**: Database files, schemas, project memories, knowledge chunks, compilations, and user records are completely preserved across backend termination and restarts.

### Ollama Runtime Detection Contract

- **Non-blocking Inspection**: `OllamaClient.check_availability()` queries `GET /api/tags` with a short 2.5s timeout.
- **Model Verification**: Determines if the configured compilation model (e.g. `qwen3:4b`) is locally pulled and present in the model list.
- **Zero Automatic Downloads**: The application never silently initiates downloads of large LLM weights. If Ollama or the model is missing, clear actionable diagnostics are returned.
- **Runtime Status Endpoint**: `GET /api/runtime/status` consolidates backend, database, Ollama, and host/port status without leaking sensitive credentials or tokens.

### Security Boundary in Desktop Mode

- **No Localhost Bypass**: Local loopback execution does not grant unauthenticated access. Clerk authentication and server-side user ownership remain strictly enforced on all business endpoints.
- **Anti-Probing 404s**: Cross-user resource requests continue returning `404 Not Found`.
- **Loopback Isolation**: The backend strictly binds to `127.0.0.1` by default and never binds to `0.0.0.0` in desktop mode.
- **Open Architectural Question (Desktop Auth)**: Clerk authentication is fully functional for online desktop sessions. A dedicated local/offline authentication strategy (e.g. local keypairs, offline tokens, or guest profiles) is scheduled for a future dedicated architectural task.

## Standalone FastAPI Backend Executable Architecture (Task 30)

Task 30 establishes the standalone backend packaging pipeline that eliminates end-user Python dependencies:

```text
Prompt Compiler Desktop Bundle (Target)
       │
       ├── Tauri 2 Native Shell
       │      │
       │      ├── Embedded Webview (React + Vite Frontend)
       │      │
       │      └── Sidecar Manager (Spawns & monitors backend)
       │             │
       │             ▼
       └── Standalone Backend Executable (Mach-O 64-bit arm64)
              │  (backend/dist/prompt-compiler-backend-aarch64-apple-darwin)
              │
              ├── Bundled Python 3.14 Runtime & PyInstaller Bootloader
              ├── FastAPI + Starlette Web Application
              ├── Uvicorn ASGI Server (uvicorn.Server running desktop_entry.py)
              ├── SQLAlchemy ORM & SQLite Persistence Models
              ├── Bundled Native Extensions (sqlean, sqlite-vec vec0.dylib)
              ├── Compiler Engine, Memory Extractor, RAG & Benchmark Services
              │
              ├── Host Filesystem: ~/Library/Application Support/Prompt Compiler/
              │      └── prompt_compiler.db (SQLite database)
              │
              └── Host Loopback Network: http://127.0.0.1:11434
                     └── Ollama Daemon (Host dependency, unbundled)
```

### Packaging Decision & Tooling

1. **Packaging Tool**: PyInstaller 6.22.3.
   - Selected for robust Python 3.14 macOS arm64 wheel support, deterministic one-file executable generation, and native C-extension (`.dylib` / `.so`) extraction into temporary runtime storage (`sys._MEIPASS`).
   - Considered alternatives:
     - *Nuitka*: Higher build complexity with C-compiler toolchains and higher risk of dynamic import breakage on modern Python 3.14.
     - *PyOxidizer*: Unmaintained and lacking support for Python 3.14.
2. **Deterministic Build Configuration**:
   - `backend/PromptCompilerBackend.spec`: Declares entry point (`app/desktop_entry.py`), hidden imports (`uvicorn`, `sqlean`, `sqlite_vec`, `clerk_backend_api`, `sqlalchemy.dialects.sqlite`), and native library packaging.
   - `scripts/build_backend.py`: Python build automation script cleaning previous artifacts, running PyInstaller, verifying binary size (~25.5 MB) and arm64 architecture, and generating the Tauri 2 target-triple binary (`prompt-compiler-backend-aarch64-apple-darwin`).
3. **Native Extension Handling (`sqlite-vec` & `sqlean`)**:
   - `sqlite_vec` includes `vec0.dylib`. In frozen mode, SQLite's extension loader requires the dynamic library to be accessible. The spec embeds `vec0.dylib` in both `binaries` and `datas` under `sqlite_vec/` to ensure deterministic loading via `sqlite_vec.load(conn)`.
4. **Desktop Entry Point**:
   - `backend/app/desktop_entry.py`: Production launcher importing `settings` and `app` directly, parsing `--host` and `--port`, enforcing loopback binding (`127.0.0.1`), and invoking `uvicorn.Server(config).run()` without process reloading or external Python interpreter dependencies.
5. **Zero Python Prerequisite for End Users**:
   - The standalone executable runs completely out-of-the-box on macOS Apple Silicon without requiring Python, pip, virtualenv, or any developer tools to be installed on the user's Mac.










