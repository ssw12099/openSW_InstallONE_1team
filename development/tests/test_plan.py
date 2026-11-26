"""프로필 → 설치 계획. 포함(includes)과 'Python 버전은 한 곳만 바꾸면 된다'를 확인합니다."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.common.catalog import CatalogError, load_profiles
from src.common.config import PROFILES_DIR
from src.common.models import Seat, SeatMode, SeatStatus
from src.installer import build_plan
from src.installer.mock_runner import run_mock_seat


def test_included_profile_items_come_along():
    profiles = load_profiles()
    basic = profiles["python-basic"]
    plan = build_plan(["python-data"], profiles)
    assert plan.profiles == ["python-data"]
    assert plan.choco == basic.choco  # Python은 python-basic에서 가져옴
    assert [c.label for c in plan.checks] == ["Python", "pip"]
    assert plan.examples == ["hello", "data"]
    assert plan.pip == ["numpy", "pandas", "matplotlib"]

    both = build_plan(["python-basic", "python-data"], profiles)
    assert both.choco == basic.choco and both.examples == ["hello", "data"]


def test_changing_python_version_takes_two_lines(tmp_path: Path, reporter):
    folder = tmp_path / "profiles"  # tmp_path에는 테스트용 seats.yml이 있어서 따로 폴더를 만듦
    folder.mkdir()
    for path in PROFILES_DIR.glob("*.yml"):
        shutil.copy(path, folder / path.name)
    basic = folder / "python-basic.yml"
    text = basic.read_text(encoding="utf-8")
    assert text.count("name: python312") == 1 and text.count('"3.12.10"') == 1
    basic.write_text(text.replace("name: python312", "name: python314").replace('"3.12.10"', '"3.14.7"'),
                     encoding="utf-8")

    plan = build_plan(["python-data"], load_profiles(folder))
    assert [(p.name, p.version) for p in plan.choco] == [("python314", "3.14.7")]
    assert plan.checks[0].expect == "3.14.7"  # 점검 기준도 같이 바뀜

    run_mock_seat(Seat(number=1, name="PC-01", mode=SeatMode.MOCK), plan, reporter, speed=0)
    assert reporter.results[1]["status"] == SeatStatus.SUCCESS
    assert reporter.results[1]["versions"]["Python"] == "Python 3.14.7"  # 모의 결과도 프로필 버전을 따라감


def test_profile_including_missing_profile_is_explained(tmp_path: Path):
    folder = tmp_path / "profiles"
    folder.mkdir()
    (folder / "a.yml").write_text("id: a\nname: A\ndescription: 설명\nincludes: [nothing]\n", encoding="utf-8")
    with pytest.raises(CatalogError) as info:
        load_profiles(folder)
    assert "'nothing'" in str(info.value)
