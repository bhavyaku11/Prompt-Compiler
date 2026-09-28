import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.ai.ollama import (
    EmptyPromptError,
    OllamaClient,
    OllamaConnectionError,
    OllamaHTTPError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from app.api.compile import (
    get_agent_formatter,
    get_compilation_repository,
    get_knowledge_retriever,
    get_ollama_client,
    get_project_service,
    get_prompt_critic,
    get_prompt_generator,
    get_prompt_interviewer,
    get_prompt_refiner,
    get_requirement_engine,
    get_template_selector,
)
from app.auth import get_current_user
from app.database.models import UserRecord
from app.database.repositories import CompilationRepository
from app.engine.agent_formatter import AgentFormatter
from app.engine.critic import PromptCritic
from app.engine.generator import PromptGenerator
from app.engine.interviewer import (
    InvalidAnswerError,
    PromptInterviewer,
    SessionCompletedError,
    SessionNotFoundError,
)
from app.engine.knowledge_retrieval import KnowledgeRetriever, RetrievalExecutionResult
from app.engine.project_memory import ProjectMemoryService, ProjectNotFoundError
from app.engine.refiner import PromptRefiner
from app.engine.requirements import (
    EmptyInputError,
    RequirementEngine,
    RequirementExtractionError,
)
from app.schemas.api import (
    CompileResponse,
    RequirementSummary,
    ValidationIssueSummary,
    ValidationSummary,
)
from app.schemas.interview import (
    InterviewAnswerRequest,
    InterviewSessionResponse,
    InterviewStartRequest,
)
from app.templates.selector import TemplateSelector, UnsupportedTaskTypeError

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/start", response_model=InterviewSessionResponse)
async def start_interview(
    request: InterviewStartRequest,
    current_user: UserRecord = Depends(get_current_user),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
    requirement_engine: RequirementEngine = Depends(get_requirement_engine),
    project_service: ProjectMemoryService = Depends(get_project_service),
) -> InterviewSessionResponse:
    """Initiate an optional clarification interview session.
    
    Orchestration:
    1. If project_id is provided, verifies that the project exists and belongs to current user.
    2. Extracts structured requirements via RequirementEngine.
    3. Identifies material unresolved implementation decisions.
    4. If none exist, session is marked 'ready' with zero questions.
    5. Otherwise, generates up to MAX_INTERVIEW_QUESTIONS targeted questions.
    6. Returns the session state and questions with project_id.
    """
    if request.project_id:
        try:
            await project_service.get_project_async(request.project_id, user_id=current_user.id)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{request.project_id}' not found.",
            ) from exc

    try:
        session = await interviewer.start_session_async(
            input_text=request.input,
            requirement_engine=requirement_engine,
            use_llm=True,
            project_id=request.project_id,
            user_id=current_user.id,
            target_agent=request.target_agent,
            enable_knowledge_retrieval=request.enable_knowledge_retrieval,
        )
        return interviewer.to_session_response(session)

    except (EmptyInputError, EmptyPromptError) as exc:
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
            detail=f"Unexpected error starting interview session: {exc}",
        ) from exc


@router.post("/{session_id}/answer", response_model=InterviewSessionResponse)
async def submit_interview_answers(
    session_id: str,
    request: InterviewAnswerRequest,
    current_user: UserRecord = Depends(get_current_user),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
) -> InterviewSessionResponse:
    """Submit answers to questions in an active interview session.
    
    Orchestration:
    1. Validates session existence and in-progress status for current user.
    2. Merges user answers into confirmed requirements.
    3. Removes resolved topics from missing information.
    4. Evaluates if further clarification is required or marks session 'ready'.
    5. Returns updated session state.
    """
    try:
        session = await interviewer.submit_answers_async(
            session_id=session_id,
            answers=request.answers,
            use_llm=True,
            user_id=current_user.id,
        )
        return interviewer.to_session_response(session)

    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except SessionCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidAnswerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
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
            detail=f"Unexpected error submitting answers: {exc}",
        ) from exc


@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview_session(
    session_id: str,
    current_user: UserRecord = Depends(get_current_user),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
) -> InterviewSessionResponse:
    """Retrieve the current state of an interview session."""
    try:
        session = await interviewer.store.get(session_id, user_id=current_user.id)
        return interviewer.to_session_response(session)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def delete_interview_session(
    session_id: str,
    current_user: UserRecord = Depends(get_current_user),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
) -> dict[str, Any]:
    """Delete an interview session belonging to the authenticated user."""
    try:
        await interviewer.store.get(session_id, user_id=current_user.id)
        await interviewer.store.delete(session_id, user_id=current_user.id)
        return {"deleted": True, "session_id": session_id}
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{session_id}/compile", response_model=CompileResponse)
async def compile_from_interview(
    session_id: str,
    current_user: UserRecord = Depends(get_current_user),
    interviewer: PromptInterviewer = Depends(get_prompt_interviewer),
    template_selector: TemplateSelector = Depends(get_template_selector),
    prompt_generator: PromptGenerator = Depends(get_prompt_generator),
    prompt_refiner: PromptRefiner = Depends(get_prompt_refiner),
    compilation_repo: CompilationRepository = Depends(get_compilation_repository),
    project_service: ProjectMemoryService = Depends(get_project_service),
    agent_formatter: AgentFormatter = Depends(get_agent_formatter),
    knowledge_retriever: KnowledgeRetriever = Depends(get_knowledge_retriever),
) -> CompileResponse:
    """Compile the final prompt using the clarified requirements from an interview session.
    
    Orchestration:
    1. Validates session is in 'ready' status for current user.
    2. Loads project context if session is associated with a project_id.
    3. Runs finalized RequirementAnalysis through the existing compilation pipeline:
       TemplateSelector -> PromptGenerator -> PromptCritic/PromptRefiner -> CompileResponse.
    4. Updates session status to 'compiled'.
    5. Returns CompileResponse.
    """
    try:
        session = await interviewer.store.get(session_id, user_id=current_user.id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    analysis = session.current_analysis
    project_context = None
    retrieval_res = RetrievalExecutionResult()

    if session.project_id:
        try:
            project_context = await project_service.get_project_context_async(session.project_id, user_id=current_user.id)
        except ProjectNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project '{session.project_id}' not found.",
            ) from exc

    try:
        # Step 1.5: Semantic Knowledge Retrieval
        retrieval_res = await knowledge_retriever.retrieve_async(
            project_id=session.project_id,
            analysis=analysis,
            raw_input=session.original_input,
            enabled=getattr(session, "enable_knowledge_retrieval", True),
        )
        retrieved_knowledge = retrieval_res.items

        template = template_selector.select(analysis.task_type)
        gen_kwargs: dict[str, Any] = {}
        if project_context is not None:
            gen_kwargs["project_context"] = project_context
        if retrieved_knowledge:
            gen_kwargs["retrieved_knowledge"] = retrieved_knowledge

        initial_generation = await prompt_generator.generate_async(
            analysis,
            **gen_kwargs,
        )

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
    except UnsupportedTaskTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
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
    except (OllamaHTTPError, OllamaResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ollama upstream error: {exc}",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error compiling interview prompt: {exc}",
        ) from exc

    # Mark session as compiled
    session.status = "compiled"
    await interviewer.store.save(session)

    # Map to CompileResponse
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

    # Format according to session's target_agent
    target_agent = getattr(session, "target_agent", "generic") or "generic"
    formatted_prompt = agent_formatter.format_prompt(
        compiled_prompt=refinement_result.final_prompt,
        target_agent=target_agent,
        analysis=analysis,
        project_context=project_context,
        retrieved_knowledge=retrieval_res.items,
    )

    # Persist compilation record
    try:
        await asyncio.to_thread(
            compilation_repo.save,
            input_text=session.original_input,
            compiled_prompt=formatted_prompt,
            task_type=refinement_result.task_type,
            template_name=refinement_result.template_name,
            requirements_summary=requirements_summary.model_dump(),
            validation_summary=validation_summary.model_dump(),
            refinement_attempts=refinement_result.refinement_attempts,
            interview_session_id=session.session_id,
            project_id=session.project_id,
            target_agent=target_agent,
            knowledge_references=[r.model_dump() for r in retrieval_res.references] if retrieval_res.references else None,
            user_id=current_user.id,
        )
    except Exception:
        pass

    return CompileResponse(
        input=session.original_input,
        result=formatted_prompt,
        task_type=refinement_result.task_type,
        template_name=refinement_result.template_name,
        requirements=requirements_summary,
        validation=validation_summary,
        refinement_attempts=refinement_result.refinement_attempts,
        interview_session_id=session.session_id,
        project_id=session.project_id,
        target_agent=target_agent,
        knowledge_references=retrieval_res.references,
        knowledge_telemetry=retrieval_res.telemetry,
    )
