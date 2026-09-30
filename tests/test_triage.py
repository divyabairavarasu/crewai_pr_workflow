"""Tests for the triage module."""
import pytest

from pr_workflow.triage import (
    compute_loc,
    is_test_path,
    module_key,
    risk_hits,
    risk_score,
    triage_batches,
    build_risk_report,
)


class TestComputeLoc:
    def test_with_loc_field(self):
        assert compute_loc({"loc": 100}) == 100

    def test_with_added_removed(self):
        assert compute_loc({"added": 50, "removed": 30}) == 80

    def test_empty_file(self):
        assert compute_loc({}) == 0


class TestIsTestPath:
    def test_test_directory(self):
        assert is_test_path("src/tests/test_auth.py")
        assert is_test_path("tests/unit/test_utils.py")
        assert is_test_path("__tests__/component.test.js")

    def test_test_file_suffix(self):
        assert is_test_path("auth_test.py")
        assert is_test_path("component.spec.ts")
        assert is_test_path("utils.test.js")

    def test_non_test_path(self):
        assert not is_test_path("src/auth/auth.py")
        assert not is_test_path("utils/helpers.py")


class TestRiskScore:
    def test_high_risk_keywords(self):
        assert risk_score("src/auth/login.py") > 0
        assert risk_score("db/migrations/001.sql") > 0
        assert risk_score("config/security.yaml") > 0

    def test_low_risk_path(self):
        assert risk_score("src/utils/format.py") == 0
        assert risk_score("components/Button.tsx") == 0


class TestTriageBatches:
    def test_single_batch_under_limit(self):
        files = [
            {"path": "a.py", "loc": 100},
            {"path": "b.py", "loc": 200},
        ]
        result = triage_batches(files, max_loc=500)
        
        assert result["total_loc"] == 300
        assert len(result["batches"]) == 1
        assert result["batches"][0]["loc"] == 300

    def test_multiple_batches_over_limit(self):
        files = [
            {"path": "src/a.py", "loc": 1000},
            {"path": "src/b.py", "loc": 1000},
            {"path": "src/c.py", "loc": 1000},
        ]
        result = triage_batches(files, max_loc=1500)
        
        assert result["total_loc"] == 3000
        assert len(result["batches"]) >= 2


class TestBuildRiskReport:
    def test_sorts_by_risk(self):
        files = [
            {"path": "utils.py", "loc": 100},
            {"path": "auth/login.py", "loc": 50},
            {"path": "db/query.py", "loc": 75},
        ]
        report = build_risk_report(files)
        
        # High risk files should be first
        assert report["files"][0]["risk_score"] >= report["files"][1]["risk_score"]
