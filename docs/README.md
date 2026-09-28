# Prompt Compiler — Development Documentation

This directory is the product-development source of truth for the Prompt Compiler project.

## What This Documentation Covers

- Product context and boundaries
- Product requirements
- Technical requirements
- Approved scope
- User flows
- Conceptual data model
- API contract
- Architecture
- UI/UX principles
- AI coding rules
- Current implementation status
- Next task
- Build history
- Decisions
- Known issues
- Change history
- Risks
- Release checklist
- AI task-state template

## Read Before Coding

At minimum, read:

1. `00-product-context.md`
2. `01-prd-product-requirements.md`
3. `02-trd-technical-requirements.md`
4. `03-approved-scope.md`
5. `07-architecture.md`
6. `09-ai-vibe-coding-rules.md`
7. `10-current-status.md`
8. `11-next-task.md`

Read other files when they are relevant to the task.

## Update After Coding

Update the relevant documentation after each implementation task:

- `10-current-status.md`
- `11-next-task.md`
- `12-build-log.md`
- `13-decision-log.md` when decisions change
- `14-known-issues.md` when issues are discovered
- `15-change-log.md`

## Golden Rules

1. Inspect before modifying.
2. Implement one focused task at a time.
3. Do not invent important requirements.
4. Do not claim unverified behavior.
5. Do not change architecture without approval.
6. Do not add unnecessary dependencies.
7. Keep local AI/provider integration isolated.
8. Treat unknown information as unknown.
9. Prefer explicit limitations over fabricated certainty.
10. Keep documentation synchronized with the actual repository state.

## Reference-Pack Note

The reference documentation pack used during preparation was structured around another project. Its structure and AI-development practices were useful as a pattern, but domain-specific content was not copied into this project.

The following reference topics were intentionally omitted because they are not currently relevant to Prompt Compiler:
- Field research
- Unit economics
