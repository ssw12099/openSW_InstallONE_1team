"""좌석 검증 스크립트·판정 테스트."""
from __future__ import annotations

import subprocess
import sys

from src.common.config import SEAT_CHECK_SCRIPT
from src.verification import evaluate


def run_seat_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SEAT_CHECK_SCRIPT), *args], capture_output=True, text=True, timeout=120)


def test_seat_check_prints_ascii_json_and_passes():
    proc = run_seat_check("--examples=hello", "--imports=json")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.isascii()
    data = evaluate.parse_seat_check(proc.stdout)
    assert data["ok"] is True
    assert data["examples"]["hello"]["output"].endswith("squares_sum=55")
    assert data["imports"]["json"]["ok"] is True


def test_seat_check_reports_missing_package():
    proc = run_seat_check("--imports=installone_no_such_package")
    assert proc.returncode == 1
    data = evaluate.parse_seat_check(proc.stdout)
    assert data["ok"] is False
    assert evaluate.seat_check_problems(data)[0].startswith("installone_no_such_package import 실패")


def test_evaluate_helpers():
    assert evaluate.parse_seat_check("no marker here") is None
    assert evaluate.first_line("\n\n  Python 3.12.10  \nmore") == "Python 3.12.10"
    assert "출력에 'Python 3.12'가 없어요" in evaluate.check_failure_text("Python", "Python 3.12", "Python 3.11.9", 0)
    assert "코드 9009" in evaluate.check_failure_text("Git", "git version", "'git' is not recognized", 9009)
