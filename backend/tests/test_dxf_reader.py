"""Tests for dxf_reader.py"""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from modules.dxf_reader import extract_dimensions_from_dxf


FAKE_EZDXF = MagicMock()


@pytest.fixture(autouse=True)
def _fake_ezdxf():
    """Make ezdxf importable via sys.modules and refuse nonexistent files."""
    FAKE_EZDXF.reset_mock()
    FAKE_EZDXF.readfile.side_effect = lambda p: (_ for _ in ()).throw(
        FileNotFoundError(f"File tidak ditemukan: {p}")
    ) if not os.path.exists(p) else MagicMock()
    sys.modules["ezdxf"] = FAKE_EZDXF
    yield
    sys.modules.pop("ezdxf", None)


class TestExtractDimensionsFromDxf:
    def test_missing_file_returns_error(self):
        result = extract_dimensions_from_dxf("/nonexistent/file.dxf")
        assert result["status"] == "error"

    def test_response_has_required_keys(self):
        path = tempfile.mktemp(suffix=".dxf")
        try:
            FAKE_EZDXF.reset_mock()
            FAKE_EZDXF.readfile.side_effect = None
            mock_msp = MagicMock()
            mock_msp.query.return_value = []
            FAKE_EZDXF.readfile.return_value.modelspace.return_value = mock_msp
            result = extract_dimensions_from_dxf(path)
            assert result["status"] == "ok"
            assert "source" in result
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_readfile_error_returns_error(self):
        path = tempfile.mktemp(suffix=".dxf")
        try:
            FAKE_EZDXF.readfile.side_effect = Exception("corrupt file")
            result = extract_dimensions_from_dxf(path)
            assert result["status"] == "error"
        finally:
            if os.path.exists(path):
                os.unlink(path)
