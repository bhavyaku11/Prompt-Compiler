"""Interview engine for Prompt Compiler multi-turn clarification mode."""

import asyncio
import concurrent.futures
import json
import re
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.ai.ollama import OllamaClient
from app.config import settings
from app.engine.requirements import (
    EmptyInputError,
    RequirementAnalysis,
    RequirementEngine,
    _parse_llm_json,
)
from app.schemas.interview import (
    InterviewAnswer,
    InterviewQuestion,
    InterviewSessionResponse,
)
from app.schemas.api import RequirementSummary


class SessionNotFoundError(KeyError):
    """Raised when an interview session ID is not found or has expired."""


class SessionCompletedError(ValueError):
    """Raised when attempting to submit answers to a completed or compiled session."""


class InvalidAnswerError(ValueError):
    """Raised when an answer payload is invalid or answers an unknown question."""


class InterviewSession(BaseModel):
    """Internal representation of an in-memory interview session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_input: str
    current_analysis: RequirementAnalysis
    questions: list[InterviewQuestion] = Field(default_factory=list)
    answers: dict[str, str] = Field(default_factory=dict)
    turn: int = Field(default=1)
    unresolved_topics: list[str] = Field(default_factory=list)
    asked_topics: list[str] = Field(default_factory=list)
    project_id: str | None = Field(default=None)
    user_id: int | None = Field(default=None)
    target_agent: str = Field(default="generic")
    enable_knowledge_retrieval: bool = Field(default=True)
    status: str = Field(default="in_progress")  # in_progress, ready, compiled
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)



class SqliteInterviewSessionStore:
    """Thread-safe persistent SQLite store for interview sessions."""

    def __init__(
        self,
        repository: Any | None = None,
        ttl_seconds: float | None = None,
        database_url: str | None = None,
    ) -> None:
        from app.database.repositories import InterviewSessionRepository

        if repository is not None:
            self._repo = repository
        else:
            self._repo = InterviewSessionRepository(database_url=database_url)
        self._ttl_seconds = ttl_seconds or settings.interview_session_ttl_seconds

    async def get(self, session_id: str, user_id: int | None = None) -> InterviewSession:
        session = await asyncio.to_thread(self._repo.get, session_id, True, user_id)
        if session is None:
            raise SessionNotFoundError(f"Interview session '{session_id}' not found or expired.")
        return session

    async def save(self, session: InterviewSession) -> None:
        await asyncio.to_thread(self._repo.save, session, self._ttl_seconds)

    async def delete(self, session_id: str, user_id: int | None = None) -> None:
        await asyncio.to_thread(self._repo.delete, session_id, user_id)

    async def clear_expired(self) -> int:
        return await asyncio.to_thread(self._repo.delete_expired)


class InMemoryInterviewSessionStore:
    """Thread-safe in-memory store for interview sessions (used for fast isolated testing)."""

    def __init__(self, ttl_seconds: float | None = None) -> None:
        self._ttl_seconds = ttl_seconds or settings.interview_session_ttl_seconds
        self._sessions: dict[str, InterviewSession] = {}
        self._lock = asyncio.Lock()

    def _is_expired(self, session: InterviewSession) -> bool:
        return (time.time() - session.updated_at) > self._ttl_seconds

    async def get(self, session_id: str, user_id: int | None = None) -> InterviewSession:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or self._is_expired(session):
                if session is not None:
                    del self._sessions[session_id]
                raise SessionNotFoundError(f"Interview session '{session_id}' not found or expired.")
            if user_id is not None and session.user_id is not None and session.user_id != user_id:
                raise SessionNotFoundError(f"Interview session '{session_id}' not found or expired.")
            return session

    async def save(self, session: InterviewSession) -> None:
        async with self._lock:
            session.updated_at = time.time()
            self._sessions[session.session_id] = session

    async def delete(self, session_id: str, user_id: int | None = None) -> None:
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                if user_id is not None and session.user_id is not None and session.user_id != user_id:
                    return
                del self._sessions[session_id]

    async def clear_expired(self) -> int:
        async with self._lock:
            expired_keys = [k for k, v in self._sessions.items() if self._is_expired(v)]
            for k in expired_keys:
                del self._sessions[k]
            return len(expired_keys)


# Default InterviewSessionStore is backed by SQLite persistence
InterviewSessionStore = SqliteInterviewSessionStore


QUESTION_GENERATION_INSTRUCTION = """You are an expert software requirement clarification interviewer.
Your task is to analyze missing information for a software project and generate concise, targeted clarification questions.

Rules:
1. Do NOT ask about information already present in confirmed requirements or constraints.
2. Ask only about material implementation decisions (e.g., deployment platform, authentication method, database, UI styling/framework).
3. Do NOT ask trivial, vague, or open-ended questions like "What else do you want?".
4. For each question, provide 3-4 sensible, concise multiple-choice options including "Leave unspecified".
5. Set allow_custom to true so the user can provide custom answers.
6. Do NOT invent answers or assume choices on behalf of the user.
7. Return a valid JSON object matching this schema:
{
  "questions": [
    {
      "id": "q1",
      "topic": "<short topic name, e.g. deployment, authentication, database, styling>",
      "question": "<concise actionable question>",
      "options": ["<option 1>", "<option 2>", "<option 3>", "Leave unspecified"],
      "allow_custom": true
    }
  ]
}
Output ONLY the JSON object. Do not include markdown commentary."""


# Deterministic question catalog for common architectural topics
TOPIC_QUESTION_TEMPLATES: dict[str, dict[str, Any]] = {
    "deployment": {
        "question": "Where should this application be deployed?",
        "options": ["Vercel", "Netlify", "AWS", "Docker / Self-hosted", "Leave unspecified"],
    },
    "authentication": {
        "question": "What authentication mechanism should be implemented?",
        "options": ["JWT with Email/Password", "Supabase Auth", "OAuth (Google/GitHub)", "No authentication needed", "Leave unspecified"],
    },
    "database": {
        "question": "What database or persistence layer should be used?",
        "options": ["PostgreSQL", "SQLite", "MongoDB", "No database / In-memory", "Leave unspecified"],
    },
    "styling": {
        "question": "What UI styling or design system should be used?",
        "options": ["Tailwind CSS", "CSS Modules", "Vanilla CSS", "Component Library (shadcn/ui)", "Leave unspecified"],
    },
    "framework": {
        "question": "What primary framework or runtime should be used?",
        "options": ["React / Next.js", "Vue / Nuxt", "Node.js / Express", "FastAPI / Python", "Leave unspecified"],
    },
    "target_platform": {
        "question": "What is the primary target platform for this project?",
        "options": ["Web (Desktop & Mobile)", "Desktop (macOS/Windows)", "Mobile App", "CLI tool", "Leave unspecified"],
    },
}


class PromptInterviewer:
    """Manages interview question generation, deduplication, and session state."""

    def __init__(
        self,
        ollama_client: OllamaClient | None = None,
        session_store: Any | None = None,
        max_questions_per_turn: int | None = None,
        max_turns: int | None = None,
        requirement_repository: Any | None = None,
        store: Any | None = None,
    ) -> None:
        self._ollama_client = ollama_client
        self._store = session_store or store or SqliteInterviewSessionStore()
        self._max_questions = max_questions_per_turn or settings.max_interview_questions
        self._max_turns = max_turns or settings.max_interview_turns
        if requirement_repository is not None:
            self._req_repo = requirement_repository
        else:
            try:
                from app.database.repositories import RequirementAnalysisRepository

                self._req_repo = RequirementAnalysisRepository()
            except Exception:
                self._req_repo = None

    @property
    def store(self) -> Any:
        return self._store

    @property
    def requirement_repository(self) -> Any:
        return self._req_repo

    TOPIC_KNOWN_INDICATORS: dict[str, list[str]] = {
        "framework": ["react", "vue", "angular", "svelte", "next", "nuxt", "fastapi", "express", "django", "flask", "spring"],
        "styling": ["tailwind", "css", "styled-components", "sass", "bootstrap", "shadcn", "chakra", "material"],
        "deployment": ["vercel", "netlify", "aws", "gcp", "azure", "docker", "render", "railway", "fly.io", "heroku"],
        "database": ["postgres", "postgresql", "sqlite", "mysql", "mongodb", "redis", "dynamodb", "supabase", "prisma"],
        "authentication": ["auth", "jwt", "oauth", "clerk", "nextauth", "cognito", "firebase auth", "supabase auth", "passport"],
    }

    def _is_exhaustively_specified(self, analysis: RequirementAnalysis) -> bool:
        """Check if sufficient key technical specifications are already confirmed."""
        confirmed_text = " ".join(analysis.confirmed_requirements + analysis.constraints).lower()
        confirmed_dimensions = 0
        for topic, indicators in self.TOPIC_KNOWN_INDICATORS.items():
            if any(kw in confirmed_text for kw in indicators):
                confirmed_dimensions += 1
        if confirmed_dimensions >= 2 and not analysis.missing_information:
            return True
        return False

    def _derive_missing_architectural_topics(
        self,
        analysis: RequirementAnalysis,
        already_asked: set[str],
    ) -> list[str]:
        """Derive candidate architectural decisions when missing_information is empty or incomplete."""
        confirmed_text = " ".join(analysis.confirmed_requirements + analysis.constraints).lower()
        candidates = ["framework", "database", "styling", "deployment", "authentication"]
        derived: list[str] = []
        for topic in candidates:
            if topic in already_asked:
                continue
            indicators = self.TOPIC_KNOWN_INDICATORS.get(topic, [topic])
            if not any(kw in confirmed_text for kw in indicators):
                derived.append(topic)
                if len(derived) >= self._max_questions:
                    break
        return derived

    def _filter_material_missing_topics(
        self,
        analysis: RequirementAnalysis,
        already_asked: set[str],
    ) -> list[str]:
        """Extract material missing topics that have NOT already been confirmed or asked."""
        confirmed_text = " ".join(analysis.confirmed_requirements + analysis.constraints).lower()
        material_candidates: list[str] = []

        for item in analysis.missing_information:
            item_clean = item.strip()
            if not item_clean:
                continue

            topic_key = self._normalize_topic(item_clean)
            if topic_key in already_asked:
                continue

            # Check if this topic or its indicators are already confirmed
            is_already_confirmed = False
            if topic_key in confirmed_text:
                is_already_confirmed = True
            elif topic_key in self.TOPIC_KNOWN_INDICATORS:
                for kw in self.TOPIC_KNOWN_INDICATORS[topic_key]:
                    if kw in confirmed_text:
                        is_already_confirmed = True
                        break

            if is_already_confirmed:
                continue

            material_candidates.append(item_clean)

        return material_candidates

    def _normalize_topic(self, topic_str: str) -> str:
        """Map free-text missing info strings to canonical topic keywords."""
        lower = topic_str.lower()
        if any(w in lower for w in ["deploy", "hosting", "cloud"]):
            return "deployment"
        if any(w in lower for w in ["auth", "login", "user account", "permission"]):
            return "authentication"
        if any(w in lower for w in ["database", "storage", "persistence", "postgres", "sql"]):
            return "database"
        if any(w in lower for w in ["style", "styling", "css", "theme", "design", "ui library"]):
            return "styling"
        if any(w in lower for w in ["framework", "tech stack", "backend framework", "frontend framework"]):
            return "framework"
        if any(w in lower for w in ["platform", "mobile", "desktop", "target"]):
            return "target_platform"
        # Fallback to sanitized first 3 words
        words = re.findall(r"\w+", lower)[:3]
        return "_".join(words) if words else "general"

    def _build_fallback_question(self, topic_str: str, q_index: int) -> InterviewQuestion:
        """Create a targeted InterviewQuestion using template catalogs or structured fallback."""
        canonical = self._normalize_topic(topic_str)
        q_id = f"q{q_index}"

        if canonical in TOPIC_QUESTION_TEMPLATES:
            entry = TOPIC_QUESTION_TEMPLATES[canonical]
            return InterviewQuestion(
                id=q_id,
                topic=canonical,
                question=entry["question"],
                options=list(entry["options"]),
                allow_custom=True,
            )

        # Generic structured fallback
        clean_topic = topic_str.strip().rstrip(".:")
        return InterviewQuestion(
            id=q_id,
            topic=canonical,
            question=f"What is your preference or requirement for {clean_topic}?",
            options=["Standard default", "Specify custom requirement", "Leave unspecified"],
            allow_custom=True,
        )

    async def generate_questions_async(
        self,
        analysis: RequirementAnalysis,
        already_asked: set[str],
        use_llm: bool = True,
        input_text: str | None = None,
    ) -> list[InterviewQuestion]:
        """Generate targeted clarification questions for unresolved missing information."""
        missing_topics = self._filter_material_missing_topics(analysis, already_asked)
        if not missing_topics and not self._is_exhaustively_specified(analysis):
            missing_topics = self._derive_missing_architectural_topics(analysis, already_asked)

        if not missing_topics:
            return []

        # Limit to configured maximum questions per turn
        selected_topics = missing_topics[: self._max_questions]

        if not use_llm or self._ollama_client is None:
            # Deterministic generation
            return [
                self._build_fallback_question(t, i + 1)
                for i, t in enumerate(selected_topics)
            ]

        # Use Ollama to generate context-aware questions
        prompt_content = (
            f"User Initial Request: \"{input_text or analysis.intent}\"\n"
            f"User Intent: {analysis.intent}\n"
            f"Domain: {analysis.domain}\n"
            f"Task Type: {analysis.task_type}\n"
            f"Confirmed Requirements: {json.dumps(analysis.confirmed_requirements)}\n"
            f"Constraints: {json.dumps(analysis.constraints)}\n"
            f"Missing Decisions to clarify (max {len(selected_topics)}): {json.dumps(selected_topics)}\n\n"
            f"Generate up to {len(selected_topics)} targeted clarification questions with options."
        )

        try:
            full_prompt = f"{QUESTION_GENERATION_INSTRUCTION}\n\n{prompt_content}"
            raw_response = await self._ollama_client.generate(
                prompt=full_prompt,
                system=QUESTION_GENERATION_INSTRUCTION,
            )
            parsed = _parse_llm_json(raw_response)
            raw_questions = parsed.get("questions", [])

            questions: list[InterviewQuestion] = []
            for i, q_dict in enumerate(raw_questions[: self._max_questions]):
                q_id = q_dict.get("id") or f"q{i+1}"
                topic = q_dict.get("topic") or self._normalize_topic(selected_topics[min(i, len(selected_topics)-1)])
                question_text = q_dict.get("question", "").strip()
                options = q_dict.get("options", [])
                if not isinstance(options, list):
                    options = []

                # Ensure 'Leave unspecified' option is present so user is never forced
                if not any("leave unspecified" in str(opt).lower() for opt in options):
                    options.append("Leave unspecified")

                if question_text:
                    questions.append(
                        InterviewQuestion(
                            id=q_id,
                            topic=topic,
                            question=question_text,
                            options=[str(opt) for opt in options],
                            allow_custom=bool(q_dict.get("allow_custom", True)),
                        )
                    )

            if questions:
                return questions

        except Exception:
            # Fall back cleanly to deterministic question builder on LLM error/parse issue
            pass

        return [
            self._build_fallback_question(t, i + 1)
            for i, t in enumerate(selected_topics)
        ]

    async def start_session_async(
        self,
        input_text: str,
        requirement_engine: RequirementEngine,
        use_llm: bool = True,
        project_id: str | None = None,
        user_id: int | None = None,
        target_agent: str = "generic",
        enable_knowledge_retrieval: bool = True,
    ) -> InterviewSession:
        """Start a new interview session from raw user input.
        
        Orchestration:
        1. Validates input.
        2. Runs RequirementEngine to extract structured requirements.
        3. Identifies whether material clarification is needed.
        4. If needed, generates up to MAX_INTERVIEW_QUESTIONS.
        5. Saves session in in-memory store.
        """
        if not input_text or not input_text.strip():
            raise EmptyInputError("Input text cannot be empty or contain only whitespace.")

        analysis = await requirement_engine.analyze_async(input_text)
        already_asked: set[str] = set()

        material_topics = self._filter_material_missing_topics(analysis, already_asked)

        # If analysis did not yield material topics, check if input is exhaustively specified
        if not material_topics and not self._is_exhaustively_specified(analysis):
            material_topics = self._derive_missing_architectural_topics(analysis, already_asked)

        if not material_topics:
            # All architectural decisions are already confirmed; immediately ready
            session = InterviewSession(
                original_input=input_text,
                current_analysis=analysis,
                questions=[],
                unresolved_topics=[],
                asked_topics=[],
                project_id=project_id,
                user_id=user_id,
                target_agent=target_agent,
                enable_knowledge_retrieval=enable_knowledge_retrieval,
                status="ready",
            )
            await self._store.save(session)
            return session

        # Generate clarification questions
        questions = await self.generate_questions_async(
            analysis=analysis,
            already_asked=already_asked,
            use_llm=use_llm,
            input_text=input_text,
        )

        asked = [q.topic for q in questions]
        session = InterviewSession(
            original_input=input_text,
            current_analysis=analysis,
            questions=questions,
            unresolved_topics=material_topics,
            asked_topics=asked,
            project_id=project_id,
            user_id=user_id,
            target_agent=target_agent,
            enable_knowledge_retrieval=enable_knowledge_retrieval,
            status="in_progress" if questions else "ready",
        )

        await self._store.save(session)
        if self._req_repo is not None:
            try:
                await asyncio.to_thread(self._req_repo.save, analysis, input_text, session.session_id)
            except Exception:
                pass
        return session

    async def submit_answers_async(
        self,
        session_id: str,
        answers: list[InterviewAnswer],
        use_llm: bool = True,
        user_id: int | None = None,
    ) -> InterviewSession:
        """Submit answers to current pending questions and update interview state.
        
        Orchestration:
        1. Validates session existence and status.
        2. Validates answers match pending questions.
        3. Merges concrete answers into confirmed_requirements without overwriting.
        4. Removes resolved topics from missing_information.
        5. Evaluates if further clarification is required.
        6. Generates next turn of questions or marks session ready.
        """
        session = await self._store.get(session_id, user_id=user_id)

        if session.status in ("ready", "compiled"):
            raise SessionCompletedError(
                f"Interview session '{session_id}' is already in status '{session.status}' and cannot accept answers."
            )

        if not answers:
            raise InvalidAnswerError("Answers payload cannot be empty.")

        pending_question_map = {q.id: q for q in session.questions}
        for ans in answers:
            if ans.question_id not in pending_question_map:
                raise InvalidAnswerError(
                    f"Question ID '{ans.question_id}' is not in the pending questions for session '{session_id}'."
                )

        # Merge answers
        updated_analysis = session.current_analysis.model_copy(deep=True)
        new_confirmed = list(updated_analysis.confirmed_requirements)
        new_missing = list(updated_analysis.missing_information)
        new_assumptions = list(updated_analysis.assumptions)

        for ans in answers:
            q = pending_question_map[ans.question_id]
            answer_text = ans.answer.strip()
            session.answers[q.id] = answer_text

            is_unspecified = any(
                phrase in answer_text.lower()
                for phrase in ["leave unspecified", "unspecified", "skip", "not needed", "no preference"]
            )

            if is_unspecified:
                # Do NOT invent an answer. Record as an explicit choice to leave unspecified.
                new_assumptions.append(f"{q.topic.capitalize()} intentionally left unspecified by user.")
                # Remove from missing information so it's not repeatedly asked
                new_missing = [
                    m for m in new_missing
                    if self._normalize_topic(m) != q.topic
                ]
            else:
                # User provided a concrete choice: add to confirmed_requirements
                confirmation_entry = f"{q.topic.capitalize()}: {answer_text}"
                if confirmation_entry not in new_confirmed:
                    new_confirmed.append(confirmation_entry)

                # Remove matching topic from missing_information
                new_missing = [
                    m for m in new_missing
                    if self._normalize_topic(m) != q.topic
                ]

        updated_analysis.confirmed_requirements = new_confirmed
        updated_analysis.missing_information = new_missing
        updated_analysis.assumptions = new_assumptions
        session.current_analysis = updated_analysis

        # Check remaining unresolved topics
        already_asked = set(session.asked_topics)
        remaining_material = self._filter_material_missing_topics(updated_analysis, already_asked)
        session.unresolved_topics = remaining_material

        if not remaining_material or session.turn >= self._max_turns:
            # All material topics resolved or turn limit reached
            session.status = "ready"
            session.questions = []
        else:
            # Generate next batch of questions
            next_questions = await self.generate_questions_async(
                analysis=updated_analysis,
                already_asked=already_asked,
                use_llm=use_llm,
                input_text=session.original_input,
            )
            if next_questions:
                session.questions = next_questions
                session.asked_topics.extend([q.topic for q in next_questions])
                session.turn += 1
                session.status = "in_progress"
            else:
                session.status = "ready"
                session.questions = []

        await self._store.save(session)
        if self._req_repo is not None:
            try:
                await asyncio.to_thread(self._req_repo.save, updated_analysis, session.original_input, session.session_id)
            except Exception:
                pass
        return session

    def to_session_response(
        self,
        session: InterviewSession,
        message: str | None = None,
    ) -> InterviewSessionResponse:
        """Convert internal InterviewSession to client-facing InterviewSessionResponse schema."""
        status_message = message
        if not status_message:
            if session.status == "ready":
                status_message = "Requirements clarified and ready for compilation."
            elif session.status == "compiled":
                status_message = "Interview completed and prompt compiled."
            else:
                status_message = f"Interview in progress (turn {session.turn}). Please answer the questions."

        return InterviewSessionResponse(
            session_id=session.session_id,
            status=session.status,
            turn=session.turn,
            questions=session.questions,
            requirements=RequirementSummary(
                intent=session.current_analysis.intent,
                task_type=session.current_analysis.task_type,
                domain=session.current_analysis.domain,
                confirmed_requirements=session.current_analysis.confirmed_requirements,
                missing_information=session.current_analysis.missing_information,
                constraints=session.current_analysis.constraints,
                assumptions=session.current_analysis.assumptions,
            ),
            unresolved_topics=session.unresolved_topics,
            message=status_message,
            project_id=session.project_id,
            target_agent=session.target_agent,
        )
