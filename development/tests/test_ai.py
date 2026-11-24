"""요청 해석(ai) 테스트: 규칙 기반 + AI 응답 검증·폴백."""
from __future__ import annotations

import json

import httpx
import pytest

from src.ai import OpenAICompatibleProvider, interpret
from src.ai.providers import LLMError, extract_json
from src.ai.rules import format_seats
from src.common.catalog import load_catalog


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.mark.parametrize(
    ("text", "seats", "profiles"),
    [
        ("1번부터 4번 PC에 Python 실습환경 설치해 줘", [1, 2, 3, 4], ["python-basic"]),
        ("2, 3번 PC에 데이터 분석 실습 환경 깔아 줘", [2, 3], ["python-data"]),
        ("전체 PC에 VS Code랑 Git 설치해 줘", [1, 2, 3, 4, 5], ["git", "vscode"]),
        ("3번 자리에 자바 21 실습 환경 부탁해", [3], ["java-basic"]),
        ("Python 3.12 설치해줘 1번", [1], ["python-basic"]),
        ("PC1~PC3에 C언어 실습환경", [1, 2, 3], ["c-basic"]),
        ("1번이랑 4번에 깃 깔아줘", [1, 4], ["git"]),
        ("1-2번 좌석에 pandas", [1, 2], ["python-data"]),
        ("파이썬 데이터 분석 환경 5번", [5], ["python-data"]),  # python-data가 python-basic을 포함
    ],
)
def test_rules(catalog, text, seats, profiles):
    result = interpret(text, catalog)
    assert result.parser == "rules"
    assert result.seats == seats
    assert result.profiles == profiles


def test_rules_warn_unknown_seat_and_tool(catalog):
    result = interpret("9번 PC에 파이썬이랑 node 설치", catalog)
    assert result.seats == []
    assert result.unsupported == ["Node.js"]
    assert any("9번" in w for w in result.warnings)
    assert any("좌석을 찾지 못했어요" in w for w in result.warnings)


def test_pc_word_does_not_trigger_c_profile(catalog):
    assert "c-basic" not in interpret("1번 PC 실습실 언어 수업용 파이썬", catalog).profiles


def test_format_seats():
    assert format_seats([1, 2, 3, 4, 6]) == "1~4, 6번"
    assert format_seats([2, 3]) == "2, 3번"
    assert format_seats([]) == "없음"


def make_provider(handler) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider("haigpt", "https://llm.example/v1", "test-model", api_key="k",
                                    transport=httpx.MockTransport(handler))


def chat_response(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]})


def test_ai_result_is_validated_against_catalog(catalog):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        assert request.headers["Authorization"] == "Bearer k"
        assert body["response_format"]["type"] == "json_schema"
        return chat_response({"seats": [1, 2, 9], "profiles": ["python-basic", "nodejs"],
                              "unsupported": [], "reason": "1·2번에 Python"})

    result = interpret("1번이랑 2번에 파이썬", catalog, make_provider(handler))
    assert result.parser == "ai" and result.provider == "haigpt"
    assert result.seats == [1, 2]
    assert result.profiles == ["python-basic"]
    assert "nodejs" in result.unsupported
    assert any("9번" in w for w in result.warnings)
    system_prompt = calls[0]["messages"][0]["content"]
    assert "python-basic" in system_prompt and "[등록된 좌석] 1, 2, 3, 4, 5" in system_prompt


def test_ai_falls_back_to_json_mode_when_schema_rejected(catalog):
    formats = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        formats.append((body.get("response_format") or {}).get("type"))
        if formats[-1] == "json_schema":
            return httpx.Response(400, json={"error": "response_format not supported"})
        return httpx.Response(200, json={"choices": [{"message": {"content":
            '```json\n{"seats": [3], "profiles": ["git"], "unsupported": [], "reason": "3번에 Git"}\n```'}}]})

    result = interpret("3번에 깃", catalog, make_provider(handler))
    assert formats == ["json_schema", "json_object"]
    assert result.parser == "ai" and result.seats == [3] and result.profiles == ["git"]


def test_ai_failure_uses_rules(catalog):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    result = interpret("1번부터 4번 PC에 Python 실습환경 설치해 줘", catalog, make_provider(handler))
    assert result.parser == "rules"
    assert result.seats == [1, 2, 3, 4]
    assert "AI 해석에 실패" in result.warnings[0]


def test_ai_auth_error_message_has_no_key(catalog):
    provider = make_provider(lambda request: httpx.Response(401, json={"error": "bad key"}))
    with pytest.raises(LLMError) as info:
        provider.complete_json("s", "u", {})
    assert "인증 실패" in str(info.value) and "k" not in str(info.value).replace("키", "")


def test_ai_disagreement_with_rules_is_flagged(catalog):
    handler = lambda request: chat_response({"seats": [1, 2, 3], "profiles": ["python-basic"],
                                             "unsupported": [], "reason": "x"})
    result = interpret("1번부터 4번 PC에 Python 실습환경 설치해 줘", catalog, make_provider(handler))
    assert any("규칙 기반으로 찾은 좌석" in w for w in result.warnings)


def test_extract_json_errors():
    with pytest.raises(LLMError):
        extract_json("설명만 있고 JSON 없음")
    assert extract_json('앞 설명 {"a": 1} 뒤 설명') == {"a": 1}


def test_javascript_is_not_java(catalog):
    result = interpret("3번 PC에 자바스크립트 실습 환경 깔아 줘", catalog)
    assert result.seats == [3]
    assert result.profiles == []
    assert result.unsupported == ["JavaScript"]
    assert interpret("1번에 자바 깔아 줘", catalog).profiles == ["java-basic"]


def test_haigpt_style_call_path_billing_and_no_temperature(catalog):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "model": "gemini-3.5-flash-lite",
            "choices": [{"message": {"content": json.dumps({"seats": [1, 2], "profiles": ["python-data"],
                                                             "unsupported": [], "reason": "시각화 수업"})}}],
            "billing": {"cost_usd": 0.0001, "cost_krw": 0.14, "deducted_credit": 0.14},
        })

    provider = OpenAICompatibleProvider("haigpt", "https://factchat-cloud.mindlogic.ai/v1/gateway",
                                        "gemini-3.5-flash-lite", api_key="k", chat_path="/chat/completions/",
                                        transport=httpx.MockTransport(handler))
    result = interpret("다음 주 파이썬 데이터 시각화 수업을 1번이랑 2번 자리에서 해", catalog, provider)
    assert seen["url"] == "https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions/"
    assert "temperature" not in seen["body"]  # temperature를 거부하는 모델이 있어 기본은 보내지 않음
    schema = seen["body"]["response_format"]["json_schema"]
    assert schema["strict"] is True and schema["schema"]["additionalProperties"] is False
    assert result.parser == "ai" and result.profiles == ["python-data"]
    assert provider.last_call["billing"]["deducted_credit"] == 0.14


def test_422_also_falls_back_and_errors_are_readable(catalog):
    formats = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        formats.append((body.get("response_format") or {}).get("type"))
        if body.get("response_format"):
            return httpx.Response(422, json={"error": {"message": "response_format is not supported for this model"}})
        return chat_response({"seats": [2], "profiles": ["git"], "unsupported": [], "reason": "x"})

    result = interpret("2번에 깃", catalog, make_provider(handler))
    assert formats == ["json_schema", "json_object", None] and result.parser == "ai"

    def bad_model(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"message": "model 'nope' not found", "type": "invalid_request_error"}})

    with pytest.raises(LLMError) as info:
        make_provider(bad_model).complete_json("s", "u", {})
    assert "404" in str(info.value) and "not found" in str(info.value)


def test_redirect_points_to_chat_path(catalog):
    provider = make_provider(lambda request: httpx.Response(301, headers={"Location": "/x/"}))
    with pytest.raises(LLMError) as info:
        provider.complete_json("s", "u", {})
    assert "LLM_CHAT_PATH" in str(info.value)


def test_list_models_shapes():
    from src.ai.providers import parse_model_list

    assert parse_model_list({"object": "list", "data": [{"id": "b"}, {"id": "a"}]}) == ["a", "b"]
    assert parse_model_list([{"id": "gpt-6-luna"}, {"x": 1}]) == ["gpt-6-luna"]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/gateway/models/" and request.url.params["type"] == "llm"
        return httpx.Response(200, json={"data": [{"id": "gemini-3.5-flash-lite"}]})

    provider = OpenAICompatibleProvider("haigpt", "https://factchat-cloud.mindlogic.ai/v1/gateway", "m",
                                        chat_path="/chat/completions/", transport=httpx.MockTransport(handler))
    assert provider.list_models() == ["gemini-3.5-flash-lite"]


def test_check_tool_without_ai_explains_setup(capsys):
    from src.ai.check import main

    assert main([]) == 1
    assert "LLM_PROVIDER=haigpt" in capsys.readouterr().out


def test_haigpt_preset(monkeypatch):
    from src.common.config import reload_settings

    monkeypatch.setenv("LLM_PROVIDER", "haigpt")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    settings = reload_settings()
    assert settings.llm_enabled
    assert settings.llm_base_url == "https://factchat-cloud.mindlogic.ai/v1/gateway"
    assert settings.llm_chat_path == "/chat/completions/" and settings.llm_temperature is None
