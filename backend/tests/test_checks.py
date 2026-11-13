"""
test_checks.py — tests for verify_total().
"""

import pytest
from invoices.checks import verify_total


class TestVerifyTotal:
    def test_exact_match(self):
        lines = [{"line_total": 10.00}, {"line_total": 5.00}]
        assert verify_total(lines, 15.00) is True

    def test_within_tolerance(self):
        # $0.01 rounding difference — should pass
        lines = [{"line_total": 3.33}, {"line_total": 3.33}, {"line_total": 3.33}]
        assert verify_total(lines, 9.99) is True

    def test_outside_tolerance(self):
        lines = [{"line_total": 10.00}, {"line_total": 5.00}]
        assert verify_total(lines, 15.02) is False

    def test_none_stated_total(self):
        lines = [{"line_total": 10.00}]
        assert verify_total(lines, None) is False

    def test_empty_lines(self):
        assert verify_total([], 0.00) is True

    def test_empty_lines_nonzero_total(self):
        assert verify_total([], 1.00) is False

    def test_none_line_total_treated_as_zero(self):
        lines = [{"line_total": None}, {"line_total": 10.00}]
        assert verify_total(lines, 10.00) is True

    def test_missing_line_total_key(self):
        lines = [{"description": "fee"}, {"line_total": 10.00}]
        assert verify_total(lines, 10.00) is True
