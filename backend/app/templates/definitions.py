"""Concrete task-type prompt template definitions for Prompt Compiler."""

from app.templates.base import PromptTemplate


class BuildTemplate(PromptTemplate):
    """Template for greenfield feature construction, component building, and new systems."""

    @property
    def name(self) -> str:
        return "Build Template"

    @property
    def task_type(self) -> str:
        return "build"

    @property
    def description(self) -> str:
        return "Structured specification for greenfield systems, new features, and application components."

    @property
    def sections(self) -> list[str]:
        return [
            "Objective",
            "Technical Domain & Context",
            "Confirmed Requirements",
            "Constraints",
            "Open Decisions & Missing Information",
            "Safe Assumptions",
            "Implementation Instructions",
            "Expected Outcome",
        ]

    def get_structure_guidance(self) -> str:
        return """# Objective
[Concise summary of the build goal]

# Technical Domain & Context
[Domain context, application type, and environment]

# Confirmed Requirements
[Explicit user-provided requirements and verified technologies]

# Constraints
[Explicit boundaries, negative constraints, and non-negotiables]

# Open Decisions & Missing Information
[Critical unknown architectural or design decisions that must not be hallucinated]

# Safe Assumptions
[Conservative operational interpretations that do not alter core requirements]

# Implementation Instructions
[Systematic steps and guidelines for building the requested feature]

# Expected Outcome
[Verifiable criteria for determining successful delivery]"""


class ModifyTemplate(PromptTemplate):
    """Template for refactoring, updating existing codebases, and implementing modifications."""

    @property
    def name(self) -> str:
        return "Modify Template"

    @property
    def task_type(self) -> str:
        return "modify"

    @property
    def description(self) -> str:
        return "Structured specification for refactoring, behavior updates, and modifying existing code."

    @property
    def sections(self) -> list[str]:
        return [
            "Objective",
            "Target System & Existing Context",
            "Requested Modifications",
            "Constraints & Invariants",
            "Open Decisions & Missing Information",
            "Safe Assumptions",
            "Expected Outcome",
        ]

    def get_structure_guidance(self) -> str:
        return """# Objective
[Summary of the modification or refactor objective]

# Target System & Existing Context
[Description of the existing codebase, component, or system being modified]

# Requested Modifications
[Itemized list of required code or structural changes]

# Constraints & Invariants
[Existing behaviors, APIs, or files that must be strictly preserved]

# Open Decisions & Missing Information
[Gaps in existing architecture or unresolved change specifications]

# Safe Assumptions
[Conservative assumptions that do not conflict with existing invariants]

# Expected Outcome
[Criteria verifying the modifications are successfully applied without regressions]"""


class DebugTemplate(PromptTemplate):
    """Template for isolating bugs, fixing errors, and resolving crashes."""

    @property
    def name(self) -> str:
        return "Debug Template"

    @property
    def task_type(self) -> str:
        return "debug"

    @property
    def description(self) -> str:
        return "Structured specification for diagnosing issues, fixing bugs, and troubleshooting failures."

    @property
    def sections(self) -> list[str]:
        return [
            "Problem Summary",
            "Context & Observed Behavior",
            "Expected Behavior",
            "Constraints",
            "Diagnostic Gaps & Missing Information",
            "Debugging & Resolution Steps",
        ]

    def get_structure_guidance(self) -> str:
        return """# Problem Summary
[Concise statement of the defect or bug being addressed]

# Context & Observed Behavior
[Symptom details, stack traces, failure modes, and reproduction context]

# Expected Behavior
[Desired correct behavior when the issue is resolved]

# Constraints
[Fix boundaries, e.g. no breaking changes, no new heavy dependencies]

# Diagnostic Gaps & Missing Information
[Missing logs, environment variables, or reproduction reproduction steps needed]

# Debugging & Resolution Steps
[Structured procedure for root-cause isolation, verification, and regression prevention]"""


class ExplainTemplate(PromptTemplate):
    """Template for technical explanations, code walkthroughs, and architectural clarifications."""

    @property
    def name(self) -> str:
        return "Explain Template"

    @property
    def task_type(self) -> str:
        return "explain"

    @property
    def description(self) -> str:
        return "Structured framework for technical explanations, system walkthroughs, and conceptual deep dives."

    @property
    def sections(self) -> list[str]:
        return [
            "Topic & Objective",
            "Context & Scope",
            "Confirmed Questions / Requirements",
            "Constraints & Audience",
            "Explanation Structure",
        ]

    def get_structure_guidance(self) -> str:
        return """# Topic & Objective
[The primary subject or technical mechanism to be explained]

# Context & Scope
[Background context and explicit boundaries of what is within scope]

# Confirmed Questions / Requirements
[Explicit questions or concepts requested by the user]

# Constraints & Audience
[Target audience expertise level, format limits, or tone constraints]

# Explanation Structure
[Systematic walkthrough: core concepts, mechanisms, code examples, and trade-offs]"""


class AnalyzeTemplate(PromptTemplate):
    """Template for code audits, performance evaluations, and architectural assessments."""

    @property
    def name(self) -> str:
        return "Analyze Template"

    @property
    def task_type(self) -> str:
        return "analyze"

    @property
    def description(self) -> str:
        return "Structured framework for code reviews, architecture critiques, and security/performance audits."

    @property
    def sections(self) -> list[str]:
        return [
            "Analysis Subject",
            "Evaluation Scope & Goals",
            "Confirmed Requirements & Focus Areas",
            "Constraints & Standards",
            "Information Gaps",
            "Analysis Requirements & Criteria",
        ]

    def get_structure_guidance(self) -> str:
        return """# Analysis Subject
[The system, module, or architecture being evaluated]

# Evaluation Scope & Goals
[Target outcomes: e.g. performance bottleneck detection, security audit, maintainability]

# Confirmed Requirements & Focus Areas
[Explicit areas requested for investigation]

# Constraints & Standards
[Evaluation benchmarks, coding guidelines, or organizational standards]

# Information Gaps
[Missing metrics, benchmark results, or architectural blueprints]

# Analysis Requirements & Criteria
[Required reporting format, severity scoring, and actionable recommendations]"""
