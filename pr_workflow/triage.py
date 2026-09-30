"""
Diff triage and batch splitting logic.
Groups related files and prioritizes high-risk code.
"""
from __future__ import annotations

import os
from collections import defaultdict
from typing import Optional

from .models import BatchInfo, TriageResult, FileInfo

# Keywords indicating high-risk files
RISK_KEYWORDS = [
    "auth",
    "login",
    "security",
    "crypto",
    "permission",
    "acl",
    "role",
    "db",
    "sql",
    "orm",
    "migration",
    "network",
    "http",
    "api",
    "config",
    "build",
    "infra",
    "secret",
    "password",
    "token",
    "key",
    "credential",
    "payment",
    "billing",
]

TEST_DIR_MARKERS = ["/test/", "/tests/", "/__tests__/", "/spec/"]
TEST_FILE_MARKERS = ["_test", ".spec", ".test", "_spec"]


def compute_loc(file_info: dict) -> int:
    """Compute lines of code changed for a file."""
    if "loc" in file_info:
        return int(file_info["loc"])
    added = int(file_info.get("added", 0))
    removed = int(file_info.get("removed", 0))
    return max(0, added + removed)


def top_level_dir(path: str) -> str:
    """Get the top-level directory of a path."""
    parts = path.strip("/").split("/")
    return parts[0] if len(parts) > 1 else "root"


def is_test_path(path: str) -> bool:
    """Check if a path is a test file."""
    lower = path.lower()
    if any(marker in lower for marker in TEST_DIR_MARKERS):
        return True
    filename = os.path.basename(lower)
    stem, _ = os.path.splitext(filename)
    return any(stem.endswith(marker) for marker in TEST_FILE_MARKERS)


def module_key(path: str) -> str:
    """Generate a module key for grouping related files."""
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    for marker in TEST_FILE_MARKERS:
        if stem.endswith(marker):
            stem = stem[: -len(marker)]
            break
    return f"{top_level_dir(path)}::{stem}"


def risk_hits(path: str) -> list[str]:
    """Find risk keywords in a path."""
    lower = path.lower()
    return [keyword for keyword in RISK_KEYWORDS if keyword in lower]


def risk_score(path: str) -> int:
    """Calculate risk score for a file based on path keywords."""
    return len(risk_hits(path))


def build_risk_report(files: list[dict]) -> dict:
    """
    Build a risk report for all files.
    
    Args:
        files: List of file info dicts
        
    Returns:
        Risk report with files sorted by risk score
    """
    report = []
    for f in files:
        path = f.get("path", "")
        report.append({
            "path": path,
            "loc": compute_loc(f),
            "is_test": is_test_path(path),
            "risk_score": risk_score(path),
            "risk_keywords": risk_hits(path),
        })
    report.sort(key=lambda x: (x["risk_score"], x["loc"]), reverse=True)
    return {"files": report}


def triage_batches(files: list[dict], max_loc: int) -> dict:
    """
    Split files into review batches.
    
    Groups related files together and respects max LOC per batch.
    High-risk files are prioritized.
    
    Args:
        files: List of file info dicts
        max_loc: Maximum lines of code per batch
        
    Returns:
        Triage result with batches
    """
    total_loc = sum(compute_loc(f) for f in files)
    triage_notes: list[str] = []

    # Single batch if within limit
    if total_loc <= max_loc:
        return {
            "total_loc": total_loc,
            "max_loc_per_batch": max_loc,
            "batches": [
                {
                    "batch_id": 1,
                    "files": [f["path"] for f in files],
                    "loc": total_loc,
                    "notes": "Single batch (LOC within limit).",
                }
            ],
            "triage_notes": triage_notes,
        }

    # Group by top-level directory, then by module key
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for f in files:
        grouped[top_level_dir(f["path"])][module_key(f["path"])].append(f)

    batches: list[dict] = []
    current_batch: dict = {"files": [], "loc": 0}
    batch_id = 1

    for group, module_groups in grouped.items():
        # Create bundles of related files
        bundles: list[tuple[list[dict], int, int]] = []
        for _, module_files in module_groups.items():
            bundle_loc = sum(compute_loc(f) for f in module_files)
            bundle_risk = max(risk_score(f["path"]) for f in module_files)
            bundles.append((module_files, bundle_loc, bundle_risk))

        # Sort by risk desc, then loc desc (high risk first)
        bundles.sort(key=lambda x: (x[2], x[1]), reverse=True)

        for module_files, bundle_loc, _ in bundles:
            # Start new batch if current would exceed limit
            if current_batch["loc"] + bundle_loc > max_loc and current_batch["files"]:
                batches.append({
                    "batch_id": batch_id,
                    "files": current_batch["files"],
                    "loc": current_batch["loc"],
                    "notes": f"Grouped by {group}.",
                })
                batch_id += 1
                current_batch = {"files": [], "loc": 0}

            current_batch["files"].extend([f["path"] for f in module_files])
            current_batch["loc"] += bundle_loc

    # Add final batch
    if current_batch["files"]:
        batches.append({
            "batch_id": batch_id,
            "files": current_batch["files"],
            "loc": current_batch["loc"],
            "notes": "Final batch.",
        })

    triage_notes.append(
        "Auto-split applied due to total LOC exceeding limit. Review batches sequentially."
    )

    return {
        "total_loc": total_loc,
        "max_loc_per_batch": max_loc,
        "batches": batches,
        "triage_notes": triage_notes,
    }


def prioritize_files(files: list[dict]) -> list[dict]:
    """
    Sort files by priority for review.
    
    High-risk files first, then by LOC.
    
    Args:
        files: List of file info dicts
        
    Returns:
        Sorted list of files
    """
    def priority_key(f: dict) -> tuple:
        path = f.get("path", "")
        return (
            -risk_score(path),  # Higher risk first
            -compute_loc(f),     # More LOC first
            path,                # Alphabetical tiebreaker
        )
    
    return sorted(files, key=priority_key)
