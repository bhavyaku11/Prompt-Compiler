"""Interview schemas for Prompt Compiler multi-turn clarification mode."""

from pydantic import BaseModel, Field, field_validator
from app.schemas.api import RequirementSummary


class InterviewStartRequest(BaseModel):
    """Request schema for starting an interview session."""

    input: str = Field(
        ...,
        description="The rough user requirement or instruction to clarify.",
    )
    project_id: str | None = Field(
        default=None,
        description="Optional project ID to associate with interview.",
    )
    target_agent: str = Field(
        default="generic",
        description="Target AI coding agent preset for prompt formatting.",
    )
    enable_knowledge_retrieval: bool = Field(
        default=True,
        description="Whether to retrieve relevant knowledge base chunks when compiling.",
    )


    @field_validator("target_agent")
    @classmethod
    def validate_target_agent_field(cls, value: str) -> str:
        from app.templates.agent_presets import validate_agent
        return validate_agent(value)

    @field_validator("input")
    @classmethod
    def validate_input_not_empty(cls, value: str) -> str:
        """Ensure input contains non-whitespace content."""
        if not value or not value.strip():
            raise ValueError("Input prompt cannot be empty or contain only whitespace.")
        return value


class InterviewQuestion(BaseModel):
    """Schema for a single clarification question presented to the user."""

    id: str = Field(..., description="Unique question identifier within the session, e.g. 'q1'.")
    topic: str = Field(..., description="Material topic, e.g., 'deployment', 'authentication', 'database'.")
    question: str = Field(..., description="Concise, actionable question text.")
    options: list[str] = Field(
        default_factory=list,
        description="Suggested selectable options for the user.",
    )
    allow_custom: bool = Field(
        default=True,
        description="Whether the user is allowed to provide a free-form custom answer.",
    )


class InterviewAnswer(BaseModel):
    """Schema for a single answer provided by the user."""

    question_id: str = Field(..., description="The ID of the question being answered.")
    answer: str = Field(..., description="The user's selected option or free-form answer.")

    @field_validator("question_id", "answer")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Question ID and answer cannot be empty or contain only whitespace.")
        return value.strip()


class InterviewAnswerRequest(BaseModel):
    """Request schema for submitting answers to an ongoing interview session."""

    answers: list[InterviewAnswer] = Field(
        ...,
        description="List of answers to the pending questions.",
    )

    @field_validator("answers")
    @classmethod
    def validate_answers_not_empty(cls, value: list[InterviewAnswer]) -> list[InterviewAnswer]:
        if not value:
            raise ValueError("At least one answer must be provided.")
        return value


class InterviewSessionResponse(BaseModel):
    """Response schema representing current state of an interview session."""

    session_id: str = Field(..., description="Unique UUID identifying the interview session.")
    status: str = Field(
        ...,
        description="Session status: 'in_progress', 'ready', or 'compiled'.",
    )
    turn: int = Field(default=1, description="Current interview turn (1-indexed).")
    questions: list[InterviewQuestion] = Field(
        default_factory=list,
        description="Targeted clarification questions for the current turn.",
    )
    requirements: RequirementSummary = Field(
        ...,
        description="Current structured requirement analysis state.",
    )
    unresolved_topics: list[str] = Field(
        default_factory=list,
        description="Remaining material topics that are still unresolved.",
    )
    message: str | None = Field(
        default=None,
        description="Informational status message for the client.",
    )
    project_id: str | None = Field(
        default=None,
        description="Associated project ID if applicable.",
    )
    target_agent: str = Field(
        default="generic",
        description="Target AI coding agent preset for prompt formatting.",
    )

