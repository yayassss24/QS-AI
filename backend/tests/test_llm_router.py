"""Tests for llm_router.py — 9router API."""

import os
from unittest.mock import patch, MagicMock

import pytest

from modules.llm_router import LLMRouter


class TestLLMRouterInit:
    def test_creates_without_byok(self):
        router = LLMRouter()
        assert router.byok_key is None

    def test_creates_with_byok(self):
        router = LLMRouter(byok_key="sk-test-key")
        assert router.byok_key == "sk-test-key"

    @patch("redis.from_url", side_effect=Exception("no redis"))
    def test_fallback_to_memory_when_no_redis(self, mock_from_url):
        router = LLMRouter()
        assert router.redis is None
        assert router._memory_usage == 0


class TestUsageTracking:
    def test_increment_memory(self):
        router = LLMRouter()
        router._increment_usage()
        assert router._memory_usage == 1

    def test_limit_not_reached(self):
        router = LLMRouter()
        router._memory_usage = 0
        assert router._check_limit() is True

    def test_limit_reached(self):
        router = LLMRouter()
        router._memory_usage = 2000
        assert router._check_limit() is False

    def test_limit_raises(self):
        router = LLMRouter()
        router._memory_usage = 2000
        with pytest.raises(RuntimeError, match="limit"):
            router.call("chat", "test")


class TestCall:
    def test_call_text_success(self):
        router = LLMRouter()
        with patch("modules.llm_router.LLMRouter._call_text") as mock_call:
            mock_call.return_value = "response text"
            result = router.call("chat", "hello")
            assert result == "response text"

    def test_call_vision_success(self):
        router = LLMRouter()
        with patch("modules.llm_router.LLMRouter._call_vision") as mock_call:
            mock_call.return_value = "vision response"
            result = router.call("extract_image", "analyze", image_b64="abc123")
            assert result == "vision response"

    def test_call_missing_api_key(self):
        router = LLMRouter()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="9ROUTER_API_KEY"):
                router.call("chat", "test")

    def test_call_with_byok_key(self):
        router = LLMRouter(byok_key="sk-byok-key")
        with (
            patch("modules.llm_router.LLMRouter._call_text") as mock_call,
            patch.dict(os.environ, {"9ROUTER_API_KEY": "sk-env-key"}, clear=True),
        ):
            mock_call.return_value = "ok"
            router.call("chat", "test")
            # BYOK key harus dipakai, bukan env key
            args, kwargs = mock_call.call_args
            assert args[0] == "sk-byok-key"


class TestOpenAIIntegration:
    def test_call_text_uses_openai_client(self):
        router = LLMRouter()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "1"

        with (
            patch("openai.OpenAI") as mock_openai,
            patch.dict(os.environ, {"9ROUTER_API_KEY": "sk-test"}, clear=True),
        ):
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            result = router._call_text("sk-test", "http://localhost:20128/v1", "groq/llama-3.3-70b-versatile", "test")
            assert result == "1"
            mock_openai.assert_called_once_with(
                base_url="http://localhost:20128/v1",
                api_key="sk-test",
            )

    def test_call_vision_uses_openai_client(self):
        router = LLMRouter()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "vision result"

        with (
            patch("openai.OpenAI") as mock_openai,
            patch.dict(os.environ, {"9ROUTER_API_KEY": "sk-test"}, clear=True),
        ):
            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            result = router._call_vision("sk-test", "http://localhost:20128/v1", "gemini/gemini-3.1-flash-lite-preview", "analyze", "imgdata")
            assert result == "vision result"
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "gemini/gemini-3.1-flash-lite-preview"
            assert "image_url" in str(call_kwargs["messages"][0]["content"][1])
