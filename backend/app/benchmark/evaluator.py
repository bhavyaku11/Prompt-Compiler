"""Deterministic quality evaluation engine for Prompt Compiler benchmarks."""

import re
from typing import Any

from app.benchmark.schemas import (
    BenchmarkCase,
    CaseEvaluationResult,
)
from app.schemas.api import KnowledgeReference


class QualityEvaluator:
    """Evaluates compiled prompt quality against structured ground-truth benchmark criteria."""

    def __init__(
        self,
        min_requirement_preservation_threshold: float = 0.8,
        min_retrieval_recall_threshold: float = 0.66,
    ) -> None:
        self.min_req_threshold = min_requirement_preservation_threshold
        self.min_retrieval_recall_threshold = min_retrieval_recall_threshold

    def evaluate_case(
        self,
        case: BenchmarkCase,
        generated_prompt: str,
        target_agent: str = "generic",
        retrieved_sources: list[str] | list[KnowledgeReference] | None = None,
        raw_compiled_prompt: str | None = None,
    ) -> CaseEvaluationResult:
        """Deterministically evaluate a generated prompt against a benchmark case.

        Args:
            case: The benchmark ground truth specification.
            generated_prompt: The final generated prompt (formatted for target_agent).
            target_agent: The preset name (generic, cursor, claude_code, cline, windsurf).
            retrieved_sources: Optional list of retrieved source names or KnowledgeReference objects.
            raw_compiled_prompt: Optional unformatted canonical prompt prior to agent formatting.

        Returns:
            CaseEvaluationResult with itemized metric scores and actionable diagnostics.
        """
        diagnostics: list[str] = []

        # 1. Requirement Preservation Evaluation
        preserved_reqs, missing_reqs, req_score = self.evaluate_requirements(
            case.expected_requirements, generated_prompt
        )
        if missing_reqs:
            for m in missing_reqs:
                diagnostics.append(f"Missing expected requirement: '{m}'")

        # 2. Constraint Adherence Evaluation
        adhered_constraints, violated_constraints, constraint_score = self.evaluate_constraints(
            case.expected_constraints, generated_prompt
        )
        if violated_constraints:
            for v in violated_constraints:
                diagnostics.append(f"Violated explicit constraint: '{v}'")

        # 3. Forbidden Assumption / Hallucination Evaluation
        detected_forbidden, forbidden_score = self.evaluate_forbidden_assumptions(
            case.forbidden_assumptions,
            generated_prompt,
            project_context=case.project_context,
        )
        if detected_forbidden:
            for d in detected_forbidden:
                diagnostics.append(f"Unsupported forbidden assumption detected: '{d}'")

        # 4. Retrieval Evaluation (if knowledge was expected)
        source_names: list[str] = []
        if retrieved_sources:
            for s in retrieved_sources:
                if isinstance(s, KnowledgeReference):
                    source_names.append(s.source_name)
                elif isinstance(s, str):
                    source_names.append(s)

        # Deduplicate retrieved source names preserving order
        unique_retrieved = list(dict.fromkeys(source_names))

        retrieval_recall: float | None = None
        retrieval_precision: float | None = None
        missing_sources: list[str] = []
        unexpected_sources: list[str] = []

        if case.expected_knowledge_sources is not None:
            expected_set = set(case.expected_knowledge_sources)
            retrieved_set = set(unique_retrieved)

            recalled = expected_set.intersection(retrieved_set)
            missing_sources = sorted(list(expected_set - retrieved_set))
            unexpected_sources = sorted(list(retrieved_set - expected_set))

            retrieval_recall = len(recalled) / len(expected_set) if expected_set else 1.0
            retrieval_precision = len(recalled) / len(retrieved_set) if retrieved_set else (1.0 if not expected_set else 0.0)

            if missing_sources:
                for ms in missing_sources:
                    diagnostics.append(f"Missing expected knowledge source: '{ms}'")

        # 5. Agent Preset Preservation Evaluation
        preset_preservation_score = 1.0
        if raw_compiled_prompt is not None and target_agent != "generic":
            preset_preservation_score = self.evaluate_preset_preservation(
                raw_compiled_prompt,
                generated_prompt,
                case.expected_requirements,
                case.expected_constraints,
            )
            if preset_preservation_score < 1.0:
                diagnostics.append(
                    f"Agent preset '{target_agent}' stripped content: retention={preset_preservation_score:.2f}"
                )

        # 6. Overall Pass/Fail Decision
        passed = True
        if req_score < self.min_req_threshold:
            passed = False
        if constraint_score < 1.0:
            passed = False
        if forbidden_score < 1.0:
            passed = False
        if retrieval_recall is not None and retrieval_recall < self.min_retrieval_recall_threshold:
            passed = False
        if preset_preservation_score < 0.95:
            passed = False

        snippet = generated_prompt.strip()[:200] + ("..." if len(generated_prompt.strip()) > 200 else "")

        return CaseEvaluationResult(
            benchmark_id=case.benchmark_id,
            target_agent=target_agent,
            task_type=case.task_type,
            passed=passed,
            requirement_preservation_score=req_score,
            constraint_adherence_score=constraint_score,
            forbidden_assumption_score=forbidden_score,
            retrieval_source_recall=retrieval_recall,
            retrieval_precision=retrieval_precision,
            agent_preset_preservation_score=preset_preservation_score,
            preserved_requirements=preserved_reqs,
            missing_requirements=missing_reqs,
            adhered_constraints=adhered_constraints,
            violated_constraints=violated_constraints,
            detected_forbidden_assumptions=detected_forbidden,
            retrieved_sources=unique_retrieved,
            missing_knowledge_sources=missing_sources,
            unexpected_knowledge_sources=unexpected_sources,
            diagnostics=diagnostics,
            raw_output_snippet=snippet,
        )

    def evaluate_requirements(
        self,
        expected_requirements: list[str],
        prompt: str,
    ) -> tuple[list[str], list[str], float]:
        """Verify presence of expected requirements in the prompt text."""
        if not expected_requirements:
            return [], [], 1.0

        prompt_lower = prompt.lower()
        preserved: list[str] = []
        missing: list[str] = []

        for req in expected_requirements:
            req_clean = req.strip()
            if not req_clean:
                continue

            req_lower = req_clean.lower()
            # 1. Exact phrase substring check
            if req_lower in prompt_lower:
                preserved.append(req_clean)
                continue

            # 2. Token-level presence for multi-word requirements (tokens > 2 chars)
            tokens = [t for t in re.split(r"\W+", req_lower) if len(t) > 2]
            if tokens and all(t in prompt_lower for t in tokens):
                preserved.append(req_clean)
            else:
                missing.append(req_clean)

        score = len(preserved) / len(expected_requirements) if expected_requirements else 1.0
        return preserved, missing, round(score, 4)

    def evaluate_constraints(
        self,
        expected_constraints: list[str],
        prompt: str,
    ) -> tuple[list[str], list[str], float]:
        """Verify that explicit constraints and negative constraints are adhered to."""
        if not expected_constraints:
            return [], [], 1.0

        prompt_lower = prompt.lower()
        adhered: list[str] = []
        violated: list[str] = []

        boundary_markers = [
            "not", "never", "do not", "don't", "must not", "without",
            "constraint", "invariant", "preserve", "keep", "only", "prohibit"
        ]

        for constraint in expected_constraints:
            c_clean = constraint.strip()
            if not c_clean:
                continue

            c_lower = c_clean.lower()

            # 1. Exact substring match
            if c_lower in prompt_lower:
                adhered.append(c_clean)
                continue

            # 2. Key terms + negative boundary presence check
            key_terms = [
                term for term in re.split(r"\W+", c_lower)
                if len(term) > 3 and term not in ["must", "only", "using", "with", "without", "should", "ensure"]
            ]

            has_terms = any(t in prompt_lower for t in key_terms) if key_terms else False
            has_boundary = any(w in prompt_lower for w in boundary_markers)

            if has_terms and has_boundary:
                adhered.append(c_clean)
            else:
                violated.append(c_clean)

        score = len(adhered) / len(expected_constraints) if expected_constraints else 1.0
        return adhered, violated, round(score, 4)

    def evaluate_forbidden_assumptions(
        self,
        forbidden_assumptions: list[str],
        prompt: str,
        project_context: dict[str, Any] | None = None,
    ) -> tuple[list[str], float]:
        """Detect whether forbidden or unsupported assumptions are affirmatively prescribed."""
        if not forbidden_assumptions:
            return [], 1.0

        prompt_lower = prompt.lower()
        detected: list[str] = []

        # Check if project context explicitly permits or contains the term
        allowed_context_text = ""
        if project_context:
            allowed_context_text = " ".join([
                str(project_context.get("description", "")),
                " ".join(project_context.get("technologies", [])),
                " ".join(project_context.get("constraints", [])),
                " ".join(project_context.get("coding_rules", [])),
            ]).lower()

        negation_prefixes = [
            "do not use", "don't use", "never use", "avoid", "without",
            "no external", "prohibit", "not using", "instead of",
        ]

        for forbidden in forbidden_assumptions:
            f_clean = forbidden.strip()
            if not f_clean:
                continue

            f_lower = f_clean.lower()

            # If term is explicitly part of approved project context, it is allowed
            if f_lower in allowed_context_text:
                continue

            # If the term does not appear in the prompt at all, it is safe
            if f_lower not in prompt_lower:
                continue

            # Check if all occurrences appear in negative / constraint contexts
            is_affirmative = False
            # Find all positions of f_lower in prompt_lower
            pos = 0
            while True:
                idx = prompt_lower.find(f_lower, pos)
                if idx == -1:
                    break

                # Extract surrounding window (up to 80 chars before and 40 chars after)
                window_start = max(0, idx - 80)
                window_end = min(len(prompt_lower), idx + len(f_lower) + 40)
                window = prompt_lower[window_start:window_end]

                # Check if this occurrence is negated
                occurrence_negated = any(neg in window for neg in negation_prefixes)
                # Check if it appears inside an open question or decision
                is_open_decision = ("open decision" in window or "?" in window)

                if not (occurrence_negated or is_open_decision):
                    is_affirmative = True
                    break

                pos = idx + len(f_lower)

            if is_affirmative:
                detected.append(f_clean)

        score = 1.0 - (len(detected) / len(forbidden_assumptions)) if forbidden_assumptions else 1.0
        return detected, max(0.0, round(score, 4))

    def evaluate_preset_preservation(
        self,
        raw_compiled_prompt: str,
        formatted_prompt: str,
        expected_requirements: list[str],
        expected_constraints: list[str],
    ) -> float:
        """Measure whether agent formatting preserves requirements and constraints from raw prompt."""
        total_items = 0
        preserved_items = 0

        # Check expected requirements
        for req in expected_requirements:
            req_clean = req.strip()
            if not req_clean:
                continue
            # If it was in raw prompt, it must also be in formatted prompt
            if req_clean.lower() in raw_compiled_prompt.lower():
                total_items += 1
                if req_clean.lower() in formatted_prompt.lower():
                    preserved_items += 1

        # Check expected constraints
        for constraint in expected_constraints:
            c_clean = constraint.strip()
            if not c_clean:
                continue
            if c_clean.lower() in raw_compiled_prompt.lower():
                total_items += 1
                if c_clean.lower() in formatted_prompt.lower():
                    preserved_items += 1

        if total_items == 0:
            return 1.0
        return round(preserved_items / total_items, 4)
