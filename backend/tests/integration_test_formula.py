"""Integration tests for formula_engine — all formula types with full mappings."""

import pytest
from modules.formula_engine import build_formula, classify_item


@pytest.fixture
def full_mapping():
    return {
        "dimensi_panjang": {"nama_kolom": "Pjg", "col_index": "C", "col_num": 3},
        "dimensi_lebar": {"nama_kolom": "Lbr", "col_index": "D", "col_num": 4},
        "dimensi_tinggi": {"nama_kolom": "T", "col_index": "E", "col_num": 5},
        "kolom_rumus": {"nama_kolom": "Rumus", "col_index": "F", "col_num": 6},
        "kolom_volume": {"nama_kolom": "Volume", "col_index": "G", "col_num": 7},
        "kolom_satuan": {"nama_kolom": "Sat", "col_index": "H", "col_num": 8},
        "kolom_uraian": {"nama_kolom": "Uraian", "col_index": "B", "col_num": 2},
        "kolom_koefisien": {"nama_kolom": "Koef", "col_index": "I", "col_num": 9},
    }


class TestFormulaTypesIntegration:
    def test_linier(self, full_mapping):
        item = {"nama_item": "Besi Tulangan D10", "P": 12.0, "L": None, "T": None, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=2, case="A")
        cells = result["cells"]
        assert cells["G2"]["value"] == "=C2", f"Expected =C2, got {cells['G2']['value']}"

    def test_linier_with_named_item(self, full_mapping):
        item = {"nama_item": "Pipa PVC 2inch", "P": 12.0, "L": None, "T": None, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=2, case="A")
        assert result["cells"]["G2"]["value"] == "=C2"

    def test_linier_no_col_p(self, full_mapping):
        no_p = {k: v for k, v in full_mapping.items() if k != "dimensi_panjang"}
        no_p["dimensi_panjang"] = None
        item = {"nama_item": "Pipa PVC", "P": 12.0, "L": None, "T": None, "confidence": 1.0}
        result = build_formula(item, no_p, row=2, case="A")
        assert "=12" in result["cells"]["G2"]["value"]

    def test_jumlah_elemen_with_koef(self, full_mapping):
        item = {"nama_item": "Kolom 20x20", "P": 0.2, "L": 0.2, "T": 3.5, "koefisien": 12, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=3, case="B")
        cells = result["cells"]
        assert cells["G3"]["value"] == "=C3*D3*E3*I3", f"Expected =C3*D3*E3*I3, got {cells['G3']['value']}"
        assert "I3" in cells

    def test_jumlah_elemen_fallback(self, full_mapping):
        no_p = {k: v for k, v in full_mapping.items()}
        no_p["dimensi_panjang"] = None
        no_p["dimensi_lebar"] = None
        no_p["dimensi_tinggi"] = None
        item = {"nama_item": "Kolom 20x20", "P": 0.2, "L": 0.2, "T": 3.5, "koefisien": 12, "confidence": 1.0}
        result = build_formula(item, no_p, row=3, case="B")
        assert "G3*I3" in result["cells"]["G3"]["value"]

    def test_3d_koefisien_with_koef(self, full_mapping):
        item = {"nama_item": "Balok Lantai", "P": 4.0, "L": 0.3, "T": 0.5, "koefisien": 1.5, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=4, case="B")
        cells = result["cells"]
        assert cells["G4"]["value"] == "=C4*D4*E4*I4", f"Expected =C4*D4*E4*I4, got {cells['G4']['value']}"

    def test_turunan_with_koef(self, full_mapping):
        item = {"nama_item": "Pemadatan Tanah", "P": None, "L": None, "T": None, "koefisien": 0.2, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=5, case="B")
        cells = result["cells"]
        assert cells["G5"]["value"] == "=G4*I5", f"Expected =G4*I5, got {cells['G5']['value']}"

    def test_turunan_first_row_fallback(self, full_mapping):
        item = {"nama_item": "Pemadatan Tanah", "P": None, "L": None, "T": None, "koefisien": 0.2, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=1, case="B")
        cells = result["cells"]
        assert cells["G1"]["value"] == "=G1*1", f"Expected =G1*1, got {cells['G1']['value']}"

    def test_3d_standar_still_works(self, full_mapping):
        item = {"nama_item": "Galian Tanah Pondasi", "P": 12.5, "L": 0.8, "T": 1.2, "confidence": 0.92}
        result = build_formula(item, full_mapping, row=2, case="A")
        assert result["cells"]["G2"]["value"] == "=C2*D2*E2"

    def test_2d_area_still_works(self, full_mapping):
        item = {"nama_item": "Plesteran Dinding", "P": 45.0, "L": 3.0, "T": None, "confidence": 0.85}
        result = build_formula(item, full_mapping, row=3, case="B")
        assert result["cells"]["G3"]["value"] == "=C3*D3"

    def test_koefisien_cell_written(self, full_mapping):
        item = {"nama_item": "Kolom 20x20", "P": 0.2, "L": 0.2, "T": 3.5, "koefisien": 12, "confidence": 1.0}
        result = build_formula(item, full_mapping, row=3, case="B")
        assert "I3" in result["cells"]
        assert result["cells"]["I3"]["value"] == 12

    def test_classifier_keys_complete(self):
        from modules.formula_engine import ITEM_TYPE_CLASSIFIER, FORMULA_TYPES
        for v in ITEM_TYPE_CLASSIFIER.values():
            assert v in FORMULA_TYPES, f"Classifier value '{v}' not in FORMULA_TYPES"
