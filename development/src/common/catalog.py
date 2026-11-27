"""좌석 목록(seats.yml)과 설치 프로필(profiles/*.yml)을 읽습니다.

파일을 손으로 고치다 생기는 실수(들여쓰기, 오타, host 빠짐)는 CatalogError 하나로 모아서
"어느 파일의 무엇이 문제인지" 한국어로 알려 줍니다. 관리 웹에 그대로 표시됩니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .config import PROFILES_DIR, get_settings
from .models import Profile, Seat


class CatalogError(Exception):
    """좌석·프로필 설정 파일 문제."""


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise CatalogError(f"{path.name} 파일이 없어요 ({path})") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" {mark.line + 1}번째 줄 근처" if mark else ""
        raise CatalogError(f"{path.name}{where}의 형식(들여쓰기, 콜론)이 맞지 않아요") from exc


def _validation_text(exc: ValidationError) -> str:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first.get("loc", ())) or "값"
    return f"'{field}' 값이 맞지 않아요 ({first.get('msg', '')})"


def load_profiles(directory: Path = PROFILES_DIR) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for path in sorted(Path(directory).glob("*.yml")):
        data = _read_yaml(path)
        try:
            profile = Profile(**data)
        except (ValidationError, TypeError) as exc:
            detail = _validation_text(exc) if isinstance(exc, ValidationError) else "형식이 맞지 않아요"
            raise CatalogError(f"프로필 {path.name}: {detail}") from exc
        if profile.id in profiles:
            raise CatalogError(f"프로필 id가 겹쳐요: {profile.id} ({path.name})")
        profiles[profile.id] = profile
    for profile in profiles.values():
        missing = [pid for pid in profile.includes if pid not in profiles]
        if missing:
            raise CatalogError(f"프로필 {profile.id}: includes에 적은 '{', '.join(missing)}' 프로필이 없어요")
    return profiles


def load_seats(path: Path | None = None) -> dict[int, Seat]:
    path = Path(path or get_settings().seats_file)
    data = _read_yaml(path)
    items = (data.get("seats") or []) if isinstance(data, dict) and "seats" in data else None
    if not isinstance(items, list):  # 'seat:' 같은 오타도 여기서 걸림
        raise CatalogError(f"{path.name}에 'seats:' 목록이 없어요")
    result: dict[int, Seat] = {}
    for index, item in enumerate(items, start=1):
        try:
            seat = Seat(**item)
        except (ValidationError, TypeError) as exc:
            detail = _validation_text(exc) if isinstance(exc, ValidationError) else "형식이 맞지 않아요"
            raise CatalogError(f"{path.name}의 {index}번째 좌석: {detail}") from exc
        if seat.number in result:
            raise CatalogError(f"{path.name}: 좌석 번호 {seat.number}이 겹쳐요")
        if seat.mode == "real" and not seat.host:
            raise CatalogError(f"{path.name}: {seat.number}번 좌석은 mode: real 인데 host(주소)가 없어요")
        result[seat.number] = seat
    return dict(sorted(result.items()))


@dataclass
class Catalog:
    seats: dict[int, Seat]
    profiles: dict[str, Profile]


def load_catalog() -> Catalog:
    """요청마다 새로 읽어서, 서버를 켠 채로 seats.yml·프로필을 고쳐도 바로 반영됩니다."""
    return Catalog(seats=load_seats(), profiles=load_profiles())
