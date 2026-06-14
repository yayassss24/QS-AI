"""Tests for formula_engine.py"""

import pytest
from modules.formula_engine import classify_item, build_formula, ITEM_TYPE_CLASSIFIER


class TestClassifier:
    @pytest.mark.parametrize("nama_item,expected", [
        ("Galian Tanah Pondasi", "3D_standar"),
        ("Urugan Kembali", "3D_standar"),
        ("Pasangan Batu Kali", "3D_standar"),
        ("Beton K250", "3D_standar"),
        ("Plesteran Dinding 1:4", "2D_area"),
        ("Acian Dinding", "2D_area"),
        ("Cat Tembok", "2D_area"),
        ("Keramik 40x40", "2D_area"),
        ("Kolom 20x20", "jumlah_elemen"),
        ("Pemadatan Tanah", "turunan"),
    ])
    def test_classify_item(self, nama_item, expected):
        assert classify_item(nama_item) == expected

    def test_default_fallback(self):
        assert classify_item("unknown item name") == "3D_standar"

    def test_all_classifier_keys_lowercase(self):
        for k in ITEM_TYPE_CLASSIFIER:
            assert k == k.lower(), f"Key '{k}' harus lowercase"


class TestBuildFormula:
    def test_3d_standar_case_a(self, sample_items, sample_mapping):
        item = sample_items[0]
        result = build_formula(item, sample_mapping, row=2, case="A")
        assert result["row"] == 2
        cells = result["cells"]
        assert "G2" in cells  # volume
        assert cells["G2"]["type"] == "formula"
        assert cells["G2"]["value"] == "=C2*D2*E2"
        assert "F2" in cells  # rumus
        assert cells["F2"]["type"] == "rumus_string"
        assert "×" in cells["F2"]["value"]

    def test_3d_standar_case_b(self, sample_items, sample_mapping):
        no_rumus = {k: v for k, v in sample_mapping.items() if k != "kolom_rumus"}
        no_rumus["kolom_rumus"] = None
        result = build_formula(sample_items[0], no_rumus, row=5, case="B")
        assert "G5" in result["cells"]
        assert result["cells"]["G5"]["type"] == "formula"

    def test_2d_area(self, sample_items, sample_mapping):
        item = sample_items[1]
        result = build_formula(item, sample_mapping, row=3, case="B")
        cells = result["cells"]
        assert "E3" in cells
        assert cells["E3"]["type"] == "empty"

    def test_low_confidence_adds_comment(self, sample_items, sample_mapping):
        item = sample_items[2]  # confidence 0.45
        result = build_formula(item, sample_mapping, row=4, case="B")
        comments = result["comments"]
        has_warning = any("⚠️" in c for c in comments.values())
        assert has_warning

    def test_case_c_no_dimensions(self, sample_mapping):
        item = {"nama_item": "Test", "P": 2, "L": 3, "T": 4, "confidence": 1.0}
        result = build_formula(item, sample_mapping, row=6, case="C")
        cells = result["cells"]
        assert "G6" in cells
        assert cells["G6"]["type"] == "angka"

    def test_returns_row_in_result(self, sample_items, sample_mapping):
        result = build_formula(sample_items[0], sample_mapping, row=10, case="A")
        assert result["row"] == 10
