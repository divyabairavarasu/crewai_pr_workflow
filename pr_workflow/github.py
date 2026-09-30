"""
GitHub API client using httpx for async support.
"""
from __future__ import annotations

import json
import re
from typing import Optional
from urllib.parse import urlencode

import httpx

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 30.0


class GitHubClient:
    """Async-capable GitHub API client."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            headers = {
                "User-Agent": "crewai-pr-workflow/2.0",
                "Accept": "application/vnd.github.v3+json",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._client = httpx.Client(
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client
    
    def close(self):
        if self._client:
            self._client.close()
            self._client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def _parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    """Parse a GitHub PR URL into (owner, repo, number)."""
    m = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError("Invalid PR URL. Expected https://github.com/<org>/<repo>/pull/<num>.")
    return m.group(1), m.group(2), m.group(3)


def _request(url: str, token: Optional[str] = None, accept: str = "application/vnd.github.v3+json") -> bytes:
    """Make a synchronous request to the GitHub API."""
    headers = {
        "User-Agent": "crewai-pr-workflow/2.0",
        "Accept": accept,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    with httpx.Client(headers=headers, timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def fetch_pr_metadata(pr_url: str, token: Optional[str] = None) -> dict:
    """Fetch PR metadata (title, description, etc.)."""
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}"
    data = json.loads(_request(url, token).decode("utf-8"))
    return {
        "id": data.get("number"),
        "title": data.get("title"),
        "description": data.get("body"),
        "base_branch": data.get("base", {}).get("ref", "main"),
        "head_branch": data.get("head", {}).get("ref", ""),
        "author": data.get("user", {}).get("login", ""),
        "state": data.get("state"),
        "mergeable": data.get("mergeable"),
        "draft": data.get("draft", False),
    }


def fetch_pr_diff(pr_url: str, token: Optional[str] = None) -> str:
    """Fetch the raw diff for a PR."""
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}"
    return _request(url, token, accept="application/vnd.github.v3.diff").decode("utf-8", errors="replace")


def fetch_pr_files(pr_url: str, token: Optional[str] = None) -> list[dict]:
    """Fetch the list of files changed in a PR with pagination."""
    owner, repo, number = _parse_pr_url(pr_url)
    files: list[dict] = []
    page = 1
    per_page = 100
    
    while True:
        params = urlencode({"page": page, "per_page": per_page})
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/files?{params}"
        data = json.loads(_request(url, token).decode("utf-8"))
        
        if not data:
            break
        
        for entry in data:
            files.append({
                "path": entry.get("filename"),
                "added": int(entry.get("additions", 0)),
                "removed": int(entry.get("deletions", 0)),
                "loc": int(entry.get("changes", 0)),
                "patch": entry.get("patch", ""),
                "status": entry.get("status", "modified"),
                "sha": entry.get("sha", ""),
                "blob_url": entry.get("blob_url", ""),
            })
        
        if len(data) < per_page:
            break
        page += 1
    
    return files


def fetch_pr_commits(pr_url: str, token: Optional[str] = None) -> list[dict]:
    """Fetch the list of commits in a PR."""
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/commits"
    data = json.loads(_request(url, token).decode("utf-8"))
    
    return [
        {
            "sha": commit.get("sha"),
            "message": commit.get("commit", {}).get("message", ""),
            "author": commit.get("commit", {}).get("author", {}).get("name", ""),
        }
        for commit in data
    ]


def fetch_pr_reviews(pr_url: str, token: Optional[str] = None) -> list[dict]:
    """Fetch existing reviews on a PR."""
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/reviews"
    data = json.loads(_request(url, token).decode("utf-8"))
    
    return [
        {
            "id": review.get("id"),
            "user": review.get("user", {}).get("login", ""),
            "state": review.get("state"),
            "body": review.get("body", ""),
        }
        for review in data
    ]


def parse_unified_diff(diff_text: str) -> list[dict]:
    """Parse a unified diff into file information."""
    files: list[dict] = []
    current = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            parts = line.split()
            a_path = parts[2][2:] if len(parts) > 2 else ""
            b_path = parts[3][2:] if len(parts) > 3 else a_path
            current = {"path": b_path, "added": 0, "removed": 0, "patch": ""}
        elif current and line.startswith("+++"):
            path = line[4:]
            if path.startswith("b/"):
                current["path"] = path[2:]
        elif current and line.startswith("+") and not line.startswith("+++ "):
            current["added"] += 1
        elif current and line.startswith("-") and not line.startswith("--- "):
            current["removed"] += 1

    if current:
        files.append(current)

    return files


def build_pr_context_from_url(pr_url: str, token: Optional[str] = None) -> dict:
    """
    Build a complete PR context from a GitHub PR URL.
    
    Args:
        pr_url: GitHub PR URL
        token: Optional GitHub token for private repos
        
    Returns:
        PR context dict with metadata and files
    """
    meta = fetch_pr_metadata(pr_url, token)
    files = fetch_pr_files(pr_url, token)
    
    # Fallback to diff parsing if files API fails
    if not files:
        diff_text = fetch_pr_diff(pr_url, token)
        files = parse_unified_diff(diff_text)

    return {
        "id": meta.get("id"),
        "title": meta.get("title"),
        "description": meta.get("description"),
        "base_branch": meta.get("base_branch", "main"),
        "head_branch": meta.get("head_branch", ""),
        "author": meta.get("author", ""),
        "diff_summary": f"Fetched diff from {pr_url}",
        "test_summary": "",
        "ci_summary": "",
        "files": files,
    }
