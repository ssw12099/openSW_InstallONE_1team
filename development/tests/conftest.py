"""테스트마다 임시 runtime 폴더·테스트용 좌석 목록을 쓰고, 모의 좌석은 기다리지 않게 합니다."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.common.config import reload_settings
from src.common.models import SeatEvent, SeatStatus, Stage
from src.storage import repository

TEST_SEATS = """
seats:
  - number: 1
    name: PC-01
    mode: mock
  - number: 2
    name: PC-02
    mode: mock
    mock_result: already_installed
  - number: 3
    name: PC-03
    mode: mock
    mock_result: install_failed
  - number: 4
    name: PC-04
    mode: mock
    mock_result: verify_failed
  - number: 5
    name: PC-05
    mode: mock
    mock_result: connect_failed
"""


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    seats_file = tmp_path / "seats.yml"
    seats_file.write_text(TEST_SEATS, encoding="utf-8")
    monkeypatch.setenv("INSTALLONE_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("INSTALLONE_SEATS", str(seats_file))
    monkeypatch.setenv("INSTALLONE_MOCK_SPEED", "0")
    monkeypatch.setenv("LLM_PROVIDER", "none")
    for name in ("INSTALLONE_DB", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    reload_settings()
    repository.init_db()
    yield
    reload_settings()


class MemoryReporter:
    """installer 테스트용: DB 대신 메모리에 기록."""

    def __init__(self) -> None:
        self.stages: list[tuple[int, Stage]] = []
        self.events: list[SeatEvent] = []
        self.results: dict[int, dict] = {}

    def stage(self, seat_no: int, stage: Stage) -> None:
        self.stages.append((seat_no, stage))

    def event(self, event: SeatEvent) -> None:
        self.events.append(event)

    def finish(self, seat_no: int, status: SeatStatus, *, versions=None, example_output="", message="") -> None:
        self.results[seat_no] = {
            "status": status, "versions": versions or {}, "example_output": example_output, "message": message,
        }


@pytest.fixture
def reporter() -> MemoryReporter:
    return MemoryReporter()
