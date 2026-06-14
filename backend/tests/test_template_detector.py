"""Tests for template_detector.py"""

import pytest
from modules.template_detector import (
    _find_header_row,
    _semantic_match,
    _col_letter,
    detect_template_format,
    SEMANTIC_MAP,
)


class TestSemanticMap:
    def test_keys_are_present(self):
        expected_keys = [
            "dimensi_panjang", "dimensi_lebar", "dimensi_tinggi",
            "kolom_volume", "kolom_rumus", "kolom_satuan",
            "kolom_uraian", "kolom_koefisien",
        ]
        for k in expected_keys:
            assert k in SEMANTIC_MAP

    def test_each_key_has_keywords(self):
        for k, v in SEMANTIC_MAP.items():
            assert len(v) >= 2, f"{k} hanya punya {len(v)} keyword"


class TestSemanticMatch:
    @pytest.mark.parametrize("input_val,expected", [
        ("panjang", "dimensi_panjang"),
        ("pjg", "dimensi_panjang"),
        ("lebar", "dimensi_lebar"),
        ("lbr", "dimensi_lebar"),
        ("tinggi", "dimensi_tinggi"),
        ("tebal", "dimensi_tinggi"),
        ("volume", "kolom_volume"),
        ("kubikasi", "kolom_volume"),
        ("rumus", "kolom_rumus"),
        ("satuan", "kolom_satuan"),
        ("uraian", "kolom_uraian"),
        ("koefisien", "kolom_koefisien"),
    ])
    def test_exact_match(self, input_val, expected):
        assert _semantic_match(input_val) == expected

    def test_case_insensitive(self):
        assert _semantic_match("PANJANG") == "dimensi_panjang"

    def test_partial_match(self):
        assert _semantic_match("Panjang (m)") == "dimensi_panjang"

    def test_none_input(self):
        assert _semantic_match(None) is None

    def test_no_match(self):
        assert _semantic_match("random_text_xyz") is None


class TestColLetter:
    @pytest.mark.parametrize("col_num,expected", [
        (1, "A"), (2, "B"), (3, "C"), (26, "Z"),
        (27, "AA"), (28, "AB"), (52, "AZ"), (53, "BA"),
    ])
    def test_conversion(self, col_num, expected):
        assert _col_letter(col_num) == expected


class TestDetectTemplateFormat:
    def test_detect_case_a(self, temp_xlsx):
        result = detect_template_format(temp_xlsx)
        assert result["status"] == "ok"
        assert result["case"] == "A"
        assert result["header_row"] == 1
        assert result["data_start_row"] == 2

    def test_mapping_contains_all_keys(self, temp_xlsx):
        result = detect_template_format(temp_xlsx)
        mapping = result["mapping"]
        for key in ["dimensi_panjang", "dimensi_lebar", "dimensi_tinggi",
                     "kolom_rumus", "kolom_volume", "kolom_satuan", "kolom_uraian"]:
            assert mapping[key] is not None, f"{key} tidak terdeteksi"

    def test_mapping_values(self, temp_xlsx):
        result = detect_template_format(temp_xlsx)
        m = result["mapping"]
        assert m["dimensi_panjang"]["col_index"] == "C"
        assert m["dimensi_lebar"]["col_index"] == "D"
        assert m["dimensi_tinggi"]["col_index"] == "E"
        assert m["kolom_volume"]["col_index"] == "G"

    def test_find_header_row(self, temp_xlsx):
        from openpyxl import load_workbook
        wb = load_workbook(temp_xlsx)
        ws = wb.active
        assert _find_header_row(ws) == 1
        wb.close()
