from __future__ import annotations

import json
import time
from typing import Any

from openai import OpenAI

from app.config import settings
from app.llm.demo import DemoLLM

class LLMClient:
    def __init__(self) -> None:
        self.demo = DemoLLM()

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_seconds,
            default_headers={"x-goog-api-client": "auditpilot-jnmv/1.0"},
        )

    def text(self, system: str, user: str, *, json_mode: bool = False) -> str:
        if settings.llm_mode != "real":
            return ""
        kwargs: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                result = self._client().chat.completions.create(**kwargs)
                return (result.choices[0].message.content or "").strip()
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(1.0)
        raise RuntimeError(f"LLM request failed after retry: {last_exc}") from last_exc

    def json(self, system: str, user: str) -> dict[str, Any]:
        raw = self.text(system, user, json_mode=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned invalid JSON: {raw}") from exc

llm_client = LLMClient()
