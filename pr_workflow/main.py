import json
import os
import subprocess
import sys
from typing import Dict
from dotenv import load_dotenv
from crewai import Crew, Process

from .agents import build_agents
from .github import build_pr_context_from_url
from .settings import load_settings
from .triage import triage_batches, build_risk_report
from .tasks import (
    triage_task,
    perf_review_task,
    perf_fix_task,
    security_review_task,
    senior_dev_fix_task,
    coverage_review_task,
    coverage_fix_task,
)


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def task_output(task) -> str:
    if hasattr(task, "output") and task.output is not None:
        if hasattr(task.output, "raw"):
            return task.output.raw
        return str(task.output)
    return ""

def run_command(cmd: str) -> str:
    if not cmd:
        return ""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip()
    except Exception as exc:
        return f"Failed to run command: {exc}"


def _is_test_file(path: str) -> bool:
    if not path:
        return False
    norm = path.lower()
    return (
        "/test/" in norm
        or "/tests/" in norm
        or norm.startswith("test_")
        or norm.endswith("_test.py")
        or norm.endswith("_test.js")
        or norm.endswith("_test.ts")
        or norm.endswith("_test.tsx")
        or norm.endswith(".spec.js")
        or norm.endswith(".spec.ts")
        or norm.endswith(".spec.tsx")
    )


def _is_doc_file(path: str) -> bool:
    if not path:
        return False
    norm = path.lower()
    return norm.endswith(".md") or norm.endswith(".mdx")


def _truncate_patch(patch: str, max_lines: int) -> str:
    if not patch:
        return patch
    lines = patch.splitlines()
    if len(lines) <= max_lines:
        return patch
    return "\n".join(lines[:max_lines]) + "\n... [truncated]"


def _strip_patches(files):
    stripped = []
    for f in files:
        if not isinstance(f, dict):
            stripped.append(f)
            continue
        f_copy = dict(f)
        f_copy.pop("patch", None)
        stripped.append(f_copy)
    return stripped


def _post_incremental_comment(reviewer, kind: str, output: str, out_dir: str, batch_id: int, dry_run: bool):
    if not reviewer or not output:
        return
    payload = {}
    if kind == "perf":
        payload["performance_findings"] = output
    elif kind == "security":
        payload["security_findings"] = output
    elif kind == "coverage":
        payload["coverage_review"] = output
    else:
        return

    try:
        write_text(
            os.path.join(out_dir, f"incremental_{kind}_batch_{batch_id}_payload.json"),
            json.dumps(payload, indent=2),
        )
        if dry_run:
            write_text(
                os.path.join(out_dir, f"incremental_{kind}_batch_{batch_id}_dry_run.txt"),
                "Dry run enabled: payload written, no comments posted.",
            )
        else:
            result = reviewer.post_review_comments(payload)
            write_text(
                os.path.join(out_dir, f"incremental_{kind}_batch_{batch_id}.json"),
                json.dumps(result, indent=2),
            )
    except Exception as exc:
        write_text(
            os.path.join(out_dir, f"incremental_{kind}_batch_{batch_id}_error.txt"),
            str(exc),
        )


def run_batch(batch, pr_context, agents, out_dir, perf_config, reviewer=None, incremental_comments=False, dry_run=False) -> Dict:
    batch_id = batch["batch_id"]
    file_index = {f["path"]: f for f in pr_context.get("files", [])}
    batch_files = [file_index.get(p, {"path": p}) for p in batch["files"]]

    if perf_config.skip_test_files:
        batch_files = [f for f in batch_files if not _is_test_file(f.get("path", ""))]

    if perf_config.skip_doc_files:
        batch_files = [f for f in batch_files if not _is_doc_file(f.get("path", ""))]

    if perf_config.max_patch_size > 0:
        for f in batch_files:
            if "patch" in f and isinstance(f["patch"], str):
                f["patch"] = _truncate_patch(f["patch"], perf_config.max_patch_size)

    batch_context = {
        "batch": batch,
        "pr": {
            "id": pr_context.get("id"),
            "title": pr_context.get("title"),
            "description": pr_context.get("description"),
        },
        "files": batch_files,
        "diff_summary": pr_context.get("diff_summary"),
        "test_summary": pr_context.get("test_summary"),
        "ci_summary": pr_context.get("ci_summary"),
    }

    coverage_files = _strip_patches(batch_files) if perf_config.strip_patch_for_coverage else batch_files
    coverage_context = dict(batch_context)
    coverage_context["files"] = coverage_files

    # Debug: print batch context summary
    print(f"\n{'='*60}")
    print(f"Batch {batch_id} Context:")
    print(f"  Files in batch: {len(batch_files)}")
    for f in batch_files[:3]:  # Show first 3
        patch_size = len(f.get('patch', ''))
        print(f"    - {f.get('path')}: {f.get('loc', 0)} LOC, patch: {patch_size} chars")
    print(f"{'='*60}\n")

    # Save batch context for debugging
    batch_context_json = json.dumps(batch_context, indent=2)
    write_text(os.path.join(out_dir, f"batch_{batch_id}_context.json"), batch_context_json)

    perf_review = perf_review_task(agents["perf_engineer"], batch_context_json)
    perf_fix = perf_fix_task(agents["implementer"], perf_review)
    security_review = security_review_task(agents["security_engineer"], batch_context_json)
    senior_fix = senior_dev_fix_task(agents["senior_dev"], security_review)
    coverage_context_json = json.dumps(coverage_context, indent=2)
    coverage_review = coverage_review_task(agents["coverage_agent"], coverage_context_json)
    coverage_fix = coverage_fix_task(agents["implementer"], coverage_review)

    errors = []

    # Run review tasks one-by-one so partial progress can be posted immediately.
    review_steps = [
        ("perf", perf_review, agents["perf_engineer"]),
        ("security", security_review, agents["security_engineer"]),
        ("coverage", coverage_review, agents["coverage_agent"]),
    ]
    review_steps = review_steps[: max(1, perf_config.max_review_agents)]

    for kind, task, agent in review_steps:
        try:
            Crew(agents=[agent], tasks=[task], process=Process.sequential).kickoff()
            if incremental_comments:
                _post_incremental_comment(reviewer, kind, task_output(task), out_dir, batch_id, dry_run)
        except Exception as exc:
            errors.append(f"{kind}_review: {exc}")

    # Run fix tasks only when the corresponding review has output.
    if not perf_config.review_only and task_output(perf_review):
        try:
            Crew(agents=[agents["implementer"]], tasks=[perf_fix], process=Process.sequential).kickoff()
        except Exception as exc:
            errors.append(f"perf_fix: {exc}")

    if not perf_config.review_only and task_output(security_review):
        try:
            Crew(agents=[agents["senior_dev"]], tasks=[senior_fix], process=Process.sequential).kickoff()
        except Exception as exc:
            errors.append(f"security_fix: {exc}")

    if not perf_config.review_only and task_output(coverage_review):
        try:
            Crew(agents=[agents["implementer"]], tasks=[coverage_fix], process=Process.sequential).kickoff()
        except Exception as exc:
            errors.append(f"coverage_fix: {exc}")

    write_text(
        os.path.join(out_dir, f"perf_review_batch_{batch_id}.json"),
        task_output(perf_review),
    )
    write_text(
        os.path.join(out_dir, f"perf_fix_batch_{batch_id}.json"),
        task_output(perf_fix),
    )
    write_text(
        os.path.join(out_dir, f"security_review_batch_{batch_id}.json"),
        task_output(security_review),
    )
    write_text(
        os.path.join(out_dir, f"security_fix_batch_{batch_id}.json"),
        task_output(senior_fix),
    )
    write_text(
        os.path.join(out_dir, f"coverage_review_batch_{batch_id}.json"),
        task_output(coverage_review),
    )
    write_text(
        os.path.join(out_dir, f"coverage_fix_batch_{batch_id}.json"),
        task_output(coverage_fix),
    )
    if errors:
        write_text(
            os.path.join(out_dir, f"batch_{batch_id}_errors.txt"),
            "\n".join(errors),
        )

    # Return all results for potential PR creation
    return {
        "batch_id": batch_id,
        "performance_findings": task_output(perf_review),
        "performance_fixes": task_output(perf_fix),
        "security_findings": task_output(security_review),
        "security_fixes": task_output(senior_fix),
        "solid_notes": task_output(senior_fix),
        "coverage_review": task_output(coverage_review),
        "coverage_fixes": task_output(coverage_fix),
        "errors": errors,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m pr_workflow.main <path_to_pr_context.json|github_pr_url> [OPTIONS]")
        print("")
        print("Options:")
        print("  --comment    : Post AI review as comments on the PR (recommended)")
        print("  --create-pr  : Create a new PR with AI-generated fixes")
        print("  (no flag)    : Save review results to out/ directory only")
        sys.exit(1)

    load_dotenv()
    settings = load_settings()

    # Apply performance optimizations for Ollama
    from .performance_config import PerformanceConfig
    perf_config = PerformanceConfig.from_env()
    perf_config.apply_ollama_settings()

    # Check workflow mode
    comment_mode = "--comment" in sys.argv
    create_pr_flag = "--create-pr" in sys.argv

    if comment_mode:
        sys.argv.remove("--comment")
    if create_pr_flag:
        sys.argv.remove("--create-pr")

    input_arg = sys.argv[1]
    if input_arg.startswith("https://github.com/") and "/pull/" in input_arg:
        pr_context = build_pr_context_from_url(input_arg, settings.github_token or None)
    else:
        pr_context = read_json(input_arg)

    # Debug: print PR context summary
    print(f"\n{'='*60}")
    print(f"PR Context Summary:")
    print(f"  ID: {pr_context.get('id')}")
    print(f"  Title: {pr_context.get('title')}")
    print(f"  Files: {len(pr_context.get('files', []))} file(s)")
    if pr_context.get('files'):
        for f in pr_context.get('files', [])[:5]:  # Show first 5 files
            print(f"    - {f.get('path')}: {f.get('loc', 0)} LOC")
    print(f"{'='*60}\n")

    out_dir = settings.out_dir
    ensure_dir(out_dir)

    # Save PR context for debugging
    write_text(os.path.join(out_dir, "pr_context.json"), json.dumps(pr_context, indent=2))

    files = pr_context.get("files", [])
    triage = triage_batches(files, settings.max_loc_per_batch)
    write_text(os.path.join(out_dir, "triage.json"), json.dumps(triage, indent=2))

    # Debug: print triage summary
    print(f"\n{'='*60}")
    print(f"Triage Summary:")
    print(f"  Total LOC: {triage.get('total_loc')}")
    print(f"  Max LOC per batch: {triage.get('max_loc_per_batch')}")
    print(f"  Number of batches: {len(triage.get('batches', []))}")
    for batch in triage.get('batches', []):
        print(f"    Batch {batch.get('batch_id')}: {len(batch.get('files', []))} files, {batch.get('loc')} LOC")
    print(f"{'='*60}\n")
    risk_report = build_risk_report(files)
    write_text(os.path.join(out_dir, "risk_report.json"), json.dumps(risk_report, indent=2))

    agents = build_agents(settings)

    reviewer = None
    if comment_mode and input_arg.startswith("https://github.com/"):
        from .github_reviewer import GitHubReviewer
        if not settings.github_token:
            print("⚠️  GITHUB_TOKEN is missing; cannot post PR comments.")
        else:
            reviewer = GitHubReviewer(input_arg, settings.github_token)

    # Optional LLM validation of triage output
    triage_validation = triage_task(agents["diff_triage"], json.dumps(triage))
    triage_crew = Crew(
        agents=[agents["diff_triage"]],
        tasks=[triage_validation],
        process=Process.sequential,
    )
    triage_crew.kickoff()
    write_text(
        os.path.join(out_dir, "triage_validation.json"),
        task_output(triage_validation),
    )

    # Collect all batch results
    all_results = []
    for batch in triage["batches"]:
        batch_result = run_batch(
            batch,
            pr_context,
            agents,
            out_dir,
            perf_config,
            reviewer=reviewer,
            incremental_comments=settings.incremental_comments,
            dry_run=settings.dry_run_comments,
        )
        all_results.append(batch_result)

    if settings.test_cmd:
        test_output = run_command(settings.test_cmd)
        if test_output:
            write_text(os.path.join(out_dir, "tests_run.txt"), test_output)
    if settings.coverage_cmd:
        coverage_output = run_command(settings.coverage_cmd)
        if coverage_output:
            write_text(os.path.join(out_dir, "coverage_run.txt"), coverage_output)

    # Aggregate results for GitHub operations
    aggregated_results = None
    if (comment_mode or create_pr_flag) and input_arg.startswith("https://github.com/"):
        aggregated_results = {
            "performance_findings": {},
            "performance_fixes": {},
            "security_findings": {},
            "security_fixes": {},
            "solid_notes": {},
            "coverage_review": {},
            "coverage_fixes": {}
        }

        for result in all_results:
            for key in aggregated_results.keys():
                if result.get(key):
                    try:
                        data = result[key] if isinstance(result[key], dict) else result[key]
                        if key not in aggregated_results or not aggregated_results[key]:
                            aggregated_results[key] = data
                        else:
                            # Merge findings/changes
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    if isinstance(v, list):
                                        aggregated_results[key].setdefault(k, []).extend(v)
                    except (json.JSONDecodeError, TypeError):
                        pass

    # Post review comments on PR if requested
    if comment_mode and input_arg.startswith("https://github.com/") and settings.post_summary_comment:
        print("\n" + "="*60)
        print("Posting AI Review Comments on PR...")
        print("="*60 + "\n")

        try:
            result = reviewer.post_review_comments(aggregated_results)
            if result.get("review_id"):
                print(f"\n✅ Successfully posted review with {result['comments_posted']} comments\n")
                write_text(os.path.join(out_dir, "review_posted.json"), json.dumps(result, indent=2))
            else:
                print("\nℹ️  Review posted as a single comment (inline comments may have failed)\n")
        except Exception as e:
            print(f"\n❌ Failed to post review comments: {e}\n")
            import traceback
            traceback.print_exc()

    # Create PR with fixes if requested
    if create_pr_flag and input_arg.startswith("https://github.com/"):
        print("\n" + "="*60)
        print("Creating Pull Request with AI Review Fixes...")
        print("="*60 + "\n")

        from .github_pr_creator import GitHubPRCreator

        pr_creator = GitHubPRCreator(input_arg, settings.github_token)
        try:
            pr_url = pr_creator.create_review_pr(aggregated_results)
            if pr_url:
                print(f"\n✅ Successfully created PR: {pr_url}\n")
                write_text(os.path.join(out_dir, "created_pr_url.txt"), pr_url)
            else:
                print("\nℹ️  No changes to apply. PR not created.\n")
        except Exception as e:
            print(f"\n❌ Failed to create PR: {e}\n")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
