"""AI 공급자 호출 (OpenAI 호환 /chat/completions 형식).

HaiGPT·Groq·Ollama 모두 이 방식으로 부릅니다. HaiGPT API 형식이 다르면
OpenAICompatibleProvider를 상속해 complete_json만 바꾸면 됩니다.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx


class LLMError(Exception):
    """AI 호출이 실패했을 때. 메시지는 화면에 그대로 보여 줍니다(키 같은 비밀은 넣지 않음)."""


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.name = name
        self.model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """JSON 객체 하나를 받아 dict로 돌려줍니다.

        스키마 강제 → JSON 모드 → 형식 지정 없음 순서로, 공급자가 지원하는 방식을 찾아 내려갑니다.
        """
        formats: list[dict[str, Any] | None] = [
            {"type": "json_schema", "json_schema": {"name": "install_request", "strict": True, "schema": schema}},
            {"type": "json_object"},
            None,
        ]
        last_problem = ""
        for response_format in formats:
            payload: dict[str, Any] = {
                "model": self.model,
                "temperature": 0,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            if response_format is not None:
                payload["response_format"] = response_format
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.TimeoutException as exc:
                raise LLMError(f"{self.name} 응답 시간 초과") from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"{self.name} 연결 실패 ({exc.__class__.__name__})") from exc

            if response.status_code == 400 and response_format is not None:
                last_problem = f"{self.name}가 응답 형식 지정을 거부함"
                continue  # 이 형식을 지원하지 않음 → 다음 방식
            if response.status_code in (401, 403):
                raise LLMError(f"{self.name} 인증 실패 (API 키 확인)")
            if response.status_code == 429:
                raise LLMError(f"{self.name} 사용 한도 초과 (429)")
            if response.status_code >= 400:
                raise LLMError(f"{self.name} 오류 응답 ({response.status_code})")
            try:
                content = response.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LLMError(f"{self.name} 응답 형식을 읽을 수 없음") from exc
            return extract_json(content or "")
        raise LLMError(last_problem or f"{self.name} 호출 실패")


def extract_json(text: str) -> dict[str, Any]:
    """코드 블록(```json)이나 앞뒤 설명이 섞여 와도 JSON 객체만 꺼냅니다."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("AI 응답에 JSON이 없음")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError("AI 응답 JSON을 읽을 수 없음") from exc
    if not isinstance(data, dict):
        raise LLMError("AI 응답이 JSON 객체가 아님")
    return data
