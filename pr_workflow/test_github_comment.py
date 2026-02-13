import argparse
import json
import os
import urllib.request
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM

from .settings import load_settings


def _parse_pr_url(pr_url: str):
    parts = pr_url.replace("https://github.com/", "").split("/")
    if len(parts) < 4 or parts[2] != "pull":
        raise ValueError(
            "Invalid PR URL. Expected https://github.com/<org>/<repo>/pull/<num>."
        )
    return parts[0], parts[1], parts[3]


def _post_issue_comment(pr_url: str, token: str, body: str) -> dict:
    owner, repo, pr_number = _parse_pr_url(pr_url)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    payload = json.dumps({"body": body}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "crewai-pr-workflow",
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _build_deepseek_comment(settings) -> str:
    llm = LLM(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.0,
        max_tokens=128,
    )

    agent = Agent(
        role="DeepSeek Comment Agent",
        goal="Return a short PR comment body.",
        backstory="You produce concise, exact comment text for PRs.",
        llm=llm,
        verbose=True,
    )

    task = Task(
        description="Return exactly this text and nothing else: Testing PR comment",
        agent=agent,
        expected_output="Testing PR comment",
    )

    Crew(agents=[agent], tasks=[task], process=Process.sequential).kickoff()

    output = ""
    if hasattr(task, "output") and task.output is not None:
        output = getattr(task.output, "raw", str(task.output))

    output = (output or "").strip()
    if output != "Testing PR comment":
        output = "Testing PR comment"
    return output


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Post a test PR comment using a DeepSeek agent."
    )
    parser.add_argument(
        "--pr-url",
        default="",
        help="PR URL (overrides PR_URL env var).",
    )
    parser.add_argument(
        "--comment-text",
        default="",
        help="Exact comment body to post (skips LLM).",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM call and post the default test comment.",
    )
    return parser.parse_args()


def main():
    load_dotenv()
    settings = load_settings()

    args = _parse_args()
    pr_url = (args.pr_url or os.getenv("PR_URL", "")).strip()
    if not pr_url:
        raise SystemExit("Missing PR_URL env var.")
    if not settings.github_token:
        raise SystemExit("Missing GITHUB_TOKEN env var.")
    if not settings.deepseek_api_key and not (args.skip_llm or args.comment_text):
        raise SystemExit("Missing DEEPSEEK_API_KEY env var (or pass --skip-llm).")

    if args.comment_text:
        comment = args.comment_text.strip() or "Testing PR comment"
    elif args.skip_llm:
        comment = "Testing PR comment"
    else:
        try:
            comment = _build_deepseek_comment(settings)
        except Exception as exc:
            print(f"LLM call failed: {exc}")
            print("Falling back to default test comment.")
            comment = "Testing PR comment"
    response = _post_issue_comment(pr_url, settings.github_token, comment)
    comment_id = response.get("id")

    print(f"Posted comment id: {comment_id}")


if __name__ == "__main__":
    main()
