"""
Pydantic models for structured outputs and type safety.
These models ensure consistent data flow between agents and tasks.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for findings."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReviewCategory(str, Enum):
    """Categories of review findings."""
    PERFORMANCE = "performance"
    SECURITY = "security"
    COVERAGE = "coverage"
    SOLID = "solid"
    CODE_QUALITY = "code_quality"
    COMPLEXITY = "complexity"


class Finding(BaseModel):
    """A single review finding."""
    file: str = Field(..., description="File path where the issue was found")
    line: int = Field(default=1, description="Line number of the issue")
    severity: Severity = Field(default=Severity.MEDIUM, description="Severity level")
    category: ReviewCategory = Field(..., description="Category of the finding")
    issue: str = Field(..., description="Description of the issue")
    suggested_change: Optional[str] = Field(None, description="Suggested fix")
    test_hint: Optional[str] = Field(None, description="Hint for testing the fix")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")


class PerformanceReview(BaseModel):
    """Output from performance review task."""
    findings: list[Finding] = Field(default_factory=list)
    summary: str = Field(default="", description="Summary of performance review")
    estimated_impact: Optional[str] = Field(None, description="Estimated performance impact")


class SecurityReview(BaseModel):
    """Output from security review task."""
    findings: list[Finding] = Field(default_factory=list)
    summary: str = Field(default="", description="Summary of security review")
    risk_level: Severity = Field(default=Severity.LOW, description="Overall risk level")
    cve_references: list[str] = Field(default_factory=list, description="Related CVEs if any")


class SOLIDNote(BaseModel):
    """A SOLID principle violation note."""
    principle: str = Field(..., description="SOLID principle (SRP/OCP/LSP/ISP/DIP/DRY)")
    file: str = Field(..., description="File path")
    line: int = Field(default=1, description="Line number")
    issue: str = Field(..., description="Description of the violation")
    fix: str = Field(..., description="Suggested fix")


class CoverageReview(BaseModel):
    """Output from coverage review task."""
    coverage_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    missing_tests: list[str] = Field(default_factory=list)
    suggested_tests: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="Summary of coverage review")


class CodeChange(BaseModel):
    """A code change to apply."""
    file: str = Field(..., description="File path to modify")
    content: str = Field(..., description="New file content")
    description: str = Field(default="", description="Description of the change")


class FixResult(BaseModel):
    """Output from fix tasks."""
    changes: list[CodeChange] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    tests_run: bool = Field(default=False)
    notes: str = Field(default="")
    solid_notes: list[SOLIDNote] = Field(default_factory=list)


class ComplexityMetrics(BaseModel):
    """Code complexity metrics for a file."""
    file: str = Field(..., description="File path")
    cyclomatic_complexity: float = Field(default=0.0, description="Average cyclomatic complexity")
    maintainability_index: float = Field(default=100.0, description="Maintainability index (0-100)")
    loc: int = Field(default=0, description="Lines of code")
    functions: int = Field(default=0, description="Number of functions")
    classes: int = Field(default=0, description="Number of classes")
    high_complexity_functions: list[str] = Field(
        default_factory=list, 
        description="Functions with complexity > 10"
    )


class BatchInfo(BaseModel):
    """Information about a review batch."""
    batch_id: int = Field(..., description="Batch identifier")
    files: list[str] = Field(default_factory=list, description="Files in this batch")
    loc: int = Field(default=0, description="Total lines of code")
    notes: str = Field(default="", description="Batch notes")


class TriageResult(BaseModel):
    """Result of diff triage."""
    total_loc: int = Field(default=0, description="Total lines of code")
    max_loc_per_batch: int = Field(default=2000, description="Maximum LOC per batch")
    batches: list[BatchInfo] = Field(default_factory=list)
    triage_notes: list[str] = Field(default_factory=list)


class FileInfo(BaseModel):
    """Information about a file in the PR."""
    path: str = Field(..., description="File path")
    added: int = Field(default=0, description="Lines added")
    removed: int = Field(default=0, description="Lines removed")
    loc: int = Field(default=0, description="Total lines changed")
    patch: str = Field(default="", description="Unified diff patch")
    status: str = Field(default="modified", description="File status (added/modified/removed)")


class PRContext(BaseModel):
    """Full PR context for review."""
    id: int = Field(..., description="PR number")
    title: str = Field(default="", description="PR title")
    description: str = Field(default="", description="PR description")
    diff_summary: str = Field(default="", description="Summary of the diff")
    test_summary: str = Field(default="", description="Test results summary")
    ci_summary: str = Field(default="", description="CI status summary")
    files: list[FileInfo] = Field(default_factory=list)
    base_branch: str = Field(default="main", description="Base branch")
    head_branch: str = Field(default="", description="Head branch")
    author: str = Field(default="", description="PR author")


class ReviewResult(BaseModel):
    """Complete review result for a batch."""
    batch_id: int = Field(..., description="Batch identifier")
    performance_findings: PerformanceReview = Field(default_factory=PerformanceReview)
    performance_fixes: FixResult = Field(default_factory=FixResult)
    security_findings: SecurityReview = Field(default_factory=SecurityReview)
    security_fixes: FixResult = Field(default_factory=FixResult)
    coverage_review: CoverageReview = Field(default_factory=CoverageReview)
    coverage_fixes: FixResult = Field(default_factory=FixResult)
    complexity_metrics: list[ComplexityMetrics] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class AggregatedReview(BaseModel):
    """Aggregated review results across all batches."""
    pr_id: int = Field(..., description="PR number")
    pr_title: str = Field(default="", description="PR title")
    total_findings: int = Field(default=0, description="Total number of findings")
    critical_findings: int = Field(default=0, description="Number of critical findings")
    high_findings: int = Field(default=0, description="Number of high severity findings")
    batches: list[ReviewResult] = Field(default_factory=list)
    summary: str = Field(default="", description="Overall review summary")
    recommendation: str = Field(
        default="needs_review", 
        description="Recommendation: approve/needs_review/request_changes"
    )
