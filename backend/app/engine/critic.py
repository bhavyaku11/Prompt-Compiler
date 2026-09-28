"""Prompt Critic and Validation Engine for Prompt Compiler."""

import asyncio
import concurrent.futures
import re
from pydantic import BaseModel, Field, ValidationError

from app.ai.ollama import OllamaClient, OllamaError
from app.config import settings
from app.engine.requirements import RequirementAnalysis, _parse_llm_json
from app.schemas.knowledge import KnowledgeContextItem
from app.schemas.project import ProjectContext



class ValidationIssue(BaseModel):
    """Represents a specific validation finding, omission, or defect."""

    category: str = Field(
        ...,
        description=(
            "Category of the issue: requirement_missing, constraint_missing, invented_requirement, "
            "missing_information_lost, task_type_mismatch, structural_problem, ambiguity, quality_problem."
        ),
    )
    severity: str = Field(
        ...,
        description="Severity level: error, warning, info.",
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the detected issue.",
    )


class ValidationResult(BaseModel):
    """Comprehensive validation outcome evaluating prompt fidelity, constraints, and completeness."""

    overall_valid: bool = Field(
        ...,
        description="True if no error-severity issues were detected; False otherwise.",
    )
    issues: list[ValidationIssue] = Field(
        default_factory=list,
        description="Itemized list of all detected validation issues.",
    )
    preserved_requirements: list[str] = Field(
        default_factory=list,
        description="Confirmed requirements verified to be preserved in the generated prompt.",
    )
    missing_requirements: list[str] = Field(
        default_factory=list,
        description="Confirmed requirements omitted from the generated prompt.",
    )
    violated_constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints omitted or violated in the generated prompt.",
    )
    invented_requirements: list[str] = Field(
        default_factory=list,
        description="Technical requirements or tools introduced without user confirmation.",
    )
    missing_information_preserved: bool = Field(
        default=True,
        description="Whether missing information items remain exposed as open decisions.",
    )
    task_type_valid: bool = Field(
        default=True,
        description="Whether the prompt is appropriate for the identified task type.",
    )
    structure_valid: bool = Field(
        default=True,
        description="Whether the prompt has sufficient structural sections and length.",
    )

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Convenience property returning all warning-severity issues."""
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def errors(self) -> list[ValidationIssue]:
        """Convenience property returning all error-severity issues."""
        return [issue for issue in self.issues if issue.severity == "error"]


class LLMCritiqueResponse(BaseModel):
    """Structured response schema returned by the LLM semantic critic."""

    logical_inconsistencies: list[str] = Field(
        default_factory=list,
        description="Contradictions or conflicting directives inside the prompt.",
    )
    unclear_instructions: list[str] = Field(
        default_factory=list,
        description="Vague or ambiguous directives.",
    )
    unresolved_decisions_flagged: list[str] = Field(
        default_factory=list,
        description="Decisions that were assumed rather than left open.",
    )
    invented_tech_detected: list[str] = Field(
        default_factory=list,
        description="Suspicious or unconfirmed technologies introduced.",
    )
    is_actionable: bool = Field(
        default=True,
        description="Whether the prompt is implementation-ready for an engineering agent.",
    )


# Catalog of common technologies checked during hallucination/invented tech detection
KNOWN_TECH_CATALOG = [
    "react",
    "next.js",
    "nextjs",
    "vue",
    "angular",
    "svelte",
    "tailwind",
    "tailwind css",
    "bootstrap",
    "supabase",
    "postgresql",
    "postgres",
    "mongodb",
    "sqlite",
    "mysql",
    "firebase",
    "vercel",
    "aws",
    "docker",
]

# Patterns indicating a technology mention is a prohibition or open decision, not an implementation mandate
PROHIBITION_PATTERNS = [
    r"do\s+not\s+(?:use|assume|include|rely|choose|pick|add)",
    r"don'?t\s+(?:use|assume|include|rely|choose|pick|add)",
    r"must\s+not\s+(?:use|assume|include)",
    r"without\s+",
    r"no\s+",
    r"never\s+(?:use|assume)",
    r"not\s+assume",
    r"avoid\s+",
    r"open\s+decision",
    r"unresolved",
    r"unspecified",
    r"unless\s+explicitly",
    r"unless\s+confirmed",
    r"tbd",
    r"to\s+be\s+determined",
    r"determine\s+(?:the|whether)",
]


CRITIC_SYSTEM_INSTRUCTION = """You are the Prompt Compiler Quality Review Engine.
Your job is to inspect a generated prompt against the original structured RequirementAnalysis and deterministic validation findings.

Strict Evaluation Tasks:
1. Identify any subtle contradictions, logical conflicts, or mutually exclusive instructions in the prompt.
2. Identify ambiguous or vague instructions that an AI coding agent cannot act on without clarification.
3. Check if any missing information / open decisions were silently resolved by assuming a specific technical choice.
4. Assess whether the prompt is actionable, implementation-ready, and coherent for the requested task type.
5. DO NOT rewrite the prompt.
6. DO NOT generate replacement text.
7. Return ONLY a valid JSON object matching the required schema:
{
  "logical_inconsistencies": ["<inconsistency 1>"],
  "unclear_instructions": ["<unclear instruction 1>"],
  "unresolved_decisions_flagged": ["<silently resolved decision>"],
  "invented_tech_detected": ["<invented tech>"],
  "is_actionable": true
}"""


class PromptCritic:
    """Quality control engine that evaluates generated prompts against RequirementAnalysis."""

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        if ollama_client is None:
            timeout = max(settings.OLLAMA_TIMEOUT, 360.0)
            self.ollama_client = OllamaClient(timeout=timeout)
        else:
            self.ollama_client = ollama_client

    def validate_deterministic(
        self,
        analysis: RequirementAnalysis,
        generated_prompt: str,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> ValidationResult:
        """Run pure programmatic validation checks on the prompt against RequirementAnalysis.

        Args:
            analysis: Validated RequirementAnalysis instance.
            generated_prompt: The generated prompt text to evaluate.
            project_context: Optional persistent ProjectContext instance.
            retrieved_knowledge: Optional list of retrieved knowledge items.

        Returns:
            ValidationResult containing all deterministic findings.
        """
        issues: list[ValidationIssue] = []

        # 1. Structural Validation
        structure_valid, struct_issues = self._validate_structure(generated_prompt)
        issues.extend(struct_issues)

        # If completely empty or whitespace, return immediately with invalid status
        if not structure_valid and (not generated_prompt or not generated_prompt.strip()):
            return ValidationResult(
                overall_valid=False,
                issues=issues,
                preserved_requirements=[],
                missing_requirements=analysis.confirmed_requirements.copy(),
                violated_constraints=analysis.constraints.copy(),
                invented_requirements=[],
                missing_information_preserved=False,
                task_type_valid=False,
                structure_valid=False,
            )

        # 2. Confirmed Requirements Validation
        preserved_reqs, missing_reqs, req_issues = self._validate_confirmed_requirements(
            analysis, generated_prompt
        )
        issues.extend(req_issues)

        # 3. Constraints Validation
        violated_constraints, constraint_issues = self._validate_constraints(
            analysis, generated_prompt
        )
        issues.extend(constraint_issues)

        # 4. Missing Information / Open Decisions Validation
        missing_info_preserved, missing_info_issues = self._validate_missing_information(
            analysis, generated_prompt
        )
        issues.extend(missing_info_issues)

        # 5. Invented Technology Detection
        invented_reqs, invented_issues = self._detect_invented_technologies(
            analysis,
            generated_prompt,
            project_context=project_context,
            retrieved_knowledge=retrieved_knowledge,
        )
        issues.extend(invented_issues)


        # 6. Task Type Validation
        task_type_valid, task_type_issues = self._validate_task_type(
            analysis, generated_prompt
        )
        issues.extend(task_type_issues)

        overall_valid = not any(issue.severity == "error" for issue in issues)

        return ValidationResult(
            overall_valid=overall_valid,
            issues=issues,
            preserved_requirements=preserved_reqs,
            missing_requirements=missing_reqs,
            violated_constraints=violated_constraints,
            invented_requirements=invented_reqs,
            missing_information_preserved=missing_info_preserved,
            task_type_valid=task_type_valid,
            structure_valid=structure_valid,
        )

    async def validate_async(
        self,
        analysis: RequirementAnalysis,
        generated_prompt: str,
        use_llm: bool = False,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> ValidationResult:
        """Asynchronously validate a prompt against RequirementAnalysis, optionally combining with LLM review.

        Args:
            analysis: Validated RequirementAnalysis instance.
            generated_prompt: The prompt text to evaluate.
            use_llm: Whether to invoke the LLM for semantic critique.
            project_context: Optional persistent ProjectContext instance.
            retrieved_knowledge: Optional list of retrieved knowledge items.

        Returns:
            Combined ValidationResult.
        """
        deterministic_result = self.validate_deterministic(
            analysis,
            generated_prompt,
            project_context=project_context,
            retrieved_knowledge=retrieved_knowledge,
        )

        # If LLM evaluation is not requested or prompt is structurally invalid, return deterministic findings
        if not use_llm or not deterministic_result.structure_valid:
            return deterministic_result

        # Run LLM Semantic Review
        try:
            llm_result = await self._run_llm_critique(analysis, generated_prompt, deterministic_result)
            return self._merge_results(deterministic_result, llm_result)
        except (OllamaError, Exception) as exc:
            # Propagate OllamaError subclasses directly per project conventions
            if isinstance(exc, OllamaError):
                raise
            # Record parsing or extraction exceptions as issues without masking deterministic checks
            merged_issues = list(deterministic_result.issues)
            merged_issues.append(
                ValidationIssue(
                    category="quality_problem",
                    severity="warning",
                    message=f"LLM semantic critique failed: {exc}",
                )
            )
            return ValidationResult(
                overall_valid=deterministic_result.overall_valid,
                issues=merged_issues,
                preserved_requirements=deterministic_result.preserved_requirements,
                missing_requirements=deterministic_result.missing_requirements,
                violated_constraints=deterministic_result.violated_constraints,
                invented_requirements=deterministic_result.invented_requirements,
                missing_information_preserved=deterministic_result.missing_information_preserved,
                task_type_valid=deterministic_result.task_type_valid,
                structure_valid=deterministic_result.structure_valid,
            )

    def validate(
        self,
        analysis: RequirementAnalysis,
        generated_prompt: str,
        use_llm: bool = False,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> ValidationResult:
        """Synchronously validate a prompt against RequirementAnalysis."""
        if not use_llm:
            return self.validate_deterministic(
                analysis,
                generated_prompt,
                project_context=project_context,
                retrieved_knowledge=retrieved_knowledge,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run,
                    self.validate_async(
                        analysis,
                        generated_prompt,
                        use_llm=True,
                        project_context=project_context,
                        retrieved_knowledge=retrieved_knowledge,
                    ),
                ).result()
        else:
            return asyncio.run(
                self.validate_async(
                    analysis,
                    generated_prompt,
                    use_llm=True,
                    project_context=project_context,
                    retrieved_knowledge=retrieved_knowledge,
                )
            )


    def _validate_structure(self, prompt: str) -> tuple[bool, list[ValidationIssue]]:
        """Check basic structural requirements (length, presence of content)."""
        issues: list[ValidationIssue] = []

        if not prompt or not prompt.strip():
            issues.append(
                ValidationIssue(
                    category="structural_problem",
                    severity="error",
                    message="Generated prompt is empty or contains only whitespace.",
                )
            )
            return False, issues

        cleaned = prompt.strip()
        if len(cleaned) < 40:
            issues.append(
                ValidationIssue(
                    category="structural_problem",
                    severity="error",
                    message=f"Generated prompt is too short ({len(cleaned)} characters) to provide an implementation-ready specification.",
                )
            )
            return False, issues

        return True, issues

    def _validate_confirmed_requirements(
        self,
        analysis: RequirementAnalysis,
        prompt: str,
    ) -> tuple[list[str], list[str], list[ValidationIssue]]:
        """Verify each confirmed requirement is represented in the prompt."""
        preserved: list[str] = []
        missing: list[str] = []
        issues: list[ValidationIssue] = []

        prompt_lower = prompt.lower()

        for req in analysis.confirmed_requirements:
            req_clean = req.strip()
            if not req_clean:
                continue

            # Check if the requirement phrase or normalized tokens appear in prompt
            req_lower = req_clean.lower()
            if req_lower in prompt_lower:
                preserved.append(req_clean)
            else:
                # Check for word-level presence if phrase is multi-word
                tokens = [t for t in re.split(r"\W+", req_lower) if len(t) > 2]
                if tokens and all(t in prompt_lower for t in tokens):
                    preserved.append(req_clean)
                else:
                    missing.append(req_clean)
                    issues.append(
                        ValidationIssue(
                            category="requirement_missing",
                            severity="error",
                            message=f"Confirmed requirement '{req_clean}' is missing from the generated prompt.",
                        )
                    )

        return preserved, missing, issues

    def _validate_constraints(
        self,
        analysis: RequirementAnalysis,
        prompt: str,
    ) -> tuple[list[str], list[ValidationIssue]]:
        """Verify explicit constraints are represented in the prompt."""
        violated: list[str] = []
        issues: list[ValidationIssue] = []

        prompt_lower = prompt.lower()

        for constraint in analysis.constraints:
            c_clean = constraint.strip()
            if not c_clean:
                continue

            c_lower = c_clean.lower()
            # If the exact constraint substring appears
            if c_lower in prompt_lower:
                continue

            # Extract key nouns/terms from constraint (e.g. 'backend', 'vanilla css', 'database')
            key_terms = [
                term for term in re.split(r"\W+", c_lower)
                if len(term) > 3 and term not in ["must", "only", "using", "with", "without", "should"]
            ]

            # If key terms are missing or no negative/invariant boundary exists
            has_terms = any(t in prompt_lower for t in key_terms) if key_terms else False
            has_boundary_words = any(
                w in prompt_lower for w in ["not", "never", "constraint", "invariant", "do not", "don't", "preserve", "leave", "keep"]
            )

            if not (has_terms and has_boundary_words):
                violated.append(c_clean)
                issues.append(
                    ValidationIssue(
                        category="constraint_missing",
                        severity="error",
                        message=f"Explicit constraint '{c_clean}' is omitted or unrepresented in the prompt.",
                    )
                )

        return violated, issues

    def _validate_missing_information(
        self,
        analysis: RequirementAnalysis,
        prompt: str,
    ) -> tuple[bool, list[ValidationIssue]]:
        """Verify that missing information items are preserved as open decisions."""
        issues: list[ValidationIssue] = []
        all_preserved = True
        prompt_lower = prompt.lower()

        for item in analysis.missing_information:
            item_clean = item.strip()
            if not item_clean:
                continue

            # Extract core tokens (e.g., 'hosting', 'styling', 'framework')
            tokens = [t for t in re.split(r"\W+", item_clean.lower()) if len(t) > 3]

            # Check if mentioned in prompt
            mentioned = any(t in prompt_lower for t in tokens)

            if not mentioned:
                all_preserved = False
                issues.append(
                    ValidationIssue(
                        category="missing_information_lost",
                        severity="warning",
                        message=f"Missing information item '{item_clean}' was omitted and not exposed as an open decision.",
                    )
                )

        return all_preserved, issues

    def _detect_invented_technologies(
        self,
        analysis: RequirementAnalysis,
        prompt: str,
        project_context: ProjectContext | None = None,
        retrieved_knowledge: list[KnowledgeContextItem] | None = None,
    ) -> tuple[list[str], list[ValidationIssue]]:
        """Identify unconfirmed technologies introduced into the prompt as affirmative requirements."""
        invented: list[str] = []
        issues: list[ValidationIssue] = []


        project_confirmed_text = ""
        if project_context is not None:
            project_confirmed_text = (
                " "
                + " ".join(project_context.technologies)
                + " "
                + " ".join(project_context.active_constraints)
                + " "
                + " ".join(project_context.coding_rules)
                + " "
                + (project_context.project.description if project_context.project else "")
            ).lower()

        confirmed_text = (
            " ".join(analysis.confirmed_requirements)
            + " "
            + analysis.intent
            + " "
            + " ".join(analysis.constraints)
            + project_confirmed_text
        ).lower()

        # Split prompt into individual lines for contextual analysis
        lines = [line.strip() for line in prompt.splitlines() if line.strip()]

        for tech in KNOWN_TECH_CATALOG:
            # If the tech was in confirmed requirements or intent, it's not invented
            if tech in confirmed_text:
                continue

            tech_pattern = rf"\b{re.escape(tech)}\b"
            if not re.search(tech_pattern, prompt, flags=re.IGNORECASE):
                continue

            # Check lines where the tech is mentioned
            affirmative_occurrences = 0
            for line in lines:
                if re.search(tech_pattern, line, flags=re.IGNORECASE):
                    line_lower = line.lower()
                    # Check if line contains prohibition or open decision phrasing
                    is_prohibition = any(
                        re.search(pat, line_lower, flags=re.IGNORECASE) for pat in PROHIBITION_PATTERNS
                    )
                    # Check if line is part of retrieved knowledge context or citation
                    is_context_evidence = (
                        "source:" in line_lower
                        or "retrieved" in line_lower
                        or "contextual evidence" in line_lower
                        or "existing documentation" in line_lower
                        or line.strip().startswith("[")
                    )
                    if not is_prohibition and not is_context_evidence:
                        affirmative_occurrences += 1

            if affirmative_occurrences > 0:

                invented.append(tech)
                issues.append(
                    ValidationIssue(
                        category="invented_requirement",
                        severity="error",
                        message=f"Detected unconfirmed technology '{tech}' introduced as an implementation requirement.",
                    )
                )

        return invented, issues

    def _validate_task_type(
        self,
        analysis: RequirementAnalysis,
        prompt: str,
    ) -> tuple[bool, list[ValidationIssue]]:
        """Verify the generated prompt aligns with the expected task type."""
        issues: list[ValidationIssue] = []
        task_type = analysis.task_type.lower()
        prompt_lower = prompt.lower()

        # Task type mismatch heuristics
        if task_type == "debug":
            has_debug_vocab = any(
                w in prompt_lower
                for w in ["debug", "fix", "bug", "error", "issue", "crash", "problem", "observed", "expected", "symptom"]
            )
            # If prompt has zero debugging vocab and only describes building from scratch
            if not has_debug_vocab:
                issues.append(
                    ValidationIssue(
                        category="task_type_mismatch",
                        severity="warning",
                        message="Prompt lacks diagnostic or debugging context for a 'debug' task type.",
                    )
                )
                return False, issues

        elif task_type == "modify":
            has_modify_vocab = any(
                w in prompt_lower
                for w in ["modify", "change", "update", "refactor", "existing", "preserve", "invariants", "migration"]
            )
            if not has_modify_vocab:
                issues.append(
                    ValidationIssue(
                        category="task_type_mismatch",
                        severity="warning",
                        message="Prompt lacks existing system or modification context for a 'modify' task type.",
                    )
                )
                return False, issues

        return True, issues

    def _build_llm_critique_prompt(
        self,
        analysis: RequirementAnalysis,
        generated_prompt: str,
        deterministic_result: ValidationResult,
    ) -> str:
        """Construct the prompt sent to Ollama for semantic critique."""
        return f"""{CRITIC_SYSTEM_INSTRUCTION}

=== ORIGINAL REQUIREMENT ANALYSIS ===
Intent: {analysis.intent}
Task Type: {analysis.task_type}
Domain: {analysis.domain}
Confirmed Requirements: {analysis.confirmed_requirements}
Constraints: {analysis.constraints}
Missing Information / Open Decisions: {analysis.missing_information}
Assumptions: {analysis.assumptions}

=== DETERMINISTIC VALIDATION FINDINGS ===
Overall Valid: {deterministic_result.overall_valid}
Preserved Requirements: {deterministic_result.preserved_requirements}
Missing Requirements: {deterministic_result.missing_requirements}
Violated Constraints: {deterministic_result.violated_constraints}
Invented Requirements: {deterministic_result.invented_requirements}

=== GENERATED PROMPT TO EVALUATE ===
\"\"\"{generated_prompt}\"\"\"

JSON:"""

    async def _run_llm_critique(
        self,
        analysis: RequirementAnalysis,
        generated_prompt: str,
        deterministic_result: ValidationResult,
    ) -> LLMCritiqueResponse:
        """Invoke Ollama for semantic critique and parse the structured output."""
        prompt = self._build_llm_critique_prompt(analysis, generated_prompt, deterministic_result)
        raw_text = await self.ollama_client.generate(prompt)
        parsed_dict = _parse_llm_json(raw_text)

        try:
            return LLMCritiqueResponse.model_validate(parsed_dict)
        except ValidationError as exc:
            raise ValueError(f"LLM critic output failed schema validation: {exc}") from exc

    def _merge_results(
        self,
        deterministic: ValidationResult,
        llm: LLMCritiqueResponse,
    ) -> ValidationResult:
        """Merge deterministic validation findings with LLM semantic critique findings."""
        merged_issues = list(deterministic.issues)
        invented_reqs = list(deterministic.invented_requirements)

        # 1. Add LLM logical inconsistencies as warnings
        for item in llm.logical_inconsistencies:
            merged_issues.append(
                ValidationIssue(
                    category="ambiguity",
                    severity="warning",
                    message=f"Logical inconsistency detected: {item}",
                )
            )

        # 2. Add LLM unclear instructions as info
        for item in llm.unclear_instructions:
            merged_issues.append(
                ValidationIssue(
                    category="quality_problem",
                    severity="info",
                    message=f"Unclear instruction noted: {item}",
                )
            )

        # 3. Add LLM unresolved decisions flagged as warnings
        for item in llm.unresolved_decisions_flagged:
            merged_issues.append(
                ValidationIssue(
                    category="missing_information_lost",
                    severity="warning",
                    message=f"Decision was assumed rather than left open: {item}",
                )
            )

        # 4. Add newly detected invented tech from LLM as errors
        for tech in llm.invented_tech_detected:
            if tech.lower() not in [t.lower() for t in invented_reqs]:
                invented_reqs.append(tech)
                merged_issues.append(
                    ValidationIssue(
                        category="invented_requirement",
                        severity="error",
                        message=f"LLM reviewer detected unconfirmed technology: {tech}",
                    )
                )

        # 5. Check if actionability is compromised
        if not llm.is_actionable:
            merged_issues.append(
                ValidationIssue(
                    category="quality_problem",
                    severity="warning",
                    message="LLM reviewer flagged prompt as lacking actionable engineering clarity.",
                )
            )

        # Critical: Deterministic errors can NEVER be erased by the LLM
        overall_valid = not any(issue.severity == "error" for issue in merged_issues)

        return ValidationResult(
            overall_valid=overall_valid,
            issues=merged_issues,
            preserved_requirements=deterministic.preserved_requirements,
            missing_requirements=deterministic.missing_requirements,
            violated_constraints=deterministic.violated_constraints,
            invented_requirements=invented_reqs,
            missing_information_preserved=deterministic.missing_information_preserved,
            task_type_valid=deterministic.task_type_valid,
            structure_valid=deterministic.structure_valid,
        )
