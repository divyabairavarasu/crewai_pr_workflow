from crewai import Agent, LLM
from .settings import Settings


def build_llms(settings: Settings):
    deepseek = LLM(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.1,
        max_tokens=2048,
    )

    implementer_llm = LLM(
        model=settings.implementer_model,
        api_key=settings.implementer_api_key,
        base_url=settings.implementer_base_url or None,
        temperature=0.1,
        max_tokens=2048,
    )

    return deepseek, implementer_llm


def build_agents(settings: Settings):
    deepseek, implementer_llm = build_llms(settings)

    # Performance optimization: Use DeepSeek for all agents if configured
    if settings.use_deepseek_only:
        print("⚡ Performance Mode: Using DeepSeek for all agents (Ollama disabled)")
        implementer_llm = deepseek

    diff_triage = Agent(
        role="Diff Triage Agent",
        goal=(
            "Split PR diffs into sequential review batches (<= max LOC). "
            "Group related files and tests together."
        ),
        backstory=(
            "You are a careful release manager who ensures large PRs are reviewed "
            "in safe, coherent batches."
        ),
        llm=deepseek,
        verbose=True,
    )

    perf_engineer = Agent(
        role="Performance Engineer",
        goal=(
            "Review code for performance risks and propose measurable improvements."
        ),
        backstory=(
            "You optimize latency, throughput, memory use, and algorithmic complexity."
        ),
        llm=deepseek,
        verbose=True,
    )

    security_engineer = Agent(
        role="Cyber Security Engineer",
        goal="Find security risks and propose fixes and tests.",
        backstory=(
            "You specialize in threat modeling, authz/authn, input validation, "
            "SSRF/SQLi/IDOR, secrets handling, and misconfigurations."
        ),
        llm=deepseek,
        verbose=True,
    )

    senior_dev = Agent(
        role="Senior Developer",
        goal=(
            "Implement fixes, ensure correctness, and enforce SOLID and DRY principles."
        ),
        backstory=(
            "You are a pragmatic senior engineer who insists on SOLID design: "
            "Single Responsibility, Open/Closed, Liskov Substitution, "
            "Interface Segregation, and Dependency Inversion. "
            "You also enforce DRY (Don't Repeat Yourself) to eliminate duplication."
        ),
        llm=implementer_llm,
        verbose=True,
    )

    coverage_agent = Agent(
        role="Coverage Auditor",
        goal=(
            "Ensure unit test coverage is >= 80% and propose missing tests."
        ),
        backstory=(
            "You validate test coverage with a focus on risky code paths."
        ),
        llm=deepseek,
        verbose=True,
    )

    implementer = Agent(
        role="Implementation Engineer",
        goal=(
            "Apply review feedback with minimal, correct code changes and tests."
        ),
        backstory=(
            "You are a reliable engineer focused on safe, well-tested patches."
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
