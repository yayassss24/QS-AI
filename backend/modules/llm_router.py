"""
modules/llm_router.py

Router ke API 9router — unified LLM gateway yang menggantikan Gemini,
Groq, dan OpenRouter. Mendukung BYOK (user bring their own key).

Task routing:
- extract_image  → 9router (vision model)
- chat           → 9router (fast model)
- format_detect  → 9router (fast model)
"""

import os
from datetime import datetime


class LLMRouter:
    """
    Router ke API 9router.

    BYOK: jika user punya API key sendiri, selalu pakai key mereka.
    Redis opsional — jika tidak tersedia, fallback ke in-memory counters.
    """

    DAILY_LIMIT: int = 2000

    def __init__(self, byok_key: str = None):
        self.byok_key = byok_key
        self._memory_usage = 0
        self.redis = None
        try:
            import redis as redis_lib
            self.redis = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        except Exception:
            pass

    def _get_usage(self) -> int:
        if self.redis is None:
            return self._memory_usage
        try:
            key = f"llm_usage:9router:{datetime.now().strftime('%Y-%m-%d')}"
            val = self.redis.get(key)
            return int(val) if val else 0
        except Exception:
            return self._memory_usage

    def _increment_usage(self):
        if self.redis is None:
            self._memory_usage += 1
            return
        try:
            key = f"llm_usage:9router:{datetime.now().strftime('%Y-%m-%d')}"
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expireat(key, datetime.now().replace(hour=23, minute=59, second=59))
            pipe.execute()
        except Exception:
            self._memory_usage += 1

    def _check_limit(self) -> bool:
        return self._get_usage() < self.DAILY_LIMIT

    def call(self, task_type: str, prompt: str, image_b64: str = None) -> str:
        """
        Panggil 9router API.

        Args:
            task_type: "extract_image" | "chat" | "format_detect"
            prompt: Teks prompt
            image_b64: Base64 gambar (untuk extract_image)

        Returns:
            Response text dari LLM
        """
        if not self._check_limit():
            raise RuntimeError("Daily limit 9router sudah tercapai")

        api_key = self.byok_key if self.byok_key else os.getenv("9ROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("9ROUTER_API_KEY tidak ditemukan. Set di .env atau gunakan BYOK.")

        base_url = os.getenv("9ROUTER_BASE_URL", "http://localhost:20128/v1").rstrip("/")

        if task_type == "extract_image":
            model = os.getenv("9ROUTER_VISION_MODEL", "gemini/gemini-3.1-flash-lite-preview")
            result = self._call_vision(api_key, base_url, model, prompt, image_b64)
        else:
            model = os.getenv("9ROUTER_MODEL", "groq/llama-3.3-70b-versatile")
            result = self._call_text(api_key, base_url, model, prompt)

        self._increment_usage()
        return result

    def _call_text(self, api_key: str, base_url: str, model: str, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
        )
        return response.choices[0].message.content

    def _call_vision(self, api_key: str, base_url: str, model: str, prompt: str, image_b64: str) -> str:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            max_tokens=4000,
        )
        return response.choices[0].message.content
