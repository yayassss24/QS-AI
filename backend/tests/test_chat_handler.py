"""Tests for chat_handler.py"""

import json
from unittest.mock import MagicMock

from modules.chat_handler import ChatHandler


class TestChatHandler:
    def test_initializes_with_router(self, mock_llm_router):
        handler = ChatHandler(mock_llm_router)
        assert handler.router == mock_llm_router
        assert handler.conversation_history == []

    def test_extract_action_returns_none_when_no_json(self):
        handler = ChatHandler(MagicMock())
        result = handler._extract_action("Halo, apa kabar?")
        assert result is None

    def test_extract_action_finds_json(self):
        handler = ChatHandler(MagicMock())
        text = 'Beberapa teks\n```json\n{"action": "update_cell", "item": "Test"}\n```\npenjelasan'
        result = handler._extract_action(text)
        assert result is not None
        assert result["action"] == "update_cell"
        assert result["item"] == "Test"

    def test_chat_returns_expected_keys(self, mock_llm_router):
        handler = ChatHandler(mock_llm_router)
        result = handler.chat(
            user_message="Berapa total volume?",
            boq_state=[],
            template_mapping={},
            file_names={"gambar": "test.pdf", "template": "test.xlsx"},
        )
        assert "response_text" in result
        assert "action" in result
        assert "flagged_items" in result

    def test_chat_adds_to_conversation_history(self, mock_llm_router):
        handler = ChatHandler(mock_llm_router)
        handler.chat("Halo", [], {}, {})
        assert len(handler.conversation_history) == 1
        assert handler.conversation_history[0]["user"] == "Halo"
