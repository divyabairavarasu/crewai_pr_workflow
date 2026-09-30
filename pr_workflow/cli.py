"""
Rich CLI for CrewAI PR Review Workflow.
Provides beautiful terminal output with progress bars and formatted results.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown

from dotenv import load_dotenv

app = typer.Typer(
    name="pr-review",
    help="AI-powered PR review using CrewAI multi-agent system",
    add_completion=False,
)
console = Console()


def print_banner():
    """Print the application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║     🤖 CrewAI PR Review Workflow v2.0                     ║
    ║     Multi-Agent Code Review System                        ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


def print_config_table(config: dict):
    """Print configuration as a table."""
    table = Table(title="Configuration", show_header=True, header_style="bold magenta")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in config.items():
        # Mask API keys
        if "key" in key.lower() or "token" in key.lower():
            value = "***" + str(value)[-4:] if value else "Not set"
        table.add_row(key, str(value))
    
    console.print(table)


def print_findings_table(findings: list, title: str = "Findings"):
    """Print findings as a formatted table."""
    if not findings:
        console.print(f"[green]✓ No {title.lower()} found[/green]")
        return
    
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Severity", style="bold", width=10)
    table.add_column("File", style="cyan", width=30)
    table.add_column("Line", justify="right", width=6)
    table.add_column("Issue", style="white", width=50)
    
    severity_colors = {
        "critical": "red bold",
        "high": "red",
        "medium": "yellow",
        "low": "green",
        "info": "blue",
    }
    
    for finding in findings:
        severity = finding.get("severity", "medium").lower()
        color = severity_colors.get(severity, "white")
        table.add_row(
            f"[{color}]{severity.upper()}[/{color}]",
            finding.get("file", "unknown")[:30],
            str(finding.get("line", "?")),
            finding.get("issue", "No description")[:50],
        )
    
    console.print(table)


@app.command()
def review(
    target: str = typer.Argument(
        ...,
        help="GitHub PR URL or path to pr_context.json file",
    ),
    comment: bool = typer.Option(
        False,
        "--comment",
        "-c",
        help="Post review comments on the PR",
    ),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        "-p",
        help="Create a new PR with AI-generated fixes",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-d",
        help="Run without posting comments (save to files only)",
    ),
    output_dir: str = typer.Option(
        "out",
        "--output",
        "-o",
        help="Output directory for review artifacts",
    ),
    max_loc: int = typer.Option(
        2000,
        "--max-loc",
        "-l",
        help="Maximum lines of code per review batch",
    ),
    review_only: bool = typer.Option(
        False,
        "--review-only",
        "-r",
        help="Skip fix generation, only run reviews",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
):
    """
    Run AI-powered code review on a GitHub PR or local context file.
    
    Examples:
    
        # Review a GitHub PR and post comments
        pr-review https://github.com/owner/repo/pull/123 --comment
        
        # Dry run (no comments posted)
        pr-review https://github.com/owner/repo/pull/123 --dry-run
        
        # Review from local context file
        pr-review examples/pr_context.json
        
        # Create a PR with fixes
        pr-review https://github.com/owner/repo/pull/123 --create-pr
    """
    load_dotenv()
    print_banner()
    
    # Set environment variables from CLI options
    os.environ["OUT_DIR"] = output_dir
    os.environ["MAX_LOC_PER_BATCH"] = str(max_loc)
    os.environ["REVIEW_ONLY"] = str(review_only).lower()
    os.environ["DRY_RUN_COMMENTS"] = str(dry_run).lower()
    
    # Import here to avoid circular imports and allow env vars to be set first
    from .settings import load_settings
    from .performance_config import PerformanceConfig
    from .github import build_pr_context_from_url
    from .triage import triage_batches, build_risk_report
    from .agents import build_agents
    from .main import run_batch, ensure_dir, write_text
    
    settings = load_settings()
    perf_config = PerformanceConfig.from_env()
    
    # Show configuration
    if verbose:
        print_config_table({
            "Target": target,
            "Output Directory": output_dir,
            "Max LOC per Batch": max_loc,
            "Review Only": review_only,
            "Dry Run": dry_run,
            "Reviewer Model": os.getenv("REVIEWER_MODEL", "deepseek-reasoner"),
            "Implementer Model": os.getenv("IMPLEMENTER_MODEL", "gpt-4o-mini"),
        })
    
    # Load PR context
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading PR context...", total=None)
        
        if target.startswith("https://github.com/") and "/pull/" in target:
            pr_context = build_pr_context_from_url(target, settings.github_token or None)
        else:
            with open(target, "r", encoding="utf-8") as f:
                pr_context = json.load(f)
        
        progress.update(task, completed=True)
    
    # Display PR info
    console.print(Panel(
        f"[bold]PR #{pr_context.get('id')}[/bold]: {pr_context.get('title', 'Untitled')}\n\n"
        f"[dim]{pr_context.get('description', 'No description')[:200]}...[/dim]",
        title="Pull Request",
        border_style="blue",
    ))
    
    # Show files
    files = pr_context.get("files", [])
    console.print(f"\n[bold]Files to review:[/bold] {len(files)}")
    
    file_table = Table(show_header=True, header_style="bold")
    file_table.add_column("File", style="cyan")
    file_table.add_column("LOC", justify="right")
    file_table.add_column("Status")
    
    for f in files[:10]:  # Show first 10
        file_table.add_row(
            f.get("path", "unknown")[:50],
            str(f.get("loc", 0)),
            f.get("status", "modified"),
        )
    
    if len(files) > 10:
        file_table.add_row("...", "...", f"+{len(files) - 10} more")
    
    console.print(file_table)
    
    # Triage
    ensure_dir(output_dir)
    triage = triage_batches(files, max_loc)
    
    console.print(f"\n[bold]Triage:[/bold] {len(triage['batches'])} batch(es), {triage['total_loc']} total LOC")
    
    # Build risk report
    risk_report = build_risk_report(files)
    write_text(os.path.join(output_dir, "risk_report.json"), json.dumps(risk_report, indent=2))
    
    # Show high-risk files
    high_risk = [f for f in risk_report.get("files", []) if f.get("risk_score", 0) > 0]
    if high_risk:
        console.print("\n[bold yellow]⚠️ High-risk files detected:[/bold yellow]")
        for f in high_risk[:5]:
            console.print(f"  • {f['path']} (risk: {f['risk_score']}, keywords: {', '.join(f['risk_keywords'])})")
    
    # Build agents
    console.print("\n[bold]Initializing AI agents...[/bold]")
    agents = build_agents(settings)
    
    # Setup reviewer for GitHub comments
    reviewer = None
    if (comment or dry_run) and target.startswith("https://github.com/"):
        from .github_reviewer import GitHubReviewer
        if settings.github_token:
            reviewer = GitHubReviewer(target, settings.github_token)
        else:
            console.print("[yellow]⚠️ GITHUB_TOKEN not set, cannot post comments[/yellow]")
    
    # Run reviews
    all_results = []
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        review_task = progress.add_task(
            "Running AI review...",
            total=len(triage["batches"]),
        )
        
        for batch in triage["batches"]:
            progress.update(
                review_task,
                description=f"Reviewing batch {batch['batch_id']}/{len(triage['batches'])}...",
            )
            
            batch_result = run_batch(
                batch,
                pr_context,
                agents,
                output_dir,
                perf_config,
                reviewer=reviewer if not dry_run else None,
                incremental_comments=settings.incremental_comments,
                dry_run=dry_run,
            )
            all_results.append(batch_result)
            
            progress.advance(review_task)
    
    # Display results
    console.print("\n" + "=" * 60)
    console.print("[bold green]✓ Review Complete[/bold green]")
    console.print("=" * 60 + "\n")
    
    # Aggregate and display findings
    all_findings = {
        "performance": [],
        "security": [],
        "coverage": [],
    }
    
    for result in all_results:
        # Parse JSON outputs
        for key, category in [
            ("performance_findings", "performance"),
            ("security_findings", "security"),
            ("coverage_review", "coverage"),
        ]:
            raw = result.get(key, "")
            if raw:
                try:
                    data = json.loads(raw) if isinstance(raw, str) else raw
                    findings = data.get("findings", []) or data.get("missing_tests", [])
                    if isinstance(findings, list):
                        for f in findings:
                            if isinstance(f, str):
                                all_findings[category].append({"file": f, "issue": "Missing test coverage"})
                            else:
                                all_findings[category].append(f)
                except json.JSONDecodeError:
                    pass
    
    # Print findings tables
    print_findings_table(all_findings["performance"], "⚡ Performance Findings")
    console.print()
    print_findings_table(all_findings["security"], "🔒 Security Findings")
    console.print()
    print_findings_table(all_findings["coverage"], "🧪 Coverage Findings")
    
    # Summary
    total_findings = sum(len(f) for f in all_findings.values())
    console.print(Panel(
        f"[bold]Total Findings:[/bold] {total_findings}\n"
        f"  • Performance: {len(all_findings['performance'])}\n"
        f"  • Security: {len(all_findings['security'])}\n"
        f"  • Coverage: {len(all_findings['coverage'])}\n\n"
        f"[dim]Results saved to: {output_dir}/[/dim]",
        title="Summary",
        border_style="green",
    ))
    
    # Post summary comment if requested
    if comment and reviewer and settings.post_summary_comment:
        console.print("\n[bold]Posting review to GitHub...[/bold]")
        try:
            # Aggregate results for posting
            aggregated = {
                "performance_findings": {"findings": all_findings["performance"]},
                "security_findings": {"findings": all_findings["security"]},
                "coverage_review": {"missing_tests": all_findings["coverage"]},
            }
            result = reviewer.post_review_comments(aggregated)
            console.print(f"[green]✓ Posted review with {result.get('comments_posted', 0)} comments[/green]")
        except Exception as e:
            console.print(f"[red]✗ Failed to post review: {e}[/red]")
    
    # Create PR with fixes if requested
    if create_pr and target.startswith("https://github.com/"):
        console.print("\n[bold]Creating PR with fixes...[/bold]")
        from .github_pr_creator import GitHubPRCreator
        
        try:
            pr_creator = GitHubPRCreator(target, settings.github_token)
            # Aggregate fix results
            aggregated_fixes = {}
            for result in all_results:
                for key in ["performance_fixes", "security_fixes", "coverage_fixes"]:
                    if result.get(key):
                        aggregated_fixes[key] = result[key]
            
            pr_url = pr_creator.create_review_pr(aggregated_fixes)
            if pr_url:
                console.print(f"[green]✓ Created PR: {pr_url}[/green]")
            else:
                console.print("[yellow]No changes to apply[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ Failed to create PR: {e}[/red]")


@app.command()
def providers():
    """List available LLM providers and models."""
    from .providers import PROVIDER_CONFIGS
    
    print_banner()
    
    table = Table(title="Available LLM Providers", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Model")
    table.add_column("Best For")
    
    best_for = {
        "deepseek-reasoner": "Complex reasoning, code review",
        "deepseek-chat": "General tasks, fast",
        "gpt-4o": "High quality, balanced",
        "gpt-4o-mini": "Fast, cost-effective",
        "o1": "Deep reasoning",
        "o3-mini": "Reasoning, cost-effective",
        "claude-sonnet": "Code generation, analysis",
        "claude-haiku": "Fast, simple tasks",
        "llama-3.3-70b": "Free, high quality",
        "llama-3.1-8b": "Free, very fast",
        "mixtral-8x7b": "Free, balanced",
        "qwen2.5-coder": "Local, code-focused",
        "codellama": "Local, code generation",
        "deepseek-coder-v2": "Local, code review",
    }
    
    for name, config in PROVIDER_CONFIGS.items():
        table.add_row(
            name,
            config.provider.value,
            config.model,
            best_for.get(name, "General"),
        )
    
    console.print(table)
    
    console.print("\n[bold]Usage:[/bold]")
    console.print("  Set REVIEWER_MODEL=<name> to use a pre-configured provider")
    console.print("  Example: REVIEWER_MODEL=claude-sonnet pr-review <url>")


@app.command()
def version():
    """Show version information."""
    console.print("[bold]CrewAI PR Review Workflow[/bold] v2.0.0")
    console.print("https://github.com/divyabairavarasu/crewai_pr_workflow")


if __name__ == "__main__":
    app()
