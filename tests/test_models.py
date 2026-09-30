"""Tests for the models module."""
import pytest
from pydantic import ValidationError

from pr_workflow.models import (
    Finding,
    PerformanceReview,
    SecurityReview,
    CoverageReview,
    Severity,
    ReviewCategory,
    BatchInfo,
    TriageResult,
)


class TestFinding:
    def test_valid_finding(self):
        finding = Finding(
            file="src/auth.py",
            line=42,
            severity=Severity.HIGH,
            category=ReviewCategory.SECURITY,
            issue="SQL injection vulnerability",
            suggested_change="Use parameterized queries",
        )
        assert finding.file == "src/auth.py"
        assert finding.severity == Severity.HIGH

    def test_default_values(self):
        finding = Finding(
            file="test.py",
            category=ReviewCategory.PERFORMANCE,
            issue="Slow loop",
        )
        assert finding.line == 1
        assert finding.severity == Severity.MEDIUM
        assert finding.confidence == 0.8

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Finding(
                file="test.py",
                category=ReviewCategory.PERFORMANCE,
                issue="Test",
                confidence=1.5,  # Out of bounds
            )


class TestPerformanceReview:
    def test_empty_review(self):
        review = PerformanceReview()
        assert review.findings == []
        assert review.summary == ""

    def test_with_findings(self):
        finding = Finding(
            file="test.py",
            category=ReviewCategory.PERFORMANCE,
            issue="O(n^2) complexity",
        )
        review = PerformanceReview(
            findings=[finding],
            summary="Found 1 performance issue",
        )
        assert len(review.findings) == 1


class TestSecurityReview:
    def test_default_risk_level(self):
        review = SecurityReview()
        assert review.risk_level == Severity.LOW

    def test_with_cve_references(self):
        review = SecurityReview(
            cve_references=["CVE-2024-1234", "CVE-2024-5678"],
        )
        assert len(review.cve_references) == 2


class TestCoverageReview:
    def test_coverage_bounds(self):
        review = CoverageReview(coverage_percent=85.5)
        assert review.coverage_percent == 85.5

        with pytest.raises(ValidationError):
            CoverageReview(coverage_percent=150.0)  # Out of bounds


class TestTriageResult:
    def test_valid_triage(self):
        batch = BatchInfo(
            batch_id=1,
            files=["a.py", "b.py"],
            loc=500,
        )
        result = TriageResult(
            total_loc=500,
            batches=[batch],
        )
        assert result.total_loc == 500
        assert len(result.batches) == 1
