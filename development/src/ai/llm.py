"""AI(LLM)로 요청 해석.

AI는 설치 명령을 만들지 않고, 등록된 좌석 번호와 프로필 id 중에서만 고릅니다.
돌아온 값은 서버에서 다시 검사해서 목록 밖의 값은 버립니다.
"""
from __future__ import annotations

from typing import Any

from ..common.catalog import Catalog
from ..common.models import ParseResult
from .providers import LLMError, OpenAICompatibleProvider
from .rules import drop_included

SYSTEM_TEMPLATE = """너는 대학 실습실 PC 관리 도우미다. 조교의 요청 문장에서 설치 대상 좌석 번호와 설치 프로필을 골라 JSON으로만 답한다.

규칙:
1. profiles에는 아래 [프로필 목록]의 id만 쓴다. 설치 명령이나 새 id를 만들지 않는다.
2. 목록에 없는 도구를 요청하면 그 도구 이름을 unsupported에 적는다.
3. seats에는 [등록된 좌석] 번호만 쓴다. "전체", "모든 PC"는 등록된 좌석 전부다. "1번부터 4번", "1~4번" 같은 범위는 양 끝을 포함한다.
4. 버전 숫자(예: Python 3.12, 자바 21)는 좌석 번호가 아니다.
5. 어떤 프로필이 다른 프로필을 포함하면(포함:) 포함하는 쪽 하나만 고른다.
6. 문장에 좌석이나 도구가 없으면 빈 목록으로 두고 지어내지 않는다.
7. reason에는 그렇게 고른 이유를 한국어 한 문장으로 쓴다.

[등록된 좌석] {seats}

[프로필 목록]
{profiles}

출력 형식(JSON 객체 하나): {{"seats": [정수], "profiles": ["id"], "unsupported": ["도구 이름"], "reason": "한 문장"}}"""


def build_system_prompt(catalog: Catalog) -> str:
    lines = []
    for p in catalog.profiles.values():
        items = [c.name for c in p.choco] + p.pip
        line = f"- {p.id}: {p.name} — {p.description} (설치: {', '.join(items)})"
        if p.includes:
            line += f" / 포함: {', '.join(p.includes)}"
        lines.append(line)
    seats = ", ".join(str(n) for n in catalog.seats)
    return SYSTEM_TEMPLATE.format(seats=seats, profiles="\n".join(lines))


def build_schema(catalog: Catalog) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "seats": {"type": "array", "items": {"type": "integer"}},
            "profiles": {"type": "array", "items": {"type": "string", "enum": list(catalog.profiles)}},
            "unsupported": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        "required": ["seats", "profiles", "unsupported", "reason"],
        "additionalProperties": False,
    }


def to_parse_result(raw: dict[str, Any], catalog: Catalog, provider_name: str) -> ParseResult:
    """AI가 준 값을 검사해서 목록 밖의 좌석·프로필은 버리고 경고를 남깁니다."""
    warnings: list[str] = []
    seats: list[int] = []
    for value in raw.get("seats") or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            warnings.append(f"AI가 준 좌석 값 '{value}'를 읽을 수 없어 뺐어요.")
            continue
        if number not in catalog.seats:
            warnings.append(f"등록되지 않은 좌석 {number}번은 뺐어요.")
        elif number not in seats:
            seats.append(number)

    unsupported = [str(u) for u in raw.get("unsupported") or [] if str(u).strip()]
    picked: list[str] = []
    for pid in raw.get("profiles") or []:
        if pid in catalog.profiles:
            picked.append(pid)
        else:
            unsupported.append(str(pid))
    profiles = drop_included(picked, catalog)

    if not seats:
        warnings.append("대상 좌석을 찾지 못했어요. 아래에서 직접 골라 주세요.")
    if not profiles:
        warnings.append("설치할 프로필을 찾지 못했어요. 아래에서 직접 골라 주세요.")
    unsupported = list(dict.fromkeys(unsupported))
    if unsupported:
        warnings.append(f"아직 설치 프로필이 없는 도구: {', '.join(unsupported)}")

    return ParseResult(
        seats=sorted(seats),
        profiles=profiles,
        unsupported=unsupported,
        reason=str(raw.get("reason") or "").strip()[:300],
        parser="ai",
        provider=provider_name,
        warnings=warnings,
    )


def parse_with_llm(text: str, catalog: Catalog, provider: OpenAICompatibleProvider) -> ParseResult:
    raw = provider.complete_json(build_system_prompt(catalog), text, build_schema(catalog))
    if not isinstance(raw, dict):  # pragma: no cover - extract_json이 이미 막음
        raise LLMError("AI 응답이 JSON 객체가 아님")
    return to_parse_result(raw, catalog, provider.name)
