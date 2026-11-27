"""AI 공급자 호출 (OpenAI 호환 /chat/completions 형식).

HAI-GPT API Gateway·Groq·Ollama 모두 이 방식으로 부릅니다.
형식이 다른 공급자가 생기면 OpenAICompatibleProvider를 상속해 complete_json만 바꾸면 됩니다.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx


class LLMError(Exception):
    """AI 호출이 실패했을 때. 메시지는 화면에 그대로 보여 줍니다(키 같은 비밀은 넣지 않음)."""


def error_text(response: httpx.Response) -> str:
    """오류 응답에서 사람이 읽을 메시지만 짧게 꺼냅니다."""
    try:
        data = response.json()
    except ValueError:
        return " ".join(response.text.split())[:200]
    message: Any = data
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message") or error.get("code") or error
        else:
            message = error or data.get("detail") or data.get("message") or data
    return " ".join(str(message).split())[:200]


class OpenAICompatibleProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
        chat_path: str = "/chat/completions",
        temperature: float | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.chat_path = "/" + chat_path.lstrip("/")
        self.temperature = temperature
        self.last_call: dict[str, Any] = {}  # 마지막 호출의 모델·걸린 시간·크레딧 (점검 도구용)
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._timeout = timeout
        self._transport = transport

    def _new_client(self) -> httpx.Client:
        """호출마다 열고 닫아서 연결이 쌓이지 않게 함 (요청마다 provider를 새로 만들기 때문)."""
        return httpx.Client(base_url=self._base_url, headers=self._headers,
                            timeout=self._timeout, transport=self._transport)

    def _check_status(self, response: httpx.Response) -> None:
        status = response.status_code
        if 300 <= status < 400:
            raise LLMError(f"{self.name} 주소가 다른 곳으로 넘어가요 ({status}). "
                           "LLM_BASE_URL과 LLM_CHAT_PATH(끝의 / 포함)를 확인하세요.")
        if status in (401, 403):
            raise LLMError(f"{self.name} 인증 실패 (API 키 확인)")
        if status == 402:
            raise LLMError(f"{self.name} 크레딧 부족 ({error_text(response)})")
        if status == 429:
            raise LLMError(f"{self.name} 사용 한도 초과 (429)")
        if status >= 400:
            raise LLMError(f"{self.name} 오류 응답 ({status}: {error_text(response)})")

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """JSON 객체 하나를 받아 dict로 돌려줍니다.

        스키마 강제 → JSON 모드 → 형식 지정 없음 순서로, 공급자가 받아 주는 방식을 찾아 내려갑니다.
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
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            }
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            if response_format is not None:
                payload["response_format"] = response_format
            started = time.perf_counter()
            try:
                with self._new_client() as client:
                    response = client.post(self.chat_path, json=payload)
            except httpx.TimeoutException as exc:
                raise LLMError(f"{self.name} 응답 시간 초과") from exc
            except httpx.HTTPError as exc:
                raise LLMError(f"{self.name} 연결 실패 ({exc.__class__.__name__})") from exc

            if response.status_code in (400, 422) and response_format is not None:
                # 이 응답 형식을 못 받는 모델 → 다음 방식으로 다시 시도
                last_problem = f"{self.name}가 요청을 거부함 ({response.status_code}: {error_text(response)})"
                continue
            self._check_status(response)
            try:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise LLMError(f"{self.name} 응답 형식을 읽을 수 없음") from exc
            self.last_call = {
                "model": data.get("model") or self.model,
                "seconds": round(time.perf_counter() - started, 2),
                "format": response_format["type"] if response_format else "없음",
                "billing": data.get("billing"),
            }
            return extract_json(content or "")
        raise LLMError(last_problem or f"{self.name} 호출 실패")

    def list_models(self, kind: str = "llm") -> list[str]:
        """쓸 수 있는 모델 ID 목록 (키·주소가 맞는지 확인하는 데도 씁니다)."""
        path = "/models/" if self.chat_path.endswith("/") else "/models"
        try:
            with self._new_client() as client:
                response = client.get(path, params={"type": kind})
        except httpx.HTTPError as exc:
            raise LLMError(f"{self.name} 연결 실패 ({exc.__class__.__name__})") from exc
        self._check_status(response)
        return parse_model_list(response.json())


def parse_model_list(data: Any) -> list[str]:
    """{"data": [...]} 형태와 [...] 형태를 모두 받습니다."""
    items = data.get("data", []) if isinstance(data, dict) else data
    return sorted(str(m["id"]) for m in items or [] if isinstance(m, dict) and m.get("id"))


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
