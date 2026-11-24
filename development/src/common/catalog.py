"""좌석 목록(seats.yml)과 설치 프로필(profiles/*.yml)을 읽습니다."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import PROFILES_DIR, get_settings
from .models import Profile, Seat


def load_profiles(directory: Path = PROFILES_DIR) -> dict[str, Profile]:
    profiles: dict[str, Profile] = {}
    for path in sorted(Path(directory).glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        profile = Profile(**data)
        if profile.id in profiles:
            raise ValueError(f"프로필 id가 겹칩니다: {profile.id} ({path.name})")
        profiles[profile.id] = profile
    return profiles


def load_seats(path: Path | None = None) -> dict[int, Seat]:
    path = Path(path or get_settings().seats_file)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    seats = [Seat(**item) for item in data.get("seats", [])]
    result: dict[int, Seat] = {}
    for seat in sorted(seats, key=lambda s: s.number):
        if seat.number in result:
            raise ValueError(f"좌석 번호가 겹칩니다: {seat.number}")
        if seat.mode == "real" and not seat.host:
            raise ValueError(f"{seat.number}번 좌석은 mode: real 인데 host(주소)가 없습니다")
        result[seat.number] = seat
    return result


@dataclass
class Catalog:
    seats: dict[int, Seat]
    profiles: dict[str, Profile]


def load_catalog() -> Catalog:
    """요청마다 새로 읽어서, 서버를 켠 채로 seats.yml·프로필을 고쳐도 바로 반영됩니다."""
    return Catalog(seats=load_seats(), profiles=load_profiles())
