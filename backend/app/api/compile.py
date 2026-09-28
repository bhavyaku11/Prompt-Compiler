import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.ollama import (
    EmptyPromptError,
    OllamaClient,
    OllamaConnectionError,
    OllamaHTTPError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from app.auth import get_current_user
from app.config import settings
from app.database.models import UserRecord
from app.database.repositories import CompilationRepository, KnowledgeRepository, ProjectRepository
from app.engine.critic import PromptCritic
from app.engine.generator import PromptGenerator
from app.engine.interviewer import PromptInterviewer, SessionNotFoundError
from app.engine.knowledge_retrieval import KnowledgeRetriever, RetrievalExecutionResult
from app.engine.knowledge_search import KnowledgeSearchService
from app.engine.refiner import PromptRefiner
from app.engine.requirements import (
    EmptyInputError,
    RequirementEngine,
    RequirementExtractionError,
)
from app.engine.project_memory import ProjectMemoryService, ProjectNotFoundError
from app.engine.agent_formatter import AgentFormatter
from app.schemas.project import ProjectContext
from app.schemas.agent_preset import AgentPreset
from app.schemas.api import (
    CompileRequest,
    CompileResponse,
    RequirementSummary,
    ValidationIssueSummary,
    ValidationSummary,
)
from app.templates.agent_presets import list_presets
from app.templates.selector import TemplateSelector, UnsupportedTaskTypeError

router = APIRouter(tags=["compile"])

_ollama_client: OllamaClient | None = None
_template_selector: TemplateSelector | None = None
_prompt_interviewer: PromptInterviewer | None = None
_compilation_repo: CompilationRepository | None = None
_project_service: ProjectMemoryService | None = None
_agent_formatter: AgentFormatter | None = None
_knowledge_retriever: KnowledgeRetriever | None = None



def get_ollama_client() -> OllamaClient:
    """Dependency provider for OllamaClient with client reuse."""
    global _ollama_client
    if _ollama_client is None:
        timeout = max(settings.ollama_timeout, 600.0)
        _ollama_client = OllamaClient(timeout=timeout)
    return _ollama_client


from app.api.projects import get_project_service


def get_requirement_engine(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> RequirementEngine:
    """Dependency provider for RequirementEngine."""
    return RequirementEngine(ollama_client=ollama_client)


def get_template_selector() -> TemplateSelector:
    """Dependency provider for TemplateSelector with reuse."""
    global _template_selector
    if _template_selector is None:
        _template_selector = TemplateSelector()
    return _template_selector


def get_prompt_generator(
    ollama_client: OllamaClient = Depends(get_ollama_client),
    template_selector: TemplateSelector = Depends(get_template_selector),
) -> PromptGenerator:
    """Dependency provider for PromptGenerator."""
    return PromptGenerator(
        ollama_client=ollama_client,
        template_selector=template_selector,
    )


def get_prompt_critic(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> PromptCritic:
    """Dependency provider for PromptCritic."""
    return PromptCritic(ollama_client=ollama_client)


def get_prompt_refiner(
    prompt_generator: PromptGenerator = Depends(get_prompt_generator),
    prompt_critic: PromptCritic = Depends(get_prompt_critic),
) -> PromptRefiner:
    """Dependency provider for PromptRefiner."""
    return PromptRefiner(
        prompt_generator=prompt_generator,
        prompt_critic=prompt_critic,
    )


def get_prompt_interviewer(
    ollama_client: OllamaClient = Depends(get_ollama_client),
) -> PromptInterviewer:
    """Dependency provider for PromptInterviewer with singleton reuse."""
    global _prompt_interviewer
    if _prompt_interviewer is None:
        _prompt_interviewer = PromptInterviewer(ollama_client=ollama_client)
    return _prompt_interviewer


def get_compilation_repository() -> CompilationRepository:
    """Dependency provider for CompilationRepository with singleton reuse."""
    global _compilation_repo
    if _compilation_repo is None:
        _compilation_repo = CompilationRepository()
    return _compilation_repo


def get_agent_formatter() -> AgentFormatter:
    """Dependency provider for AgentFormatter with singleton reuse."""
    global _agent_formatter
    if _agent_formatter is None:
        _agent_formatter = AgentFormatter()
    return _agent_formatter


def get_knowledge_search_service(
    project_service: ProjectMemoryService = Depends(get_project_service),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> KnowledgeSearchService:
    """Dependency provider for KnowledgeSearchService scoped to the active project service database."""
    project_repo = getattr(project_service, "_project_repo", getattr(project_service, "project_repo", None))
    session_factory = getattr(project_repo, "_session_factory", None) if project_repo else None
    knowledge_repo = KnowledgeRepository(session_factory=session_factory)
    return KnowledgeSearchService(
        project_repository=project_repo or ProjectRepository(),
        knowledge_repository=knowledge_repo,
        embedding_provider=embedding_provider,
    )


def get_knowledge_retriever(
    search_service: KnowledgeSearchService = Depends(get_knowledge_search_service),
) -> KnowledgeRetriever:
    """Dependency provider for KnowledgeRetriever."""
    return KnowledgeRetriever(search_service=search_service)


@router.get("/api/presets", response_model=list[AgentPreset])
async def list_agent_presets() -> list[AgentPreset]:
    """List all supported downstream AI coding agent formatting presets."""
    return list_presets()


@router.post("/api/compile", response_model=CompileResponse)
async def compile_prompt(
    request: CompileRequest,
    current_user: UserRecord = Depends(get_current_user),
    requirement_engine: RequirementEngine = Depends(get_requirement_engine),
    template_selector: TemplateSelector = Depends(get_template_selector),
    prompt_generator: PromptGenerator = Depends(get_prompt_generator),
    prompt_critic: PromptCritic = Depends(get_prompt_critic),
    prompt_refiner: PromptRefiner = Depends(get_prompt_refiner),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
    compilation_repo: CompilationRepository = Depends(get_compilation_repository),
    project_service: ProjectMemoryService = Depends(get_project_service),
    agent_formatter: AgentFormatter = Depends(get_agent_formatter),
    knowledge_retriever: KnowledgeRetriever = Depends(get_knowledge_retriever),
) -> CompileResponse:
    """Process a compilation request through the complete Prompt Compiler pipeline.

    Orchestration:
    1. If project_id is provided, loads persistent project context via ProjectMemoryService.
    2. RequirementEngine extracts structured RequirementAnalysis (or retrieves clarified analysis from session).
    3. TemplateSelector selects the task-type PromptTemplate.
    4. PromptGenerator builds the generation context (with project context) and generates the implementation prompt.
    5. PromptRefiner evaluates the prompt with PromptCritic and runs iterative refinement if actionable issues exist.
    6. Returns CompileResponse with compiled prompt, requirements summary, validation findings, and refinement metrics.
    """
    if request.interview_mode and not request.interview_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview mode requested. Please initiate an interview session via POST /api/interview/start.",
        )

    target_project_id = request.project_id
    project_context: ProjectContext | None = None
    retrieval_res = RetrievalExecutionResult()

    try:
        # Step 0: Load project context if project_id is explicitly specified
        if target_project_id:
            try:
                project_context = await project_service.get_project_context_async(target_project_id, user_id=current_user.id)
            except ProjectNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Project '{target_project_id}' not found.",
                ) from exc

        # Step 1: Requirement Extraction / Session Resolution
        if request.interview_session_id:
            session = await interviewer.store.get(request.interview_session_id, user_id=current_user.id)
            if not target_project_id and session.project_id:
                target_project_id = session.project_id
                try:
                    project_context = await project_service.get_project_context_async(target_project_id, user_id=current_user.id)
                except ProjectNotFoundError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Project '{target_project_id}' not found.",
                    ) from exc
            analysis = session.current_analysis
        else:
            if project_context is not None:
                analysis = await requirement_engine.analyze_async(request.input, project_context=project_context)
            else:
                analysis = await requirement_engine.analyze_async(request.input)

        # Step 1.5: Semantic Knowledge Retrieval
        retrieval_res = await knowledge_retriever.retrieve_async(
            project_id=target_project_id,
            analysis=analysis,
            raw_input=request.input,
            enabled=request.enable_knowledge_retrieval,
        )
        retrieved_knowledge = retrieval_res.items

        # Step 2: Template Selection
        template = template_selector.select(analysis.task_type)

        # Step 3: Initial Prompt Generation
        gen_kwargs: dict[str, Any] = {}
        if project_context is not None:
            gen_kwargs["project_context"] = project_context
        if retrieved_knowledge:
            gen_kwargs["retrieved_knowledge"] = retrieved_knowledge

        initial_generation = await prompt_generator.generate_async(
            analysis,
            **gen_kwargs,
        )

        # Step 4: Quality & Fidelity Validation + Automated Refinement Loop
        refine_kwargs: dict[str, Any] = {"use_llm_critic": False}
        if project_context is not None:
            refine_kwargs["project_context"] = project_context
        if retrieved_knowledge:
            refine_kwargs["retrieved_knowledge"] = retrieved_knowledge

        refinement_result = await prompt_refiner.run_loop_async(
            analysis=analysis,
            initial_generation=initial_generation,
            **refine_kwargs,
        )

    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (EmptyInputError, EmptyPromptError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except UnsupportedTaskTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except RequirementExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Requirement extraction failure: {exc}",
        ) from exc
    except OllamaConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Ollama service unavailable: {exc}",
        ) from exc
    except OllamaTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Ollama request timed out: {exc}",
        ) from exc
    except OllamaHTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama upstream HTTP error ({exc.status_code}): {exc.response_body}",
        ) from exc
    except OllamaResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Invalid response from Ollama: {exc}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred during compilation.",
        ) from exc

    # Map internal objects to API response schemas
    requirements_summary = RequirementSummary(
        intent=analysis.intent,
        task_type=analysis.task_type,
        domain=analysis.domain,
        confirmed_requirements=analysis.confirmed_requirements,
        missing_information=analysis.missing_information,
        constraints=analysis.constraints,
        assumptions=analysis.assumptions,
        project_context_summary=analysis.project_context_summary,
    )

    validation_summary = ValidationSummary(
        overall_valid=refinement_result.validation_result.overall_valid,
        issues=[
            ValidationIssueSummary(
                category=issue.category,
                severity=issue.severity,
                message=issue.message,
            )
            for issue in refinement_result.validation_result.issues
        ],
        preserved_requirements=refinement_result.validation_result.preserved_requirements,
        missing_requirements=refinement_result.validation_result.missing_requirements,
        violated_constraints=refinement_result.validation_result.violated_constraints,
        invented_requirements=refinement_result.validation_result.invented_requirements,
        missing_information_preserved=refinement_result.validation_result.missing_information_preserved,
        task_type_valid=refinement_result.validation_result.task_type_valid,
        structure_valid=refinement_result.validation_result.structure_valid,
    )

    # Format according to target_agent
    formatted_prompt = agent_formatter.format_prompt(
        compiled_prompt=refinement_result.final_prompt,
        target_agent=request.target_agent,
        analysis=analysis,
        project_context=project_context,
        retrieved_knowledge=retrieval_res.items,
    )

    # Persist compilation record
    try:
        await asyncio.to_thread(
            compilation_repo.save,
            input_text=request.input,
            compiled_prompt=formatted_prompt,
            task_type=refinement_result.task_type,
            template_name=refinement_result.template_name,
            requirements_summary=requirements_summary.model_dump(),
            validation_summary=validation_summary.model_dump(),
            refinement_attempts=refinement_result.refinement_attempts,
            interview_session_id=request.interview_session_id,
            project_id=target_project_id,
            target_agent=request.target_agent,
            knowledge_references=[r.model_dump() for r in retrieval_res.references] if retrieval_res.references else None,
            user_id=current_user.id,
        )
    except Exception:
        pass

    return CompileResponse(
        input=request.input,
        result=formatted_prompt,
        task_type=refinement_result.task_type,
        template_name=refinement_result.template_name,
        requirements=requirements_summary,
        validation=validation_summary,
        refinement_attempts=refinement_result.refinement_attempts,
        interview_session_id=request.interview_session_id,
        project_id=target_project_id,
        target_agent=request.target_agent,
        knowledge_references=retrieval_res.references,
        knowledge_telemetry=retrieval_res.telemetry,
    )


