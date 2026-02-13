"""
Module to create pull requests with AI-generated fixes back to the source repository.
"""
import json
import subprocess
import tempfile
import os
import shutil
from typing import Dict, List
from pathlib import Path


class GitHubPRCreator:
    """Creates PRs with AI-suggested fixes back to the source repository."""

    def __init__(self, pr_url: str, github_token: str):
        """
        Initialize PR creator.

        Args:
            pr_url: Original PR URL (e.g., https://github.com/user/repo/pull/123)
            github_token: GitHub personal access token
        """
        self.pr_url = pr_url
        self.github_token = github_token
        self.temp_dir = None

        # Parse PR URL
        parts = pr_url.replace('https://github.com/', '').split('/')
        self.owner = parts[0]
        self.repo = parts[1]
        self.pr_number = parts[3]
        self.repo_url = f"https://github.com/{self.owner}/{self.repo}.git"

    def create_review_pr(self, review_results: Dict, branch_name: str = None) -> str:
        """
        Create a new PR with AI review fixes.

        Args:
            review_results: Dictionary containing all review outputs
            branch_name: Name for the new branch (default: ai-review-fixes-pr-{number})

        Returns:
            URL of the created PR
        """
        if not branch_name:
            branch_name = f"ai-review-fixes-pr-{self.pr_number}"

        try:
            # Clone repository
            self._clone_repository()

            # Apply fixes from review results
            changes_made = self._apply_fixes(review_results)

            if not changes_made:
                print("No changes to apply. Skipping PR creation.")
                return None

            # Create and push branch
            self._create_and_push_branch(branch_name)

            # Create PR using GitHub CLI
            pr_url = self._create_pull_request(branch_name, review_results)

            return pr_url

        finally:
            # Cleanup
            self._cleanup()

    def _clone_repository(self):
        """Clone the repository to a temporary directory."""
        self.temp_dir = tempfile.mkdtemp(prefix="crewai_pr_")
        print(f"Cloning repository to {self.temp_dir}...")

        # Use gh CLI for secure cloning (uses existing authentication)
        # This is more secure than embedding token in URL
        subprocess.run(
            ["gh", "repo", "clone", f"{self.owner}/{self.repo}", self.temp_dir],
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "GH_TOKEN": self.github_token}
        )

        # Fetch the PR branch
        original_branch = self._get_pr_branch()
        os.chdir(self.temp_dir)
        subprocess.run(
            ["git", "fetch", "origin", f"pull/{self.pr_number}/head:{original_branch}"],
            check=True,
            capture_output=True
        )
        subprocess.run(["git", "checkout", original_branch], check=True, capture_output=True)

    def _get_pr_branch(self) -> str:
        """Get the source branch of the original PR."""
        cmd = [
            "gh", "pr", "view", self.pr_number,
            "--repo", f"{self.owner}/{self.repo}",
            "--json", "headRefName",
            "--jq", ".headRefName"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def _apply_fixes(self, review_results: Dict) -> bool:
        """
        Apply fixes from review results to the repository.

        Returns:
            True if changes were made, False otherwise
        """
        changes_made = False

        # Process performance fixes
        if review_results.get("performance_fixes"):
            changes_made |= self._apply_changes(review_results["performance_fixes"])

        # Process security fixes
        if review_results.get("security_fixes"):
            changes_made |= self._apply_changes(review_results["security_fixes"])

        # Process coverage fixes (new tests)
        if review_results.get("coverage_fixes"):
            changes_made |= self._apply_changes(review_results["coverage_fixes"])

        return changes_made

    def _apply_changes(self, fixes_data: Dict) -> bool:
        """Apply changes from fix data to files."""
        changes = fixes_data.get("changes", [])
        if not changes:
            return False

        for change in changes:
            file_path = change.get("file")
            new_content = change.get("content")

            if not file_path or not new_content:
                continue

            # Write the new content
            full_path = os.path.join(self.temp_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            print(f"Applied fixes to {file_path}")

        return len(changes) > 0

    def _create_and_push_branch(self, branch_name: str):
        """Create a new branch with fixes and push to remote."""
        os.chdir(self.temp_dir)

        # Create new branch
        subprocess.run(["git", "checkout", "-b", branch_name], check=True, capture_output=True)

        # Stage all changes
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)

        # Commit
        commit_message = f"""AI Code Review Fixes for PR #{self.pr_number}

Applied fixes from CrewAI multi-agent review:
- Performance optimizations
- Security improvements
- Test coverage enhancements

Co-Authored-By: CrewAI Review Bot <noreply@crewai.com>
"""
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            check=True,
            capture_output=True,
            text=True
        )

        # Push to remote using gh authentication
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            check=True,
            capture_output=True,
            env={**os.environ, "GH_TOKEN": self.github_token}
        )

        print(f"Pushed branch: {branch_name}")

    def _create_pull_request(self, branch_name: str, review_results: Dict) -> str:
        """Create PR using GitHub CLI."""
        # Build PR body from review results
        pr_body = self._build_pr_body(review_results)

        # Use gh CLI to create PR
        cmd = [
            "gh", "pr", "create",
            "--repo", f"{self.owner}/{self.repo}",
            "--base", self._get_pr_branch(),
            "--head", branch_name,
            "--title", f"🤖 AI Code Review Fixes for PR #{self.pr_number}",
            "--body", pr_body
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        pr_url = result.stdout.strip()

        print(f"Created PR: {pr_url}")
        return pr_url

    def _build_pr_body(self, review_results: Dict) -> str:
        """Build detailed PR description from review results."""
        body = f"""## 🤖 Automated Code Review Fixes

This PR contains fixes generated by CrewAI multi-agent code review for PR #{self.pr_number}.

---

"""

        # Performance section
        if review_results.get("performance_findings"):
            body += "### ⚡ Performance Improvements\n\n"
            for finding in review_results["performance_findings"].get("findings", []):
                severity = finding.get("severity", "medium")
                emoji = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                body += f"{emoji} **{finding.get('file')}:{finding.get('line')}**\n"
                body += f"   - Issue: {finding.get('issue')}\n"
                body += f"   - Fix: {finding.get('suggested_change')}\n\n"

        # Security section
        if review_results.get("security_findings"):
            body += "### 🔒 Security Fixes\n\n"
            for finding in review_results["security_findings"].get("findings", []):
                severity = finding.get("severity", "medium")
                emoji = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                body += f"{emoji} **{finding.get('file')}:{finding.get('line')}**\n"
                body += f"   - Issue: {finding.get('issue')}\n"
                body += f"   - Fix: {finding.get('suggested_change')}\n\n"

        # SOLID violations section
        if review_results.get("solid_notes"):
            body += "### 🏗️ SOLID Principle Fixes\n\n"
            for note in review_results["solid_notes"].get("solid_notes", []):
                body += f"**{note.get('principle')}** - {note.get('file')}:{note.get('line')}\n"
                body += f"   - Issue: {note.get('issue')}\n"
                body += f"   - Fix: {note.get('fix')}\n\n"

        # Coverage section
        if review_results.get("coverage_fixes"):
            body += "### 🧪 Test Coverage Improvements\n\n"
            coverage = review_results.get("coverage_review", {}).get("coverage_percent", "N/A")
            body += f"Coverage: {coverage}%\n\n"
            body += "New tests added:\n"
            for test in review_results.get("coverage_fixes", {}).get("files_touched", []):
                body += f"- {test}\n"

        body += "\n---\n\n"
        body += "🤖 Generated by [CrewAI PR Workflow](https://github.com/your-org/crewai_pr_workflow)\n"

        return body

    def _cleanup(self):
        """Remove temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"Cleaned up temporary directory: {self.temp_dir}")
