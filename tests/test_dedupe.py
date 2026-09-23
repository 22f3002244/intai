"""
Unit tests for src/entity_resolution/dedupe.py (Fix #18).
Uses mocked DataFrames — no DB connections required.
"""
import pytest
import pandas as pd
from src.entity_resolution.dedupe import (
    normalize,
    find_duplicate_customers,
    find_cross_source_matches,
    NAME_MATCH_THRESHOLD,
    EMAIL_MATCH_THRESHOLD,
)


class TestNormalize:
    def test_strips_and_lowercases(self):
        assert normalize("  ALICE  ") == "alice"

    def test_collapses_double_spaces(self):
        assert normalize("alice  bob") == "alice bob"

    def test_handles_non_string(self):
        assert normalize(123) == "123"


class TestFindDuplicateCustomers:
    def _df(self, records):
        return pd.DataFrame(records, columns=["customer_id", "full_name", "email"])

    def test_identical_names_and_emails_match(self):
        df = self._df([
            (1, "Alice Smith", "alice@example.com"),
            (2, "Alice Smith", "alice@example.com"),
        ])
        matches = find_duplicate_customers(df)
        assert len(matches) == 1
        m = matches[0]
        assert m["name_similarity"] == 100
        assert m["email_similarity"] == 100

    def test_email_dup_tag_stripped_before_comparison(self):
        """alice+dup1@example.com should match alice@example.com."""
        df = self._df([
            (1, "Bob Jones", "bob@example.com"),
            (2, "Bob Jones", "bob+dup1@example.com"),
        ])
        matches = find_duplicate_customers(df)
        assert len(matches) == 1

    def test_completely_different_records_no_match(self):
        df = self._df([
            (1, "Alice Smith", "alice@a.com"),
            (2, "Zoe Baker", "zoe@b.com"),
        ])
        matches = find_duplicate_customers(df)
        assert matches == []

    def test_single_record_no_combinations(self):
        df = self._df([(1, "Solo Person", "solo@example.com")])
        assert find_duplicate_customers(df) == []

    def test_match_keys_present(self):
        df = self._df([
            (1, "Jane Doe", "jane@example.com"),
            (2, "Jane Doe", "jane@example.com"),
        ])
        match = find_duplicate_customers(df)[0]
        assert "customer_id_a" in match
        assert "customer_id_b" in match
        assert "name_similarity" in match
        assert "email_similarity" in match


class TestFindCrossSourceMatches:
    def _customers(self, records):
        return pd.DataFrame(records, columns=["customer_id", "email"])

    def _leads(self, records):
        return pd.DataFrame(records, columns=["lead_id", "email"])

    def test_exact_email_match(self):
        customers = self._customers([(1, "alice@example.com")])
        leads = self._leads([(101, "alice@example.com")])
        matches = find_cross_source_matches(customers, leads)
        assert len(matches) == 1
        assert matches[0]["customer_id"] == 1
        assert matches[0]["lead_id"] == 101
        assert matches[0]["email_similarity"] == 100.0

    def test_no_match_for_different_emails(self):
        customers = self._customers([(1, "alice@example.com")])
        leads = self._leads([(101, "zoe@other.com")])
        matches = find_cross_source_matches(customers, leads)
        assert matches == []

    def test_empty_leads_returns_empty(self):
        customers = self._customers([(1, "alice@example.com")])
        leads = self._leads([])
        assert find_cross_source_matches(customers, leads) == []

    def test_empty_customers_returns_empty(self):
        customers = self._customers([])
        leads = self._leads([(101, "alice@example.com")])
        assert find_cross_source_matches(customers, leads) == []

    def test_multiple_matches(self):
        customers = self._customers([
            (1, "alice@example.com"),
            (2, "bob@example.com"),
        ])
        leads = self._leads([
            (101, "alice@example.com"),
            (102, "bob@example.com"),
            (103, "carol@example.com"),
        ])
        matches = find_cross_source_matches(customers, leads)
        assert len(matches) == 2
