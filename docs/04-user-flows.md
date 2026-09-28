# User Flows

## Quick Refine
Rough input → classify intent → extract requirements → detect important unknowns → apply safe defaults where appropriate → build prompt → validate → show final prompt.

## Prompt Interview
User chooses Interview Mode → analyze input → identify only material missing information → ask targeted questions → incorporate answers → build prompt → validate → show final prompt.

## Prompt Analysis
Existing prompt → analyze intent → identify ambiguity → identify missing requirements → identify unsupported assumptions → suggest improvements → produce refined prompt.

## Template-Based Task
User selects task/domain → provide rough details → template engine selects structure → fill known fields → identify missing fields → generate prompt → validate.

## Project Context
Current input → retrieve approved project context → apply relevant constraints/conventions → generate prompt → show which context materially affected the result.

## Visual Input (Later)
Screenshot/sketch/image → vision model → extract visual requirements → classify → compile prompt.

## URL/File Input (Later)
URL/file → extract relevant content → identify requirements → compile prompt.

## Final Review
Generated prompt → validation → quality warnings if needed → user can edit/copy/regenerate.
