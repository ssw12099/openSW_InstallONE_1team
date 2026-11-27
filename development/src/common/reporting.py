"""installer가 진행 상황을 알릴 때 쓰는 통로.

installer는 저장 방식(DB)을 몰라도 되도록 이 Protocol만 씁니다.
실제 구현은 app/jobs.py의 JobReporter(→ storage)입니다.
"""
from __future__ import annotations

from typing import Protocol

from .models import SeatEvent, SeatStatus, Stage


class Reporter(Protocol):
    def stage(self, seat_no: int, stage: Stage) -> None:
        """좌석이 새 단계(연결/설치/검증)에 들어갔음."""

    def event(self, event: SeatEvent) -> None:
        """실행 기록 한 줄."""

    def finish(
        self,
        seat_no: int,
        status: SeatStatus,
        *,
        versions: dict[str, str] | None = None,
        example_output: str = "",
        message: str = "",
    ) -> None:
        """좌석 최종 결과."""
