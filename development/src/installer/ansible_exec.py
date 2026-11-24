"""실제 좌석(Windows VM)에 Ansible로 설치합니다.

ansible-runner는 AWX가 내부에서 쓰는 실행 엔진이라, 좌석·작업별 결과를 이벤트로 바로 받을 수 있습니다.
Ansible은 Linux/WSL2에서만 돌아서, Windows에서 서버를 켜면 실제 좌석은 '오류'와 이유를 표시합니다.
접속 비밀번호는 파일에 쓰지 않고 실행 중에 환경 변수에서만 읽습니다.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from ..common.config import PLAYBOOK_DIR, SEAT_CHECK_SCRIPT, get_settings
from ..common.models import InstallPlan, Seat, SeatEvent, SeatStatus, Stage
from ..common.reporting import Reporter
from .events import SeatTracker, item_label, short, stage_of

log = logging.getLogger(__name__)

HOST_FORMAT = "seat{:02d}"

WINRM_VARS: dict[str, Any] = {
    "ansible_connection": "winrm",
    "ansible_port": 5985,
    "ansible_winrm_scheme": "http",
    "ansible_winrm_transport": "ntlm",  # 로컬 계정 + HTTP에서도 NTLM 메시지 암호화가 적용됨
    "ansible_user": "{{ lookup('ansible.builtin.env', 'INSTALLONE_WINRM_USER') }}",
    "ansible_password": "{{ lookup('ansible.builtin.env', 'INSTALLONE_WINRM_PASSWORD') }}",
    "ansible_winrm_operation_timeout_sec": 60,
    "ansible_winrm_read_timeout_sec": 70,
}


def build_inventory(
    seats: list[Seat],
    connection_vars: dict[str, Any] | None = None,
    host_overrides: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    hosts = {}
    for seat in seats:
        host_vars: dict[str, Any] = {"ansible_host": seat.host, "seat_no": seat.number}
        host_vars.update((host_overrides or {}).get(seat.number, {}))
        hosts[HOST_FORMAT.format(seat.number)] = host_vars
    group_vars = WINRM_VARS if connection_vars is None else connection_vars
    return {"all": {"children": {"seats": {"hosts": hosts, "vars": group_vars}}}}


def build_extravars(plan: InstallPlan) -> dict[str, Any]:
    return {
        "choco_packages": [p.model_dump() for p in plan.choco],
        "pip_packages": plan.pip,
        "checks": [c.model_dump() for c in plan.checks],
        "examples": plan.examples,
        "imports": plan.imports,
        "run_seat_check": plan.needs_seat_check,
        "seat_check_src": str(SEAT_CHECK_SCRIPT),
    }


def _fail_all(seats: list[Seat], reporter: Reporter, message: str) -> None:
    for seat in seats:
        reporter.event(SeatEvent(seat_no=seat.number, kind="info", ok=False, detail=message))
        reporter.finish(seat.number, SeatStatus.ERROR, message=message)


def run_real_seats(
    job_id: int,
    seats: list[Seat],
    plan: InstallPlan,
    reporter: Reporter,
    *,
    playbook_path: Path | None = None,
    connection_vars: dict[str, Any] | None = None,
    host_overrides: dict[int, dict[str, Any]] | None = None,
    require_credentials: bool = True,
) -> None:
    """실제 좌석들에 한 번의 플레이북 실행으로 동시에 설치합니다 (좌석 수만큼 병렬)."""
    settings = get_settings()
    try:
        import ansible_runner
    except ImportError:
        _fail_all(seats, reporter, "ansible-runner가 없어 실제 설치를 못 해요. WSL2(Linux)에서 "
                  "requirements-ansible.txt를 설치하고 서버를 켜 주세요.")
        return
    if require_credentials and not (settings.winrm_user and settings.winrm_password_set):
        _fail_all(seats, reporter, "좌석 접속 계정이 없어요. .env에 INSTALLONE_WINRM_USER와 "
                  "INSTALLONE_WINRM_PASSWORD를 적어 주세요.")
        return

    host_to_seat = {HOST_FORMAT.format(s.number): s.number for s in seats}
    trackers = {s.number: SeatTracker(s.number) for s in seats}
    playbook = Path(playbook_path or PLAYBOOK_DIR / "install.yml")
    private_dir = settings.runtime_dir / "ansible" / f"job-{job_id}"
    private_dir.mkdir(parents=True, exist_ok=True)

    for seat in seats:
        reporter.stage(seat.number, Stage.CONNECT)

    def on_event(event: dict[str, Any]) -> bool:
        data = event.get("event_data") or {}
        seat_no = host_to_seat.get(data.get("host"))
        if seat_no is None:
            return True
        event_type = str(event.get("event") or "")
        if event_type in ("runner_item_on_ok", "runner_item_on_failed"):  # 반복 작업의 항목별 기록
            res = data.get("res") or {}
            label = item_label(res)
            reporter.event(SeatEvent(
                seat_no=seat_no, stage=stage_of(str(data.get("task") or "")), kind="item",
                task=str(data.get("task") or ""), ok=event_type == "runner_item_on_ok",
                detail=f"{label}: {'바뀜' if res.get('changed') else '그대로'}"
                if event_type == "runner_item_on_ok" else f"{label}: {short(res.get('msg') or res.get('stdout'))}",
            ))
            return True
        tracker = trackers[seat_no]
        before = tracker.stage
        seat_event = tracker.handle(event_type, data)
        if seat_event is not None:
            reporter.event(seat_event)
        if tracker.failed_status is None and tracker.stage is not None and tracker.stage != before:
            reporter.stage(seat_no, tracker.stage)
        return True

    try:
        runner = ansible_runner.run(
            private_data_dir=str(private_dir),
            project_dir=str(playbook.parent),
            playbook=playbook.name,
            inventory=build_inventory(seats, connection_vars, host_overrides),
            extravars=build_extravars(plan),
            event_handler=on_event,
            quiet=True,
            forks=settings.ansible_forks,
            envvars={
                # 가상환경을 activate하지 않고 서버를 켜도 같은 환경의 ansible-playbook을 찾도록
                "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
                "ANSIBLE_HOST_KEY_CHECKING": "False", "ANSIBLE_NOCOLOR": "1",
                "ANSIBLE_RETRY_FILES_ENABLED": "False",
            },
        )
        status, rc = runner.status, runner.rc
    except Exception as exc:  # 실행 자체가 안 됨
        log.exception("ansible-runner 실행 실패")
        _fail_all(seats, reporter, f"Ansible 실행 중 오류: {short(exc)}")
        return

    for seat in seats:
        final = trackers[seat.number].final()
        if final["status"] == SeatStatus.ERROR:
            final["message"] = (f"Ansible이 이 좌석을 실행하지 못했어요 (상태 {status}, 코드 {rc}). "
                                f"runtime/ansible/job-{job_id}/artifacts 의 로그를 확인하세요.")
        reporter.finish(seat.number, final.pop("status"), **final)
