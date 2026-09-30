"""
CrewAI agent definitions with multi-provider support.
"""
from crewai import Agent

from .providers import llm_factory
from .settings import Settings


def build_agents(settings: Settings) -> dict[str, Agent]:
    """
    Build all review agents with appropriate LLMs.
    
    Args:
        settings: Application settings
        
    Returns:
        Dictionary of agent name -> Agent instance
    """
    # Get LLMs from factory (supports multiple providers)
    reviewer_llm = llm_factory.get_reviewer_llm()
    implementer_llm = llm_factory.get_implementer_llm()
    fast_llm = llm_factory.get_fast_llm()
    
    # Use reviewer LLM for all if configured
    if settings.use_deepseek_only:
        print("⚡ Performance Mode: Using single model for all agents")
        implementer_llm = reviewer_llm
        fast_llm = reviewer_llm

    diff_triage = Agent(
        role="Diff Triage Agent",
        goal=(
            "Split PR diffs into sequential review batches (<= max LOC). "
            "Group related files and tests together. Prioritize high-risk files."
        ),
        backstory=(
            "You are a careful release manager who ensures large PRs are reviewed "
            "in safe, coherent batches. You understand code dependencies and "
            "prioritize security-sensitive and performance-critical files."
        ),
        llm=fast_llm,
        verbose=True,
    )

    perf_engineer = Agent(
        role="Performance Engineer",
        goal=(
            "Review code for performance risks and propose measurable improvements. "
            "Focus on algorithmic complexity, memory usage, I/O patterns, and caching opportunities."
        ),
        backstory=(
            "You are a senior performance engineer who optimizes latency, throughput, "
            "memory use, and algorithmic complexity. You've profiled thousands of applications "
            "and know the common performance pitfalls in every language."
        ),
        llm=reviewer_llm,
        verbose=True,
    )

    security_engineer = Agent(
        role="Cyber Security Engineer",
        goal=(
            "Find security vulnerabilities and propose fixes with test cases. "
            "Focus on OWASP Top 10, authentication, authorization, and data validation."
        ),
        backstory=(
            "You are a security researcher who specializes in threat modeling, "
            "authz/authn, input validation, SSRF/SQLi/IDOR, secrets handling, "
            "and misconfigurations. You've found vulnerabilities in major systems "
            "and know how attackers think."
        ),
        llm=reviewer_llm,
        verbose=True,
    )

    senior_dev = Agent(
        role="Senior Developer",
        goal=(
            "Implement fixes, ensure correctness, and enforce SOLID and DRY principles. "
            "Refactor code that violates clean code principles."
        ),
        backstory=(
            "You are a pragmatic senior engineer with 15+ years of experience. "
            "You insist on SOLID design: Single Responsibility, Open/Closed, "
            "Liskov Substitution, Interface Segregation, and Dependency Inversion. "
            "You also enforce DRY (Don't Repeat Yourself) to eliminate duplication. "
            "You write clean, maintainable, well-tested code."
        ),
        llm=implementer_llm,
        verbose=True,
    )

    coverage_agent = Agent(
        role="Coverage Auditor",
        goal=(
            "Ensure unit test coverage is >= 80% and propose missing tests. "
            "Focus on edge cases, error handling, and critical code paths."
        ),
        backstory=(
            "You are a QA engineer who validates test coverage with a focus on "
            "risky code paths. You understand that good tests are documentation "
            "and prevent regressions. You know the testing patterns for every language."
        ),
        llm=reviewer_llm,
        verbose=True,
    )

    implementer = Agent(
        role="Implementation Engineer",
        goal=(
            "Apply review feedback with minimal, correct code changes and tests. "
            "Ensure all changes are backwards compatible and well-documented."
        ),
        backstory=(
            "You are a reliable engineer focused on safe, well-tested patches. "
            "You make the smallest possible changes to fix issues while maintaining "
            "code quality. You always add tests for your changes."
        ),
        llm=implementer_llm,
        verbose=True,
    )

    return {
        "diff_triage": diff_triage,
        "perf_engineer": perf_engineer,
        "security_engineer": security_engineer,
        "senior_dev": senior_dev,
        "coverage_agent": coverage_agent,
        "implementer": implementer,
    }
