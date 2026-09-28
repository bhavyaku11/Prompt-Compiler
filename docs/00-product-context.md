# Product Context — Prompt Compiler

## Product
Prompt Compiler

## Product Goal
Convert rough, incomplete, or unstructured user requirements into clear, structured, context-aware, implementation-ready prompts for AI coding and development agents.

## Core Problem
Users often give AI development agents short or ambiguous instructions. The agent then has to guess missing requirements, which can lead to:
- incorrect implementation
- missing functionality
- unnecessary changes
- repeated prompting
- inconsistent output
- prompts that are difficult to reuse across agents

## Core Product Promise
A user can provide a rough requirement in natural language and receive a refined prompt that preserves the user's intent, identifies important missing information, applies only safe defaults, and is structured for implementation.

## Primary Users
1. Developers and students using AI coding agents.
2. Vibe coders who want better results from short requirements.
3. Teams that need repeatable prompt structures for recurring development tasks.

## Supported Input Types
Initial:
- Plain text requirements

Planned:
- Screenshots
- UI references
- Handwritten sketches
- Images
- URLs/webpages
- Files/documents
- Existing prompts
- Conversation/project context

## Core Capabilities
- Quick Prompt Refinement
- Optional Prompt Interview Mode
- Requirement extraction
- Missing-information detection
- Safe-default handling
- Task/domain-specific prompt templates
- Prompt analysis and criticism
- Project/conversation memory
- Agent-specific prompt formatting
- Local AI inference
- Prompt validation and quality checks

## Product Principles
- Preserve user intent.
- Never invent important requirements.
- Separate confirmed requirements, safe defaults, and unknowns.
- Prefer explicit uncertainty over fabricated certainty.
- Keep the compiler model-agnostic and provider-replaceable.
- Keep local inference as the default architecture.
- Build features as small, testable vertical slices.
- Do not claim functionality has been verified without testing.

## Local-First Principle
The initial product uses local AI inference through Ollama. The application should not require cloud AI APIs for its core prompt-compilation workflow.

## Terminology
"Prompt Compiler" is the product/architecture name for this system. It is not required to be a standardized industry term. The product uses the compiler analogy because the system transforms unstructured human intent into a structured, validated instruction suitable for another AI agent.
