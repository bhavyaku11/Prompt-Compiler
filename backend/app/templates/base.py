"""Abstract base definitions for Prompt Compiler templates."""

from abc import ABC, abstractmethod


class PromptTemplate(ABC):
    """Abstract base class defining the interface for task-specific prompt templates."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name of the template."""

    @property
    @abstractmethod
    def task_type(self) -> str:
        """Canonical task type identifier matching RequirementAnalysis.task_type."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Summary of the template's purpose and usage scope."""

    @property
    @abstractmethod
    def sections(self) -> list[str]:
        """Ordered list of section titles included in this template."""

    @abstractmethod
    def get_structure_guidance(self) -> str:
        """Returns the formatted markdown skeleton guiding prompt generation."""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(task_type='{self.task_type}')>"
