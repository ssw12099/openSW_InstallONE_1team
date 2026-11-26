"""AI 연결 점검 도구 (서버를 켜지 않고 터미널에서 확인).

development 폴더에서:
  python -m src.ai.check            예시 문장으로 AI 해석 확인
  python -m src.ai.check --models   쓸 수 있는 채팅 모델 목록 (키·주소 확인용)
  python -m src.ai.check "문장"      직접 쓴 문장으로 확인
"""
from __future__ import annotations

import argparse
import sys
import time

from ..common.catalog import CatalogError, load_catalog
from ..common.config import get_settings
from . import get_provider, interpret
from .providers import LLMError
from .rules import format_seats

# 마지막 두 문장은 규칙 기반으로는 제대로 못 푸는 문장 (AI를 쓰는 이유)
EXAMPLES = [
    "1번부터 4번 PC에 Python 실습환경 설치해 줘",
    "다음 주 파이썬 데이터 시각화 수업을 1번이랑 2번 자리에서 해",
    "4번 자리에 전공 기초 C 수업 준비해 줘",
    "3번 PC에 자바스크립트 실습 환경 깔아 줘",
]


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 콘솔에서도 한글이 깨지지 않게
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="InstallONE AI 연결 점검")
    parser.add_argument("text", nargs="*", help="해석해 볼 문장 (없으면 예시 문장)")
    parser.add_argument("--models", action="store_true", help="쓸 수 있는 채팅 모델 목록 보기")
    args = parser.parse_args(argv)

    settings = get_settings()
    provider = get_provider(settings)
    if provider is None:
        print("AI가 꺼져 있어요. development/.env에 LLM_PROVIDER=haigpt 와 LLM_API_KEY를 넣어 주세요.")
        return 1
    print(f"공급자: {settings.llm_provider}  모델: {settings.llm_model}")
    print(f"주소: {settings.llm_base_url}{settings.llm_chat_path}")

    if args.models:
        try:
            models = provider.list_models()
        except LLMError as exc:
            print(f"모델 목록을 받지 못했어요: {exc}")
            return 1
        print(f"\n채팅 모델 {len(models)}개 (키와 주소는 정상):")
        for model in models:
            print(f"  {'*' if model == settings.llm_model else '-'} {model}")
        return 0

    try:
        catalog = load_catalog()
    except CatalogError as exc:
        print(f"설정 파일을 확인해 주세요. {exc}")
        return 1
    sentences = [" ".join(args.text)] if args.text else EXAMPLES
    fallbacks = 0
    for text in sentences:
        provider.last_call = {}
        started = time.perf_counter()
        result = interpret(text, catalog, provider)
        took = time.perf_counter() - started
        print(f"\n요청: {text}")
        print(f"  해석: {'AI' if result.parser == 'ai' else '규칙 기반 (AI 실패)'}, {took:.1f}초")
        line = f"  좌석: {format_seats(result.seats)}  프로필: {', '.join(result.profiles) or '없음'}"
        if result.unsupported:
            line += f"  지원 안 함: {', '.join(result.unsupported)}"
        print(line)
        if result.reason:
            print(f"  근거: {result.reason}")
        for warning in result.warnings:
            print(f"  ! {warning}")
        billing = provider.last_call.get("billing")
        if result.parser == "ai" and isinstance(billing, dict):
            print(f"  크레딧: {billing.get('deducted_credit')} 차감")
        if result.parser != "ai":
            fallbacks += 1
    return 1 if fallbacks else 0


if __name__ == "__main__":
    sys.exit(main())
