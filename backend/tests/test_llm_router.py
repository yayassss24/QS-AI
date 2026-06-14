"""Tests for llm_router.py"""

import os
from unittest.mock import patch, MagicMock

import pytest

from modules.llm_router import LLMRouter


class TestLLMRouterInit:
    def test_creates_without_byok(self):
        router = LLMRouter()
        assert router.byok_key is None

    def test_creates_with_byok(self):
        router = LLMRouter(byok_key="test-key")
        assert router.byok_key == "test-key"

    @patch("redis.from_url", side_effect=Exception("no redis"))
    def test_fallback_to_memory_when_no_redis(self, mock_from_url):
        router = LLMRouter()
        assert router.redis is None
        assert router._memory_usage is not None


class TestProviderSelection:
    def test_byok_always_uses_gemini(self):
        router = LLMRouter(byok_key="my-key")
        provider = router._select_provider("extract_image")
        assert provider == "gemini_byok"

    def test_extract_image_prefers_gemini(self):
        router = LLMRouter()
        router._memory_usage = {"gemini": 0, "groq": 0, "openrouter": 0}
        provider = router._select_provider("extract_image")
        assert provider == "gemini"

    def test_chat_prefers_groq(self):
        router = LLMRouter()
        provider = router._select_provider("chat")
        assert provider == "groq"

    def test_format_detect_prefers_groq(self):
        router = LLMRouter()
        provider = router._select_provider("format_detect")
        assert provider == "groq"


class TestUsageTracking:
    def test_increment_memory(self):
        router = LLMRouter()
        router._increment_usage("gemini")
        assert router._memory_usage["gemini"] == 1

    def test_limit_check(self):
        router = LLMRouter()
        router._memory_usage = {"gemini": 1400, "groq": 0, "openrouter": 0}
        provider = router._select_provider("extract_image")
        assert provider == "openrouter_vision"

    def test_all_providers_exhausted_raises(self):
        router = LLMRouter()
        router._memory_usage = {
            "gemini": 1400, "groq": 900, "openrouter": 950,
        }
        with pytest.raises(RuntimeError, match="limit"):
            router._select_provider("extract_image")


class TestFailover:
    def test_failover_chain_falls_back(self):
        router = LLMRouter()
        router._memory_usage = {"gemini": 0, "groq": 0, "openrouter": 0}

        with patch.object(router, '_call_gemini') as mock_g:
            mock_g.side_effect = Exception("gemini fail")
            with patch.object(router, '_call_groq') as mock_gr:
                mock_gr.return_value = "groq response"
                result = router.call("chat", "test prompt")
                assert result == "groq response"
                mock_gr.assert_called_once_with("test prompt")
