"""좌석에서 돌아온 검증 결과를 서버에서 읽고 판정합니다."""
from __future__ import annotations

import json
import re
from typing import Any

from .seat_check import MARKER


def first_line(text: str | None) -> str:
    for line in str(text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def version_text(output: str | None) -> str:
    """점검 명령 출력의 첫 줄에서 버전 표시만 남김 (예: 'pip 25.0.1 from C:\\...' → 'pip 25.0.1')."""
    return re.sub(r"\s+from\s+\S.*$", "", first_line(output))


def parse_seat_check(stdout: str) -> dict[str, Any] | None:
    """출력에서 'INSTALLONE_RESULT {...}' 줄을 찾아 dict로 돌려줍니다."""
    for line in reversed(str(stdout or "").splitlines()):
        line = line.strip()
        if line.startswith(MARKER):
            try:
                data = json.loads(line[len(MARKER) :].strip())
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None
    return None


def check_failure_text(label: str, expect: str, output: str, rc: Any) -> str:
    shown = first_line(output) or "출력 없음"
    if rc not in (0, None, "0"):
        return f"{label} 확인 실패: 명령 실행 오류(코드 {rc}) — {shown}"
    if expect:
        return f"{label} 확인 실패: 출력에 '{expect}'가 없어요 (출력: {shown})"
    return f"{label} 확인 실패 — {shown}"


def seat_check_problems(seat_check: dict[str, Any] | None) -> list[str]:
    if not seat_check:
        return ["검증 스크립트 결과를 읽을 수 없어요"]
    problems = []
    for name, info in (seat_check.get("imports") or {}).items():
        if not info.get("ok"):
            problems.append(f"{name} import 실패: {info.get('error', '')}")
    for name, info in (seat_check.get("examples") or {}).items():
        if not info.get("ok"):
            reason = info.get("error") or f"출력에 '{info.get('expect')}'가 없어요 (출력: {info.get('output', '')})"
            problems.append(f"예제 {name} 실패: {reason}")
    return problems


def collect_versions(check_outputs: dict[str, str], seat_check: dict[str, Any] | None) -> dict[str, str]:
    versions = {label: version_text(out) for label, out in check_outputs.items() if first_line(out)}
    if seat_check:
        for name, info in (seat_check.get("imports") or {}).items():
            if info.get("ok"):
                versions[name] = info.get("version") or "설치됨"
    return versions


def example_summary(seat_check: dict[str, Any] | None) -> str:
    if not seat_check:
        return ""
    parts = []
    for name, info in (seat_check.get("examples") or {}).items():
        if info.get("ok"):
            parts.append(f"{name} → {info.get('output', '')}")
        else:
            parts.append(f"{name} → 실패 ({info.get('error') or '기대 출력 없음'})")
    return " / ".join(parts)
