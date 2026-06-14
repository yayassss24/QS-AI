"""Tests for pdf_reader.py"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from modules.pdf_reader import (
    _assess_quality,
    extract_dimensions_from_pdf,
)


class TestAssessQuality:
    def test_empty_vector_returns_false(self):
        ok, _ = _assess_quality([{"page": 1, "raw_texts": []}], [])
        assert ok is False

    def test_sufficient_vector_returns_true(self):
        texts = [{"text": "12.5", "bbox": [0, 0, 10, 10]}]
        ok, _ = _assess_quality([{"page": 1, "raw_texts": texts * 5}], [])
        assert ok is True


FAKE_PAGE = MagicMock()
FAKE_PAGE.get_text.return_value = {"blocks": []}

FAKE_DOC = MagicMock()
FAKE_DOC.__iter__.return_value = iter([FAKE_PAGE])
FAKE_DOC.__enter__.return_value = FAKE_DOC

FAKE_FITZ = MagicMock()
FAKE_FITZ.open.return_value = FAKE_DOC
FAKE_FITZ.Matrix.return_value = None

FAKE_PADDLE = MagicMock()
FAKE_PADDLE.PaddleOCR.return_value.ocr.return_value = []


@pytest.fixture(autouse=True)
def _fake_heavy_deps():
    """Make fitz and paddleocr importable via sys.modules."""
    REAL_OS_PATH_EXISTS = os.path.exists
    def _fake_fitz_open(path):
        if not REAL_OS_PATH_EXISTS(path):
            raise FileNotFoundError(f"No such file: {path}")
        return FAKE_DOC
    FAKE_FITZ.open.side_effect = _fake_fitz_open
    sys.modules["fitz"] = FAKE_FITZ
    sys.modules["paddleocr"] = FAKE_PADDLE
    FAKE_PADDLE.PaddleOCR.return_value.ocr.return_value = []
    yield
    sys.modules.pop("fitz", None)
    sys.modules.pop("paddleocr", None)


class TestExtractDimensionsFromPdf:

    def test_missing_file_returns_error(self):
        result = extract_dimensions_from_pdf("/nonexistent/file.pdf")
        assert result["status"] == "error"

    def test_response_has_required_keys(self):
        result = extract_dimensions_from_pdf("/nonexistent/file.pdf")
        assert "status" in result

    def test_empty_pdf_handled_gracefully(self):
        path = tempfile.mktemp(suffix=".pdf")
        open(path, "a").close()
        try:
            result = extract_dimensions_from_pdf(path)
            assert result["status"] == "ok"
            assert "items" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    @patch("modules.pdf_reader._extract_scanned_pdf")
    def test_vector_fallback_to_ocr(self, mock_scanned):
        mock_scanned.return_value = [{"page": 1, "ocr_result": [
            {"text": "12.5", "confidence": 0.95, "bbox": [0, 0, 10, 10]},
            {"text": "1.2", "confidence": 0.92, "bbox": [0, 0, 10, 10]},
            {"text": "m³", "confidence": 0.90, "bbox": [0, 0, 10, 10]},
        ]}]
        path = tempfile.mktemp(suffix=".pdf")
        open(path, "a").close()
        try:
            result = extract_dimensions_from_pdf(path, llm_router=MagicMock())
            assert result["status"] == "ok"
            assert result["source"] == "paddleocr"
        finally:
            if os.path.exists(path):
                os.unlink(path)
