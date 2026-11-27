"""[개발 A] 자연어 요청 해석.

interpret()가 이 모듈의 입구입니다. AI(HaiGPT 등)를 먼저 쓰고, 꺼져 있거나 실패하면 규칙 기반으로 해석합니다.
"""
from __future__ import annotations

import logging

from ..common.catalog import Catalog
from ..common.config import Settings, get_settings
from ..common.models import ParseResult
from .llm import parse_with_llm
from .providers import LLMError, OpenAICompatibleProvider
from .rules import format_seats, parse_with_rules

__all__ = ["interpret", "get_provider", "LLMError", "OpenAICompatibleProvider", "format_seats"]
log = logging.getLogger(__name__)


def get_provider(settings: Settings | None = None) -> OpenAICompatibleProvider | None:
    settings = settings or get_settings()
    if not settings.llm_enabled:
        return None
    return OpenAICompatibleProvider(
        name=settings.llm_provider,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
        chat_path=settings.llm_chat_path,
        temperature=settings.llm_temperature,
    )


def interpret(text: str, catalog: Catalog, provider: OpenAICompatibleProvider | None = None) -> ParseResult:
    text = text.strip()
    rule_result = parse_with_rules(text, catalog)
    if provider is None:
        return rule_result

    try:
        result = parse_with_llm(text, catalog, provider)
    except LLMError as exc:
        rule_result.warnings.insert(0, f"AI 해석에 실패해서 규칙 기반 해석으로 대신했어요. ({exc})")
        return rule_result
    except Exception:  # 예상 못 한 응답이어도 서버 오류 대신 규칙 기반으로 계속
        log.exception("AI 응답 처리 중 예상 못 한 오류")
        rule_result.warnings.insert(0, "AI 응답을 처리하지 못해서 규칙 기반 해석으로 대신했어요.")
        return rule_result

    # 규칙 기반 결과와 교차 확인: 다르면 실행 전에 한 번 더 보도록 알림
    if rule_result.seats and set(rule_result.seats) != set(result.seats):
        result.warnings.append(
            f"규칙 기반으로 찾은 좌석({format_seats(rule_result.seats)})과 AI 결과가 달라요. 실행 전에 확인해 주세요."
        )
    if rule_result.profiles and set(rule_result.profiles) != set(result.profiles):
        def names(ids: list[str]) -> str:
            return ", ".join(catalog.profiles[pid].name for pid in ids if pid in catalog.profiles) or "없음"

        result.warnings.append(
            f"규칙 기반은 '{names(rule_result.profiles)}', AI는 '{names(result.profiles)}'를 골랐어요. "
            "실행 전에 확인해 주세요."
        )
    return result
