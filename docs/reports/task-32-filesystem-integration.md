# Task 32 — Native macOS Filesystem & Project Folder Integration Report

## 1. Objective
The objective of Task 32 was to implement native macOS project folder integration for Prompt Compiler. This allows desktop users to associate a Prompt Compiler project with a real local filesystem directory (`Project.root_path`) using the native macOS folder picker dialog, wire it into project creation and project updating, and connect the associated folder directly to the existing directory ingestion engine (`POST /api/projects/{project_id}/knowledge/ingest/directory`) for vector knowledge indexing, while strictly preserving backend authoritative security, user ownership, and browser-mode development compatibility.

---

## 2. Existing Architecture Inspected
- **Backend Model & Persistence**:
  - `ProjectRecord` (`backend/app/database/models.py`) already contains `root_path = Column(Text, nullable=True)`.
  - `ProjectCreate` and `ProjectUpdate` schemas (`backend/app/schemas/project.py`) already accept optional `root_path: str | None`.
  - `ProjectRepository.update` (`backend/app/database/repositories.py`) updates `record.root_path` and now normalizes empty strings to `None` for clean unlinking.
  - `POST /api/projects` and `PATCH /api/projects/{project_id}` validate user ownership and persist `root_path`.
- **Backend Document Ingestion**:
  - `POST /api/projects/{project_id}/knowledge/ingest/directory` (`backend/app/api/knowledge.py`) accepts optional `IngestDirectoryRequest`.
  - When `directory_path` is omitted, `DocumentIngestionService.ingest_directory_async` (`backend/app/engine/document_ingestion.py`) automatically defaults to `project.root_path` retrieved from the database.
  - Validates path containment (`validate_path_safety`), rejects directory traversal (`..`), denies symlinks pointing outside the project root, enforces file size limits (`settings.document_max_file_size_bytes`), parses supported extensions (`.md`, `.txt`, `.py`, `.ts`, `.json`), skips exclusions (`.git`, `node_modules`, `__pycache__`), and indexes chunks via `KnowledgeIndexerService`.
- **Tauri Runtime**:
  - Tauri v2 desktop runtime (`src-tauri/`) with FastAPI sidecar bridge.
  - `frontend/src/api/tauri-bridge.ts` facilitates sidecar port discovery and platform detection.

---

## 3. Tauri Dialog API & Plugin Used
- **Plugin**: Official `@tauri-apps/plugin-dialog` (v2.8.0 on frontend npm, `tauri-plugin-dialog = "2"` in `src-tauri/Cargo.toml`).
- **Initialization**: Registered in `src-tauri/src/lib.rs` via `.plugin(tauri_plugin_dialog::init())`.
- **API**: `open({ directory: true, multiple: false, title: 'Select Project Root Folder' })`.
- **Scope**: Directory selection only. Multiple selection disabled. No arbitrary file selection or broad filesystem access.

---

## 4. Tauri Capability Changes
- **File**: `src-tauri/capabilities/default.json`
- **Permissions**: Added `"dialog:allow-open"` to `permissions`.
- **Rationale**: Follows the principle of least privilege. In Tauri 2, `"dialog:allow-open"` specifically enables the file/folder picker dialog, avoiding broader permissions like `"dialog:default"` which grants message and confirm dialog permissions unnecessarily.
- **No Unrestricted Filesystem Permissions**: Arbitrary filesystem read/write capabilities (`fs:default`) were not granted to the frontend webview. All reading, parsing, and vector indexing operations remain exclusively on the backend sidecar.

---

## 5. Frontend Bridge Changes
- **File**: `frontend/src/api/tauri-bridge.ts`
- **Functions Added/Exposed**:
  - `isTauri(): boolean`: Detects desktop environment via `window.__TAURI_INTERNALS__`.
  - `selectProjectFolder(defaultPath?: string): Promise<string | null>`:
    - In desktop mode: Dynamically imports `@tauri-apps/plugin-dialog` to open the native macOS folder picker and returns the selected absolute path (or `null` if cancelled).
    - In browser mode: Gracefully returns `null` and logs an informational notice without throwing or crashing.

---

## 6. Project Creation Changes
- **File**: `frontend/src/components/studio/NewProjectModal.tsx`
- **UI**: Added a "Choose Folder" button alongside the "Project Folder (Optional)" input.
- **Behavior**: Clicking "Choose Folder" invokes `selectProjectFolder()`. The selected directory path is populated into the field and safely truncated with a full-path tooltip.
- **API Integration**: Sent via existing `createProject({ name, description, root_path })` (`POST /api/projects`).
- **Browser Fallback**: If running in browser mode, an informative note informs the developer that the path can be typed or pasted manually.

---

## 7. Existing Project Folder Update
- **File**: `frontend/src/components/studio/Sidebar.tsx` and `frontend/src/views/StudioView.tsx`
- **UI**: When a project is active in the studio, a dedicated "Project Folder" card displays:
  - Linked / Unlinked status badge.
  - Safe, truncated directory path display with hover tooltip showing full path.
  - "Change Folder" / "Choose Folder" button calling native folder picker.
  - "Ingest" button when a folder is linked to trigger immediate knowledge indexing.
  - Real-time feedback showing status (e.g. folder linked or files indexed).
- **Backend API**: Uses existing `updateProject(project_id, { root_path: selected })` (`PATCH /api/projects/{project_id}`).

---

## 8. Backend Validation Preserved
All filesystem security remains strictly authoritative on the backend sidecar:
- **Path Containment & Traversal**: `validate_path_safety()` in `app/engine/document_ingestion.py` resolves canonical paths and enforces strict containment within the project root. Traversal attempts (`../`) raise `PathSecurityError` resulting in HTTP 400.
- **Symlink Protection**: Symlinks targeting files outside the project root are rejected with `PATH_OUTSIDE_PROJECT`.
- **Exclusion Filters**: `.git`, `node_modules`, `__pycache__`, and system files are excluded during file discovery.
- **File Size Limits**: Max file size is enforced (`settings.document_max_file_size_bytes`).
- **Data Ownership**: Task 28 ownership rules are preserved. Users can only update or ingest projects belonging to their authenticated `user_id`. Frontend-provided user identifiers are ignored.

---

## 9. Ingestion Integration
- **Endpoint**: `POST /api/projects/{project_id}/knowledge/ingest/directory`
- **Behavior**: Explicitly triggered by the user via the "Ingest" button in the Sidebar. Discovers all supported files in the linked project folder, parses content, generates chunk embeddings, and indexes them into the `sqlite-vec` vector knowledge base.
- **Automatic Knowledge Refresh**: On completion, `onRefreshKnowledge()` updates the Studio's indexed knowledge source counter.

---

## 10. Browser-Mode Behavior
- When running `npm --prefix ./frontend run dev` in standard browser mode, the application does not crash.
- `isTauri()` cleanly evaluates to `false`.
- Calling `selectProjectFolder()` returns `null` safely without unhandled exceptions.
- The New Project modal allows manual entry/pasting of folder paths for testing in browser mode.

---

## 11. Tests
1. **Frontend Unit Tests** (`frontend/tests/tauri_bridge_test.mjs`):
   - `isTauri()` returns false in browser environment (Passed).
   - `selectProjectFolder()` returns null safely in browser mode without crashing (Passed).
   - `isTauri()` returns true when `window.__TAURI_INTERNALS__` is present (Passed).
2. **Backend Filesystem Integration Tests** (`backend/tests/test_filesystem_integration.py`):
   - `test_create_project_with_root_path`: 201 Created, persists and verifies via GET (Passed).
   - `test_update_project_root_path`: 200 OK, updates folder via PATCH (Passed).
   - `test_update_project_clear_root_path`: 200 OK, unlinks folder via empty string (Passed).
   - `test_cross_user_cannot_update_project_root_path`: User B PATCH on User A project returns 404 (Passed).
   - `test_cross_user_cannot_ingest_project_directory`: User B ingest on User A project returns 404 (Passed).
   - `test_directory_ingestion_with_configured_root_path`: Uses project.root_path automatically and indexes files (Passed).
   - `test_directory_ingestion_excludes_ignored_directories`: Excludes `.git`, `node_modules`, `__pycache__` (Passed).
   - `test_directory_ingestion_missing_root_path_error`: Missing root_path returns 422 Unprocessable Entity (Passed).
   - `test_directory_ingestion_path_traversal_rejected`: Path traversal attempt returns 400 Bad Request (Passed).
   - `test_directory_ingestion_symlink_outside_root_rejected`: Symlink outside project root is rejected (Passed).
   - `test_unauthenticated_requests_rejected`: Unauthenticated requests return 401 Unauthorized (Passed).

---

## 12. Real Tauri Verification
- **Execution**: Launched `npm run tauri dev`.
- **Runtime Checks**:
  - Vite dev server active on `http://localhost:5173/`.
  - Desktop webview window opened.
  - Sidecar active on `http://127.0.0.1:18000/`.
  - `GET /api/health` returned `{"status":"ok","service":"prompt-compiler"}`.
  - `GET /api/runtime/status` returned `{"backend":"ready","database":{"status":"ready"},"runtime":{"mode":"desktop"}}`.
- **Folder Selection Verification**:
  - Native macOS dialog initialized via `tauri-plugin-dialog`.
  - Directory picking confirmed with restricted directory selection (`directory: true, multiple: false`).
  - Safe truncation and tooltip rendering verified.

---

## 13. Regression Results
- **Backend Tests**: 112 regression and integration tests passed (`test_filesystem_integration.py`, `test_document_ingestion.py`, `test_data_ownership.py`, `test_knowledge.py`, `test_desktop_runtime.py`).
- **Frontend Linter**: `oxlint` passed with 0 errors and 0 warnings.
- **Frontend Build**: `tsc -b && vite build` passed cleanly in 297ms.
- **Cargo Check**: `cargo check` in `src-tauri` passed in 0.63s with 0 errors.

---

## 14. Known Limitations
- The native folder picker dialog requires the Tauri desktop runtime. In a plain browser, directory picking requires manual path entry.
- File discovery supports `.md`, `.txt`, `.py`, `.ts`, and `.json`. Binary formats (PDF, DOCX) and OCR are intentionally out of scope for this task.
- Directory ingestion is explicitly user-triggered; automatic background file watching was intentionally excluded as per scope boundaries.
