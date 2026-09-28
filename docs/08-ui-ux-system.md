# UI/UX System

## Product Experience
The final application should feel like a focused developer utility rather than a generic AI chat application.

## Core Screens
- Home / Quick Refine
- Prompt Interview
- Prompt Analysis
- Templates
- Project Context
- History
- Settings

## Quick Refine
- Large primary input area
- Clear mode selection
- Target-agent selection when applicable
- Visible processing state
- Structured final prompt output
- Copy/edit/regenerate actions

## Interview
- Ask only material questions.
- Show progress.
- Keep questions concise.
- Allow the user to skip non-critical questions.
- Never force Interview Mode when Quick Refine was selected.

## Final Prompt
Show:
- Final prompt
- Important assumptions, if any
- Missing information warnings, if any
- Selected template
- Target agent, if selected

## States
Every applicable screen should define:
- loading
- empty
- error
- success
- unavailable
- validation failure

## Design Principles
- Minimal
- Professional
- Fast
- Clear hierarchy
- Avoid unnecessary animation
- Do not make the interface look like an AI-generated template
- Responsive macOS-first development UI
