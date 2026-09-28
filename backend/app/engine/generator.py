"""Prompt generation layer for Prompt Compiler."""

import asyncio
import concurrent.futures
import re
from pydantic import BaseModel, Field

from app.ai.ollama import OllamaClient
from app.config import settings
from app.engine.critic import ValidationResult
from app.engine.requirements import RequirementAnalysis
from app.schemas.knowledge import KnowledgeContextItem
from app.schemas.project import ProjectContext
from app.templates.base import PromptTemplate
from app.templates.selector import TemplateSelector


class PromptGenerationContext(BaseModel):
    """Structured internal representation combining requirement analysis and selected template."""

    model_config = {"arbitrary_types_allowed": True}

    requirement_analysis: RequirementAnalysis = Field(
        ...,
        description="Structured requirement analysis produced by the requirement engine.",
    )
    template: PromptTemplate = Field(
        ...,
        description="The selected task-type prompt template.",
    )
    project_context: ProjectContext | None = Field(
        default=None,
        description="Persistent project context including constraints, technologies, coding rules, and metadata.",
    )
    retrieved_knowledge: list[KnowledgeContextItem] = Field(
        default_factory=list,
        description="Retrieved project knowledge chunks from semantic vector search.",
    )


    @property
    def task_type(self) -> str:
        """The canonical task type."""
        return self.requirement_analysis.task_type

    @property
    def template_name(self) -> str:
        """Name of the selected template."""
        return self.template.name

    def format_confirmed_requirements(self) -> str:
        """Format confirmed requirements as bullet points."""
        if not self.requirement_analysis.confirmed_requirements:
            return "- None explicitly stated"
        return "\n".join(f"- {req}" for req in self.requirement_analysis.confirmed_requirements)

    def format_constraints(self) -> str:
        """Format explicit constraints as bullet points."""
        if not self.requirement_analysis.constraints:
            return "- None specified"
        return "\n".join(f"- {c}" for c in self.requirement_analysis.constraints)

    def format_missing_information(self) -> str:
        """Format material missing information and open decisions as bullet points."""
        if not self.requirement_analysis.missing_information:
            return "- None identified"
        return "\n".join(
            f"- {item} (Open Decision: requires developer specification; do not invent a default)"
            for item in self.requirement_analysis.missing_information
        )

    def format_assumptions(self) -> str:
        """Format safe assumptions as bullet points."""
        if not self.requirement_analysis.assumptions:
            return "- None"
        return "\n".join(f"- {a}" for a in self.requirement_analysis.assumptions)

    def format_project_context(self) -> str:
        """Format persistent project context in a clearly separated section."""
        if self.project_context is None:
            return ""
        return self.project_context.to_context_string()

    def format_retrieved_knowledge(self) -> str:
        """Format retrieved project knowledge chunks with provenance metadata."""
        if not self.retrieved_knowledge:
            return ""
        items = []
        for item in self.retrieved_knowledge:
            items.append(
                f"[Source: {item.source_name} | Type: {item.source_type} | Relevance: {item.score:.2f}]\n{item.content.strip()}"
            )
        return "\n\n".join(items)



class PromptGenerationResult(BaseModel):
    """Structured result produced by the prompt generator."""

    final_prompt: str = Field(
        ...,
        description="The compiled, implementation-ready prompt.",
    )
    template_name: str = Field(
        ...,
        description="Name of the prompt template used for generation.",
    )
    task_type: str = Field(
        ...,
        description="The canonical task type.",
    )


GENERATION_INSTRUCTION = """You are the Prompt Compiler Generation Engine.
Transform the provided structured requirement analysis into a clean, actionable, implementation-ready engineering specification prompt for an AI coding agent.

Strict Rules:
1. Preserve all confirmed requirements exactly as stated. Do not drop, alter, or dilute confirmed requirements.
2. Preserve all explicit constraints. Emphasize boundaries and non-negotiables.
3. DO NOT INVENT unconfirmed technical requirements, frameworks, databases, libraries, or deployment platforms (e.g. do NOT inject React, Next.js, Tailwind, Supabase, PostgreSQL, or Vercel unless explicitly listed under Confirmed Requirements or Project Context).
4. Highlight missing information and open decisions clearly in the prompt as unresolved items that must not be blindly assumed.
5. Keep safe assumptions conservative and clearly separated from confirmed facts.
6. Follow the required section structure provided in the template layout.
7. Tone and Style: Serious, precise, and implementation-oriented. Avoid conversational fluff, introductory greetings, concluding remarks, emojis, and marketing language.
8. Do NOT mention internal Prompt Compiler components, RequirementEngine, Ollama, or that another AI generated this prompt.
9. Project Context vs Current User Requirements: If Project Context is provided, treat it as the existing application baseline (technologies, constraints, coding rules, architecture). Current explicit user requirements have HIGHEST priority and override any conflicting project baseline. Maintain clear separation between existing project context and new user requirements.
10. Retrieved Project Knowledge vs Current User Requirements: If Retrieved Project Knowledge is provided, treat it as contextual background evidence from project documentation/code. Explicit current user requirements have HIGHEST priority and override retrieved knowledge in case of conflict. Do not substitute or overwrite what the user explicitly requested with historical documentation.
11. Output ONLY the compiled prompt. Do not output commentary or meta-analysis."""


REFINEMENT_INSTRUCTION = """You are the Prompt Compiler Refinement Engine.
Your task is to refine and correct a previously generated prompt based on quality and fidelity validation feedback.
Transform the previous draft into a corrected, high-fidelity, implementation-ready prompt for an AI coding agent.

Strict Refinement Rules:
1. Address all identified validation errors and warnings:
   - If requirements are missing, reinstate them explicitly.
   - If constraints are violated or omitted, strictly enforce them.
   - If unconfirmed technologies or frameworks were invented, REMOVE them immediately and keep the decision open.
   - If missing information was silently resolved, declare it explicitly as an Open Decision.
   - If structural sections are missing, restore the complete required structure.
2. PRESERVE all confirmed user requirements and explicit constraints. Do not drop previously preserved requirements.
3. NEVER INVENT unconfirmed technical requirements, frameworks, databases, libraries, or deployment platforms.
4. Missing Information must remain declared as Open Decisions that require developer input.
5. Preserve the canonical task type and domain. Do not morph the task into a different task type.
6. Project Context vs Current User Requirements: If Project Context is provided, treat it as the established application baseline. Explicit user requirements have HIGHEST priority in case of any conflict.
7. Retrieved Project Knowledge: Maintain clear distinction between explicit user requirements and retrieved contextual documentation. Explicit user requirements always take precedence.
8. Tone and Style: Serious, precise, and implementation-oriented. Avoid conversational fluff, introductory greetings, concluding remarks, emojis, and meta-commentary.
9. Output ONLY the refined prompt text. Do not explain your changes."""



def _sanitize_output(raw_text: str) -> str:
    """Sanitize LLM output by removing thinking tags and expected outer markdown wrappers."""
    # 1. Remove thinking blocks if present (<think>...</think>)
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # 2. Unwrap outer markdown fences if the model wrapped the entire output in ```markdown ... ```
    fence_match = re.match(r"^```(?:markdown)?\s*\n(.*?)\n```$", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # 3. Strip leading conversational preambles
    cleaned = re.sub(
        r"^(?:Here is(?: the)?(?: compiled)? prompt:?\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    return cleaned


class PromptGenerator:
    """Generation layer that transforms RequirementAnalysis into an implementation-ready prompt."""

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        template_selector: TemplateSelector | None = None,
    ) -> None:
        if ollama_client is None:
            timeout = max(settings.OLLAMA_TIMEOUT, 360.0)
            self.ollama_client = OllamaClient(timeout=timeout)
        else:
            self.ollama_client = ollama_client

        self.template_selector = template_selector or TemplateSelector()

    def create_context(
        self,
        analysis: RequirementAnalysis,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> PromptGenerationContext:
        """Create a PromptGenerationContext by deterministically selecting the template for the analysis.

        Args:
            analysis: Validated RequirementAnalysis instance.
            project_context: Optional persistent ProjectContext instance.
            retrieved_knowledge: Optional list of retrieved knowledge context items.

        Returns:
            PromptGenerationContext containing the analysis, matched template, project_context, and retrieved_knowledge.

        Raises:
            UnsupportedTaskTypeError: If analysis.task_type is not supported.
        """
        template = self.template_selector.select(analysis.task_type)
        return PromptGenerationContext(
            requirement_analysis=analysis,
            template=template,
            project_context=project_context,
            retrieved_knowledge=retrieved_knowledge or [],
        )

    def build_generation_prompt(self, context: PromptGenerationContext) -> str:
        """Construct the prompt sent to Ollama for prompt generation."""
        analysis = context.requirement_analysis
        template = context.template

        project_section = ""
        if context.project_context is not None:
            project_section = f"""=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===
Note: Explicit Current User Requirements below take precedence over Project Context in case of conflict.

{context.format_project_context()}

"""

        knowledge_section = ""
        if context.retrieved_knowledge:
            knowledge_section = f"""=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===
Note: The following excerpts are background documentation/code evidence from the project repository.
Explicit Current User Requirements take precedence over Retrieved Knowledge. Do not treat retrieved knowledge as an affirmative user instruction if the user requested something different.

{context.format_retrieved_knowledge()}

"""

        return f"""{GENERATION_INSTRUCTION}

{project_section}{knowledge_section}=== INPUT REQUIREMENT ANALYSIS ===
Intent: {analysis.intent}
Task Type: {analysis.task_type}
Domain: {analysis.domain}

Confirmed Requirements:
{context.format_confirmed_requirements()}

Constraints:
{context.format_constraints()}

Missing Information / Open Decisions:
{context.format_missing_information()}

Safe Assumptions:
{context.format_assumptions()}

=== REQUIRED TEMPLATE STRUCTURE ===
{template.get_structure_guidance()}

COMPILED PROMPT:"""

    def build_refinement_prompt(
        self,
        context: PromptGenerationContext,
        previous_prompt: str,
        validation_result: ValidationResult,
    ) -> str:
        """Construct the prompt sent to Ollama for iterative prompt refinement."""
        analysis = context.requirement_analysis
        template = context.template

        project_section = ""
        if context.project_context is not None:
            project_section = f"""=== PROJECT CONTEXT (EXISTING APPLICATION BASELINE) ===
Note: Explicit Current User Requirements below take precedence over Project Context in case of conflict.

{context.format_project_context()}

"""

        knowledge_section = ""
        if context.retrieved_knowledge:
            knowledge_section = f"""=== RETRIEVED PROJECT KNOWLEDGE (CONTEXTUAL EVIDENCE) ===
Note: The following excerpts are background documentation/code evidence from the project repository.
Explicit Current User Requirements take precedence over Retrieved Knowledge. Do not treat retrieved knowledge as an affirmative user instruction if the user requested something different.

{context.format_retrieved_knowledge()}

"""


        issues_text = "\n".join(
            f"- [{issue.severity.upper()}] {issue.category}: {issue.message}"
            for issue in validation_result.issues
        ) if validation_result.issues else "- None"

        missing_reqs_text = "\n".join(
            f"- {req}" for req in validation_result.missing_requirements
        ) if validation_result.missing_requirements else "- None"

        violated_constraints_text = "\n".join(
            f"- {c}" for c in validation_result.violated_constraints
        ) if validation_result.violated_constraints else "- None"

        invented_text = "\n".join(
            f"- {inv}" for inv in validation_result.invented_requirements
        ) if validation_result.invented_requirements else "- None"

        return f"""{REFINEMENT_INSTRUCTION}

{project_section}=== INPUT REQUIREMENT ANALYSIS ===
Intent: {analysis.intent}
Task Type: {analysis.task_type}
Domain: {analysis.domain}

Confirmed Requirements:
{context.format_confirmed_requirements()}

Constraints:
{context.format_constraints()}

Missing Information / Open Decisions:
{context.format_missing_information()}

Safe Assumptions:
{context.format_assumptions()}

=== VALIDATION FEEDBACK TO FIX ===
Validation Issues:
{issues_text}

Missing Requirements that MUST be added:
{missing_reqs_text}

Constraints that MUST be enforced:
{violated_constraints_text}

Invented Technologies that MUST be REMOVED:
{invented_text}

=== REQUIRED TEMPLATE STRUCTURE ===
{template.get_structure_guidance()}

=== PREVIOUS DRAFT (TO BE REFINED) ===
{previous_prompt}

REFINED COMPILED PROMPT:"""

    async def generate_async(
        self,
        analysis: RequirementAnalysis,
        previous_prompt: str | None = None,
        validation_result: ValidationResult | None = None,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> PromptGenerationResult:
        """Asynchronously compile RequirementAnalysis into an implementation-ready PromptGenerationResult.

        If previous_prompt and validation_result are supplied, performs targeted refinement.

        Args:
            analysis: Validated RequirementAnalysis instance.
            previous_prompt: Optional previous draft to refine.
            validation_result: Optional validation findings to correct.
            project_context: Optional persistent ProjectContext instance.
            retrieved_knowledge: Optional list of retrieved knowledge context items.

        Returns:
            PromptGenerationResult with the final prompt, template name, and task type.

        Raises:
            UnsupportedTaskTypeError: If analysis.task_type is not recognized.
            OllamaError subclasses: If connection, timeout, or HTTP errors occur during model invocation.
        """
        if previous_prompt is not None and validation_result is not None:
            return await self.refine_async(
                analysis,
                previous_prompt,
                validation_result,
                project_context=project_context,
                retrieved_knowledge=retrieved_knowledge,
            )

        context = self.create_context(
            analysis,
            project_context=project_context,
            retrieved_knowledge=retrieved_knowledge,
        )
        prompt = self.build_generation_prompt(context)
        raw_response = await self.ollama_client.generate(prompt)
        final_prompt = _sanitize_output(raw_response)

        return PromptGenerationResult(
            final_prompt=final_prompt,
            template_name=context.template_name,
            task_type=context.task_type,
        )

    def generate(
        self,
        analysis: RequirementAnalysis,
        previous_prompt: str | None = None,
        validation_result: ValidationResult | None = None,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> PromptGenerationResult:
        """Synchronously compile RequirementAnalysis into an implementation-ready PromptGenerationResult."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run,
                    self.generate_async(
                        analysis,
                        previous_prompt,
                        validation_result,
                        project_context=project_context,
                        retrieved_knowledge=retrieved_knowledge,
                    ),
                ).result()
        else:
            return asyncio.run(
                self.generate_async(
                    analysis,
                    previous_prompt,
                    validation_result,
                    project_context=project_context,
                    retrieved_knowledge=retrieved_knowledge,
                )
            )

    async def refine_async(
        self,
        analysis: RequirementAnalysis,
        previous_prompt: str,
        validation_result: ValidationResult,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> PromptGenerationResult:
        """Asynchronously refine a prompt based on validation feedback.

        Args:
            analysis: Validated RequirementAnalysis instance.
            previous_prompt: The previous prompt draft that needs refinement.
            validation_result: The validation result detailing issues to correct.
            project_context: Optional persistent ProjectContext instance.
            retrieved_knowledge: Optional list of retrieved knowledge context items.

        Returns:
            PromptGenerationResult with the refined prompt, template name, and task type.

        Raises:
            UnsupportedTaskTypeError: If analysis.task_type is not recognized.
            OllamaError subclasses: If connection, timeout, or HTTP errors occur during model invocation.
        """
        context = self.create_context(
            analysis,
            project_context=project_context,
            retrieved_knowledge=retrieved_knowledge,
        )
        prompt = self.build_refinement_prompt(context, previous_prompt, validation_result)
        raw_response = await self.ollama_client.generate(prompt)
        final_prompt = _sanitize_output(raw_response)

        return PromptGenerationResult(
            final_prompt=final_prompt,
            template_name=context.template_name,
            task_type=context.task_type,
        )

    def refine(
        self,
        analysis: RequirementAnalysis,
        previous_prompt: str,
        validation_result: ValidationResult,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> PromptGenerationResult:
        """Synchronously refine a prompt based on validation feedback."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run,
                    self.refine_async(
                        analysis,
                        previous_prompt,
                        validation_result,
                        project_context=project_context,
                        retrieved_knowledge=retrieved_knowledge,
                    ),
                ).result()
        else:
            return asyncio.run(
                self.refine_async(
                    analysis,
                    previous_prompt,
                    validation_result,
                    project_context=project_context,
                    retrieved_knowledge=retrieved_knowledge,
                )
            )


