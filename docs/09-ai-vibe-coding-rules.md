# AI Vibe Coding Rules

## Before Coding
The AI must:
1. Read relevant documentation.
2. Inspect repository files.
3. Inspect git status when available.
4. Identify current architecture.
5. Explain task scope.
6. List files to inspect/change.
7. List assumptions.
8. List acceptance criteria.
9. Identify dependencies.
10. Ask before changing architecture or scope.

## Documentation Priority
The `docs/` directory is the product-development source of truth.

Relevant documentation must be read before implementing a task.

## Never Do
- Invent requirements.
- Invent APIs or schemas.
- Invent test results.
- Claim a feature works without verification.
- Rewrite unrelated files.
- Add unapproved features.
- Add unnecessary dependencies.
- Add cloud AI providers without approval.
- Replace Ollama without approval.
- Delete project data blindly.
- Commit secrets.
- Hide errors with fake fallback output.
- Change unrelated UI.

## Prompt Isolation
Each coding prompt must implement one focused task or vertical slice.

Do not combine unrelated features in one prompt.

## Requirement Integrity
The AI must distinguish:
- Confirmed requirement
- Safe default
- Unknown / needs clarification

Important unknowns must not be silently converted into confirmed requirements.

## Implementation Order
Prefer:
1. Schemas / models
2. Core logic
3. API
4. Validation
5. Integration
6. Tests
7. Documentation

## Required Final Report
```text
Implemented:
Files changed:
Dependencies changed:
Tests actually run:
Test results:
Known limitations:
Manual verification:
Next recommended task:
Docs updated:
```

## When Uncertain
Use explicit language:
- "I cannot verify this from the repository."
- "This is an assumption."
- "This requirement is not specified."
- "I need approval before changing scope."
