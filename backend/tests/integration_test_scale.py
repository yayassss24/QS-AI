"""Integration tests for scale application in PDF and image readers."""

from unittest.mock import MagicMock, patch

import pytest


class TestPdfScale:
    def test_scale_applied_to_9router_items(self):
        from modules.pdf_reader import extract_dimensions_from_pdf

        with (
            patch("modules.pdf_reader._extract_vector_pdf") as mock_vec,
            patch("modules.pdf_reader._extract_scanned_pdf") as mock_ocr,
            patch("modules.pdf_reader._extract_via_9router_vision") as mock_vision,
        ):
            mock_vec.return_value = [{"page": 1, "raw_texts": []}]
            mock_ocr.return_value = [{"page": 1, "ocr_result": []}]
            mock_vision.return_value = [
                {"page": 1, "items": [
                    {"nama_item": "Galian", "P": 10.0, "L": 5.0, "T": 2.0, "confidence": 0.9},
                ]},
            ]
            result = extract_dimensions_from_pdf("dummy.pdf", scale=2.0, llm_router=MagicMock())

        assert result["status"] == "ok"
        assert result["source"] == "9router_vision"
        assert len(result["items"]) == 1
        assert result["items"][0]["P"] == 20.0, f"Expected 20.0, got {result['items'][0]['P']}"
        assert result["items"][0]["L"] == 10.0
        assert result["items"][0]["T"] == 4.0

    def test_scale_none_unchanged(self):
        from modules.pdf_reader import extract_dimensions_from_pdf

        with (
            patch("modules.pdf_reader._extract_vector_pdf") as mock_vec,
            patch("modules.pdf_reader._extract_scanned_pdf") as mock_ocr,
            patch("modules.pdf_reader._extract_via_9router_vision") as mock_vision,
        ):
            mock_vec.return_value = [{"page": 1, "raw_texts": []}]
            mock_ocr.return_value = [{"page": 1, "ocr_result": []}]
            mock_vision.return_value = [
                {"page": 1, "items": [
                    {"nama_item": "Galian", "P": 10.0, "L": 5.0, "T": 2.0, "confidence": 0.9},
                ]},
            ]
            result = extract_dimensions_from_pdf("dummy.pdf", scale=None, llm_router=MagicMock())

        assert result["items"][0]["P"] == 10.0
        assert result["items"][0]["L"] == 5.0
        assert result["items"][0]["T"] == 2.0

    def test_scale_1_0_unchanged(self):
        from modules.pdf_reader import extract_dimensions_from_pdf

        with (
            patch("modules.pdf_reader._extract_vector_pdf") as mock_vec,
            patch("modules.pdf_reader._extract_scanned_pdf") as mock_ocr,
            patch("modules.pdf_reader._extract_via_9router_vision") as mock_vision,
        ):
            mock_vec.return_value = [{"page": 1, "raw_texts": []}]
            mock_ocr.return_value = [{"page": 1, "ocr_result": []}]
            mock_vision.return_value = [
                {"page": 1, "items": [
                    {"nama_item": "Galian", "P": 10.0, "L": 5.0, "T": 2.0, "confidence": 0.9},
                ]},
            ]
            result = extract_dimensions_from_pdf("dummy.pdf", scale=1.0, llm_router=MagicMock())

        assert result["items"][0]["P"] == 10.0

    def test_flagged_items_also_scaled(self):
        from modules.pdf_reader import extract_dimensions_from_pdf

        with (
            patch("modules.pdf_reader._extract_vector_pdf") as mock_vec,
            patch("modules.pdf_reader._extract_scanned_pdf") as mock_ocr,
            patch("modules.pdf_reader._extract_via_9router_vision") as mock_vision,
        ):
            mock_vec.return_value = [{"page": 1, "raw_texts": []}]
            mock_ocr.return_value = [{"page": 1, "ocr_result": []}]
            mock_vision.return_value = [
                {"page": 1, "items": [
                    {"nama_item": "Galian", "P": 10.0, "L": 5.0, "T": 2.0, "confidence": 0.5},
                ]},
            ]
            result = extract_dimensions_from_pdf("dummy.pdf", scale=3.0, llm_router=MagicMock())

        assert len(result["items_flagged"]) == 1
        assert result["items_flagged"][0]["P"] == 30.0


class TestChatFlaggedItems:
    def test_flag_low_confidence(self, sample_items):
        from modules.chat_handler import ChatHandler
        handler = ChatHandler(MagicMock())
        flagged = handler._flag_items(sample_items)
        names = [f["nama_item"] for f in flagged]
        assert "Besi Beton" in names

    def test_flag_missing_3d_dimensions(self):
        from modules.chat_handler import ChatHandler
        items = [
            {"nama_item": "Galian Tanah", "P": 12.0, "L": None, "T": None, "confidence": 0.9},
        ]
        handler = ChatHandler(MagicMock())
        flagged = handler._flag_items(items)
        assert len(flagged) == 1
        assert "Lebar" in flagged[0]["alasan"] or "Tinggi" in flagged[0]["alasan"]

    def test_flag_unrealistic_dimensions(self):
        from modules.chat_handler import ChatHandler
        items = [
            {"nama_item": "Galian Tanah", "P": 200.0, "L": 0.8, "T": 1.2, "confidence": 0.9},
        ]
        handler = ChatHandler(MagicMock())
        flagged = handler._flag_items(items)
        assert len(flagged) == 1
        assert "200" in flagged[0]["alasan"]

    def test_no_flag_for_clean_items(self):
        from modules.chat_handler import ChatHandler
        items = [
            {"nama_item": "Galian Tanah", "P": 12.0, "L": 0.8, "T": 1.2, "confidence": 0.92},
        ]
        handler = ChatHandler(MagicMock())
        flagged = handler._flag_items(items)
        assert len(flagged) == 0

    def test_history_included_in_prompt(self):
        from modules.chat_handler import ChatHandler
        router = MagicMock()
        router.call.return_value = "Tidak ada aksi"
        handler = ChatHandler(router)
        handler.conversation_history = [
            {"user": "Halo", "assistant": "Halo, ada yang bisa dibantu?"}
        ]
        result = handler.chat(
            user_message="Berapa volume galian?",
            boq_state=[],
            template_mapping={},
            file_names={"gambar": "test.pdf", "template": "test.xlsx"},
        )
        assert "response_text" in result
        assert "action" in result
        assert "flagged_items" in result

    def test_history_max_size(self):
        from modules.chat_handler import ChatHandler
        router = MagicMock()
        router.call.return_value = "Tidak ada aksi"
        handler = ChatHandler(router)
        for i in range(25):
            handler.conversation_history.append({"user": str(i), "assistant": str(i)})
        assert len(handler.conversation_history) == 25
        handler.chat("test", [], {}, {"gambar": "", "template": ""})
        assert len(handler.conversation_history) <= 21
