"""
modules/formula_engine.py

Generate formula Excel hidup berdasarkan dimensi item BOQ.
Semua output berupa string formula (diawali =) yang akan dievaluasi Excel.
"""

from typing import Optional

FORMULA_TYPES: dict[str, str] = {
    "3D_standar": "=P*L*T",
    "3D_koefisien": "=P*L*T*koef",
    "2D_area": "=P*L",
    "linier": "=P",
    "turunan": "=vol_parent*koef",
    "jumlah_elemen": "=P*L*T*n",
}

ITEM_TYPE_CLASSIFIER: dict[str, str] = {
    "galian": "3D_standar",
    "urugan": "3D_standar",
    "pasangan": "3D_standar",
    "batu kali": "3D_standar",
    "beton": "3D_standar",
    "pondasi": "3D_standar",
    "sloof": "3D_standar",
    "ring balok": "3D_standar",
    "plesteran": "2D_area",
    "acian": "2D_area",
    "cat": "2D_area",
    "keramik": "2D_area",
    "penutup atap": "2D_area",
    "kolom": "jumlah_elemen",
    "balok": "3D_koefisien",
    "buangan": "turunan",
    "pemadatan": "turunan",
}


def classify_item(nama_item: str) -> str:
    """
    Klasifikasi item pekerjaan ke tipe rumus berdasarkan keyword.

    Args:
        nama_item: Nama item pekerjaan (misal "Galian Tanah Pondasi")

    Returns:
        Tipe formula: 3D_standar, 2D_area, linier, turunan, jumlah_elemen
    """
    nama_lower = nama_item.lower()
    for keyword, formula_type in ITEM_TYPE_CLASSIFIER.items():
        if keyword in nama_lower:
            return formula_type
    return "3D_standar"


def build_formula(
    item: dict,
    mapping: dict,
    row: int,
    case: str,
) -> dict:
    """
    Generate formula Excel untuk satu item BOQ.

    Args:
        item: Item dimensi {nama_item, P, L, T, satuan, confidence, sumber, ...}
        mapping: Output dari template_detector (col_index per kategori)
        row: Nomor baris di Excel
        case: "A", "B", atau "C"

    Returns:
        dict dengan row, cells, comments
    """
    formula_type = classify_item(item.get("nama_item", ""))
    col_p = mapping["dimensi_panjang"]["col_index"] if mapping.get("dimensi_panjang") else None
    col_l = mapping["dimensi_lebar"]["col_index"] if mapping.get("dimensi_lebar") else None
    col_t = mapping["dimensi_tinggi"]["col_index"] if mapping.get("dimensi_tinggi") else None
    vol_mapping = mapping.get("kolom_volume")
    col_vol = vol_mapping["col_index"] if vol_mapping else None
    col_rumus = mapping["kolom_rumus"]["col_index"] if mapping.get("kolom_rumus") else None

    cells: dict[str, dict] = {}
    comments: dict[str, str] = {}

    conf = item.get("confidence", 1.0)

    if col_p and item.get("P") is not None:
        cell_p = f"{col_p}{row}"
        cells[cell_p] = {"value": item["P"], "type": "dimension", "color": "#EEEDFE"}
        if conf < 0.7:
            comments[cell_p] = "⚠️ Perlu verifikasi manual — AI kurang yakin"

    if col_l and item.get("L") is not None:
        cell_l = f"{col_l}{row}"
        cells[cell_l] = {"value": item["L"], "type": "dimension", "color": "#EEEDFE"}
        if conf < 0.7:
            comments[cell_l] = "⚠️ Perlu verifikasi manual — AI kurang yakin"

    if col_t and item.get("T") is not None:
        cell_t = f"{col_t}{row}"
        cells[cell_t] = {"value": item["T"], "type": "dimension", "color": "#EEEDFE"}
        if conf < 0.7:
            comments[cell_t] = "⚠️ Perlu verifikasi manual — AI kurang yakin"
    elif col_t and formula_type == "2D_area":
        cells[f"{col_t}{row}"] = {"value": None, "type": "empty"}

    p = item.get("P")
    l = item.get("L")
    t = item.get("T")

    if formula_type == "3D_standar" and col_p and col_l and col_t:
        formula_str = f"={col_p}{row}*{col_l}{row}*{col_t}{row}"
    elif formula_type == "2D_area" and col_p and col_l:
        formula_str = f"={col_p}{row}*{col_l}{row}"
    elif formula_type == "linier" and col_p:
        formula_str = f"={col_p}{row}"
    elif formula_type == "linier":
        formula_str = "=" + str(p if p is not None else 1)
    else:
        pv = p if p is not None else 1
        lv = l if l is not None else 1
        tv = t if t is not None else 1
        formula_str = f"={pv}*{lv}*{tv}"

    if case == "A" and col_rumus and col_vol:
        cells[f"{col_rumus}{row}"] = {
            "value": formula_str.replace("=", "").replace("*", "×"),
            "type": "rumus_string",
        }
        cells[f"{col_vol}{row}"] = {"value": formula_str, "type": "formula"}
    elif case == "B" and col_vol:
        cells[f"{col_vol}{row}"] = {"value": formula_str, "type": "formula"}
    elif col_vol:
        pv = p if p is not None else 1
        lv = l if l is not None else 1
        tv = t if t is not None else 1
        hasil = pv * lv * tv
        cells[f"{col_vol}{row}"] = {"value": round(hasil, 3), "type": "angka"}
        comments[f"{col_vol}{row}"] = (
            f"Rumus: {formula_str.replace('=', '')}\n"
            f"P={p} × L={l} × T={t}"
        )

    return {"row": row, "cells": cells, "comments": comments}
