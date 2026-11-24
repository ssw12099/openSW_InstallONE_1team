"""실제 ansible-runner로 로컬 플레이북을 돌려 이벤트 → 좌석 상태 분류를 확인합니다.

ansible-runner가 설치된 환경(Linux/WSL2)에서만 실행되고, 없으면 건너뜁니다.
접속 실패 좌석은 열려 있지 않은 포트로 WinRM 접속을 시도해 만듭니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.common.models import Check, ChocoPackage, InstallPlan, Seat, SeatMode, SeatStatus
from src.installer.ansible_exec import build_inventory, run_real_seats

pytest.importorskip("ansible_runner")
pytest.importorskip("winrm")

FIXTURE = Path(__file__).parent / "fixtures" / "local_install.yml"


def test_runner_events_map_to_seat_status(reporter):
    seats = [Seat(number=n, name=f"PC-0{n}", mode=SeatMode.REAL, host="127.0.0.1") for n in range(1, 6)]
    plan = InstallPlan(
        profiles=["python-basic"],
        choco=[ChocoPackage(name="python312", version="3.12.10")],
        checks=[Check(label="Python", command="echo Python $FAKE_PY", expect="Python 3.12")],
        examples=["hello"],
    )
    overrides = {
        2: {"already": True},
        3: {"fake_python": "3.11.9"},
        4: {"fail_install": True},
        5: {"ansible_connection": "winrm", "ansible_port": 1, "ansible_user": "seat-user", "ansible_password": "Not-A-Real-Password-7f3",
            "ansible_winrm_transport": "ntlm", "ansible_winrm_scheme": "http",
            "ansible_winrm_connection_timeout": 3},
    }
    run_real_seats(
        1, seats, plan, reporter,
        playbook_path=FIXTURE,
        connection_vars={"ansible_connection": "local", "ansible_python_interpreter": sys.executable},
        host_overrides=overrides,
        require_credentials=False,
    )
    results = reporter.results
    assert results[1]["status"] == SeatStatus.SUCCESS, results[1]
    assert results[1]["versions"]["Python"] == "Python 3.12.10"
    assert "squares_sum=55" in results[1]["example_output"]
    assert results[2]["status"] == SeatStatus.ALREADY_INSTALLED, results[2]
    assert results[3]["status"] == SeatStatus.VERIFY_FAILED, results[3]
    assert "3.11.9" in results[3]["message"]
    assert results[4]["status"] == SeatStatus.INSTALL_FAILED, results[4]
    assert "python312" in results[4]["message"]
    assert results[5]["status"] == SeatStatus.CONNECT_FAILED, results[5]

    kinds = {(e.seat_no, e.kind) for e in reporter.events}
    assert (1, "start") in kinds and (1, "changed") in kinds and (5, "unreachable") in kinds
    assert any(e.kind == "item" and "python312" in e.detail for e in reporter.events)


def test_inventory_keeps_password_out_of_files():
    inventory = build_inventory([Seat(number=1, name="PC-01", mode=SeatMode.REAL, host="192.0.2.10")])
    group_vars = inventory["all"]["children"]["seats"]["vars"]
    assert group_vars["ansible_connection"] == "winrm" and group_vars["ansible_winrm_transport"] == "ntlm"
    assert "lookup" in group_vars["ansible_password"]  # 값 대신 실행 중 환경 변수에서 읽음
    host = inventory["all"]["children"]["seats"]["hosts"]["seat01"]
    assert host == {"ansible_host": "192.0.2.10", "seat_no": 1}


def test_without_credentials_real_seats_report_error(reporter):
    seats = [Seat(number=1, name="PC-01", mode=SeatMode.REAL, host="192.0.2.10")]
    run_real_seats(1, seats, InstallPlan(profiles=["git"]), reporter)
    assert reporter.results[1]["status"] == SeatStatus.ERROR
    assert "INSTALLONE_WINRM_USER" in reporter.results[1]["message"]
