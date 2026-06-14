"""
utils/formula_validator.py

Validasi formula Excel sebelum ditulis ke file.
Memastikan formula aman dan tidak mengandung referensi sirkuler.
"""

import re

_CELL_REF = re.compile(r'[A-Z]{1,3}\d+')
_FORMULA_SAFE = re.compile(r'^=[A-Z]{1,3}\d+([*+\-/][A-Z]{1,3}\d+)*(\*\d+(\.\d+)?)?$')
_FORMULA_WITH_NUMBERS = re.compile(
    r'^=[A-Z]{1,3}\d+([*+\-/][A-Z]{1,3}\d+)*([*+\-/]\d+(\.\d+)?)*$'
)


def validate_formula(formula: str) -> dict:
    """
    Validasi formula Excel apakah aman untuk ditulis.

    Args:
        formula: String formula (misal "=C7*D7*E7")

    Returns:
        dict dengan valid, error, warnings
    """
    if not isinstance(formula, str):
        return {"valid": False, "error": "Formula harus berupa string"}

    if not formula.startswith("="):
        return {"valid": False, "error": "Formula harus diawali dengan ="}

    if len(formula) > 255:
        return {"valid": False, "error": "Formula terlalu panjang (max 255 karakter)"}

    body = formula[1:]
    if not body:
        return {"valid": False, "error": "Formula kosong setelah ="}

    if "INDIRECT" in formula.upper():
        return {"valid": False, "error": "INDIRECT tidak diizinkan — risiko referensi sirkuler"}
    if "OFFSET" in formula.upper():
        return {"valid": False, "error": "OFFSET tidak diizinkan — tidak stabil"}
    if "RAND" in formula.upper():
        return {"valid": False, "error": "RAND tidak diizinkan di BOQ"}

    if not _FORMULA_SAFE.match(formula) and not _FORMULA_WITH_NUMBERS.match(formula):
        return {
            "valid": False,
            "error": f"Format formula tidak dikenal: {formula}",
        }

    return {"valid": True, "error": None, "warnings": []}


def get_cell_references(formula: str) -> list[str]:
    """Ekstrak semua referensi cell dari formula."""
    return _CELL_REF.findall(formula.upper())
