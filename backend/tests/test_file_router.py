"""Tests for file_router.py"""

import pytest
import tempfile
from pathlib import Path
from modules.file_router import detect_file_type, route_to_reader, SUPPORTED_FORMATS


class TestDetectFileType:
    @pytest.mark.parametrize("ext,category", [
        ("pdf", "pdf"),
        ("jpg", "image"),
        ("jpeg", "image"),
        ("png", "image"),
        ("webp", "image"),
        ("tiff", "image"),
        ("bmp", "image"),
        ("heic", "image"),
        ("dxf", "cad"),
        ("dwg", "cad"),
    ])
    def test_supported_formats(self, ext, category):
        path = f"/tmp/test.{ext}"
        result = detect_file_type(path)
        assert result["supported"] is True
        assert result["category"] == category
        assert result["error"] is None

    def test_unsupported_format(self):
        result = detect_file_type("/tmp/test.xyz")
        assert result["supported"] is False
        assert result["error"] is not None
        assert "tidak didukung" in result["error"]

    def test_all_supported_formats_in_map(self):
        for ext in SUPPORTED_FORMATS:
            path = f"/tmp/test.{ext}"
            result = detect_file_type(path)
            assert result["supported"] is True

    def test_extension_case_insensitive(self):
        result_upper = detect_file_type("/tmp/test.PDF")
        result_lower = detect_file_type("/tmp/test.pdf")
        assert result_upper == result_lower

    def test_dwg_returns_error_from_router(self):
        result = route_to_reader("/tmp/test.dwg")
        assert result["status"] == "error"
        assert "ODA" in result["message"]
