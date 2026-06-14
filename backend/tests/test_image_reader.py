"""Tests for image_reader.py"""

import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch

from PIL import Image

from modules.image_reader import (
    _normalize_image,
    _image_to_base64,
    extract_dimensions_from_image,
    NEEDS_CONVERSION,
)


class TestNeedsConversion:
    def test_expected_extensions(self):
        assert ".heic" in NEEDS_CONVERSION
        assert ".heif" in NEEDS_CONVERSION
        assert ".tiff" in NEEDS_CONVERSION
        assert ".bmp" in NEEDS_CONVERSION
        assert ".webp" in NEEDS_CONVERSION
        assert ".png" not in NEEDS_CONVERSION


class TestNormalizeImage:
    def test_png_passthrough(self, temp_image):
        result, was_converted = _normalize_image(temp_image)
        assert result.endswith("_normalized.png")
        # cleanup
        if os.path.exists(result):
            os.unlink(result)

    def test_creates_png_output(self, temp_image):
        result, was_converted = _normalize_image(temp_image)
        assert result.lower().endswith(".png")
        if os.path.exists(result):
            os.unlink(result)

    def test_rgba_to_rgb(self):
        path = tempfile.mktemp(suffix=".png")
        img = Image.new("RGBA", (50, 50), (255, 0, 0, 128))
        img.save(path)
        try:
            result, converted = _normalize_image(path)
            from PIL import Image as PILImage
            opened = PILImage.open(result)
            assert opened.mode == "RGB"
            opened.close()
            if os.path.exists(result):
                os.unlink(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_large_image_resize(self):
        path = tempfile.mktemp(suffix=".png")
        img = Image.new("RGB", (5000, 3000), color=(255, 255, 255))
        img.save(path)
        try:
            result, converted = _normalize_image(path)
            from PIL import Image as PILImage
            opened = PILImage.open(result)
            assert max(opened.size) <= 4096
            opened.close()
            if os.path.exists(result):
                os.unlink(result)
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestImageToBase64:
    def test_returns_string(self, temp_image):
        result = _image_to_base64(temp_image)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_valid_base64(self, temp_image):
        import base64
        result = _image_to_base64(temp_image)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0


class TestExtractDimensions:
    def test_requires_llm_router(self, temp_image):
        result = extract_dimensions_from_image(temp_image)
        assert result["status"] == "error"
        assert "wajib" in result["message"]

    @patch("modules.image_reader._ocr_image")
    def test_calls_llm_router(self, mock_ocr, temp_image, mock_llm_router):
        mock_ocr.return_value = []
        result = extract_dimensions_from_image(temp_image, llm_router=mock_llm_router)
        assert result["status"] == "ok"


class TestNormalizeErrors:
    def test_nonexistent_file(self):
        with pytest.raises(RuntimeError, match="Gagal normalisasi"):
            _normalize_image("/nonexistent/file.png")
