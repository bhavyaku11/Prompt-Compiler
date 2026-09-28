"""API request and response schemas for Prompt Compiler."""

from pydantic import BaseModel, Field, field_validator


class CompileRequest(BaseModel):
    """Request schema for prompt compilation."""

    input: str = Field(
        ...,
        description="The rough user requirement or instruction to compile.",
    )
    interview_mode: bool = Field(
        default=False,
        description="Whether to route through interview clarification mode.",
    )
    interview_session_id: str | None = Field(
        default=None,
        description="Optional interview session ID to compile from directly.",
    )
    project_id: str | None = Field(
        default=None,
        description="Optional project ID to load persistent project context.",
    )
    target_agent: str = Field(
        default="generic",
        description="Target AI coding agent preset for prompt formatting (generic, cursor, claude_code, cline, windsurf).",
    )
    enable_knowledge_retrieval: bool = Field(
        default=True,
        description="Whether to retrieve relevant knowledge base chunks when project_id is provided.",
    )


    @field_validator("target_agent")
    @classmethod
    def validate_target_agent_field(cls, value: str) -> str:
        from app.templates.agent_presets import validate_agent
        return validate_agent(value)

    @field_validator("input")
    @classmethod
    def validate_input_not_empty(cls, value: str) -> str:
        """Ensure input is non-empty and contains non-whitespace content without trimming."""
        if not value or not value.strip():
            raise ValueError("Input prompt cannot be empty or contain only whitespace.")
        return value


class RequirementSummary(BaseModel):
    """Structured requirement analysis summary in API responses."""

    intent: str = Field(..., description="The fundamental objective.")
    task_type: str = Field(..., description="The canonical task type.")
    domain: str = Field(..., description="Subject domain.")
    confirmed_requirements: list[str] = Field(default_factory=list, description="Explicit user requirements.")
    missing_information: list[str] = Field(default_factory=list, description="Absent material decisions.")
    constraints: list[str] = Field(default_factory=list, description="Explicit constraints.")
    assumptions: list[str] = Field(default_factory=list, description="Conservative assumptions.")
    project_context_summary: str | None = Field(
        default=None,
        description="Optional summary of active project context.",
    )


class ValidationIssueSummary(BaseModel):
    """Validation finding summary in API responses."""

    category: str = Field(..., description="Category of the validation issue.")
    severity: str = Field(..., description="Severity level: error, warning, info.")
    message: str = Field(..., description="Human-readable explanation of the issue.")


class ValidationSummary(BaseModel):
    """Validation result summary in API responses."""

    overall_valid: bool = Field(..., description="Whether the prompt is valid without critical errors.")
    issues: list[ValidationIssueSummary] = Field(default_factory=list, description="Itemized validation issues.")
    preserved_requirements: list[str] = Field(default_factory=list, description="Confirmed requirements present in prompt.")
    missing_requirements: list[str] = Field(default_factory=list, description="Confirmed requirements omitted from prompt.")
    violated_constraints: list[str] = Field(default_factory=list, description="Explicit constraints omitted or violated.")
    invented_requirements: list[str] = Field(default_factory=list, description="Unconfirmed technologies detected.")
    missing_information_preserved: bool = Field(default=True, description="Whether open decisions remained open.")
    task_type_valid: bool = Field(default=True, description="Whether prompt aligns with task type.")
    structure_valid: bool = Field(default=True, description="Whether prompt meets structural requirements.")


class CompileResponse(BaseModel):
    """Response schema for prompt compilation."""

    input: str = Field(
        ...,
        description="The original user input requirement.",
    )
    result: str = Field(
        ...,
        description="The compiled, structured prompt ready for an AI agent.",
    )
    task_type: str | None = Field(
        default=None,
        description="The canonical task type identified for the requirement.",
    )
    template_name: str | None = Field(
        default=None,
        description="The prompt template used to construct the result.",
    )
    requirements: RequirementSummary | None = Field(
        default=None,
        description="Structured requirement analysis summary.",
    )
    validation: ValidationSummary | None = Field(
        default=None,
        description="Quality and fidelity validation findings.",
    )
    refinement_attempts: int = Field(
        default=0,
        description="Number of automated refinement attempts performed (0 if initially valid).",
    )
    interview_session_id: str | None = Field(
        default=None,
        description="Interview session ID if compilation originated from an interview session.",
    )
    project_id: str | None = Field(
        default=None,
        description="Project ID if compilation used project context.",
    )
    target_agent: str = Field(
        default="generic",
        description="Target AI coding agent preset used for prompt formatting.",
    )
    knowledge_references: list["KnowledgeReference"] = Field(
        default_factory=list,
        description="Provenance references to knowledge chunks retrieved and supplied as background context.",
    )
    knowledge_telemetry: "KnowledgeRetrievalTelemetry | None" = Field(
        default=None,
        description="Lightweight telemetry for semantic knowledge retrieval execution.",
    )


class KnowledgeReference(BaseModel):
    """Provenance reference to a retrieved knowledge chunk used in compilation."""

    chunk_id: str = Field(..., description="ID of the retrieved knowledge chunk.")
    source_id: str = Field(..., description="ID of the parent knowledge source.")
    source_name: str = Field(..., description="Name of the knowledge source document or code snippet.")
    source_type: str = Field(..., description="Type of knowledge source: documentation, text, code.")
    score: float = Field(..., description="Cosine similarity relevance score (0.0 to 1.0).")
    matched_queries: list[str] = Field(
        default_factory=list,
        description="Search queries that retrieved or matched this chunk.",
    )


class KnowledgeRetrievalTelemetry(BaseModel):
    """Lightweight telemetry metrics for knowledge retrieval in compilation."""

    attempted: bool = Field(default=False, description="Whether knowledge retrieval was attempted.")
    skipped: bool = Field(default=True, description="Whether knowledge retrieval was skipped.")
    skip_reason: str | None = Field(default=None, description="Reason retrieval was skipped, if applicable.")
    raw_count: int = Field(default=0, description="Total chunks returned by vector search across all queries.")
    filtered_count: int = Field(default=0, description="Number of chunks retained after relevance threshold filtering.")
    latency_ms: float = Field(default=0.0, description="Knowledge retrieval execution time in milliseconds.")
    query_used: str | None = Field(default=None, description="Primary search query string used for retrieval.")
    queries_attempted: list[str] = Field(
        default_factory=list,
        description="All deterministic search queries generated and attempted.",
    )
    successful_queries: int = Field(default=0, description="Number of queries successfully executed.")
    failed_queries: int = Field(default=0, description="Number of queries that encountered errors.")
    results_before_deduplication: int = Field(
        default=0,
        description="Total raw candidate results across all queries before deduplication.",
    )
    results_after_deduplication: int = Field(
        default=0,
        description="Unique candidate results after deduplicating by chunk ID.",
    )
    results_after_threshold: int = Field(
        default=0,
        description="Candidates meeting or exceeding min_relevance_score.",
    )
    final_result_count: int = Field(
        default=0,
        description="Final number of knowledge items budgeted and injected into context.",
    )
    sources_represented: list[str] = Field(
        default_factory=list,
        description="Unique knowledge sources represented in the final context.",
    )







class HealthResponse(BaseModel):
    """Response schema for the service health check endpoint."""

    status: str = Field(
        default="ok",
        description="Health status of the service.",
    )
    service: str = Field(
        default="prompt-compiler",
        description="Identifier of the service.",
    )


class RootResponse(BaseModel):
    """Response schema for the root service endpoint."""

    name: str = Field(
        default="Prompt Compiler",
        description="Application name.",
    )
    version: str = Field(
        default="0.1.0",
        description="Application version.",
    )
    status: str = Field(
        default="running",
        description="Application runtime status.",
    )
