"""Agent-specific deterministic prompt formatter for Prompt Compiler."""

import re
from typing import Any

from app.engine.requirements import RequirementAnalysis
from app.schemas.knowledge import KnowledgeContextItem
from app.schemas.project import ProjectContext
from app.templates.agent_presets import (
    AgentPresetRegistry,
    UnsupportedAgentPresetError,
    validate_agent,
)


class AgentFormatter:
    """Deterministic prompt formatter for downstream AI coding agents.

    Transforms canonical Prompt Compiler outputs into tailored presentation formats
    optimized for specific AI coding agents (Generic, Cursor, Claude Code, Cline, Windsurf)
    without altering underlying requirements, constraints, or project context.
    """

    def format_prompt(
        self,
        compiled_prompt: str,
        target_agent: str = "generic",
        analysis: RequirementAnalysis | None = None,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> str:
        """Format a compiled prompt for a specific target agent preset.

        Args:
            compiled_prompt: The refined, canonical compiled prompt string.
            target_agent: Stable identifier of the target agent (generic, cursor, claude_code, cline, windsurf).
            analysis: Optional RequirementAnalysis providing structured fallback data.
            project_context: Optional persistent ProjectContext providing baseline context.
            retrieved_knowledge: Optional list of retrieved knowledge context items.

        Returns:
            The deterministically formatted prompt string.

        Raises:
            UnsupportedAgentPresetError: If target_agent is unrecognized.
        """
        agent_id = validate_agent(target_agent)

        # For canonical generic prompt, return the compiled prompt directly
        if agent_id == "generic":
            return compiled_prompt

        # Parse sections from the compiled prompt and supplement with structured analysis
        sections = self.extract_sections(compiled_prompt)
        self._supplement_sections(sections, analysis, project_context, retrieved_knowledge)

        # Dispatch to preset formatter
        if agent_id == "cursor":
            return self._format_cursor(sections)
        elif agent_id == "claude_code":
            return self._format_claude_code(sections)
        elif agent_id == "cline":
            return self._format_cline(sections)
        elif agent_id == "windsurf":
            return self._format_windsurf(sections)

        return compiled_prompt.strip()

    def extract_sections(self, text: str) -> dict[str, str]:
        """Parse markdown headings from prompt text into canonical section keys."""
        sections: dict[str, str] = {
            "objective": "",
            "domain_context": "",
            "project_context": "",
            "retrieved_knowledge": "",
            "requirements": "",
            "constraints": "",
            "open_decisions": "",
            "assumptions": "",
            "implementation": "",
            "outcome": "",
            "raw_body": "",
        }

        # Extract project context banner if present at the top
        proj_banner_match = re.search(
            r"=== PROJECT CONTEXT \(EXISTING APPLICATION BASELINE\) ===\s*(.*?)(?=(?:===|\n#|\Z))",
            text,
            re.DOTALL,
        )
        if proj_banner_match:
            sections["project_context"] = proj_banner_match.group(1).strip()

        # Extract retrieved knowledge banner if present
        knowledge_banner_match = re.search(
            r"=== RETRIEVED PROJECT KNOWLEDGE \(CONTEXTUAL EVIDENCE\) ===\s*(.*?)(?=(?:===|\n#|\Z))",
            text,
            re.DOTALL,
        )
        if knowledge_banner_match:
            sections["retrieved_knowledge"] = knowledge_banner_match.group(1).strip()

        # Match markdown headers: # Title, ## Title, or ### Title
        heading_matches = list(re.finditer(r"^(#{1,3})\s+([^\n]+)", text, re.MULTILINE))

        if not heading_matches:
            # Fallback if no markdown headers exist
            cleaned = text.strip()
            sections["raw_body"] = cleaned
            sections["objective"] = cleaned
            return sections

        for i, match in enumerate(heading_matches):
            raw_title = match.group(2).strip()
            clean_title = raw_title.lower()

            start_idx = match.end()
            end_idx = heading_matches[i + 1].start() if i + 1 < len(heading_matches) else len(text)
            content = text[start_idx:end_idx].strip()

            # Categorize into canonical slots
            if any(w in clean_title for w in ("objective", "task", "goal", "overview")):
                sections["objective"] = content
            elif "project context" in clean_title or "project baseline" in clean_title:
                if not sections["project_context"]:
                    sections["project_context"] = content
            elif "retrieved" in clean_title or "knowledge" in clean_title:
                if not sections["retrieved_knowledge"]:
                    sections["retrieved_knowledge"] = content
            elif any(w in clean_title for w in ("domain", "technical domain", "environment")) and "project" not in clean_title:
                sections["domain_context"] = content
            elif any(w in clean_title for w in ("requirement", "confirmed requirement")):
                sections["requirements"] = content
            elif any(w in clean_title for w in ("constraint", "boundary", "non-negotiable", "rules")):
                sections["constraints"] = content
            elif any(w in clean_title for w in ("open decision", "missing information", "unresolved")):
                sections["open_decisions"] = content
            elif any(w in clean_title for w in ("safe assumption", "assumption")):
                sections["assumptions"] = content
            elif any(w in clean_title for w in ("implementation", "instructions", "steps", "guidance")):
                sections["implementation"] = content
            elif any(w in clean_title for w in ("expected outcome", "outcome", "validation", "verification", "acceptance")):
                sections["outcome"] = content

        return sections

    def _supplement_sections(
        self,
        sections: dict[str, str],
        analysis: RequirementAnalysis | None,
        project_context: ProjectContext | None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> None:
        """Supplement any empty section slots with structured metadata."""
        if project_context is not None and not sections["project_context"]:
            sections["project_context"] = project_context.to_context_string().strip()

        if retrieved_knowledge and not sections["retrieved_knowledge"]:
            items = []
            for item in retrieved_knowledge:
                items.append(
                    f"[Source: {item.source_name} | Type: {item.source_type} | Relevance: {item.score:.2f}]\n{item.content.strip()}"
                )
            sections["retrieved_knowledge"] = "\n\n".join(items)

        if analysis is not None:
            if not sections["objective"]:
                sections["objective"] = analysis.intent

            if not sections["domain_context"] and analysis.domain:
                sections["domain_context"] = f"Domain: {analysis.domain}"

            if not sections["requirements"] and analysis.confirmed_requirements:
                sections["requirements"] = "\n".join(f"- {r}" for r in analysis.confirmed_requirements)

            if not sections["constraints"] and analysis.constraints:
                sections["constraints"] = "\n".join(f"- {c}" for c in analysis.constraints)

            if not sections["open_decisions"] and analysis.missing_information:
                sections["open_decisions"] = "\n".join(
                    f"- {m} (Open Decision: requires user specification; do not invent a default)"
                    for m in analysis.missing_information
                )

            if not sections["assumptions"] and analysis.assumptions:
                sections["assumptions"] = "\n".join(f"- {a}" for a in analysis.assumptions)

    def _build_context_block(self, sections: dict[str, str]) -> str:
        """Construct a unified context block preserving project baseline, domain context, and retrieved knowledge."""
        parts: list[str] = []

        if sections.get("project_context"):
            clean_proj = sections["project_context"].strip()
            # If the header banner isn't in clean_proj, wrap it cleanly
            if "=== PROJECT CONTEXT" not in clean_proj:
                parts.append(
                    "=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===\n"
                    "Note: Explicit Current User Requirements take precedence over Project Context in case of conflict.\n\n"
                    f"{clean_proj}"
                )
            else:
                parts.append(clean_proj)

        if sections.get("retrieved_knowledge"):
            clean_know = sections["retrieved_knowledge"].strip()
            if "=== RETRIEVED PROJECT KNOWLEDGE" not in clean_know:
                parts.append(
                    "=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===\n"
                    "Note: Background documentation evidence. Explicit user requirements take precedence.\n\n"
                    f"{clean_know}"
                )
            else:
                parts.append(clean_know)

        if sections.get("domain_context"):
            parts.append(sections["domain_context"].strip())

        return "\n\n".join(parts) if parts else ""


    def _format_cursor(self, sections: dict[str, str]) -> str:
        """Format prompt optimized for Cursor Composer / Agent mode."""
        blocks: list[str] = []

        # 1. Context (Top-level project and domain alignment)
        context_body = self._build_context_block(sections)
        if context_body:
            blocks.append(f"# Context\n{context_body}")

        # 2. Objective
        obj = sections.get("objective") or "Execute the requested feature implementation."
        blocks.append(f"# Objective\n{obj}")

        # 3. Requirements
        reqs = sections.get("requirements") or "- None explicitly stated"
        blocks.append(f"# Requirements\n{reqs}")

        # 4. Constraints & Rules
        constraints = sections.get("constraints") or "- None specified"
        blocks.append(f"# Constraints & Rules\n{constraints}")

        # 5. Open Decisions (if any)
        if sections.get("open_decisions"):
            blocks.append(f"# Open Decisions\n{sections['open_decisions']}")

        # 6. Implementation Instructions
        impl = sections.get("implementation") or sections.get("raw_body") or "Implement the requirements following project architecture."
        blocks.append(f"# Implementation Instructions\n{impl}")

        # 7. Validation
        val = sections.get("outcome") or "Ensure all requirements pass automated tests and manual inspection."
        blocks.append(f"# Validation\n{val}")

        return "\n\n".join(blocks)

    def _format_claude_code(self, sections: dict[str, str]) -> str:
        """Format prompt optimized for Claude Code CLI autonomous workflow."""
        blocks: list[str] = []

        # 1. Explicit Role
        blocks.append(
            "# Role\n"
            "Act as an expert software engineering agent executing this task in the workspace."
        )

        # 2. Task
        task = sections.get("objective") or "Execute the requested feature implementation."
        blocks.append(f"# Task\n{task}")

        # 3. Project Context
        context_body = self._build_context_block(sections)
        if context_body:
            blocks.append(f"# Project Context\n{context_body}")

        # 4. Requirements
        reqs = sections.get("requirements") or "- None explicitly stated"
        blocks.append(f"# Requirements\n{reqs}")

        # 5. Constraints
        constraints = sections.get("constraints") or "- None specified"
        blocks.append(f"# Constraints\n{constraints}")

        # 6. Open Decisions (if any)
        if sections.get("open_decisions"):
            blocks.append(f"# Open Decisions\n{sections['open_decisions']}")

        # 7. Implementation Steps
        impl = sections.get("implementation") or sections.get("raw_body") or "Implement the requirements systematically."
        blocks.append(f"# Implementation Steps\n{impl}")

        # 8. Verification
        ver = sections.get("outcome") or "Verify the implementation by running relevant test suites and checking outputs."
        blocks.append(f"# Verification\n{ver}")

        return "\n\n".join(blocks)

    def _format_cline(self, sections: dict[str, str]) -> str:
        """Format prompt optimized for Cline / Roo Code autonomous VS Code extensions."""
        blocks: list[str] = []

        # 1. Task (Headline)
        task = sections.get("objective") or "Execute the requested feature implementation."
        blocks.append(f"# Task\n{task}")

        # 2. Context
        context_body = self._build_context_block(sections)
        if context_body:
            blocks.append(f"# Context\n{context_body}")

        # 3. Requirements
        reqs = sections.get("requirements") or "- None explicitly stated"
        blocks.append(f"# Requirements\n{reqs}")

        # 4. Constraints
        constraints = sections.get("constraints") or "- None specified"
        blocks.append(f"# Constraints\n{constraints}")

        # 5. Open Decisions (if any)
        if sections.get("open_decisions"):
            blocks.append(f"# Open Decisions\n{sections['open_decisions']}")

        # 6. Implementation
        impl = sections.get("implementation") or sections.get("raw_body") or "Follow systematic implementation steps."
        blocks.append(f"# Implementation\n{impl}")

        # 7. Validation
        val = sections.get("outcome") or "Run verification checks to confirm all requirements are met."
        blocks.append(f"# Validation\n{val}")

        return "\n\n".join(blocks)

    def _format_windsurf(self, sections: dict[str, str]) -> str:
        """Format prompt optimized for Windsurf Cascade agent."""
        blocks: list[str] = []

        # 1. Task
        task = sections.get("objective") or "Execute the requested feature implementation."
        blocks.append(f"# Task\n{task}")

        # 2. Context
        context_body = self._build_context_block(sections)
        if context_body:
            blocks.append(f"# Context\n{context_body}")

        # 3. Requirements
        reqs = sections.get("requirements") or "- None explicitly stated"
        blocks.append(f"# Requirements\n{reqs}")

        # 4. Constraints
        constraints = sections.get("constraints") or "- None specified"
        blocks.append(f"# Constraints\n{constraints}")

        # 5. Open Decisions (if any)
        if sections.get("open_decisions"):
            blocks.append(f"# Open Decisions\n{sections['open_decisions']}")

        # 6. Implementation
        impl = sections.get("implementation") or sections.get("raw_body") or "Execute code modifications following project conventions."
        blocks.append(f"# Implementation\n{impl}")

        # 7. Verification
        ver = sections.get("outcome") or "Verify correct operation and absence of regressions."
        blocks.append(f"# Verification\n{ver}")

        return "\n\n".join(blocks)
