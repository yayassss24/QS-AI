"""Tests for formula_validator.py"""

import pytest
from utils.formula_validator import validate_formula, get_cell_references


class TestValidateFormula:
    @pytest.mark.parametrize("formula", [
        "=C7*D7*E7",
        "=B5*C5",
        "=A1",
        "=A1*2",
        "=A1+B1",
        "=C7*D7*E7*F7",
    ])
    def test_valid_formulas(self, formula):
        result = validate_formula(formula)
        assert result["valid"] is True, f"Formula {formula} harus valid"

    @pytest.mark.parametrize("formula,error_substr", [
        ("C7*D7", "harus diawali dengan ="),
        ("", "harus diawali dengan ="),
        ("=INDIRECT(A1)", "INDIRECT"),
        ("=OFFSET(A1,0,0)", "OFFSET"),
        ("=RAND()", "RAND"),
    ])
    def test_invalid_formulas(self, formula, error_substr):
        result = validate_formula(formula)
        assert result["valid"] is False
        assert error_substr in result["error"]

    def test_non_string_returns_error(self):
        result = validate_formula(123)
        assert result["valid"] is False

    def test_empty_after_equals(self):
        result = validate_formula("=")
        assert result["valid"] is False


class TestGetCellReferences:
    def test_finds_references(self):
        refs = get_cell_references("=C7*D7*E7")
        assert "C7" in refs
        assert "D7" in refs
        assert "E7" in refs

    def test_empty_for_no_refs(self):
        refs = get_cell_references("=42")
        assert refs == []

    def test_handles_mixed_case(self):
        refs = get_cell_references("=a1*b2")
        assert "A1" in refs
        assert "B2" in refs
