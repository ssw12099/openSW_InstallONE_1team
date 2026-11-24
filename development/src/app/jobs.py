"""설치 작업 실행 관리.

확인된 요청을 작업으로 만들고, 좌석을 실제(Ansible)·모의로 나눠 백그라운드에서 동시에 실행합니다.
installer가 알려 주는 진행 상황은 JobReporter가 storage에 기록합니다.
"""
from __future__ import annotations

import logging
import threading

from ..common.catalog import load_catalog
from ..common.models import FINAL_STATUSES, InstallPlan, Seat, SeatEvent, SeatMode, SeatStatus, Stage
from ..installer import build_plan
from ..installer.ansible_exec import run_real_seats
from ..installer.mock_runner import run_mock_seat
from ..storage import repository as repo

log = logging.getLogger(__name__)
_threads: dict[int, threading.Thread] = {}


class JobReporter:
    """installer → storage 연결 (common.reporting.Reporter 구현)."""

    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
        self._started: set[int] = set()
        self._lock = threading.Lock()

    def stage(self, seat_no: int, stage: Stage) -> None:
        fields = {"status": SeatStatus.RUNNING, "stage": stage}
        with self._lock:
            if seat_no not in self._started:
                self._started.add(seat_no)
                fields["started_at"] = repo.now()
        repo.update_seat(self.job_id, seat_no, **fields)

    def event(self, event: SeatEvent) -> None:
        repo.add_event(self.job_id, event)

    def finish(self, seat_no: int, status: SeatStatus, *, versions=None, example_output="", message="") -> None:
        repo.update_seat(
            self.job_id, seat_no,
            status=status, stage=Stage.DONE, versions=versions or {},
            example_output=example_output, message=message, finished_at=repo.now(),
        )


def submit_job(request_id: int | None, seat_numbers: list[int], profile_ids: list[str]) -> int:
    """입력 검사 → 작업 기록 → 백그라운드 실행 시작. 잘못된 입력이면 ValueError."""
    catalog = load_catalog()
    numbers = sorted(set(seat_numbers))
    if not numbers:
        raise ValueError("설치할 좌석을 하나 이상 골라 주세요.")
    unknown = [n for n in numbers if n not in catalog.seats]
    if unknown:
        raise ValueError(f"등록되지 않은 좌석: {', '.join(map(str, unknown))}")
    plan = build_plan(profile_ids, catalog.profiles)  # 없는 프로필이면 ValueError
    seats = [catalog.seats[n] for n in numbers]

    job_id = repo.create_job(request_id, seats, plan.profiles)
    thread = threading.Thread(target=_run_job, args=(job_id, seats, plan), name=f"job-{job_id}", daemon=True)
    _threads[job_id] = thread
    thread.start()
    return job_id


def wait_for_job(job_id: int, timeout: float | None = None) -> bool:
    """테스트·스크립트용: 작업 스레드가 끝날 때까지 기다림."""
    thread = _threads.get(job_id)
    if thread is None:
        return True
    thread.join(timeout)
    return not thread.is_alive()


def _guard(target, seats: list[Seat], reporter: JobReporter, *args) -> None:
    """좌석 실행 중 예상 못 한 오류가 나도 좌석이 '진행 중'에 멈춰 있지 않게 함."""
    try:
        target(*args)
    except Exception as exc:  # pragma: no cover - 방어 코드
        log.exception("좌석 실행 오류")
        for seat in seats:
            reporter.finish(seat.number, SeatStatus.ERROR, message=f"서버 오류: {exc}")


def _run_job(job_id: int, seats: list[Seat], plan: InstallPlan) -> None:
    reporter = JobReporter(job_id)
    repo.set_job_status(job_id, "running")
    real = [s for s in seats if s.mode == SeatMode.REAL]
    mock = [s for s in seats if s.mode == SeatMode.MOCK]

    workers = [
        threading.Thread(target=_guard, args=(run_mock_seat, [s], reporter, s, plan, reporter), daemon=True)
        for s in mock
    ]
    if real:
        workers.append(threading.Thread(
            target=_guard, args=(run_real_seats, real, reporter, job_id, real, plan, reporter), daemon=True
        ))
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    # 혹시 끝나지 않은 좌석이 있으면 오류로 마감
    job = repo.get_job(job_id) or {"seats": []}
    for seat in job["seats"]:
        if SeatStatus(seat["status"]) not in FINAL_STATUSES:
            reporter.finish(seat["seat_no"], SeatStatus.ERROR, message="실행이 끝났는데 결과가 없어요.")
    repo.set_job_status(job_id, "done")
