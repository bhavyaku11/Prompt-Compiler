"""Requirement engine foundation and AI-powered extraction for Prompt Compiler."""

import asyncio
import concurrent.futures
import json
import re
from pydantic import BaseModel, Field, ValidationError
from app.ai.ollama import OllamaClient
from app.config import settings


class EmptyInputError(ValueError):
    """Raised when the input text provided to the requirement engine is empty or whitespace."""


class RequirementExtractionError(Exception):
    """Raised when requirement extraction from model output fails (parsing or validation)."""


class RequirementAnalysis(BaseModel):
    """Structured representation of extracted user requirements."""

    intent: str = Field(
        ...,
        description="The fundamental objective the user is trying to accomplish.",
    )
    task_type: str = Field(
        default="build",
        description="Broad classification of the task (e.g., build, modify, debug, explain, analyze).",
    )
    domain: str = Field(
        default="general software",
        description="Subject domain of the task (e.g., web development, backend, database, UI/UX).",
    )
    confirmed_requirements: list[str] = Field(
        default_factory=list,
        description="Explicit requirements and facts provided directly by the user.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Material information that is absent and may affect implementation.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Explicit limitations, conditions, or boundaries specified by the user.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Safe, non-material interpretations that do not alter the requested outcome.",
    )
    project_context_summary: str | None = Field(
        default=None,
        description="Optional high-level summary of active project context.",
    )


EXTRACTION_INSTRUCTION = """You are a software requirement analysis engine.
Analyze the user's input and extract only information directly supported by the input.
Do not invent technical requirements, frameworks, databases, or libraries that are not explicitly mentioned.
Separate confirmed requirements from assumptions and missing information.

Return a valid JSON object matching this schema:
{
  "intent": "<fundamental objective of the user>",
  "task_type": "<one of: build, modify, debug, explain, analyze>",
  "domain": "<subject domain, e.g., web development, backend, database, UI/UX, general software>",
  "confirmed_requirements": ["<explicit requirement 1>", "<explicit requirement 2>"],
  "missing_information": ["<material information absent that affects implementation>"],
  "constraints": ["<explicit limitation or boundary condition>"],
  "assumptions": ["<conservative safe interpretation>"]
}

Critical Extraction Rules:
1. intent: Describe what the user is trying to accomplish. Do not rewrite into a large implementation specification.
2. task_type: Must be one of "build", "modify", "debug", "explain", "analyze". Do not invent new types.
3. domain: Identify the relevant domain supported by the request (e.g., web development, backend, database, general software).
4. confirmed_requirements: Include ONLY information explicitly stated or unambiguously implied by the input (e.g., specific named technologies, specific requested features). DO NOT add unmentioned technologies (e.g., do not add React, Next.js, Tailwind, Supabase, PostgreSQL unless explicitly stated).
5. missing_information: Identify material information that is genuinely absent and could materially affect implementation (e.g. unknown framework, unknown database, unknown styling, unknown hosting).
6. constraints: Include ONLY explicit limitations or boundaries (e.g., "do not modify existing backend", "using only vanilla CSS").
7. assumptions: Must be conservative. Do not convert missing technical choices into assumptions.
8. Output ONLY the JSON object. Do not include markdown commentary, introductions, or explanations."""


def _parse_llm_json(raw_text: str) -> dict:
    """Parse raw LLM response text into a JSON dictionary, safely handling code fences and think tags."""
    # 1. Remove thinking blocks if present (<think>...</think>)
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # 2. Check for markdown code fences (```json ... ``` or ``` ... ```)
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        target_str = fence_match.group(1).strip()
    else:
        # 3. Locate the outermost curly braces
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            target_str = cleaned[start : end + 1].strip()
        else:
            target_str = cleaned

    try:
        data = json.loads(target_str)
    except json.JSONDecodeError as exc:
        raise RequirementExtractionError(
            f"Failed to parse LLM response as JSON: {exc}. Response snippet: {raw_text[:200]}"
        ) from exc

    if not isinstance(data, dict):
        raise RequirementExtractionError(
            f"Expected a JSON object from LLM response, got {type(data).__name__}."
        )

    return data


def _validate_requirement_analysis(data: dict) -> RequirementAnalysis:
    """Validate parsed JSON dictionary against the RequirementAnalysis Pydantic model."""
    try:
        return RequirementAnalysis.model_validate(data)
    except ValidationError as exc:
        raise RequirementExtractionError(
            f"LLM output failed RequirementAnalysis validation: {exc}"
        ) from exc


class RequirementEngine:
    """Requirement engine responsible for analyzing and structuring user inputs using AI extraction."""

    def __init__(self, ollama_client: OllamaClient | None = None) -> None:
        if ollama_client is None:
            # Configure default OllamaClient with generous timeout for local model inference
            timeout = max(settings.OLLAMA_TIMEOUT, 360.0)
            self.ollama_client = OllamaClient(timeout=timeout)
        else:
            self.ollama_client = ollama_client

    def _build_prompt(self, user_input: str) -> str:
        """Construct the prompt sent to Ollama for structured requirement extraction."""
        return f"""{EXTRACTION_INSTRUCTION}

User input:
\"\"\"{user_input}\"\"\"

JSON:"""

    async def analyze_async(
        self,
        user_input: str,
        project_context: Any | None = None,
    ) -> RequirementAnalysis:
        """Asynchronously analyze raw user input and extract a structured RequirementAnalysis representation.

        Args:
            user_input: Non-empty requirement text supplied by the user.
            project_context: Optional persistent ProjectContext object.

        Returns:
            RequirementAnalysis containing intent, task_type, domain, confirmed_requirements,
            missing_information, constraints, assumptions, and optional project_context_summary.

        Raises:
            EmptyInputError: If user_input is empty or only whitespace.
            RequirementExtractionError: If model response is invalid JSON or fails schema validation.
            OllamaError subclasses: If connection, timeout, or HTTP errors occur communicating with Ollama.
        """
        if not user_input or not user_input.strip():
            raise EmptyInputError("Requirement input cannot be empty or contain only whitespace.")

        prompt = self._build_prompt(user_input.strip())
        raw_text = await self.ollama_client.generate(prompt)
        parsed_dict = _parse_llm_json(raw_text)
        analysis = _validate_requirement_analysis(parsed_dict)
        if project_context is not None:
            if hasattr(project_context, "to_context_string"):
                analysis.project_context_summary = project_context.to_context_string()
            else:
                analysis.project_context_summary = str(project_context)
        return analysis

    def analyze(
        self,
        user_input: str,
        project_context: Any | None = None,
    ) -> RequirementAnalysis:
        """Synchronously analyze raw user input and extract a structured RequirementAnalysis representation."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(asyncio.run, self.analyze_async(user_input, project_context)).result()
        else:
            return asyncio.run(self.analyze_async(user_input, project_context))

    def analyze_deterministic(
        self,
        user_input: str,
        project_context: Any | None = None,
    ) -> RequirementAnalysis:
        """Deterministic baseline analysis preserved for test support and baseline validation.

        Args:
            user_input: Non-empty requirement text supplied by the user.
            project_context: Optional persistent ProjectContext object.

        Returns:
            RequirementAnalysis generated via deterministic pattern matching.

        Raises:
            EmptyInputError: If user_input is empty or only whitespace.
        """
        if not user_input or not user_input.strip():
            raise EmptyInputError("Requirement input cannot be empty or contain only whitespace.")

        text = user_input.strip()
        lower_text = text.lower()

        task_type = self._classify_task_type(lower_text)
        domain = self._classify_domain(lower_text)
        intent = self._extract_intent(text)
        confirmed_requirements = self._extract_confirmed_requirements(text)
        constraints = self._extract_constraints(text)
        missing_information = self._detect_missing_information(
            domain=domain,
            task_type=task_type,
            confirmed_requirements=confirmed_requirements,
            constraints=constraints,
        )
        assumptions: list[str] = []

        summary = None
        if project_context is not None:
            if hasattr(project_context, "to_context_string"):
                summary = project_context.to_context_string()
            else:
                summary = str(project_context)

        return RequirementAnalysis(
            intent=intent,
            task_type=task_type,
            domain=domain,
            confirmed_requirements=confirmed_requirements,
            missing_information=missing_information,
            constraints=constraints,
            assumptions=assumptions,
            project_context_summary=summary,
        )

    def _classify_task_type(self, lower_text: str) -> str:
        if re.search(r"\b(debug|fix|bug|issue|error|crash|problem)\b", lower_text):
            return "debug"
        if re.search(r"\b(modify|refactor|update|change|edit|rewrite|convert)\b", lower_text):
            return "modify"
        if re.search(r"\b(explain|why|how does|what is|clarify)\b", lower_text):
            return "explain"
        if re.search(r"\b(analyze|critique|review|audit|evaluate)\b", lower_text):
            return "analyze"
        return "build"

    def _classify_domain(self, lower_text: str) -> str:
        if re.search(r"\b(website|web|frontend|html|css|portfolio|landing page)\b", lower_text):
            return "web development"
        if re.search(r"\b(api|backend|endpoint|fastapi|server|microservice|rest)\b", lower_text):
            return "backend"
        if re.search(r"\b(database|sql|postgres|sqlite|db|query|table|schema)\b", lower_text):
            return "database"
        if re.search(r"\b(ui|ux|styling|design|component|theme|layout)\b", lower_text):
            return "UI/UX"
        if re.search(r"\b(college|academic|assignment|homework|thesis|paper)\b", lower_text):
            return "college work"
        return "general software"

    def _extract_intent(self, text: str) -> str:
        cleaned = re.sub(
            r"^(please\s+|can you\s+|i want to\s+|i need to\s+|build me\s+)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned:
            return cleaned[0].upper() + cleaned[1:]
        return text

    def _extract_confirmed_requirements(self, text: str) -> list[str]:
        confirmed: list[str] = []

        known_tech_patterns = [
            r"\bReact\b",
            r"\bVue\b",
            r"\bAngular\b",
            r"\bSvelte\b",
            r"\bNext\.?js\b",
            r"\bFastAPI\b",
            r"\bFlask\b",
            r"\bDjango\b",
            r"\bExpress\b",
            r"\bNode(?:\.js)?\b",
            r"\bPython\b",
            r"\bJava\b",
            r"\bTypeScript\b",
            r"\bJavaScript\b",
            r"\bGo\b",
            r"\bRust\b",
            r"\bPostgreSQL\b",
            r"\bMySQL\b",
            r"\bSQLite\b",
            r"\bMongoDB\b",
            r"\bSupabase\b",
            r"\bFirebase\b",
            r"\bTailwind(?:\s*CSS)?\b",
            r"\bBootstrap\b",
            r"\bGoogle authentication\b",
            r"\bOAuth\b",
            r"\bJWT\b",
        ]
        for pattern in known_tech_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                confirmed.append(match.group(0))

        feature_patterns = [
            (r"\blogin(?:\s+page|\s+experience|\s+screen)?\b", "login page"),
            (r"\bportfolio(?:\s+website)?\b", "portfolio website"),
            (r"\bdashboard\b", "dashboard"),
            (r"\blanding\s+page\b", "landing page"),
            (r"\bcheckout\b", "checkout flow"),
            (r"\bcontact\s+form\b", "contact form"),
        ]
        for pattern, label in feature_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                if label not in confirmed:
                    confirmed.append(label)

        if not confirmed:
            confirmed.append(text.strip())

        return confirmed

    def _extract_constraints(self, text: str) -> list[str]:
        constraints: list[str] = []
        patterns = [
            r"do\s+not\s+[^,.]+",
            r"don'?t\s+[^,.]+",
            r"without\s+[^,.]+",
            r"only\s+using\s+[^,.]+",
            r"using\s+only\s+[^,.]+",
            r"must\s+not\s+[^,.]+",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                constraints.append(match.group(0).strip())
        return constraints

    def _detect_missing_information(
        self,
        domain: str,
        task_type: str,
        confirmed_requirements: list[str],
        constraints: list[str],
    ) -> list[str]:
        missing: list[str] = []
        confirmed_str = " ".join(confirmed_requirements).lower()
        constraint_str = " ".join(constraints).lower()
        combined = confirmed_str + " " + constraint_str

        if domain == "web development" and task_type in ("build", "modify"):
            has_tech = any(
                tech in combined
                for tech in ["react", "vue", "angular", "svelte", "next", "html", "vanilla"]
            )
            if not has_tech:
                missing.append("frontend technology / framework preference")

            has_styling = any(
                style in combined
                for style in ["tailwind", "css", "bootstrap", "sass", "styling"]
            )
            if not has_styling:
                missing.append("visual design and styling direction")

        if "login" in combined or "auth" in combined:
            has_auth_provider = any(
                provider in combined
                for provider in ["supabase", "firebase", "google", "oauth", "jwt", "auth0"]
            )
            if not has_auth_provider:
                missing.append("authentication provider and strategy")

        if domain == "database" and task_type in ("build", "modify"):
            has_dbms = any(
                db in combined
                for db in ["postgres", "mysql", "sqlite", "mongo"]
            )
            if not has_dbms:
                missing.append("target database engine (e.g. PostgreSQL, SQLite)")

        return missing

