"""
utils/dimension_parser.py

Parse output LLM (text) menjadi JSON dimensi terstruktur.
Membersihkan dan memvalidasi hasil ekstraksi dimensi.
"""

import json
import re
from typing import Optional


def parse_llm_dimensions(raw_response: str) -> list[dict]:
    """
    Parse response LLM menjadi list item dimensi.

    Args:
        raw_response: Response text dari LLM

    Returns:
        list of dict dengan nama_item, P, L, T, satuan, confidence
    """
    clean = re.sub(r'```json\s*|\s*```', '', raw_response.strip())
    try:
        items = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', raw_response, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group())
            except Exception:
                items = []
        else:
            items = []
    return items


def validate_dimension_item(item: dict) -> dict:
    """
    Validasi dan normalisasi satu item dimensi.

    Args:
        item: Dict item dimensi mentah

    Returns:
        Dict item yang sudah divalidasi, atau dict dengan error
    """
    result = {
        "nama_item": item.get("nama_item", "Tidak dikenal"),
        "P": _normalize_number(item.get("P")),
        "L": _normalize_number(item.get("L")),
        "T": _normalize_number(item.get("T")),
        "satuan": item.get("satuan", "m³"),
        "confidence": _normalize_confidence(item.get("confidence", 1.0)),
        "catatan": item.get("catatan", ""),
    }

    if result["confidence"] < 0.7:
        result["alasan_flag"] = result.get("catatan", "Confidence rendah")

    return result


def _normalize_number(value) -> Optional[float]:
    """Normalisasi angka: string ke float, null tetap null."""
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (ValueError, TypeError):
        return None


def _normalize_confidence(value) -> float:
    """Normalisasi confidence score ke range 0-1."""
    if value is None:
        return 0.0
    try:
        val = float(value)
        if val > 1.0:
            val = val / 100.0
        return max(0.0, min(1.0, round(val, 3)))
    except (ValueError, TypeError):
        return 0.0
