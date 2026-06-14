"""
modules/llm_router.py

Router otomatis ke 3 provider LLM (Gemini, Groq, OpenRouter) berdasarkan
jenis task dan rate limit. Mendukung BYOK dan failover chain.

Priority routing:
- extract_image  → Gemini Flash (Vision) → OpenRouter Vision fallback
- chat           → Groq (cepat) → Gemini → OpenRouter
- format_detect  → Groq → Gemini → OpenRouter
"""

import os
from datetime import datetime


class LLMRouter:
    """
    Router otomatis ke 3 provider LLM berdasarkan jenis task dan rate limit.

    BYOK: jika user punya API key sendiri, selalu pakai Gemini dengan key mereka.
    Redis opsional — jika tidak tersedia, fallback ke in-memory counters.
    """

    DAILY_LIMITS: dict[str, int] = {
        "gemini": 1400,
        "groq": 900,
        "openrouter": 950,
    }

    def __init__(self, byok_key: str = None):
        self.byok_key = byok_key
        self._memory_usage: dict[str, int] = {"gemini": 0, "groq": 0, "openrouter": 0}
        self.redis = None
        try:
            import redis as redis_lib
            self.redis = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        except Exception:
            pass

    def _get_usage(self, provider: str) -> int:
        if self.redis is None:
            return self._memory_usage.get(provider, 0)
        try:
            key = f"llm_usage:{provider}:{datetime.now().strftime('%Y-%m-%d')}"
            val = self.redis.get(key)
            return int(val) if val else 0
        except Exception:
            return self._memory_usage.get(provider, 0)

    def _increment_usage(self, provider: str):
        if self.redis is None:
            self._memory_usage[provider] = self._memory_usage.get(provider, 0) + 1
            return
        try:
            key = f"llm_usage:{provider}:{datetime.now().strftime('%Y-%m-%d')}"
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expireat(key, datetime.now().replace(hour=23, minute=59, second=59))
            pipe.execute()
        except Exception:
            self._memory_usage[provider] = self._memory_usage.get(provider, 0) + 1

    def _select_provider(self, task_type: str) -> str:
        if self.byok_key:
            return "gemini_byok"

        usage = {p: self._get_usage(p) for p in ["gemini", "groq", "openrouter"]}

        if task_type == "extract_image":
            if usage["gemini"] < self.DAILY_LIMITS["gemini"]:
                return "gemini"
            elif usage["openrouter"] < self.DAILY_LIMITS["openrouter"]:
                return "openrouter_vision"
            else:
                raise RuntimeError("Semua provider Vision sudah mencapai limit hari ini")

        elif task_type in ("chat", "format_detect"):
            if usage["groq"] < self.DAILY_LIMITS["groq"]:
                return "groq"
            elif usage["gemini"] < self.DAILY_LIMITS["gemini"]:
                return "gemini"
            elif usage["openrouter"] < self.DAILY_LIMITS["openrouter"]:
                return "openrouter"
            else:
                raise RuntimeError("Semua provider sudah mencapai limit hari ini")

        return "openrouter"

    def call(self, task_type: str, prompt: str, image_b64: str = None) -> str:
        """
        Panggil LLM dengan routing otomatis.

        Args:
            task_type: "extract_image" | "chat" | "format_detect"
            prompt: Teks prompt
            image_b64: Base64 gambar (wajib untuk extract_image)

        Returns:
            Response text dari LLM
        """
        provider = self._select_provider(task_type)

        try:
            if provider in ("gemini", "gemini_byok"):
                result = self._call_gemini(prompt, image_b64, byok=(provider == "gemini_byok"))
            elif provider == "groq":
                result = self._call_groq(prompt)
            elif provider == "openrouter_vision":
                result = self._call_openrouter(prompt, image_b64, vision=True)
            else:
                result = self._call_openrouter(prompt)

            self._increment_usage(provider.split("_")[0])
            return result

        except Exception as e:
            return self._failover(task_type, prompt, image_b64, failed_provider=provider, error=str(e))

    def _call_gemini(self, prompt: str, image_b64: str = None, byok: bool = False) -> str:
        import google.generativeai as genai
        api_key = self.byok_key if byok else os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        content = [prompt]
        if image_b64:
            content.append({
                "mime_type": "image/png",
                "data": image_b64,
            })
        response = model.generate_content(content)
        return response.text

    def _call_groq(self, prompt: str) -> str:
        from groq import Groq
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        return response.choices[0].message.content

    def _call_openrouter(self, prompt: str, image_b64: str = None, vision: bool = False) -> str:
        import openai
        client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        model = "meta-llama/llama-3.2-11b-vision-instruct:free" if vision else "meta-llama/llama-3.1-8b-instruct:free"

        messages = [{"role": "user", "content": prompt}]
        if image_b64 and vision:
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }]

        response = client.chat.completions.create(model=model, messages=messages)
        return response.choices[0].message.content

    def _failover(self, task_type: str, prompt: str, image_b64: str, failed_provider: str, error: str) -> str:
        print(f"[LLMRouter] Failover dari {failed_provider}: {error}")
        fallback_order = ["groq", "gemini", "openrouter"]
        for provider in fallback_order:
            if provider in failed_provider:
                continue
            try:
                if provider == "groq":
                    return self._call_groq(prompt)
                elif provider == "gemini":
                    return self._call_gemini(prompt, image_b64)
                else:
                    return self._call_openrouter(prompt, image_b64)
            except Exception:
                continue
        raise RuntimeError("Semua provider LLM gagal. Cek koneksi internet dan API key.")
