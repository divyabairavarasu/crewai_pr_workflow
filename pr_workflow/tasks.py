"""
CrewAI task definitions with structured output support.
"""
from crewai import Task

from .models import (
    PerformanceReview,
    SecurityReview,
    CoverageReview,
    FixResult,
    TriageResult,
)


def triage_task(agent, pr_context: str) -> Task:
    """Create a triage task for splitting PR into batches."""
    return Task(
        description=(
            f"Analyze the PR context and confirm the proposed diff batches. "
            f"If the provided batches violate max LOC, adjust them. "
            f"Group related files together (e.g., source + tests). "
            f"Prioritize high-risk files (auth, security, database). "
            f"Return JSON only.\n\n"
            f"PR CONTEXT:\n{pr_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: total_loc, max_loc_per_batch, batches[], triage_notes[]. "
            "Each batch includes batch_id, files[], loc, notes."
        ),
        output_json=TriageResult,
    )


def perf_review_task(agent, batch_context: str) -> Task:
    """Create a performance review task."""
    return Task(
        description=(
            f"Review this batch for performance risks. Focus on:\n"
            f"- Algorithmic complexity (O(n²), O(n³) patterns)\n"
            f"- Hot paths and tight loops\n"
            f"- I/O operations (disk, network, database)\n"
            f"- Memory allocation patterns\n"
            f"- Caching opportunities\n"
            f"- Unnecessary computations\n\n"
            f"Return JSON only.\n\n"
            f"BATCH CONTEXT:\n{batch_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: findings[], summary, estimated_impact. "
            "Each finding has file, line, severity, category, issue, suggested_change, test_hint, confidence."
        ),
        output_json=PerformanceReview,
    )


def perf_fix_task(agent, perf_review: Task) -> Task:
    """Create a performance fix implementation task."""
    return Task(
        description=(
            "Implement the performance fixes from the review. "
            "Make minimal, targeted changes. Add benchmarks or tests where appropriate. "
            "Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, notes."
        ),
        context=[perf_review],
        output_json=FixResult,
    )


def security_review_task(agent, batch_context: str) -> Task:
    """Create a security review task."""
    return Task(
        description=(
            f"Review for security vulnerabilities. Focus on:\n"
            f"- Authentication and authorization flaws\n"
            f"- Input validation (SQLi, XSS, command injection)\n"
            f"- SSRF, IDOR, path traversal\n"
            f"- Secrets and credential handling\n"
            f"- Cryptographic issues\n"
            f"- Configuration security\n"
            f"- OWASP Top 10 vulnerabilities\n\n"
            f"Return JSON only.\n\n"
            f"BATCH CONTEXT:\n{batch_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: findings[], summary, risk_level, cve_references[]. "
            "Each finding has file, line, severity, category, issue, suggested_change, test_hint, confidence."
        ),
        output_json=SecurityReview,
    )


def senior_dev_fix_task(agent, security_review: Task) -> Task:
    """Create a senior developer fix task with SOLID enforcement."""
    return Task(
        description=(
            "Implement security fixes and ensure SOLID principles. "
            "If a change violates SOLID or DRY, refactor. "
            "Explicitly report any SOLID/DRY violations found:\n"
            "- SRP: Single Responsibility Principle\n"
            "- OCP: Open/Closed Principle\n"
            "- LSP: Liskov Substitution Principle\n"
            "- ISP: Interface Segregation Principle\n"
            "- DIP: Dependency Inversion Principle\n"
            "- DRY: Don't Repeat Yourself\n\n"
            "Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, solid_notes[]. "
            "solid_notes[] entries must include: principle (SRP/OCP/LSP/ISP/DIP/DRY), "
            "file, line, issue, fix."
        ),
        context=[security_review],
        output_json=FixResult,
    )


def coverage_review_task(agent, coverage_context: str) -> Task:
    """Create a test coverage review task."""
    return Task(
        description=(
            f"Check whether unit test coverage is >= 80%. Identify:\n"
            f"- Missing test files\n"
            f"- Untested functions/methods\n"
            f"- Missing edge case tests\n"
            f"- Missing error handling tests\n"
            f"- Missing integration tests for critical paths\n\n"
            f"Return JSON only.\n\n"
            f"COVERAGE CONTEXT:\n{coverage_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: coverage_percent, missing_tests[], suggested_tests[], summary."
        ),
        output_json=CoverageReview,
    )


def coverage_fix_task(agent, coverage_review: Task) -> Task:
    """Create a test coverage fix task."""
    return Task(
        description=(
            "Implement tests to reach >= 80% coverage. "
            "Focus on critical paths and edge cases. "
            "Use appropriate testing patterns for the language. "
            "Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, notes."
        ),
        context=[coverage_review],
        output_json=FixResult,
    )


def complexity_review_task(agent, batch_context: str) -> Task:
    """Create a code complexity review task."""
    return Task(
        description=(
            f"Analyze code complexity and maintainability. Focus on:\n"
            f"- Cyclomatic complexity (flag functions > 10)\n"
            f"- Cognitive complexity\n"
            f"- Function/method length (flag > 50 lines)\n"
            f"- Class size and responsibilities\n"
            f"- Nesting depth (flag > 4 levels)\n"
            f"- Code duplication\n\n"
            f"Return JSON only.\n\n"
            f"BATCH CONTEXT:\n{batch_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: findings[], summary. "
            "Each finding has file, line, severity, issue, suggested_change."
        ),
    )
