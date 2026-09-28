# Security Policy

## Reporting Security Vulnerabilities

We take the security of Prompt Compiler seriously. If you believe you have discovered a security vulnerability in this project, please report it responsibly.

### How to Report

Please **do not** report security vulnerabilities through public GitHub issues or discussions.

Instead, please submit a vulnerability report via **GitHub Private Vulnerability Reporting** on this repository:
- Navigate to the **Security** tab of [https://github.com/bhavyaku11/Prompt-Compiler](https://github.com/bhavyaku11/Prompt-Compiler)
- Click **Report a vulnerability**

Include as much information as possible:
- Steps to reproduce the issue or proof-of-concept
- Affected component (`frontend`, `backend`, `src-tauri`, or packaging)
- Potential impact of the vulnerability

We will review your submission and respond promptly.

---

## Security Architecture & Invariants

Prompt Compiler is engineered with strict local-first security boundaries:

1. **Loopback Isolation**: The local FastAPI sidecar binds strictly to `127.0.0.1` and never exposes open network listeners (`0.0.0.0`).
2. **Zero-Secret Invariant**: Production client bundles, desktop installers, and macOS `.app` binaries contain **zero** server secret keys or private keys. Authentication utilizes offline public RSA key verification.
3. **Server-Side Data Ownership**: Client-supplied `user_id` parameters in request bodies are ignored. Resource access is strictly scoped to the authenticated user on the backend.
4. **Anti-Probing Boundaries**: Unauthorized attempts to access, mutate, or delete resources belonging to another user return HTTP `404 Not Found` (never `403 Forbidden`) to prevent resource enumeration.
5. **Path Traversal Protection**: Directory and document ingestion validates canonical filesystem paths (`pathlib.Path.resolve()`) against the project root boundary. Traversal attempts (`../`, symbolic link escapes) are rejected with security errors.
6. **Local Persistence**: All compiled prompts, memories, and vector embeddings reside on the local filesystem outside the application bundle (`~/Library/Application Support/com.promptcompiler.app/prompt_compiler.db`).
