"""Ansible 이벤트 → 좌석 상태 분류 테스트 (ansible-runner 이벤트 모양을 흉내 냄)."""
from __future__ import annotations

import json

from src.common.models import SeatStatus
from src.installer.events import CHECK_TASK, SEAT_CHECK_TASK, SeatTracker
from src.verification.seat_check import MARKER


def feed(tracker: SeatTracker, *events):
    for event_type, task, res, extra in events:
        tracker.handle(event_type, {"task": task, "host": "seat01", "res": res, **extra})
    return tracker.final()


def ok(task, res=None, **extra):
    return ("runner_on_ok", task, res or {}, extra)


def failed(task, res=None, **extra):
    return ("runner_on_failed", task, res or {}, extra)


SEAT_CHECK_OUT = MARKER + " " + json.dumps({
    "python": "3.12.10", "pip": "25.0.1", "imports": {},
    "examples": {"hello": {"ok": True, "output": "hello ok: avg=84.0, squares_sum=55", "expect": "squares_sum=55"}},
    "ok": True,
})
CHECKS_OK = {"changed": False, "results": [
    {"item": {"label": "Python", "command": "python --version", "expect": "Python 3.12"},
     "stdout": "Python 3.12.10\r\n", "rc": 0, "failed": False},
]}


def test_success_collects_versions_and_example():
    final = feed(SeatTracker(1),
                 ok("[연결] 좌석 접속 확인", {"ping": "pong"}),
                 ok("[설치] Chocolatey 패키지 설치", {"changed": True}),
                 ok(CHECK_TASK, CHECKS_OK),
                 ok(SEAT_CHECK_TASK, {"stdout": SEAT_CHECK_OUT + "\r\n"}))
    assert final["status"] == SeatStatus.SUCCESS
    assert final["versions"] == {"Python": "Python 3.12.10"}
    assert "squares_sum=55" in final["example_output"]


def test_nothing_changed_means_already_installed():
    final = feed(SeatTracker(1),
                 ok("[연결] 좌석 접속 확인"),
                 ok("[설치] Chocolatey 패키지 설치", {"changed": False}),
                 ("runner_on_skipped", "[설치] pip 패키지 설치", {}, {}),
                 ok(CHECK_TASK, CHECKS_OK))
    assert final["status"] == SeatStatus.ALREADY_INSTALLED


def test_unreachable_is_connect_failure():
    final = feed(SeatTracker(1), ("runner_on_unreachable", "[연결] 좌석 접속 확인",
                                  {"msg": "ntlm: HTTPConnectionPool(host='10.0.0.5', port=5985) timed out",
                                   "unreachable": True}, {}))
    assert final["status"] == SeatStatus.CONNECT_FAILED
    assert "5985" in final["message"]


def test_connect_failure_gets_a_korean_hint():
    def unreachable(msg):
        return feed(SeatTracker(1), ("runner_on_unreachable", "[연결] 좌석 접속 확인",
                                     {"msg": msg, "unreachable": True}, {}))["message"]

    refused = unreachable("ntlm: HTTPConnectionPool(host='192.168.56.101', port=5985): Max retries exceeded "
                          "with url: /wsman (Caused by NewConnectionError: [Errno 111] Connection refused)")
    assert "VM 주소·전원·네트워크" in refused and "Connection refused" in refused  # 원문도 남김
    wrong_password = unreachable("ntlm: the specified credentials were rejected by the server")
    assert "계정 이름이나 비밀번호" in wrong_password
    assert unreachable("뭔가 다른 오류") == "좌석에 접속할 수 없어요: 뭔가 다른 오류"


def test_install_failure_names_failed_package():
    res = {"results": [{"item": {"name": "python312"}, "failed": True,
                        "msg": "Error installing package 'python312'"}]}
    final = feed(SeatTracker(1), ok("[연결] 좌석 접속 확인"), failed("[설치] Chocolatey 패키지 설치", res))
    assert final["status"] == SeatStatus.INSTALL_FAILED
    assert "python312" in final["message"]


def test_wrong_version_is_verify_failure():
    res = {"results": [{"item": {"label": "Python", "expect": "Python 3.12"}, "stdout": "Python 3.11.9",
                        "rc": 0, "failed": True}]}
    final = feed(SeatTracker(1), ok("[연결] 좌석 접속 확인"), ok("[설치] Chocolatey 패키지 설치", {"changed": True}),
                 failed(CHECK_TASK, res))
    assert final["status"] == SeatStatus.VERIFY_FAILED
    assert "Python 3.12" in final["message"] and "3.11.9" in final["message"]
    assert final["versions"]["Python"] == "Python 3.11.9"


def test_example_failure_is_verify_failure():
    bad = MARKER + " " + json.dumps({"python": "3.12.10", "imports": {"pandas": {"ok": False, "error": "ModuleNotFoundError"}},
                                     "examples": {}, "ok": False})
    final = feed(SeatTracker(1), ok("[연결] 좌석 접속 확인"), ok("[설치] Chocolatey 패키지 설치", {"changed": True}),
                 ok(CHECK_TASK, CHECKS_OK), failed(SEAT_CHECK_TASK, {"stdout": bad, "rc": 1}))
    assert final["status"] == SeatStatus.VERIFY_FAILED
    assert "pandas import 실패" in final["message"]


def test_ignored_failure_does_not_fail_seat():
    final = feed(SeatTracker(1), ok("[연결] 좌석 접속 확인"), failed("[설치] 선택 작업", {"msg": "x"}, ignore_errors=True),
                 ok("[설치] Chocolatey 패키지 설치", {"changed": True}))
    assert final["status"] == SeatStatus.SUCCESS


def test_no_events_is_error():
    assert SeatTracker(1).final()["status"] == SeatStatus.ERROR


def test_ansible_2_19_item_results_without_failed_key():
    """ansible-core 2.19+ 이벤트처럼 항목 결과에 'failed'가 없고 failed_when_result/exception만 있는 경우."""
    res = {"msg": "One or more items failed", "results": [
        {"item": {"label": "Python", "expect": "Python 3.12"}, "stdout": "Python 3.11.9", "rc": 0,
         "failed_when_result": True, "exception": "(traceback unavailable)"},
    ]}
    final = feed(SeatTracker(1), ok("[연결] 좌석 접속 확인"), ok("[설치] Chocolatey 패키지 설치", {"changed": True}),
                 failed(CHECK_TASK, res))
    assert final["status"] == SeatStatus.VERIFY_FAILED
    assert "Python 확인 실패" in final["message"] and "3.11.9" in final["message"]
