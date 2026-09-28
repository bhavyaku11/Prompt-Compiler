# Data Model

## Persistent Storage Architecture (Implemented in Task 15)

The Prompt Compiler uses a local-first SQLite database managed via SQLAlchemy 2.x declarative models and repositories.

### Storage Location
- Default: `backend/data/prompt_compiler.db`
- Configuration: `DATABASE_URL` (configurable via environment/Settings)
- Concurrency: WAL mode (`PRAGMA journal_mode=WAL`), `check_same_thread=False`, connection pooling via `NullPool` for file databases.

---

### Implemented Tables & Persistence Schemas

#### 0. `users` (`UserRecord`) (Implemented in Task 28)
Stores local user identity mapped to verified Clerk user IDs. Created on demand upon first authenticated request with safe idempotent upsert.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `clerk_user_id` | String(128) | No | Unique Clerk subject identifier (`sub` claim) (unique indexed) |
| `created_at` | Float | No | Unix timestamp when user was created |
| `updated_at` | Float | No | Unix timestamp of last update |

#### 1. `interview_sessions` (`InterviewSessionRecord`)
Stores multi-turn interview clarification sessions across backend server restarts.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `session_id` | String(64) | No | Unique session UUID (indexed) |
| `project_id` | String(64) | Yes | Optional foreign reference to associated project (indexed) |
| `user_id` | Integer | Yes | Foreign key reference to `users.id` (indexed, Task 28) |
| `target_agent` | String(32) | No | Downstream AI coding agent preset (default: 'generic') |
| `original_input` | Text | No | Original raw requirement prompt from user |
| `status` | String(32) | No | Session status (`in_progress`, `ready`, `compiled`) |
| `turn` | Integer | No | Turn count (1-indexed) |
| `current_analysis` | JSON | No | Serialized current `RequirementAnalysis` dictionary |
| `questions` | JSON | No | Serialized list of `InterviewQuestion` objects |
| `answers` | JSON | No | Key-value mapping of `{question_id: answer_text}` |
| `unresolved_topics` | JSON | No | List of material topic strings still unresolved |
| `asked_topics` | JSON | No | List of material topic strings already asked |
| `created_at` | Float | No | Unix timestamp when session was created |
| `updated_at` | Float | No | Unix timestamp of last session update |
| `expires_at` | Float | No | Unix timestamp for TTL expiration (default: +1 hour) |

#### 2. `requirement_analyses` (`RequirementAnalysisRecord`)
Stores structured requirement extractions and clarified states.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `analysis_id` | String(64) | No | Unique analysis UUID (indexed) |
| `interview_session_id` | String(64) | Yes | Foreign reference to associated interview session |
| `original_input` | Text | No | Input prompt analyzed |
| `intent` | Text | No | Extracted high-level intent |
| `task_type` | String(64) | No | Classification (`build`, `modify`, `debug`, etc.) |
| `domain` | String(64) | No | Technical domain (`web development`, `cli`, etc.) |
| `confirmed_requirements` | JSON | No | List of confirmed technical requirements |
| `missing_information` | JSON | No | List of identified missing items/decisions |
| `constraints` | JSON | No | List of technical or negative constraints |
| `assumptions` | JSON | No | List of safe baseline assumptions |
| `created_at` | Float | No | Unix timestamp of extraction |
| `updated_at` | Float | No | Unix timestamp of update |

#### 3. `compilations` (`CompilationRecord`)
Stores compilation results, generated prompts, and validation audit trails.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `compilation_id` | String(64) | No | Unique compilation UUID (indexed) |
| `interview_session_id` | String(64) | Yes | Foreign reference to source interview session (if applicable) |
| `project_id` | String(64) | Yes | Optional foreign reference to associated project (indexed) |
| `user_id` | Integer | Yes | Foreign key reference to `users.id` (indexed, Task 28) |
| `target_agent` | String(32) | No | Downstream AI coding agent preset used (default: 'generic') |
| `input_text` | Text | No | Raw input prompt compiled |
| `compiled_prompt` | Text | No | Final production-ready prompt |
| `task_type` | String(64) | Yes | Task type selected |
| `template_name` | String(128) | Yes | Template used for generation |
| `requirements_summary` | JSON | Yes | Snapshot of requirement summary dictionary |
| `validation_summary` | JSON | Yes | Snapshot of validation report dictionary |
| `refinement_attempts` | Integer | No | Number of critic-driven refinement loop iterations |
| `created_at` | Float | No | Unix timestamp when compilation completed |

#### 4. `projects` (`ProjectRecord`) (Implemented in Task 16, User Ownership in Task 28)
Stores development project identities and scopes across long-running sessions.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `project_id` | String(64) | No | Unique project UUID (indexed) |
| `user_id` | Integer | Yes | Foreign key reference to `users.id` (indexed, Task 28) |
| `name` | String(128) | No | Project name (indexed) |
| `description` | Text | No | Detailed project description or goals |
| `root_path` | String(512) | Yes | Configured local filesystem root path for document discovery & ingestion (Task 22) |
| `created_at` | Float | No | Unix timestamp of creation |
| `updated_at` | Float | No | Unix timestamp of last update |

#### 5. `project_memories` (`ProjectMemoryRecord`) (Implemented in Task 16)
Stores categorized, source-attributed memory items for a project.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `memory_id` | String(64) | No | Unique memory UUID (indexed) |
| `project_id` | String(64) | No | Reference to associated project (indexed) |
| `category` | String(64) | No | Category tag (`technology`, `architecture`, `constraint`, `coding_rule`, etc.) |
| `content` | Text | No | Memory statement or architectural fact |
| `source` | String(64) | No | Trust attribution (`user_confirmed`, `extracted_from_user_input`, `generated_assumption`, `system_defined`) |
| `confidence` | Float | No | Confidence metric between 0.0 and 1.0 (extraction certainty, not importance) |
| `status` | String(32) | No | Lifecycle status (`active`, `deprecated`, `superseded`) |
| `metadata_json` | JSON | No | Contextual metadata dictionary |
| `created_at` | Float | No | Unix timestamp of creation |
| `updated_at` | Float | No | Unix timestamp of last update |

#### 6. `candidate_memories` (`CandidateMemoryRecord`) (Implemented in Task 18)
Stores temporary, unconfirmed candidate memory proposals extracted from user interactions. Candidate extraction NEVER writes directly to `project_memories`; candidates require explicit user approval.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | Integer | No | Autoincrementing primary key |
| `candidate_id` | String(64) | No | Unique candidate UUID (indexed) |
| `project_id` | String(64) | No | Reference to associated project (indexed) |
| `category` | String(64) | No | Category tag (`backend`, `frontend`, `database`, `deployment`, `coding_rule`, `constraint`, etc.) |
| `content` | Text | No | Proposed memory statement |
| `source` | String(64) | No | Source attribution (`user_confirmed`, `extracted_from_user_input`, `generated_assumption`) |
| `confidence` | Float | No | Extraction confidence score between 0.0 and 1.0 (extraction fidelity, not business importance) |
| `status` | String(32) | No | Proposal status (`pending`, `approved`, `rejected`, `duplicate`, `conflict`) |
| `evidence` | Text | No | Concise user-readable quotation or reason justifying the proposal |
| `conflicting_memory_id` | String(64) | Yes | Reference to conflicting active ProjectMemory if status is `conflict` |
| `conflicting_content` | Text | Yes | Content of the conflicting memory for user inspection |
| `metadata_json` | JSON | No | Contextual metadata dictionary |
| `created_at` | Float | No | Unix timestamp of creation |
| `updated_at` | Float | No | Unix timestamp of last update |

---

## Domain Mapping Principle

SQLAlchemy models (`*Record`) are strictly internal persistence representations.
Pydantic schemas (`RequirementAnalysis`, `InterviewSession`, `CompileResponse`, `Project`, `ProjectMemory`, `ProjectContext`, `CandidateMemory`) remain the authoritative domain and API representation.
The repository layer handles bidirectional mapping between domain entities and database records.

## Deterministic Context Retrieval
Project context retrieval (`ProjectMemoryRepository.get_project_context()`) strictly guarantees deterministic, reproducible sorting without semantic heuristics or vector search:
1. Category importance rank (`project_description` -> `architecture` -> `technology` -> `backend` -> `frontend` -> `database` -> `deployment` -> `requirement` -> `constraint` -> `coding_rule` -> `preference` -> `other`).
2. Source trust rank (`user_confirmed` -> `extracted_from_user_input` -> `system_defined` -> `generated_assumption`).
3. Chronological creation timestamp (`created_at` ascending).
4. Memory UUID tie-breaker (`memory_id` ascending).

## Project Memory Integration in Compilation Pipeline (Implemented in Task 17)

When `project_id` is supplied in `POST /api/compile` or `POST /api/interview/start`:
- `ProjectContext` is loaded via `ProjectMemoryService` and attached to `PromptGenerationContext.project_context`.
- `RequirementAnalysis.project_context_summary` retains a reference string of the project context, while `confirmed_requirements` only contains explicit user-requested items.
- In prompt construction, persistent context is rendered in a dedicated section: `=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===`.
- **Precedence Hierarchy**:
  1. Current explicit user requirements (Highest Priority — overrides conflicting project baseline).
  2. Persistent user-confirmed project memory.
  3. Extracted project context.
  4. System-defined defaults.
  5. Generated assumptions (Lowest Trust).
- **Read-Only Context**: Compiling a requirement NEVER writes or alters memories automatically.

## Candidate Memory & Confirmation Workflow (Implemented in Task 18)

Candidate extraction separates memory suggestion from persistence:
- **No Silent Writes**: Interaction text generates `CandidateMemory` proposals with status `pending`, `duplicate`, or `conflict`.
- **Deduplication**: Proposed candidates matching existing active project memories are flagged as `duplicate` and prevented from duplicating storage.
- **Conflict Detection**: Mutually exclusive or conflicting stack choices are flagged as `conflict` and linked to `conflicting_memory_id`.
- **Explicit Confirmation**:
  - `POST /api/projects/{project_id}/memory-candidates/{candidate_id}/approve`: Transitions candidate to `approved` and creates a persistent `ProjectMemory`. If `supersede_conflicting=True` is supplied, the conflicting memory is marked as `superseded`.
## Agent Formatting Presets (Implemented in Task 19)

Agent presets define downstream AI coding agent presentation formats without altering requirement semantics:
- **Core Principle**: "Agent presets change prompt presentation, not the underlying requirement semantics."
- **Supported Targets**:
  - `generic`: Canonical Prompt Compiler structure suitable for any standard LLM or coding assistant (default).
  - `cursor`: Optimized for Cursor IDE (Composer / Agent mode) with prioritized context, direct objectives, and clear validation.
  - `claude_code`: Optimized for Claude Code CLI autonomous terminal workflow with explicit role definition, task framing, and verification steps.
  - `cline`: Optimized for Cline / Roo Code autonomous VS Code extensions with direct task framing, clear constraints, and step execution.
  - `windsurf`: Optimized for Windsurf Cascade agent with contextual framing, objective, requirements, implementation instructions, and verification checkpoints.
- **Preset Model (`AgentPreset`)**:
  - `id`: Unique stable identifier (`generic`, `cursor`, `claude_code`, `cline`, `windsurf`).
  - `name`: Human-readable display name.
  - `description`: Purpose and style summary.
  - `instruction_style`: Style tag (`canonical_specification`, `ide_composer`, `autonomous_cli`, etc.).
  - `sections`: Ordered list of markdown headings for the preset.
  - `formatting_rules`: Formatting rules applied by the preset.
  - `metadata`: Additional configuration details.
- **Deterministic Formatting**: Pure Python string and section assembly; strictly zero additional LLM/Ollama calls.
- **Semantic Preservation**: Confirmed requirements, negative constraints, open decisions, coding rules, and project memory baseline are fully preserved across all presets.

## Vector Knowledge Base & Semantic Retrieval (Implemented in Task 20)

Task 20 establishes the local vector storage and semantic retrieval foundation using `sqlite-vec` over SQLite:

### `knowledge_sources` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal surrogate primary key |
| `source_id` | VARCHAR(64) | UNIQUE NOT NULL INDEX | Public UUID string identifier |
| `project_id` | VARCHAR(64) | NOT NULL INDEX | Associated project identifier (scoped isolation) |
| `source_type` | VARCHAR(32) | NOT NULL | Category: `documentation`, `text`, `code` |
| `source_name` | VARCHAR(255) | NOT NULL INDEX | Human-readable name or relative file path |
| `content_hash` | VARCHAR(64) | NOT NULL INDEX | Deterministic SHA-256 hash of normalized content |
| `chunk_count` | INTEGER | NOT NULL DEFAULT 0 | Number of generated chunks |
| `metadata_json` | JSON | NOT NULL DEFAULT '{}' | Structured source metadata (author, tags, file info) |
| `created_at` | FLOAT | NOT NULL | Unix epoch timestamp |
| `updated_at` | FLOAT | NOT NULL | Unix epoch timestamp |

### `knowledge_chunks` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal surrogate primary key |
| `chunk_id` | VARCHAR(64) | UNIQUE NOT NULL INDEX | Public UUID string identifier |
| `project_id` | VARCHAR(64) | NOT NULL INDEX | Associated project identifier |
| `source_id` | VARCHAR(64) | NOT NULL INDEX | Foreign reference to `knowledge_sources.source_id` |
| `chunk_index` | INTEGER | NOT NULL | Sequential chunk order index (0-based) |
| `content` | TEXT | NOT NULL | Normalized text chunk content |
| `content_hash` | VARCHAR(64) | NOT NULL INDEX | SHA-256 hash of chunk content |
| `metadata_json` | JSON | NOT NULL DEFAULT '{}' | Metadata (headings, offsets, source name/type) |
| `created_at` | FLOAT | NOT NULL | Unix epoch timestamp |

### `vec_chunks` Virtual Table (`sqlite-vec`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `chunk_id` | TEXT PRIMARY KEY | Primary key linked 1-to-1 with `knowledge_chunks.chunk_id` |
| `embedding` | float[768] distance_metric=cosine | Float32 embedding vector with cosine distance metric |

- **Score Semantics**: Vector search computes cosine distance $d \in [0.0, 2.0]$. Converted to similarity score $s = \max(0.0, \min(1.0, 1.0 - d))$ where $1.0$ is exact identity and $0.0$ is orthogonal/unrelated.
- **Project Isolation**: Every vector similarity query joins `vec_chunks` with `knowledge_chunks` and strictly filters on `knowledge_chunks.project_id = :project_id`. Chunks from Project A are never retrieved for Project B.
- **Separate from Project Memory**: Project Memory stores structured application facts; Knowledge Base stores searchable source documents and code.

## Semantic Retrieval Compiler Integration (Implemented in Task 21)

Task 21 integrates project-isolated semantic knowledge retrieval directly into the compilation pipeline:

### Compilation Persistence Schema Extension (`compilations`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `knowledge_references` | JSON | NULLABLE | List of serialized `KnowledgeReference` objects retrieved and injected as context |

### Interview Session Schema Extension (`interview_sessions`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `enable_knowledge_retrieval` | BOOLEAN | NOT NULL DEFAULT 1 | Request-level toggle controlling semantic context retrieval during interview compile |

### `KnowledgeContextItem` (Internal Generation Context Schema)
- `chunk_id`: String UUID of the retrieved chunk.
- `source_id`: String UUID of the originating knowledge source.
- `source_name`: Filename or title of the source (e.g. `architecture.md`).
- `source_type`: Origin category (`documentation`, `text`, `code`).
- `chunk_index`: 0-based sequence index within the source document.
- `content`: Bounded text snippet injected into generation context.
- `score`: Effective relevance score normalized between 0.0 and 1.0 (with source-type weighting applied).
- `metadata`: Arbitrary key-value metadata preserved from the index.
- `matched_queries`: List of deterministic search queries that retrieved or matched this chunk (Task 23).

### `KnowledgeReference` (API Response Schema)
- `chunk_id`: String UUID identifier.
- `source_id`: String UUID identifier.
- `source_name`: Display title or relative path.
- `source_type`: Source type identifier.
- `score`: Float similarity score rounded to 4 decimal places.
- `matched_queries`: List of deterministic search queries matching this chunk (Task 23).

### `KnowledgeRetrievalTelemetry` (Diagnostic Metadata Schema)
- `attempted`: Boolean flag indicating whether retrieval was executed.
- `skipped`: Boolean flag indicating whether retrieval was bypassed.
- `skip_reason`: Explanation if skipped (`no_project_id`, `retrieval_disabled`, `empty_query`, `embedding_unavailable`, etc.).
- `raw_count`: Total chunks returned by vector KNN before relevance filtering across all queries.
- `filtered_count`: Chunks passing `KNOWLEDGE_MIN_RELEVANCE_SCORE`.
- `latency_ms`: Execution time of the retrieval operation in milliseconds.
- `query_used`: Primary deterministic search query string used for retrieval.
- `queries_attempted`: All search query strings generated and executed (Task 23).
- `successful_queries`: Number of search queries successfully executed against the vector store (Task 23).
- `failed_queries`: Number of search queries that encountered embedding/connection errors (Task 23).
- `results_before_deduplication`: Total candidate results retrieved across all queries before deduplication (Task 23).
- `results_after_deduplication`: Unique candidate results after deduplicating by chunk ID (Task 23).
- `results_after_threshold`: Candidate chunks meeting or exceeding the relevance score threshold (Task 23).
- `final_result_count`: Number of items budgeted and injected into generation context (Task 23).
- `sources_represented`: Unique document/code source names represented in the final context (Task 23).

## Document Ingestion Foundation (Implemented in Task 22)

Task 22 introduces a local document discovery and parsing service feeding directly into the Vector Knowledge Base:

### Supported File Types & Source Mapping
| Extension | Source Type | Semantic Role |
| :--- | :--- | :--- |
| `.md` | `documentation` | Preserved Markdown structure (headings, lists, code blocks, links) |
| `.txt` | `text` | Clean plain text with normalized CRLF newlines |
| `.py` | `code` | Static source code (functions, classes, docstrings, comments preserved) |
| `.ts` | `code` | Static TypeScript source (interfaces, types, functions preserved) |
| `.json` | `code` | Validated JSON with deterministic key sorting (`indent=2, sort_keys=True`) |

### Ingestion Schemas
- **`DocumentIngestionResult`**:
  - `path`: Original path requested.
  - `relative_path`: Project-relative path used as canonical `source_name`.
  - `source_type`: Inferred category (`documentation`, `text`, `code`).
  - `status`: Outcome (`indexed`, `unchanged`, `skipped`, `failed`).
  - `source_id`: UUID of indexed knowledge source if successful.
  - `chunk_count`: Number of chunks generated and embedded.
  - `content_hash`: SHA-256 hash of normalized content.
  - `error`: Actionable error description if skipped or failed (`FILE_NOT_FOUND`, `INVALID_JSON`, `FILE_TOO_LARGE`, `PATH_OUTSIDE_PROJECT`, etc.).

- **`BatchDocumentIngestionResponse`**:
  - `project_id`: Project UUID.
  - `total`: Total discovered candidate files.
  - `indexed`: Number of newly indexed files.
  - `unchanged`: Number of unchanged files skipping re-embedding.
  - `skipped`: Number of skipped files (unsupported type, size limit).
  - `failed`: Number of failed files (invalid JSON, decode error).
  - `results`: List of `DocumentIngestionResult` items.

- **`IngestFileRequest`**:
  - `file_path`: Path to file relative to project root or within project root.
  - `project_root`: Optional project root path override if not configured on project.

- **`IngestDirectoryRequest`**:
  - `directory_path`: Optional sub-directory path relative to project root.
  - `project_root`: Optional project root path override if not configured on project.
  - `recursive`: Boolean flag (default `True`) controlling sub-directory traversal.

## Advanced Retrieval & Multi-Document Context Synthesis (Implemented in Task 23)

Task 23 extends the retrieval engine with deterministic multi-query synthesis, source-type weighting, and source diversity:

### Multi-Query Synthesis
- Bounded to `KNOWLEDGE_MAX_RETRIEVAL_QUERIES` (default 3).
- **Deterministic**: Derived strictly from `RequirementAnalysis` (Intent, Domain, Confirmed Requirements, Constraints, Missing Information). Zero extra LLM calls.
- **Deduplication**: Query strings are normalized and deduplicated before vector search execution.

### Result Merging & Scoring
- Results from all queries are merged and deduplicated by `chunk_id`.
- Score aggregation retains `max(query_scores)` across matching queries.
- Query provenance is tracked via `matched_queries: list[str]`.

### Source-Type Weighting
- Conservative multiplier applied based on `task_type` (`TASK_SOURCE_WEIGHTS`):
  - `build`: documentation (1.05), code (1.05), text (1.00)
  - `modify`: code (1.10), documentation (1.05), text (1.00)
  - `debug`: code (1.15), documentation (1.00), text (0.95)
  - `explain` / `analyze`: documentation (1.15), code (1.05), text (1.00)
  - Configuration files (`subtype="configuration"`) receive a 1.10 multiplier for build/modify/debug tasks.
- Effective score calculation: `effective_score = round(min(1.0, raw_score * weight), 4)`.

### Source Diversity
- Evaluates candidate sources to prevent single-source monopolies on competitive candidates.
- If an unrepresented source achieves `effective_score >= top_score * KNOWLEDGE_SOURCE_DIVERSITY_MIN_SCORE_RATIO` (default 0.8), it is prioritized for multi-source representation up to `top_k`.
- Weak sources are never forced; high-relevance chunks from a single source are retained if alternative sources are not competitive.

## Future Schemas (Phase 2+)
- **Conversation History** (`conversations`, `messages`)
- **Feedback & Evaluations** (`prompt_evaluations`, `user_edits`)
- **Reranker Scores** (Advanced cross-encoder re-ranking metadata)






