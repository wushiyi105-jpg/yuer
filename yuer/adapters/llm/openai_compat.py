"""OpenAI 兼容客户端：给家长看的说明。"""

from __future__ import annotations

import time
from typing import Any

import httpx


class LLMError(RuntimeError):
    pass


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        timeout: float = 30.0,
        retries: int = 2,
        max_tokens: int = 500,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.retries = retries
        self.max_tokens = max_tokens

    def write(self, system: str, facts: str) -> str:
        system = system or self.system_prompt
        last: str | None = None
        for attempt in range(self.retries):
            payload: dict[str, Any] = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": facts},
                ],
                "temperature": 0.3,
                "max_tokens": self.max_tokens,
            }
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                last = str(exc)
                time.sleep(0.3 * (2 ** attempt))
                continue
            choice = (data.get("choices") or [{}])[0]
            content = str((choice.get("message") or {}).get("content") or "").strip()
            if content:
                return content
            last = "模型返回空 content"
            time.sleep(0.3 * (2 ** attempt))
        raise LLMError(last or "模型调用失败")


def build_llm(base_url: str, api_key: str, model: str, system_prompt: str) -> OpenAICompatLLM:
    return OpenAICompatLLM(base_url, api_key, model, system_prompt)
