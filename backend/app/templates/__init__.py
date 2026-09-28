"""Prompt templates package for Prompt Compiler."""

from app.templates.base import PromptTemplate
from app.templates.definitions import (
    AnalyzeTemplate,
    BuildTemplate,
    DebugTemplate,
    ExplainTemplate,
    ModifyTemplate,
)
from app.templates.selector import (
    TemplateSelector,
    UnsupportedTaskTypeError,
)
from app.templates.agent_presets import (
    AgentPresetRegistry,
    UnsupportedAgentPresetError,
    get_preset,
    is_supported,
    list_presets,
    validate_agent,
)

__all__ = [
    "PromptTemplate",
    "BuildTemplate",
    "ModifyTemplate",
    "DebugTemplate",
    "ExplainTemplate",
    "AnalyzeTemplate",
    "TemplateSelector",
    "UnsupportedTaskTypeError",
    "AgentPresetRegistry",
    "UnsupportedAgentPresetError",
    "get_preset",
    "list_presets",
    "validate_agent",
    "is_supported",
]

