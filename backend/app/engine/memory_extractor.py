"""Candidate Memory Extraction Engine for Prompt Compiler (Task 18).

Extracts durable long-term project knowledge (technologies, constraints, coding rules,
architecture, deployment) from user interaction text and confirmed requirements.
Performs deterministic deduplication and conflict detection against existing ProjectContext.
Candidate memories remain unconfirmed proposals until explicitly approved by the user.
"""

import re
from typing import Any

from app.schemas.candidate_memory import CandidateMemoryCreate, CandidateStatus
from app.schemas.project import (
    MemoryCategory,
    MemorySource,
    ProjectContext,
    ProjectMemory,
)

# Known technologies for stack classification
KNOWN_BACKENDS = {
    "fastapi", "django", "flask", "express", "expressjs", "nestjs", "spring",
    "springboot", "rails", "rubyonrails", "gin", "fiber", "actix", "axum",
    "aspnet", "dotnet", "laravel", "koa", "hono", "fastify",
}
KNOWN_FRONTENDS = {
    "react", "vue", "vuejs", "angular", "svelte", "sveltekit", "nextjs",
    "nuxtjs", "remix", "astro", "solidjs", "solid", "htmx", "tailwind",
}
KNOWN_DATABASES = {
    "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis",
    "dynamodb", "cassandra", "mariadb", "oracle", "cockroachdb", "supabase",
    "firebase", "planetscale", "neo4j",
}
KNOWN_DEPLOYMENTS = {
    "railway", "vercel", "flyio", "render", "aws", "gcp", "azure",
    "heroku", "digitalocean", "cloudflare", "k8s", "kubernetes", "docker",
}
KNOWN_ARCHITECTURES = {
    "microservices", "event-driven", "monolith", "modular monolith",
    "hexagonal", "clean architecture", "serverless", "cqrs", "mvc",
}

# Regex to detect transient debugging, test data, or casual conversation
TRANSIENT_PATTERNS = [
    re.compile(r"^\s*(?:hello|hi|hey|greetings|thanks|thank you|can you help)\b", re.IGNORECASE),
    re.compile(r"\b(?:print\s*\([^)]*\)|console\.log|debug log|dump variable)\b", re.IGNORECASE),
    re.compile(r"\b(?:fix typo|fix bug on line \d+|fix the indent)\b", re.IGNORECASE),
    re.compile(r"\b(?:error 500|exception|nullpointer|traceback|undefined is not)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:run pytest|pip install|npm install|git commit|git push)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:make this button blue|change the font size|add padding here)\s*$", re.IGNORECASE),
]


def is_transient_or_ephemeral(text: str) -> bool:
    """Return True if the text represents ephemeral debugging or casual chat."""
    stripped = text.strip()
    if len(stripped) < 4:
        return True
    return any(p.search(stripped) for p in TRANSIENT_PATTERNS)


def _normalize_tokens(text: str) -> set[str]:
    """Extract lowercase alphanumeric tokens for normalized comparison."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    stop_words = {
        "use", "uses", "using", "the", "for", "a", "an", "is", "as", "with",
        "and", "to", "in", "of", "all", "our", "we", "be", "must", "should",
        "framework", "library", "technology", "database", "backend", "frontend",
    }
    return {token for token in cleaned.split() if token not in stop_words and len(token) > 1}


class CandidateMemoryExtractor:
    """Extractor identifying candidate project memories from user interactions."""

    def __init__(self) -> None:
        pass

    def extract_candidates(
        self,
        user_input: str,
        confirmed_requirements: list[str] | None = None,
        project_context: ProjectContext | None = None,
    ) -> list[CandidateMemoryCreate]:
        """Synchronously extract candidate memories with deduplication and conflict detection.

        Args:
            user_input: Raw interaction text from the user.
            confirmed_requirements: Optional list of confirmed requirement statements.
            project_context: Optional current active project context for deduplication and conflicts.

        Returns:
            List of CandidateMemoryCreate objects with appropriate status (pending, duplicate, conflict).
        """
        raw_candidates: list[CandidateMemoryCreate] = []

        # 1. Skip extraction if user input is purely transient/ephemeral
        if not is_transient_or_ephemeral(user_input):
            self._extract_from_text(user_input, raw_candidates, is_direct_user_input=True)

        # 2. Extract from confirmed requirements if supplied
        if confirmed_requirements:
            for req_text in confirmed_requirements:
                if not is_transient_or_ephemeral(req_text):
                    self._extract_from_text(req_text, raw_candidates, is_direct_user_input=False)

        # 3. Deduplicate internally within this extraction batch
        unique_batch = self._deduplicate_batch(raw_candidates)

        # 4. Check deduplication and conflicts against existing project memories
        if project_context and project_context.memories:
            return self._evaluate_against_existing(unique_batch, project_context.memories)

        return unique_batch

    async def extract_candidates_async(
        self,
        user_input: str,
        confirmed_requirements: list[str] | None = None,
        project_context: ProjectContext | None = None,
    ) -> list[CandidateMemoryCreate]:
        """Asynchronously extract candidate memories."""
        return self.extract_candidates(
            user_input=user_input,
            confirmed_requirements=confirmed_requirements,
            project_context=project_context,
        )

    def _extract_from_text(
        self,
        text: str,
        results: list[CandidateMemoryCreate],
        is_direct_user_input: bool = True,
    ) -> None:
        """Apply deterministic patterns to extract candidate memories."""
        source_val = (
            MemorySource.USER_CONFIRMED.value
            if is_direct_user_input
            else MemorySource.EXTRACTED_FROM_USER_INPUT.value
        )
        base_confidence = 0.95 if is_direct_user_input else 0.85

        # 1. Backend technology patterns
        backend_matches = re.finditer(
            r"(?:(?:use|using)\s+([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+(?:the\s+)?backend|as\s+backend)|"
            r"(?:backend|server)\s+(?:uses|is|built with|framework is)\s+([A-Za-z0-9_#\+\.\-]+)|"
            r"([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+(?:the\s+)?backend|as\s+(?:the\s+|our\s+)?backend))",
            text,
            re.IGNORECASE,
        )
        for match in backend_matches:
            tech = match.group(1) or match.group(2) or match.group(3)
            if tech and tech.lower() not in {"the", "a", "our", "clean", "and", "will", "we"}:
                results.append(
                    CandidateMemoryCreate(
                        category=MemoryCategory.BACKEND.value,
                        content=f"Backend uses {tech}",
                        source=source_val,
                        confidence=base_confidence,
                        evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                    )
                )

        if re.search(r"\b(?:backend|server)\b", text, re.IGNORECASE):
            for b_name in KNOWN_BACKENDS:
                if re.search(rf"\b{re.escape(b_name)}\b", text, re.IGNORECASE):
                    if not any(b_name in c.content.lower() for c in results if c.category == MemoryCategory.BACKEND.value):
                        display_name = b_name.capitalize()
                        if b_name == "fastapi":
                            display_name = "FastAPI"
                        elif b_name == "django":
                            display_name = "Django"
                        elif b_name == "nestjs":
                            display_name = "NestJS"
                        results.append(
                            CandidateMemoryCreate(
                                category=MemoryCategory.BACKEND.value,
                                content=f"Backend uses {display_name}",
                                source=source_val,
                                confidence=base_confidence,
                                evidence=f"User stated: '{b_name} for backend'",
                            )
                        )

        # 2. Frontend technology patterns
        frontend_matches = re.finditer(
            r"(?:(?:use|using)\s+([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+(?:the\s+)?frontend|as\s+frontend|for\s+the\s+client)|"
            r"(?:frontend|client|ui)\s+(?:uses|is|built with|framework is)\s+([A-Za-z0-9_#\+\.\-]+)|"
            r"([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+(?:the\s+)?frontend|as\s+(?:the\s+|our\s+)?frontend))",
            text,
            re.IGNORECASE,
        )
        for match in frontend_matches:
            tech = match.group(1) or match.group(2) or match.group(3)
            if tech and tech.lower() not in {"the", "a", "our", "clean", "and", "will", "we"}:
                results.append(
                    CandidateMemoryCreate(
                        category=MemoryCategory.FRONTEND.value,
                        content=f"Frontend uses {tech}",
                        source=source_val,
                        confidence=base_confidence,
                        evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                    )
                )

        if re.search(r"\b(?:frontend|ui|client)\b", text, re.IGNORECASE):
            for f_name in KNOWN_FRONTENDS:
                if re.search(rf"\b{re.escape(f_name)}\b", text, re.IGNORECASE):
                    if not any(f_name in c.content.lower() for c in results if c.category == MemoryCategory.FRONTEND.value):
                        display_name = f_name.capitalize()
                        if f_name == "nextjs":
                            display_name = "Next.js"
                        results.append(
                            CandidateMemoryCreate(
                                category=MemoryCategory.FRONTEND.value,
                                content=f"Frontend uses {display_name}",
                                source=source_val,
                                confidence=base_confidence,
                                evidence=f"User stated: '{f_name} for frontend'",
                            )
                        )

        # 3. Database technology patterns
        db_matches = re.finditer(
            r"(?:(?:use|using)\s+([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+(?:the\s+)?database|as\s+(?:the\s+)?database|as\s+db)|"
            r"(?:database|datastore|db)\s+(?:uses|is|target is)\s+([A-Za-z0-9_#\+\.\-]+)|"
            r"([A-Za-z0-9_#\+\.\-]+)\s+(?:as\s+(?:our\s+|the\s+)?database|for\s+(?:the\s+|our\s+)?database))",
            text,
            re.IGNORECASE,
        )
        for match in db_matches:
            tech = match.group(1) or match.group(2) or match.group(3)
            if tech and tech.lower() not in {"the", "a", "our", "relational", "sql", "and", "will", "we"}:
                results.append(
                    CandidateMemoryCreate(
                        category=MemoryCategory.DATABASE.value,
                        content=f"Database uses {tech}",
                        source=source_val,
                        confidence=base_confidence,
                        evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                    )
                )

        if re.search(r"\b(?:database|datastore|db)\b", text, re.IGNORECASE):
            for db_name in KNOWN_DATABASES:
                if re.search(rf"\b{re.escape(db_name)}\b", text, re.IGNORECASE):
                    if not any(db_name in c.content.lower() for c in results if c.category == MemoryCategory.DATABASE.value):
                        display_name = db_name.capitalize()
                        if db_name == "postgresql":
                            display_name = "PostgreSQL"
                        elif db_name == "sqlite":
                            display_name = "SQLite"
                        elif db_name == "mongodb":
                            display_name = "MongoDB"
                        results.append(
                            CandidateMemoryCreate(
                                category=MemoryCategory.DATABASE.value,
                                content=f"Database uses {display_name}",
                                source=source_val,
                                confidence=base_confidence,
                                evidence=f"User stated: '{display_name} as database'",
                            )
                        )

        # 4. Deployment target patterns
        deploy_matches = re.finditer(
            r"(?:deploy(?:ing|ed|ment)?\s+(?:target\s+is\s+|to\s+|on\s+)([A-Za-z0-9_#\+\.\-]+)|"
            r"host(?:ing|ed)?\s+on\s+([A-Za-z0-9_#\+\.\-]+)|"
            r"([A-Za-z0-9_#\+\.\-]+)\s+for\s+deployment)",
            text,
            re.IGNORECASE,
        )
        for match in deploy_matches:
            target = match.group(1) or match.group(2) or match.group(3)
            if target and target.lower() not in {"the", "a", "production", "cloud", "staging", "and", "will", "we"}:
                results.append(
                    CandidateMemoryCreate(
                        category=MemoryCategory.DEPLOYMENT.value,
                        content=f"Deployment target is {target}",
                        source=source_val,
                        confidence=base_confidence,
                        evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                    )
                )

        if re.search(r"\b(?:deploy|deployment|host|hosting)\b", text, re.IGNORECASE):
            for d_name in KNOWN_DEPLOYMENTS:
                if re.search(rf"\b{re.escape(d_name)}\b", text, re.IGNORECASE):
                    if not any(d_name in c.content.lower() for c in results if c.category == MemoryCategory.DEPLOYMENT.value):
                        display_name = d_name.capitalize()
                        results.append(
                            CandidateMemoryCreate(
                                category=MemoryCategory.DEPLOYMENT.value,
                                content=f"Deployment target is {display_name}",
                                source=source_val,
                                confidence=base_confidence,
                                evidence=f"User stated: '{display_name} for deployment'",
                            )
                        )

        # 5. Coding rules patterns
        rule_matches = re.finditer(
            r"(?:(?:all|every)\s+(?:api\s+)?endpoints?\s+(?:must|should|have to)\s+([^,\.\n]+)|"
            r"(?:always\s+use|must\s+use)\s+([A-Za-z0-9_#\+\.\-]+)\s+(?:for\s+type\s+safety|for\s+formatting|type hints)|"
            r"coding\s+rules?:\s*([^,\.\n]+))",
            text,
            re.IGNORECASE,
        )
        for match in rule_matches:
            rule_text = match.group(1) or match.group(2) or match.group(3)
            if rule_text:
                clean_rule = rule_text.strip()
                if not is_transient_or_ephemeral(clean_rule):
                    content = (
                        f"All API endpoints must {clean_rule}"
                        if match.group(1)
                        else f"Coding rule: {clean_rule}"
                    )
                    results.append(
                        CandidateMemoryCreate(
                            category=MemoryCategory.CODING_RULE.value,
                            content=content,
                            source=source_val,
                            confidence=base_confidence,
                            evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                        )
                    )

        # 5b. TypeScript / Type Hint standalone rule
        if re.search(r"\b(?:use\s+typescript|strict\s+typescript)\b", text, re.IGNORECASE):
            results.append(
                CandidateMemoryCreate(
                    category=MemoryCategory.CODING_RULE.value,
                    content="Use TypeScript for all client and server code",
                    source=source_val,
                    confidence=base_confidence,
                    evidence="User explicitly stated: 'use TypeScript'",
                )
            )

        # 6. Persistent constraints patterns
        constraint_matches = re.finditer(
            r"(?:(?:never|do not|must not|cannot)\s+([^,\.\n]+)|"
            r"constraint:\s*([^,\.\n]+)|"
            r"(?:leave|keep)\s+([^,\.\n]+)\s+(?:untouched|unchanged|as is))",
            text,
            re.IGNORECASE,
        )
        for match in constraint_matches:
            c_text = match.group(1) or match.group(2) or match.group(3)
            if c_text:
                clean_c = c_text.strip()
                if not is_transient_or_ephemeral(clean_c) and len(clean_c) > 6:
                    # Filter out short casual conversational fragments
                    if not re.search(r"^(?:worry|forget|hesitate|be afraid)\b", clean_c, re.IGNORECASE):
                        content = (
                            f"Do not {clean_c}"
                            if match.group(1)
                            else f"Constraint: {clean_c}"
                        )
                        results.append(
                            CandidateMemoryCreate(
                                category=MemoryCategory.CONSTRAINT.value,
                                content=content,
                                source=source_val,
                                confidence=base_confidence,
                                evidence=f"User explicitly stated: '{match.group(0).strip()}'",
                            )
                        )

        # 7. Architecture patterns
        for arch in KNOWN_ARCHITECTURES:
            if re.search(rf"\b(?:use|using|architecture is)\s+{re.escape(arch)}\b", text, re.IGNORECASE):
                results.append(
                    CandidateMemoryCreate(
                        category=MemoryCategory.ARCHITECTURE.value,
                        content=f"Architecture pattern is {arch}",
                        source=source_val,
                        confidence=base_confidence,
                        evidence=f"User stated: 'use {arch} architecture'",
                    )
                )

    def _deduplicate_batch(
        self,
        candidates: list[CandidateMemoryCreate],
    ) -> list[CandidateMemoryCreate]:
        """Deduplicate candidates within the single extraction batch."""
        unique: list[CandidateMemoryCreate] = []
        seen_keys: set[tuple[str, str]] = set()

        for c in candidates:
            # Normalize content key
            norm_tokens = sorted(_normalize_tokens(c.content))
            key = (str(c.category), " ".join(norm_tokens))
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(c)

        return unique

    def _evaluate_against_existing(
        self,
        candidates: list[CandidateMemoryCreate],
        existing_memories: list[ProjectMemory],
    ) -> list[CandidateMemoryCreate]:
        """Detect duplicates and conflicts against existing active ProjectMemory records."""
        evaluated: list[CandidateMemoryCreate] = []

        active_memories = [m for m in existing_memories if m.status == "active"]

        for cand in candidates:
            cand_tokens = _normalize_tokens(cand.content)
            cand_cat = str(cand.category)

            is_duplicate = False
            duplicate_memory: ProjectMemory | None = None

            is_conflict = False
            conflicting_memory: ProjectMemory | None = None

            for existing in active_memories:
                existing_tokens = _normalize_tokens(existing.content)
                existing_cat = str(existing.category)

                # Check exact or near-identical duplicate
                # 1. Same category with high token overlap
                if cand_cat == existing_cat:
                    if cand_tokens and existing_tokens:
                        intersection = cand_tokens & existing_tokens
                        smaller_len = min(len(cand_tokens), len(existing_tokens))
                        if smaller_len > 0 and len(intersection) / smaller_len >= 0.8:
                            is_duplicate = True
                            duplicate_memory = existing
                            break

                # 2. General duplicate check across categories for identical core technologies
                # e.g. technology: "FastAPI backend" vs backend: "FastAPI backend"
                if {cand_cat, existing_cat} <= {"technology", "backend", "frontend", "database"}:
                    if cand_tokens and existing_tokens:
                        shared = cand_tokens & existing_tokens
                        # If the key technology name matches (e.g. 'fastapi')
                        if shared & (KNOWN_BACKENDS | KNOWN_FRONTENDS | KNOWN_DATABASES | KNOWN_DEPLOYMENTS):
                            is_duplicate = True
                            duplicate_memory = existing
                            break

            if is_duplicate and duplicate_memory is not None:
                evaluated.append(
                    CandidateMemoryCreate(
                        category=cand.category,
                        content=cand.content,
                        source=cand.source,
                        confidence=cand.confidence,
                        status=CandidateStatus.DUPLICATE.value,
                        evidence=f"Duplicate of existing memory '{duplicate_memory.content}' (ID: {duplicate_memory.memory_id})",
                        conflicting_memory_id=duplicate_memory.memory_id,
                        conflicting_content=duplicate_memory.content,
                        metadata=cand.metadata,
                    )
                )
                continue

            # Check conflict detection
            # Mutually exclusive stack choices in single-choice categories (frontend, backend, database)
            for existing in active_memories:
                existing_tokens = _normalize_tokens(existing.content)
                existing_cat = str(existing.category)

                # Backend conflict: e.g. React vs Vue, or FastAPI vs Django
                if cand_cat in {"backend", "technology"} and existing_cat in {"backend", "technology"}:
                    cand_backends = cand_tokens & KNOWN_BACKENDS
                    existing_backends = existing_tokens & KNOWN_BACKENDS
                    if cand_backends and existing_backends and cand_backends != existing_backends:
                        is_conflict = True
                        conflicting_memory = existing
                        break

                # Frontend conflict: e.g. React vs Vue
                if cand_cat in {"frontend", "technology"} and existing_cat in {"frontend", "technology"}:
                    cand_frontends = cand_tokens & KNOWN_FRONTENDS
                    existing_frontends = existing_tokens & KNOWN_FRONTENDS
                    if cand_frontends and existing_frontends and cand_frontends != existing_frontends:
                        is_conflict = True
                        conflicting_memory = existing
                        break

                # Database conflict: e.g. PostgreSQL vs MongoDB
                if cand_cat in {"database", "technology"} and existing_cat in {"database", "technology"}:
                    cand_dbs = cand_tokens & KNOWN_DATABASES
                    existing_dbs = existing_tokens & KNOWN_DATABASES
                    if cand_dbs and existing_dbs and cand_dbs != existing_dbs:
                        is_conflict = True
                        conflicting_memory = existing
                        break

            if is_conflict and conflicting_memory is not None:
                evaluated.append(
                    CandidateMemoryCreate(
                        category=cand.category,
                        content=cand.content,
                        source=cand.source,
                        confidence=cand.confidence,
                        status=CandidateStatus.CONFLICT.value,
                        evidence=f"Conflicts with existing memory '{conflicting_memory.content}' (ID: {conflicting_memory.memory_id})",
                        conflicting_memory_id=conflicting_memory.memory_id,
                        conflicting_content=conflicting_memory.content,
                        metadata=cand.metadata,
                    )
                )
                continue

            # If neither duplicate nor conflict, preserve original candidate with pending status
            evaluated.append(cand)

        return evaluated
