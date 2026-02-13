from crewai import Task


def triage_task(agent, pr_context):
    return Task(
        description=(
            f"Analyze the PR context and confirm the proposed diff batches. "
            f"If the provided batches violate max LOC, adjust them. "
            f"Return JSON only.\n\n"
            f"PR CONTEXT:\n{pr_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: total_loc, max_loc_per_batch, batches[], triage_notes[]. "
            "Each batch includes batch_id, files[], loc, notes."
        ),
    )


def perf_review_task(agent, batch_context):
    return Task(
        description=(
            f"Review this batch for performance risks. Focus on algorithmic complexity, "
            f"hot paths, I/O, caching, and data access. Return JSON only.\n\n"
            f"BATCH CONTEXT:\n{batch_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: findings[]. Each finding has file, line, severity, "
            "issue, suggested_change, test_hint."
        ),
    )


def perf_fix_task(agent, perf_review):
    return Task(
        description=(
            "Implement the performance fixes from the review. Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, notes."
        ),
        context=[perf_review],
    )


def security_review_task(agent, batch_context):
    return Task(
        description=(
            f"Review for security risks. Focus on authn/authz, validation, SSRF/SQLi/IDOR, "
            f"secrets handling, config. Return JSON only.\n\n"
            f"BATCH CONTEXT:\n{batch_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: findings[]. Each finding has file, line, severity, "
            "issue, suggested_change, test_hint."
        ),
    )


def senior_dev_fix_task(agent, security_review):
    return Task(
        description=(
            "Implement security fixes and ensure SOLID principles. "
            "If a change violates SOLID or DRY, refactor. "
            "Explicitly report any SOLID/DRY violations found. Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, solid_notes[]. "
            "solid_notes[] entries must include: principle (SRP/OCP/LSP/ISP/DIP/DRY), "
            "file, line, issue, fix."
        ),
        context=[security_review],
    )


def coverage_review_task(agent, coverage_context):
    return Task(
        description=(
            f"Check whether unit test coverage is >= 80%. Identify missing tests. "
            f"Return JSON only.\n\n"
            f"COVERAGE CONTEXT:\n{coverage_context}"
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: coverage_percent, missing_tests[], suggested_tests[]."
        ),
    )


def coverage_fix_task(agent, coverage_review):
    return Task(
        description=(
            "Implement tests to reach >= 80% coverage. Return JSON only."
        ),
        agent=agent,
        expected_output=(
            "JSON with fields: changes[], files_touched[], tests_run, notes."
        ),
        context=[coverage_review],
    )
