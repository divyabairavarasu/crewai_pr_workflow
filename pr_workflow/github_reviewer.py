"""
Module to post AI review comments directly on GitHub PRs.
Uses httpx for modern HTTP handling.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx

GITHUB_API = "https://api.github.com"


class GitHubReviewer:
    """Posts AI-generated review comments on GitHub PRs."""

    def __init__(self, pr_url: str, github_token: str):
        parts = pr_url.replace("https://github.com/", "").split("/")
        self.owner = parts[0]
        self.repo = parts[1]
        self.pr_number = parts[3]
        self.github_token = github_token
        self._commit_sha: Optional[str] = None
        self._diff_position_map: Optional[dict[str, dict[int, int]]] = None
        
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "crewai-pr-workflow/2.0",
            },
            timeout=30.0,
        )

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def post_review_comments(self, review_results: dict) -> dict:
        """Post review comments on the PR."""
        findings = self._collect_findings(review_results)

        if not findings:
            print("No findings to post as comments.")
            return {"comments_posted": 0, "findings": []}

        summary = self._build_review_summary(findings)
        inline_comments, fallback_findings = self._resolve_positions(findings)

        review_id = None
        if inline_comments:
            review_id = self._submit_review(summary, inline_comments)

        if not review_id or fallback_findings:
            self._post_as_issue_comment(summary, fallback_findings)

        return {
            "review_id": review_id,
            "comments_posted": len(inline_comments),
            "fallback_findings": len(fallback_findings),
            "summary": summary,
            "findings": findings,
        }

    def _get_diff_position_map(self) -> dict[str, dict[int, int]]:
        """Fetch PR diff and build position map."""
        if self._diff_position_map is not None:
            return self._diff_position_map

        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
        response = self._client.get(url, headers={"Accept": "application/vnd.github.v3.diff"})
        response.raise_for_status()
        diff_text = response.text

        position_map: dict[str, dict[int, int]] = {}
        current_file = None
        diff_position = 0
        new_line = 0

        for raw_line in diff_text.splitlines():
            if raw_line.startswith("diff --git "):
                current_file = None
                diff_position = 0
            elif raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                position_map.setdefault(current_file, {})
            elif current_file and raw_line.startswith("@@"):
                m = re.search(r"\+(\d+)", raw_line)
                new_line = int(m.group(1)) - 1 if m else 0
                diff_position += 1
                position_map[current_file][new_line] = diff_position
            elif current_file:
                diff_position += 1
                if raw_line.startswith("-"):
                    pass
                elif raw_line.startswith("+"):
                    new_line += 1
                    position_map[current_file][new_line] = diff_position
                else:
                    new_line += 1
                    position_map[current_file][new_line] = diff_position

        self._diff_position_map = position_map
        return position_map

    def _resolve_positions(self, findings: list[dict]) -> tuple[list[dict], list[dict]]:
        """Split findings into inline and fallback."""
        try:
            pos_map = self._get_diff_position_map()
        except Exception as exc:
            print(f"⚠️ Could not fetch diff positions ({exc}). Falling back to issue comment.")
            return [], findings

        inline: list[dict] = []
        fallback: list[dict] = []
        skip_paths = {"All files", "user-provided batch", ""}

        for finding in findings:
            path = (finding.get("file") or "").strip()
            if path in skip_paths:
                fallback.append(finding)
                continue

            file_positions = pos_map.get(path)
            if not file_positions:
                fallback.append(finding)
                continue

            target_line = int(finding.get("line") or 1)
            position = None
            for candidate in range(target_line, max(0, target_line - 50), -1):
                if candidate in file_positions:
                    position = file_positions[candidate]
                    break

            if position is None:
                position = next(iter(file_positions.values()))

            inline.append({**finding, "_diff_position": position})

        return inline, fallback

    def _build_review_summary(self, findings: list[dict]) -> str:
        """Build review summary markdown."""
        if not findings:
            return "✅ No issues found. Code looks good!"

        categories: dict[str, int] = {}
        severities = {"high": 0, "critical": 0, "medium": 0, "low": 0}

        for f in findings:
            cat = f.get("category", "Other")
            categories[cat] = categories.get(cat, 0) + 1
            sev = f.get("severity", "low").lower()
            if sev in severities:
                severities[sev] += 1

        total_high = severities["high"] + severities["critical"]

        body = "## 🤖 AI Code Review Summary\n\n"
        body += f"Found **{len(findings)} issue(s)** across {len(categories)} categorie(s):\n\n"

        for cat, count in sorted(categories.items()):
            body += f"- {cat}: **{count}**\n"

        body += "\n### Severity\n\n"
        if total_high > 0:
            body += f"- 🔴 **High/Critical**: {total_high}\n"
        if severities["medium"] > 0:
            body += f"- 🟡 **Medium**: {severities['medium']}\n"
        if severities["low"] > 0:
            body += f"- 🟢 **Low**: {severities['low']}\n"

        body += "\n---\n"
        body += "_🤖 Generated by CrewAI Multi-Agent Review v2.0_\n"
        return body

    def _finding_body(self, finding: dict) -> str:
        """Format a single finding as markdown."""
        severity = finding.get("severity", "low").lower()
        sev_emoji = {"high": "🔴", "critical": "🔴", "medium": "🟡"}.get(severity, "🟢")
        cat_emoji = finding.get("emoji", "💡")
        category = finding.get("category", "Issue")

        body = f"{cat_emoji} **{category}** &nbsp; {sev_emoji} `{severity.upper()}`\n\n"
        body += f"**Issue:** {finding.get('issue', 'No description')}\n\n"

        suggestion = finding.get("suggested_change")
        if suggestion and suggestion not in ("No suggestion", ""):
            body += f"**Suggested Fix:**\n```suggestion\n{suggestion}\n```\n\n"

        hint = finding.get("test_hint")
        if hint:
            body += f"**Testing:** {hint}\n"

        return body

    def _submit_review(self, summary: str, inline_comments: list[dict]) -> Optional[int]:
        """Submit a PR review with inline comments."""
        commit_id = self._get_commit_sha()
        if not commit_id:
            return None

        review_payload = {
            "commit_id": commit_id,
            "body": summary,
            "event": "COMMENT",
            "comments": [
                {
                    "path": c["file"],
                    "position": c["_diff_position"],
                    "body": self._finding_body(c),
                }
                for c in inline_comments
            ],
        }

        try:
            url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}/reviews"
            response = self._client.post(url, json=review_payload)
            response.raise_for_status()
            data = response.json()
            review_id = data.get("id")
            print(f"✅ Posted review #{review_id} with {len(inline_comments)} inline comment(s)")
            return review_id
        except httpx.HTTPStatusError as exc:
            print(f"❌ Failed to post inline review ({exc.response.status_code}): {exc.response.text}")
            return None

    def _post_as_issue_comment(self, summary: str, extra_findings: list[dict]):
        """Post a plain issue comment."""
        body = summary

        if extra_findings:
            body += "\n\n---\n\n### Findings Without Inline Location\n\n"
            for f in extra_findings:
                path = f.get("file", "unknown")
                line = f.get("line", "?")
                body += f"**`{path}` (line {line})**\n\n"
                body += self._finding_body(f)
                body += "\n---\n\n"

        try:
            url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/issues/{self.pr_number}/comments"
            response = self._client.post(url, json={"body": body})
            response.raise_for_status()
            data = response.json()
            print(f"✅ Posted issue comment #{data.get('id')}")
        except Exception as exc:
            print(f"❌ Failed to post issue comment: {exc}")

    def _get_commit_sha(self) -> Optional[str]:
        """Get the head commit SHA of the PR."""
        if self._commit_sha:
            return self._commit_sha
        try:
            url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}"
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
            self._commit_sha = data.get("head", {}).get("sha")
            return self._commit_sha
        except Exception as exc:
            print(f"❌ Could not fetch commit SHA: {exc}")
            return None

    def _collect_findings(self, review_results: dict) -> list[dict]:
        """Collect all findings from review results."""
        findings = []

        for raw in self._parse_json_output(
            review_results.get("performance_findings", "{}")
        ).get("findings", []):
            findings.append({**raw, "category": "⚡ Performance", "emoji": "⚡"})

        for raw in self._parse_json_output(
            review_results.get("security_findings", "{}")
        ).get("findings", []):
            findings.append({**raw, "category": "🔒 Security", "emoji": "🔒"})

        for note in self._parse_json_output(
            review_results.get("solid_notes", "{}")
        ).get("solid_notes", []):
            findings.append({
                "file": note.get("file"),
                "line": note.get("line"),
                "severity": "medium",
                "issue": f"{note.get('principle')} violation: {note.get('issue')}",
                "suggested_change": note.get("fix"),
                "category": "🏗️ SOLID Principles",
                "emoji": "🏗️",
            })

        for test in self._parse_json_output(
            review_results.get("coverage_review", "{}")
        ).get("missing_tests", []):
            findings.append({
                "file": test,
                "line": 1,
                "severity": "low",
                "issue": "Missing test coverage",
                "suggested_change": f"Add unit tests for {test}",
                "category": "🧪 Test Coverage",
                "emoji": "🧪",
            })

        return findings

    def _parse_json_output(self, output) -> dict:
        """Parse JSON from agent output."""
        if not output:
            return {}
        if isinstance(output, dict):
            return output
        output = str(output).strip()
        for fence in ("```json", "```"):
            if output.startswith(fence):
                output = output[len(fence):]
        if output.endswith("```"):
            output = output[:-3]
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            return {}
