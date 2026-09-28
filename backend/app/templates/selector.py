"""Deterministic template selector and registry for Prompt Compiler."""

from app.templates.base import PromptTemplate
from app.templates.definitions import (
    AnalyzeTemplate,
    BuildTemplate,
    DebugTemplate,
    ExplainTemplate,
    ModifyTemplate,
)


class UnsupportedTaskTypeError(ValueError):
    """Raised when an unsupported task type is provided for template selection."""


class TemplateSelector:
    """Deterministic selector that maps task types to prompt templates."""

    def __init__(self) -> None:
        self._registry: dict[str, PromptTemplate] = {
            "build": BuildTemplate(),
            "modify": ModifyTemplate(),
            "debug": DebugTemplate(),
            "explain": ExplainTemplate(),
            "analyze": AnalyzeTemplate(),
        }

    @property
    def supported_task_types(self) -> list[str]:
        """List of all supported canonical task type strings."""
        return sorted(self._registry.keys())

    def get_template(self, task_type: str) -> PromptTemplate:
        """Retrieve the appropriate template for a given task type string.

        Args:
            task_type: Canonical task type identifier (e.g. 'build', 'modify', etc.).

        Returns:
            The matching PromptTemplate instance.

        Raises:
            UnsupportedTaskTypeError: If task_type is empty, unknown, or not supported.
        """
        normalized = task_type.strip().lower() if task_type else ""
        template = self._registry.get(normalized)
        if template is None:
            raise UnsupportedTaskTypeError(
                f"Unsupported task type '{task_type}'. Supported types: {self.supported_task_types}"
            )
        return template

    def select(self, task_type: str) -> PromptTemplate:
        """Alias for get_template providing a standard select interface."""
        return self.get_template(task_type)
