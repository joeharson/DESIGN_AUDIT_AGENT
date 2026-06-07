"""Groq vision LLM wrapper for the Design Audit Agent."""

from __future__ import annotations

import os


class LLMClient:
    def __init__(self) -> None:
        self.provider = "groq"
        self.model = os.getenv("LLM_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        self.max_tokens = self._parse_int_env("LLM_MAX_TOKENS", default=4096, minimum=512, maximum=8192)
        self.timeout_seconds = self._parse_int_env("LLM_TIMEOUT_SECONDS", default=60, minimum=5, maximum=180)
        self._client = None
        self._init_groq()

    @staticmethod
    def _parse_int_env(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.getenv(name, str(default)))
        except ValueError:
            return default
        return min(max(value, minimum), maximum)

    def _init_groq(self) -> None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError("Set GROQ_API_KEY in .env before starting the server.")
        from groq import Groq

        self._client = Groq(api_key=api_key, timeout=self.timeout_seconds)

    def analyze_image(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: str,
        image_format: str,
    ) -> str:
        return self._call_groq(system_prompt, user_prompt, image_base64, image_format)

    def _call_groq(self, system_prompt: str, user_prompt: str, image_base64: str, image_format: str) -> str:
        mime_type = f"image/{'jpeg' if image_format == 'JPEG' else image_format.lower()}"
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                            },
                        ],
                    },
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Groq returned an empty response.")
            return content
        except Exception as exc:
            raise RuntimeError(f"Groq request failed: {exc}") from exc
