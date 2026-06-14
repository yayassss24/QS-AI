"""Tests for dimension_parser.py"""

import pytest
from utils.dimension_parser import (
    parse_llm_dimensions,
    validate_dimension_item,
    _normalize_number,
    _normalize_confidence,
)


class TestNormalizeNumber:
    @pytest.mark.parametrize("input_val,expected", [
        (12.5, 12.5),
        ("12.5", 12.5),
        ("3", 3.0),
        (None, None),
        ("abc", None),
    ])
    def test_normalize(self, input_val, expected):
        assert _normalize_number(input_val) == expected


class TestNormalizeConfidence:
    @pytest.mark.parametrize("input_val,expected", [
        (0.92, 0.92),
        ("0.5", 0.5),
        (None, 0.0),
        (50, 0.5),
        (1.5, 0.015),
        (-0.5, 0.0),
    ])
    def test_normalize(self, input_val, expected):
        assert _normalize_confidence(input_val) == expected


class TestValidateDimensionItem:
    def test_valid_item(self):
        item = {"nama_item": "Test", "P": 12.5, "L": 0.8, "T": 1.2, "satuan": "m³", "confidence": 0.92}
        result = validate_dimension_item(item)
        assert result["P"] == 12.5
        assert result["confidence"] == 0.92

    def test_low_confidence_adds_alasan(self):
        item = {"nama_item": "Test", "P": 12.5, "confidence": 0.5}
        result = validate_dimension_item(item)
        assert "alasan_flag" in result

    def test_missing_name_default(self):
        item = {"P": 1}
        result = validate_dimension_item(item)
        assert result["nama_item"] == "Tidak dikenal"

    def test_null_dimensions(self):
        item = {"nama_item": "Test", "P": None, "L": None, "T": None}
        result = validate_dimension_item(item)
        assert result["P"] is None
        assert result["L"] is None
        assert result["T"] is None


class TestParseLLMDimensions:
    def test_parse_valid_json(self):
        raw = '[{"nama_item": "Test", "P": 12.5}]'
        result = parse_llm_dimensions(raw)
        assert len(result) == 1
        assert result[0]["nama_item"] == "Test"

    def test_parse_with_markdown_fence(self):
        raw = '```json\n[{"nama_item": "Test", "P": 5}]\n```'
        result = parse_llm_dimensions(raw)
        assert len(result) == 1

    def test_parse_invalid_returns_empty(self):
        result = parse_llm_dimensions("not json at all")
        assert result == []

    def test_parse_empty_string(self):
        result = parse_llm_dimensions("")
        assert result == []
