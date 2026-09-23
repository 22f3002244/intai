"""
Unit tests for src/metadata/pii_detection.py (Fix #18).
spaCy is mocked so tests run without loading the model.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock



from src.metadata.pii_detection import (
    classify_by_pattern,
    PATTERN_MATCH_THRESHOLD,
)


class TestClassifyByPattern:
    def _series(self, values):
        return pd.Series(values)

    def test_detects_email(self):
        emails = [f"user{i}@example.com" for i in range(80)]
        label, confidence = classify_by_pattern(self._series(emails))
        assert label == "email"
        assert confidence >= PATTERN_MATCH_THRESHOLD

    def test_detects_ssn(self):
        ssns = [f"{i:03d}-{i:02d}-{i:04d}" for i in range(1, 80)]
        label, confidence = classify_by_pattern(self._series(ssns))
        assert label == "ssn_like"

    def test_no_match_for_random_strings(self):
        data = [f"random_word_{i}" for i in range(80)]
        label, confidence = classify_by_pattern(self._series(data))
        assert label is None
        assert confidence == 0.0

    def test_empty_series_returns_none(self):
        label, confidence = classify_by_pattern(pd.Series([], dtype=str))
        assert label is None
        assert confidence == 0.0

    def test_all_null_series_returns_none(self):
        label, confidence = classify_by_pattern(pd.Series([None] * 50))
        assert label is None

    def test_confidence_is_between_0_and_1(self):
        emails = [f"a{i}@b.com" for i in range(50)]
        _, confidence = classify_by_pattern(self._series(emails))
        assert 0.0 <= confidence <= 1.0

    def test_mixed_data_below_threshold_returns_none(self):
        # Only ~30% are emails — below the 70% threshold.
        mixed = [f"a{i}@b.com" if i < 30 else f"notanemail_{i}" for i in range(100)]
        label, _ = classify_by_pattern(self._series(mixed))
        assert label is None


