import json
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Tuple

GITHUB_API = "https://api.github.com"


def _request(url: str, token: str | None = None) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "crewai-pr-workflow")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _parse_pr_url(pr_url: str) -> Tuple[str, str, str]:
    m = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise ValueError("Invalid PR URL. Expected https://github.com/<org>/<repo>/pull/<num>.")
    return m.group(1), m.group(2), m.group(3)


def fetch_pr_metadata(pr_url: str, token: str | None = None) -> Dict:
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}"
    data = json.loads(_request(url, token).decode("utf-8"))
    return {
        "id": data.get("number"),
        "title": data.get("title"),
        "description": data.get("body"),
    }


def fetch_pr_diff(pr_url: str, token: str | None = None) -> str:
    owner, repo, number = _parse_pr_url(pr_url)
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}.diff"
    return _request(url, token).decode("utf-8", errors="replace")


def fetch_pr_files(pr_url: str, token: str | None = None) -> List[Dict]:
    owner, repo, number = _parse_pr_url(pr_url)
    files: List[Dict] = []
    page = 1
    per_page = 100
    while True:
        params = urllib.parse.urlencode({"page": page, "per_page": per_page})
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/files?{params}"
        data = json.loads(_request(url, token).decode("utf-8"))
        if not data:
            break
        for entry in data:
            files.append(
                {
                    "path": entry.get("filename"),
                    "added": int(entry.get("additions", 0)),
                    "removed": int(entry.get("deletions", 0)),
                    "loc": int(entry.get("changes", 0)),
                    "patch": entry.get("patch", ""),
                    "status": entry.get("status", ""),
                }
            )
        if len(data) < per_page:
            break
        page += 1
    return files


def parse_unified_diff(diff_text: str) -> List[Dict]:
    files: List[Dict] = []
    current = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            parts = line.split()
            a_path = parts[2][2:] if len(parts) > 2 else ""
            b_path = parts[3][2:] if len(parts) > 3 else a_path
            current = {"path": b_path, "added": 0, "removed": 0}
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


def build_pr_context_from_url(pr_url: str, token: str | None = None) -> Dict:
    meta = fetch_pr_metadata(pr_url, token)
    files = fetch_pr_files(pr_url, token)
    if not files:
        diff_text = fetch_pr_diff(pr_url, token)
        files = parse_unified_diff(diff_text)

    return {
        "id": meta.get("id"),
        "title": meta.get("title"),
        "description": meta.get("description"),
        "diff_summary": f"Fetched diff from {pr_url}",
        "test_summary": "",
        "ci_summary": "",
        "files": files,
    }
