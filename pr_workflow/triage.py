import os
from collections import defaultdict
from typing import Dict, List, Tuple

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
]

TEST_DIR_MARKERS = ["/test/", "/tests/", "/__tests__/"]
TEST_FILE_MARKERS = ["_test", ".spec", ".test"]


def compute_loc(file_info: Dict) -> int:
    if "loc" in file_info:
        return int(file_info["loc"])
    added = int(file_info.get("added", 0))
    removed = int(file_info.get("removed", 0))
    return max(0, added + removed)


def top_level_dir(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[0] if len(parts) > 1 else "root"


def is_test_path(path: str) -> bool:
    lower = path.lower()
    if any(marker in lower for marker in TEST_DIR_MARKERS):
        return True
    filename = os.path.basename(lower)
    stem, _ = os.path.splitext(filename)
    return any(stem.endswith(marker) for marker in TEST_FILE_MARKERS)


def module_key(path: str) -> str:
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    for marker in TEST_FILE_MARKERS:
        if stem.endswith(marker):
            stem = stem[: -len(marker)]
            break
    return f"{top_level_dir(path)}::{stem}"


def risk_hits(path: str) -> List[str]:
    lower = path.lower()
    return [keyword for keyword in RISK_KEYWORDS if keyword in lower]


def risk_score(path: str) -> int:
    return len(risk_hits(path))


def build_risk_report(files: List[Dict]) -> Dict:
    report = []
    for f in files:
        path = f.get("path", "")
        report.append(
            {
                "path": path,
                "loc": compute_loc(f),
                "is_test": is_test_path(path),
                "risk_score": risk_score(path),
                "risk_keywords": risk_hits(path),
            }
        )
    report.sort(key=lambda x: (x["risk_score"], x["loc"]), reverse=True)
    return {"files": report}


def triage_batches(files: List[Dict], max_loc: int) -> Dict:
    total_loc = sum(compute_loc(f) for f in files)
    triage_notes: List[str] = []

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

    # Group by top-level directory, then by module key (keeping related tests together).
    grouped: Dict[str, Dict[str, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    for f in files:
        grouped[top_level_dir(f["path"])][module_key(f["path"])].append(f)

    batches: List[Dict] = []
    current_batch = {"files": [], "loc": 0}
    batch_id = 1

    for group, module_groups in grouped.items():
        bundles: List[Tuple[List[Dict], int, int]] = []
        for _, module_files in module_groups.items():
            bundle_loc = sum(compute_loc(f) for f in module_files)
            bundle_risk = max(risk_score(f["path"]) for f in module_files)
            bundles.append((module_files, bundle_loc, bundle_risk))

        # Sort by risk desc, then loc desc
        bundles.sort(key=lambda x: (x[2], x[1]), reverse=True)

        for module_files, bundle_loc, _ in bundles:
            if current_batch["loc"] + bundle_loc > max_loc and current_batch["files"]:
                batches.append(
                    {
                        "batch_id": batch_id,
                        "files": current_batch["files"],
                        "loc": current_batch["loc"],
                        "notes": f"Grouped by {group}.",
                    }
                )
                batch_id += 1
                current_batch = {"files": [], "loc": 0}

            current_batch["files"].extend([f["path"] for f in module_files])
            current_batch["loc"] += bundle_loc

    if current_batch["files"]:
        batches.append(
            {
                "batch_id": batch_id,
                "files": current_batch["files"],
                "loc": current_batch["loc"],
                "notes": "Final batch.",
            }
        )

    triage_notes.append(
        "Auto-split applied due to total LOC exceeding limit. Review batches sequentially."
    )

    return {
        "total_loc": total_loc,
        "max_loc_per_batch": max_loc,
        "batches": batches,
        "triage_notes": triage_notes,
    }
