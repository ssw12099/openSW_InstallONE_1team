"""규칙 기반 요청 해석.

AI를 못 쓰거나 AI가 실패했을 때의 안전망이고, AI 결과를 교차 확인하는 데도 씁니다.
좌석: "1번부터 4번", "1~4번", "2, 3번", "PC3", "전체 PC"
도구: 프로필 YAML의 keywords
"""
from __future__ import annotations

import re

from ..common.catalog import Catalog
from ..common.models import ParseResult

# 버전 숫자(3.12)와 도구 이름에 붙은 숫자(python3, 자바 21)는 좌석 번호로 보지 않습니다.
_VERSION = re.compile(r"\d+(?:\.\d+)+")
_TOOL_NUMBER = re.compile(r"(python|파이썬|java|자바|jdk|node|노드|gcc)\s*\d+", re.I)

_RANGE = re.compile(
    r"(?:pc\s*-?\s*)?(\d{1,3})\s*번?\s*(?:pc|좌석|자리)?\s*(?:부터|에서|~|∼|〜|-|–|—)\s*"
    r"(?:pc\s*-?\s*)?(\d{1,3})\s*(번|pc|좌석|자리|까지)?",
    re.I,
)
_LIST = re.compile(
    r"(\d{1,3}(?:\s*번)?(?:\s*(?:,|，|、|/|와|과|및|이랑|랑|하고|그리고)\s*\d{1,3}(?:\s*번)?)*)"
    r"\s*(번|pc|좌석|자리)",
    re.I,
)
_PC_PREFIX = re.compile(r"pc\s*-?\s*(\d{1,3})", re.I)
_ALL = re.compile(r"전체|모든\s*(?:pc|좌석|자리|컴퓨터)|전\s*좌석", re.I)
_SEAT_MARK = re.compile(r"번|pc|좌석|자리|까지", re.I)

# 아직 프로필이 없는 도구: 요청에 나오면 '지원하지 않음'으로 알려 줍니다.
KNOWN_UNSUPPORTED = {
    "node": "Node.js", "노드": "Node.js", "docker": "Docker", "도커": "Docker",
    "eclipse": "Eclipse", "이클립스": "Eclipse", "intellij": "IntelliJ", "인텔리제이": "IntelliJ",
    "android studio": "Android Studio", "안드로이드 스튜디오": "Android Studio",
    "unity": "Unity", "유니티": "Unity", "mysql": "MySQL", "jupyter": "Jupyter", "주피터": "Jupyter",
    "anaconda": "Anaconda", "아나콘다": "Anaconda", "visual studio 20": "Visual Studio",
}
# '자바스크립트'가 Java 프로필로 잡히지 않게 따로 처리
_JAVASCRIPT = re.compile(r"자바\s*스크립트|java\s*script", re.I)


def format_seats(seats: list[int]) -> str:
    """[1,2,3,4,6] → '1~4, 6번'"""
    if not seats:
        return "없음"
    nums = sorted(set(seats))
    parts: list[str] = []
    start = prev = nums[0]
    for n in nums[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.append(f"{start}~{prev}" if prev - start >= 2 else (f"{start}, {prev}" if prev != start else f"{start}"))
        if n is not None:
            start = prev = n
    return ", ".join(parts) + "번"


def _keyword_hit(text: str, keyword: str) -> bool:
    kw = keyword.lower()
    if re.match(r"[a-z0-9]", kw):  # 영문 키워드는 다른 단어 중간에 걸리지 않게 (예: 'pc 언어' ≠ 'c 언어')
        return re.search(r"(?<![a-z0-9])" + re.escape(kw), text) is not None
    return kw in text


def drop_included(profile_ids: list[str], catalog: Catalog) -> list[str]:
    """python-data가 python-basic을 포함하듯, 포함되는 쪽은 빼고 목록 순서대로 정리."""
    chosen = [pid for pid in catalog.profiles if pid in profile_ids]
    covered = {inc for pid in chosen for inc in catalog.profiles[pid].includes}
    return [pid for pid in chosen if pid not in covered]


def extract_seats(text: str, catalog: Catalog) -> tuple[list[int], list[str], list[str]]:
    """(좌석 목록, 근거 문구, 경고)"""
    cleaned = _TOOL_NUMBER.sub(lambda m: m.group(1), _VERSION.sub(" ", text))
    found: set[int] = set()
    evidence: list[str] = []
    warnings: list[str] = []

    if _ALL.search(cleaned):
        found.update(catalog.seats)
        evidence.append(_ALL.search(cleaned).group(0))

    for m in _RANGE.finditer(cleaned):
        if not _SEAT_MARK.search(m.group(0)):
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        if b - a > 200:
            continue
        found.update(range(a, b + 1))
        evidence.append(m.group(0).strip())

    for m in _LIST.finditer(cleaned):
        nums = [int(n) for n in re.findall(r"\d{1,3}", m.group(1))]
        found.update(nums)
        evidence.append(m.group(0).strip())

    for m in _PC_PREFIX.finditer(cleaned):
        found.add(int(m.group(1)))
        evidence.append(m.group(0).strip())

    missing = sorted(n for n in found if n not in catalog.seats)
    if missing:
        warnings.append(f"등록되지 않은 좌석 {format_seats(missing)}은 뺐어요.")
    seats = sorted(n for n in found if n in catalog.seats)
    return seats, list(dict.fromkeys(evidence)), warnings


def extract_profiles(text: str, catalog: Catalog) -> tuple[list[str], dict[str, str], list[str]]:
    """(프로필 id 목록, id별 근거 키워드, 지원하지 않는 도구)"""
    lowered = text.lower()
    masked = _JAVASCRIPT.sub(" ", lowered)
    hits: dict[str, str] = {}
    for profile in catalog.profiles.values():
        for keyword in profile.keywords:
            if _keyword_hit(masked, keyword):
                hits[profile.id] = keyword
                break
    unsupported = ["JavaScript"] if _JAVASCRIPT.search(lowered) else []
    for word, name in KNOWN_UNSUPPORTED.items():
        if _keyword_hit(lowered, word) and name not in unsupported:
            unsupported.append(name)
    return drop_included(list(hits), catalog), hits, unsupported


def parse_with_rules(text: str, catalog: Catalog) -> ParseResult:
    seats, seat_evidence, warnings = extract_seats(text, catalog)
    profiles, hits, unsupported = extract_profiles(text, catalog)

    if not seats:
        warnings.append("대상 좌석을 찾지 못했어요. 아래에서 직접 골라 주세요.")
    if not profiles:
        warnings.append("설치할 도구를 찾지 못했어요. 아래에서 직접 골라 주세요.")
    if unsupported:
        warnings.append(f"아직 설치 프로필이 없는 도구: {', '.join(unsupported)}")

    seat_part = (
        f"'{seat_evidence[0]}' → 좌석 {format_seats(seats)}" if seats and seat_evidence else "좌석 없음"
    )
    profile_part = ", ".join(f"'{hits[pid]}' → {catalog.profiles[pid].name}" for pid in profiles) or "프로필 없음"
    return ParseResult(
        seats=seats,
        profiles=profiles,
        unsupported=unsupported,
        reason=f"근거: {seat_part}, {profile_part}",
        parser="rules",
        warnings=warnings,
    )
