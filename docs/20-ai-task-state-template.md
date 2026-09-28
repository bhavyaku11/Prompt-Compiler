# AI Task State Template

Use this template before asking an AI coding agent to implement a task.

```text
PROJECT: Prompt Compiler

READ FIRST:
- docs/00-product-context.md
- docs/01-prd-product-requirements.md
- docs/02-trd-technical-requirements.md
- docs/03-approved-scope.md
- docs/07-architecture.md
- docs/09-ai-vibe-coding-rules.md
- docs/10-current-status.md
- docs/11-next-task.md

TASK:
[ONE CLEAR TASK]

WHY:
[PRODUCT OR ENGINEERING REASON]

SCOPE:
[WHAT IS INCLUDED]

OUT OF SCOPE:
[WHAT MUST NOT CHANGE]

BEFORE CODING:
- Read relevant docs.
- Inspect repository files.
- Inspect current patterns.
- Explain the implementation plan.
- List assumptions.
- List files to inspect/change.
- List acceptance criteria.

IMPLEMENTATION:
- Smallest complete vertical slice.
- Reuse existing code and conventions.
- No unrelated changes.
- No invented APIs, schemas, or requirements.
- No fake production data.
- Keep provider-specific logic isolated.

AFTER CODING:
- Run relevant tests.
- Report exact files changed.
- Report actual tests and results.
- Report known limitations.
- Update current-status.md.
- Update next-task.md.
- Append build-log.md.
- Update change-log.md.
- Update decision-log.md if a decision changed.
- Update known-issues.md if an issue was discovered.
```
