"""Schemas for AI coding agent formatting presets."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class AgentTarget(str, Enum):
    """Supported downstream AI coding agent targets."""

    GENERIC = "generic"
    CURSOR = "cursor"
    CLAUDE_CODE = "claude_code"
    CLINE = "cline"
    WINDSURF = "windsurf"


SUPPORTED_AGENTS: tuple[str, ...] = tuple(agent.value for agent in AgentTarget)


class AgentPreset(BaseModel):
    """Representation of an agent-specific prompt formatting preset."""

    id: str = Field(..., description="Unique stable identifier of the agent preset (e.g., 'cursor').")
    name: str = Field(..., description="Human-readable display name of the target agent.")
    description: str = Field(..., description="Summary of the preset's purpose and formatting style.")
    instruction_style: str = Field(..., description="Guidance style (e.g., 'autonomous_cli', 'ide_composer').")
    sections: list[str] = Field(..., description="Ordered list of section headings used in the preset.")
    formatting_rules: list[str] = Field(default_factory=list, description="Formatting rules applied by this preset.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional preset metadata.")
