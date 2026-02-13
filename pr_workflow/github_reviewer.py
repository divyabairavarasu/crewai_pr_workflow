"""
Module to post AI review comments directly on GitHub PRs.
Acts like a human code reviewer, leaving inline comments and suggestions.

GitHub's PR review API requires `position` = the 1-based line offset inside the
unified diff (counting every hunk header + context + added + removed line).
Line numbers from the file are NOT valid positions.
"""
import json
import re
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple


class GitHubReviewer:
    """Posts AI-generated review comments on GitHub PRs."""

    def __init__(self, pr_url: str, github_token: str):
        parts = pr_url.replace("https://github.com/", "").split("/")
        self.owner = parts[0]
        self.repo = parts[1]
        self.pr_number = parts[3]
        self.github_token = github_token

        # Lazily populated
        self._commit_sha: Optional[str] = None
        # {file_path: {new_line_number: diff_position}}
        self._diff_position_map: Optional[Dict[str, Dict[int, int]]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def post_review_comments(self, review_results: Dict) -> Dict:
        findings = self._collect_findings(review_results)

        if not findings:
            print("No findings to post as comments.")
            return {"comments_posted": 0, "findings": []}

        # Build the summary body
        summary = self._build_review_summary(findings)

        # Try to map findings to valid diff positions for inline comments
        inline_comments, fallback_findings = self._resolve_positions(findings)

        # If inline comments are not possible, fall back entirely to a single comment
        if inline_comments:
            review_id = self._submit_review(summary, inline_comments)
        else:
            review_id = None

        # Post summary + any findings that couldn't be pinned inline
        if not review_id or fallback_findings:
            self._post_as_issue_comment(summary, fallback_findings)

        return {
            "review_id": review_id,
            "comments_posted": len(inline_comments),
            "fallback_findings": len(fallback_findings),
            "summary": summary,
            "findings": findings,
        }

    # ------------------------------------------------------------------
    # Diff position resolution
    # ------------------------------------------------------------------

    def _get_diff_position_map(self) -> Dict[str, Dict[int, int]]:
        """
        Fetch the PR's unified diff and return:
            {file_path: {new_line_number: diff_position}}

        diff_position is the 1-based counter that increments for every line
        in the diff output (hunk headers, context, added, removed lines).
        Removed lines (-) have no new_line_number so they are skipped.
        """
        if self._diff_position_map is not None:
            return self._diff_position_map

        diff_text = self._api_request(
            f"https://api.github.com/repos/{self.owner}/{self.repo}/pulls/{self.pr_number}",
            accept="application/vnd.github.v3.diff",
        ).decode("utf-8", errors="replace")

        position_map: Dict[str, Dict[int, int]] = {}
        current_file = None
        diff_position = 0
        new_line = 0

        for raw_line in diff_text.splitlines():
            # New file
            if raw_line.startswith("diff --git "):
                current_file = None
                diff_position = 0

            elif raw_line.startswith("+++ b/"):
                current_file = raw_line[6:]
                position_map.setdefault(current_file, {})
                # reset; hunk header comes next and will set new_line

            elif current_file and raw_line.startswith("@@"):
                # e.g. @@ -10,7 +10,9 @@
                m = re.search(r"\+(\d+)", raw_line)
                new_line = int(m.group(1)) - 1 if m else 0
                diff_position += 1
                position_map[current_file][new_line] = diff_position  # hunk header itself

            elif current_file:
                diff_position += 1
                if raw_line.startswith("-"):
                    pass  # removed line: no new_line increment
                elif raw_line.startswith("+"):
                    new_line += 1
                    position_map[current_file][new_line] = diff_position
                else:
                    # context line
                    new_line += 1
                    position_map[current_file][new_line] = diff_position

        self._diff_position_map = position_map
        return position_map

    def _resolve_positions(
        self, findings: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Split findings into:
        - inline_comments: findings with a resolvable diff position
        - fallback_findings: findings that will go into the summary comment

        For each finding we look for the exact line, then walk backwards up to
        50 lines to find the nearest available diff position (useful when the
        agent reports a line that is context rather than a changed line).
        """
        try:
            pos_map = self._get_diff_position_map()
        except Exception as exc:
            print(f"⚠️  Could not fetch diff positions ({exc}). Falling back to issue comment.")
            return [], findings

        inline: List[Dict] = []
        fallback: List[Dict] = []

        SKIP_PATHS = {"All files", "user-provided batch", ""}

        for finding in findings:
            path = (finding.get("file") or "").strip()
            if path in SKIP_PATHS:
                fallback.append(finding)
                continue

            file_positions = pos_map.get(path)
            if not file_positions:
                fallback.append(finding)
                continue

            target_line = int(finding.get("line") or 1)

            # Walk backwards from target_line to find the nearest changed/context line
            position = None
            for candidate in range(target_line, max(0, target_line - 50), -1):
                if candidate in file_positions:
                    position = file_positions[candidate]
                    break

            if position is None:
                # Use the first available position for the file
                position = next(iter(file_positions.values()))

            inline.append({**finding, "_diff_position": position})

        return inline, fallback

    # ------------------------------------------------------------------
    # Comment body builders
    # ------------------------------------------------------------------

    def _build_review_summary(self, findings: List[Dict]) -> str:
        if not findings:
            return "✅ No issues found. Code looks good!"

        categories: Dict[str, int] = {}
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
        body += "_🤖 Generated by CrewAI Multi-Agent Review_\n"
        return body

    def _finding_body(self, finding: Dict) -> str:
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

    # ------------------------------------------------------------------
    # GitHub API calls
    # ------------------------------------------------------------------

    def _submit_review(self, summary: str, inline_comments: List[Dict]) -> Optional[int]:
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
            data = self._api_post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}"
                f"/pulls/{self.pr_number}/reviews",
                review_payload,
            )
            review_id = data.get("id")
            print(f"✅ Posted review #{review_id} with {len(inline_comments)} inline comment(s)")
            return review_id

        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            print(f"❌ Failed to post inline review ({exc.code}): {body}")
            return None

    def _post_as_issue_comment(self, summary: str, extra_findings: List[Dict]):
        """Post a plain issue comment (always works, no diff-position needed)."""
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
            data = self._api_post(
                f"https://api.github.com/repos/{self.owner}/{self.repo}"
                f"/issues/{self.pr_number}/comments",
                {"body": body},
            )
            print(f"✅ Posted issue comment #{data.get('id')}")
        except Exception as exc:
            print(f"❌ Failed to post issue comment: {exc}")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _get_commit_sha(self) -> Optional[str]:
        if self._commit_sha:
            return self._commit_sha
        try:
            data = json.loads(
                self._api_request(
                    f"https://api.github.com/repos/{self.owner}/{self.repo}"
                    f"/pulls/{self.pr_number}"
                ).decode("utf-8")
            )
            self._commit_sha = data.get("head", {}).get("sha")
            return self._commit_sha
        except Exception as exc:
            print(f"❌ Could not fetch commit SHA: {exc}")
            return None

    def _api_request(self, url: str, accept: str = "application/vnd.github.v3+json") -> bytes:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.github_token}",
                "Accept": accept,
                "User-Agent": "crewai-pr-workflow",
            },
        )
        with urllib.request.urlopen(req) as resp:
            return resp.read()

    def _api_post(self, url: str, payload: Dict) -> Dict:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "crewai-pr-workflow",
            },
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ------------------------------------------------------------------
    # Finding collectors (unchanged logic, kept here)
    # ------------------------------------------------------------------

    def _collect_findings(self, review_results: Dict) -> List[Dict]:
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

    def _parse_json_output(self, output: str) -> Dict:
        if not output:
            return {}
        output = output.strip()
        # Strip markdown code fences
        for fence in ("```json", "```"):
            if output.startswith(fence):
                output = output[len(fence):]
        if output.endswith("```"):
            output = output[:-3]
        try:
            return json.loads(output.strip())
        except json.JSONDecodeError:
            return {}
