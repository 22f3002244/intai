"""
Unit tests for src/quality/quality_engine.py (Fix #18).
"""
import pytest
from src.quality.quality_engine import score_column, score_dataset


# ── score_column ───────────────────────────────────────────────────────────────

class TestScoreColumn:
    def _profile(self, null_rate=0.0, cardinality_ratio=1.0, col_name="value", outlier_rate=0.0):
        return {
            "null_rate": null_rate,
            "cardinality_ratio": cardinality_ratio,
            "outlier_rate": outlier_rate,
        }

    def test_perfect_column(self):
        score, issues = score_column("value", self._profile())
        assert score == 100
        assert issues == []

    def test_moderate_null_rate(self):
        score, issues = score_column("value", self._profile(null_rate=0.10))
        assert score == 85
        assert any("moderate null rate" in i for i in issues)

    def test_high_null_rate(self):
        score, issues = score_column("value", self._profile(null_rate=0.20))
        assert score == 60
        assert any("high null rate" in i for i in issues)

    def test_id_column_low_cardinality(self):
        score, issues = score_column("customer_id", self._profile(cardinality_ratio=0.5))
        assert score <= 75
        assert any("low uniqueness" in i for i in issues)

    def test_id_column_high_cardinality_is_fine(self):
        score, issues = score_column("customer_id", self._profile(cardinality_ratio=0.95))
        assert score == 100
        assert issues == []

    def test_high_outlier_rate_penalised(self):
        score, issues = score_column("age", self._profile(outlier_rate=0.10))
        assert score <= 85
        assert any("outlier rate" in i for i in issues)

    def test_low_outlier_rate_not_penalised(self):
        score, issues = score_column("age", self._profile(outlier_rate=0.02))
        assert score == 100
        assert issues == []

    def test_score_never_below_zero(self):
        # All penalties at once should not produce a negative score.
        score, _ = score_column(
            "record_id",
            self._profile(null_rate=0.50, cardinality_ratio=0.1, outlier_rate=0.20),
        )
        assert score >= 0


# ── score_dataset ──────────────────────────────────────────────────────────────

class TestScoreDataset:
    def _make_profile(self, columns: dict, dup_count=0, dup_rate=0.0):
        return {
            "dataset": "test_ds",
            "row_count": 100,
            "column_count": len(columns),
            "duplicate_row_count": dup_count,
            "duplicate_row_rate": dup_rate,
            "columns": columns,
        }

    def test_all_perfect_columns(self):
        cols = {
            "a": {"null_rate": 0.0, "cardinality_ratio": 1.0, "outlier_rate": 0.0},
            "b": {"null_rate": 0.0, "cardinality_ratio": 1.0, "outlier_rate": 0.0},
        }
        result = score_dataset(self._make_profile(cols))
        assert result["overall_score"] == 100.0
        assert result["flagged_issues"] == []

    def test_duplicate_row_fields_surfaced(self):
        cols = {"x": {"null_rate": 0.0, "cardinality_ratio": 1.0, "outlier_rate": 0.0}}
        result = score_dataset(self._make_profile(cols, dup_count=5, dup_rate=0.05))
        assert result["duplicate_row_count"] == 5
        assert result["duplicate_row_rate"] == 0.05

    def test_mixed_issues_lower_overall_score(self):
        cols = {
            "ok_col": {"null_rate": 0.0, "cardinality_ratio": 1.0, "outlier_rate": 0.0},
            "bad_col": {"null_rate": 0.20, "cardinality_ratio": 1.0, "outlier_rate": 0.0},
        }
        result = score_dataset(self._make_profile(cols))
        assert result["overall_score"] < 100.0
        assert len(result["flagged_issues"]) == 1
