"""
Code complexity analysis using radon.
Provides cyclomatic complexity, maintainability index, and other metrics.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .models import ComplexityMetrics


def analyze_complexity(file_path: str, content: Optional[str] = None) -> Optional[ComplexityMetrics]:
    """
    Analyze code complexity for a Python file.
    
    Args:
        file_path: Path to the file
        content: Optional file content (if not provided, reads from disk)
        
    Returns:
        ComplexityMetrics or None if analysis fails
    """
    # Only analyze Python files for now
    if not file_path.endswith(".py"):
        return None
    
    try:
        from radon.complexity import cc_visit, cc_rank
        from radon.metrics import mi_visit
        from radon.raw import analyze
    except ImportError:
        return None
    
    try:
        if content is None:
            if not os.path.exists(file_path):
                return None
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        
        # Cyclomatic complexity
        cc_results = cc_visit(content)
        avg_complexity = 0.0
        high_complexity_functions = []
        
        if cc_results:
            complexities = [r.complexity for r in cc_results]
            avg_complexity = sum(complexities) / len(complexities)
            
            for r in cc_results:
                if r.complexity > 10:  # High complexity threshold
                    high_complexity_functions.append(
                        f"{r.name} (complexity: {r.complexity}, rank: {cc_rank(r.complexity)})"
                    )
        
        # Maintainability index
        mi_score = mi_visit(content, multi=False)
        
        # Raw metrics
        raw = analyze(content)
        
        # Count classes and functions
        num_functions = len([r for r in cc_results if r.classname is None])
        num_classes = len(set(r.classname for r in cc_results if r.classname))
        
        return ComplexityMetrics(
            file=file_path,
            cyclomatic_complexity=round(avg_complexity, 2),
            maintainability_index=round(mi_score, 2),
            loc=raw.loc,
            functions=num_functions,
            classes=num_classes,
            high_complexity_functions=high_complexity_functions,
        )
        
    except Exception:
        return None


def analyze_batch_complexity(files: list[dict]) -> list[ComplexityMetrics]:
    """
    Analyze complexity for a batch of files.
    
    Args:
        files: List of file info dicts with 'path' and optionally 'patch' keys
        
    Returns:
        List of ComplexityMetrics for analyzable files
    """
    results = []
    
    for file_info in files:
        path = file_info.get("path", "")
        
        # Skip non-Python files
        if not path.endswith(".py"):
            continue
        
        # Try to analyze from patch content if available
        # Note: This is a simplified approach - full file content would be better
        metrics = analyze_complexity(path)
        
        if metrics:
            results.append(metrics)
    
    return results


def get_complexity_summary(metrics: list[ComplexityMetrics]) -> dict:
    """
    Generate a summary of complexity metrics.
    
    Args:
        metrics: List of ComplexityMetrics
        
    Returns:
        Summary dict with aggregated metrics
    """
    if not metrics:
        return {
            "total_files": 0,
            "avg_complexity": 0.0,
            "avg_maintainability": 0.0,
            "high_complexity_count": 0,
            "high_complexity_files": [],
        }
    
    total_complexity = sum(m.cyclomatic_complexity for m in metrics)
    total_mi = sum(m.maintainability_index for m in metrics)
    
    high_complexity_files = [
        m.file for m in metrics 
        if m.cyclomatic_complexity > 10 or m.high_complexity_functions
    ]
    
    return {
        "total_files": len(metrics),
        "avg_complexity": round(total_complexity / len(metrics), 2),
        "avg_maintainability": round(total_mi / len(metrics), 2),
        "high_complexity_count": len(high_complexity_files),
        "high_complexity_files": high_complexity_files,
        "details": [m.model_dump() for m in metrics],
    }


def format_complexity_report(metrics: list[ComplexityMetrics]) -> str:
    """
    Format complexity metrics as a readable report.
    
    Args:
        metrics: List of ComplexityMetrics
        
    Returns:
        Formatted string report
    """
    if not metrics:
        return "No complexity metrics available."
    
    lines = ["# Code Complexity Report\n"]
    
    summary = get_complexity_summary(metrics)
    lines.append(f"**Files Analyzed:** {summary['total_files']}")
    lines.append(f"**Average Cyclomatic Complexity:** {summary['avg_complexity']}")
    lines.append(f"**Average Maintainability Index:** {summary['avg_maintainability']}")
    lines.append("")
    
    if summary["high_complexity_files"]:
        lines.append("## ⚠️ High Complexity Files\n")
        for file in summary["high_complexity_files"]:
            lines.append(f"- {file}")
        lines.append("")
    
    lines.append("## File Details\n")
    lines.append("| File | Complexity | Maintainability | LOC | Functions | Classes |")
    lines.append("|------|------------|-----------------|-----|-----------|---------|")
    
    for m in sorted(metrics, key=lambda x: x.cyclomatic_complexity, reverse=True):
        complexity_indicator = "🔴" if m.cyclomatic_complexity > 10 else "🟡" if m.cyclomatic_complexity > 5 else "🟢"
        mi_indicator = "🔴" if m.maintainability_index < 20 else "🟡" if m.maintainability_index < 50 else "🟢"
        
        lines.append(
            f"| {Path(m.file).name} | {complexity_indicator} {m.cyclomatic_complexity} | "
            f"{mi_indicator} {m.maintainability_index} | {m.loc} | {m.functions} | {m.classes} |"
        )
    
    if any(m.high_complexity_functions for m in metrics):
        lines.append("\n## High Complexity Functions\n")
        for m in metrics:
            if m.high_complexity_functions:
                lines.append(f"### {m.file}\n")
                for func in m.high_complexity_functions:
                    lines.append(f"- {func}")
                lines.append("")
    
    return "\n".join(lines)
