"""seats.yml·프로필 파일을 손으로 고치다 생기는 실수를 알아보기 쉽게 알려 주는지 확인."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.main import app
from src.common.catalog import CatalogError, load_profiles, load_seats


@pytest.mark.parametrize(("yaml_text", "expected"), [
    ("seats:\n  - number: 1\n    name: PC-01\n    mode: real\n", "host(주소)가 없어요"),
    ("seats:\n  - number: 1\n    name: PC-01\n    mode: reel\n", "'mode' 값이 맞지 않아요"),
    ("seats:\n  - number: 1\n   name: PC-01\n", "줄 근처의 형식"),
    ("seats:\n  - number: 1\n    name: A\n  - number: 1\n    name: B\n", "좌석 번호 1이 겹쳐요"),
    ("좌석:\n  - number: 1\n", "'seats:' 목록이 없어요"),
])
def test_seat_file_mistakes_are_explained(tmp_path: Path, yaml_text: str, expected: str):
    path = tmp_path / "seats.yml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(CatalogError) as info:
        load_seats(path)
    assert expected in str(info.value)


def test_api_shows_the_seat_file_problem(tmp_path: Path):
    (tmp_path / "seats.yml").write_text("seats:\n  - number: 1\n    name: PC-01\n    mode: real\n", encoding="utf-8")
    with TestClient(app) as client:
        response = client.get("/api/catalog")
        assert response.status_code == 500
        assert response.json()["detail"].startswith("설정 파일을 확인해 주세요.")
        assert "host(주소)" in response.json()["detail"]
        assert "설정 파일을 확인" in client.post("/api/parse", json={"text": "1번에 깃"}).json()["detail"]


def test_profile_file_mistakes_are_explained(tmp_path: Path):
    folder = tmp_path / "profiles"  # tmp_path에는 테스트용 seats.yml이 있어서 따로 폴더를 만듦
    folder.mkdir()
    (folder / "broken.yml").write_text("name: 이름만 있음\n", encoding="utf-8")
    with pytest.raises(CatalogError) as info:
        load_profiles(folder)
    assert "broken.yml" in str(info.value) and "'id'" in str(info.value)


def test_bundled_seat_and_profile_files_are_valid():
    from src.common.config import DEFAULT_SEATS_FILE

    seats = load_seats(DEFAULT_SEATS_FILE)
    assert seats and all(seat.mode == "mock" for seat in seats.values())
    assert {"python-basic", "python-data", "java-basic", "c-basic", "git", "vscode"} <= set(load_profiles())
