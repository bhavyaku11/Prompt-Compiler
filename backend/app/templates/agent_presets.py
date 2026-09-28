"""Agent preset registry and definitions for Prompt Compiler."""

from app.schemas.agent_preset import AgentPreset, AgentTarget, SUPPORTED_AGENTS


class UnsupportedAgentPresetError(ValueError):
    """Raised when an unknown or unsupported agent preset ID is requested."""


GENERIC_PRESET = AgentPreset(
    id="generic",
    name="Generic AI Agent",
    description="Canonical Prompt Compiler specification suitable for any standard AI coding assistant or LLM.",
    instruction_style="canonical_specification",
    sections=[
        "Objective",
        "Technical Domain & Context",
        "Confirmed Requirements",
        "Constraints",
        "Open Decisions & Missing Information",
        "Safe Assumptions",
        "Implementation Instructions",
        "Expected Outcome",
    ],
    formatting_rules=[
        "Preserve canonical Prompt Compiler template headings",
        "Maintain strict separation between project baseline and user requirements",
        "Highlight open decisions without assuming defaults",
    ],
    metadata={"target_platform": "generic_llm"},
)

CURSOR_PRESET = AgentPreset(
    id="cursor",
    name="Cursor IDE / Composer",
    description="Optimized for Cursor IDE (Composer / Agent mode) with prioritized context, direct objectives, and clear validation.",
    instruction_style="ide_composer",
    sections=[
        "Context",
        "Objective",
        "Requirements",
        "Constraints & Rules",
        "Open Decisions",
        "Implementation Instructions",
        "Validation",
    ],
    formatting_rules=[
        "Place Context at the top for immediate repository alignment",
        "Group negative constraints and coding conventions into Constraints & Rules",
        "Provide actionable implementation steps with clear validation criteria",
    ],
    metadata={"target_platform": "cursor_ide", "preferred_mode": "composer"},
)

CLAUDE_CODE_PRESET = AgentPreset(
    id="claude_code",
    name="Claude Code CLI",
    description="Optimized for Claude Code CLI autonomous terminal workflow with explicit role definition, task framing, and verification steps.",
    instruction_style="autonomous_cli",
    sections=[
        "Role",
        "Task",
        "Project Context",
        "Requirements",
        "Constraints",
        "Open Decisions",
        "Implementation Steps",
        "Verification",
    ],
    formatting_rules=[
        "Include explicit Role statement for workspace autonomy",
        "Define task with clear imperative command structure",
        "Group verification into testable terminal inspection steps",
    ],
    metadata={"target_platform": "claude_code_cli", "execution_mode": "terminal_agent"},
)

CLINE_PRESET = AgentPreset(
    id="cline",
    name="Cline / Roo Code",
    description="Optimized for Cline / Roo Code autonomous VS Code extensions with direct task framing, clear constraints, and step execution.",
    instruction_style="autonomous_extension",
    sections=[
        "Task",
        "Context",
        "Requirements",
        "Constraints",
        "Open Decisions",
        "Implementation",
        "Validation",
    ],
    formatting_rules=[
        "Task-first headline framing",
        "Clean separation of context, constraints, and requirements",
        "Clear validation checklist for tool-driven verification",
    ],
    metadata={"target_platform": "vscode_extension", "extension_name": "cline"},
)

WINDSURF_PRESET = AgentPreset(
    id="windsurf",
    name="Windsurf Cascade",
    description="Optimized for Windsurf Cascade agent with contextual framing, objective, requirements, implementation instructions, and verification checkpoints.",
    instruction_style="cascade_flow",
    sections=[
        "Task",
        "Context",
        "Requirements",
        "Constraints",
        "Open Decisions",
        "Implementation",
        "Verification",
    ],
    formatting_rules=[
        "Direct task specification",
        "Contextual domain and project memory grouping",
        "Stepwise implementation guidance with verification checkpoints",
    ],
    metadata={"target_platform": "windsurf_ide", "agent_name": "cascade"},
)

PRESET_REGISTRY: dict[str, AgentPreset] = {
    "generic": GENERIC_PRESET,
    "cursor": CURSOR_PRESET,
    "claude_code": CLAUDE_CODE_PRESET,
    "cline": CLINE_PRESET,
    "windsurf": WINDSURF_PRESET,
}


class AgentPresetRegistry:
    """Registry providing centralized lookup and validation for agent presets."""

    @classmethod
    def get(cls, agent_id: str) -> AgentPreset:
        """Retrieve an AgentPreset by its identifier, raising UnsupportedAgentPresetError if unknown."""
        normalized = cls.validate(agent_id)
        return PRESET_REGISTRY[normalized]

    @classmethod
    def list(cls) -> list[AgentPreset]:
        """Return all registered agent presets in deterministic order."""
        return list(PRESET_REGISTRY.values())

    @classmethod
    def validate(cls, agent_id: str | None) -> str:
        """Validate and normalize an agent preset identifier."""
        if not agent_id or not isinstance(agent_id, str):
            return "generic"
        normalized = agent_id.strip().lower()
        if normalized not in PRESET_REGISTRY:
            supported = ", ".join(f"'{k}'" for k in PRESET_REGISTRY.keys())
            raise UnsupportedAgentPresetError(
                f"Unsupported target agent '{agent_id}'. Supported agents: {supported}."
            )
        return normalized

    @classmethod
    def is_supported(cls, agent_id: str | None) -> bool:
        """Check if an agent preset identifier is supported."""
        if not agent_id or not isinstance(agent_id, str):
            return False
        return agent_id.strip().lower() in PRESET_REGISTRY


# Top-level helper functions for convenience
def get_preset(agent_id: str) -> AgentPreset:
    return AgentPresetRegistry.get(agent_id)


def list_presets() -> list[AgentPreset]:
    return AgentPresetRegistry.list()


def validate_agent(agent_id: str | None) -> str:
    return AgentPresetRegistry.validate(agent_id)


def is_supported(agent_id: str | None) -> bool:
    return AgentPresetRegistry.is_supported(agent_id)
