"""모의 좌석 실행기.

실제 설치 없이, 실제 좌석과 같은 단계·같은 기록 형식으로 흐름을 재현합니다.
모든 기록·결과에 '(모의)'를 붙여 실제 VM 결과와 섞이지 않게 합니다.
결과는 seats.yml의 mock_result로 정합니다 (실패 화면 확인용).
"""
from __future__ import annotations

import time

from ..common.config import get_settings
from ..common.models import InstallPlan, Seat, SeatEvent, SeatStatus, Stage
from ..common.reporting import Reporter
from ..verification import evaluate, seat_check

MOCK = "(모의)"

# 점검 명령별 정상 출력 예시
FAKE_OUTPUTS = {
    "Python": "Python 3.12.10",
    "pip": "pip 25.0.1 from C:\\Python312\\Lib\\site-packages\\pip (python 3.12)",
    "Java": 'openjdk version "21.0.5" 2024-10-15 LTS',
    "javac": "javac 21.0.5",
    "gcc": "gcc.exe (x86_64-posix-seh-rev0, Built by MinGW-W64 project) 13.2.0",
    "Git": "git version 2.47.1.windows.2",
    "VS Code": "1.96.2",
}
# 검증 실패를 흉내 낼 때의 출력 (버전이 다르거나 명령을 못 찾음)
WRONG_OUTPUTS = {"Python": "Python 3.11.9", "Java": 'openjdk version "17.0.13" 2024-10-15'}
FAKE_IMPORT_VERSIONS = {"numpy": "2.3.5", "pandas": "2.3.3", "matplotlib": "3.10.7"}


def fake_seat_check(plan: InstallPlan) -> dict:
    examples = {}
    for name in plan.examples:
        result = seat_check.run_example(name)  # 서버에서 돌릴 수 있는 예제는 실제로 실행
        if not result.get("ok"):
            expect = seat_check.EXAMPLES.get(name, (None, ""))[1]
            result = {"ok": True, "output": f"{name} ok: rows=5, y_sum=55" if name == "data" else f"{name} ok", "expect": expect}
        examples[name] = result
    imports = {name: {"ok": True, "version": FAKE_IMPORT_VERSIONS.get(name, "1.0")} for name in plan.imports}
    return {"python": "3.12.10", "pip": "25.0.1", "imports": imports, "examples": examples, "ok": True}


def run_mock_seat(seat: Seat, plan: InstallPlan, reporter: Reporter, speed: float | None = None) -> None:
    speed = get_settings().mock_speed if speed is None else speed
    outcome = seat.mock_result
    n = seat.number

    def pause(seconds: float) -> None:
        if speed > 0:
            time.sleep(seconds * speed)

    def log(stage: Stage, kind: str, task: str, ok: bool = True, detail: str = "") -> None:
        reporter.event(SeatEvent(seat_no=n, stage=stage, kind=kind, task=f"{task} {MOCK}", ok=ok, detail=detail))

    # 1) 연결
    reporter.stage(n, Stage.CONNECT)
    log(Stage.CONNECT, "start", "[연결] 좌석 접속 확인")
    pause(0.6)
    if outcome == SeatStatus.CONNECT_FAILED:
        message = f"좌석에 접속할 수 없어요: WinRM 5985 포트 응답 없음 {MOCK}"
        log(Stage.CONNECT, "unreachable", "[연결] 좌석 접속 확인", False, message)
        reporter.finish(n, SeatStatus.CONNECT_FAILED, message=message)
        return
    log(Stage.CONNECT, "ok", "[연결] 좌석 접속 확인", detail="pong")

    # 2) 설치
    reporter.stage(n, Stage.INSTALL)
    already = outcome == SeatStatus.ALREADY_INSTALLED
    for index, package in enumerate(plan.choco):
        label = package.name + (f" {package.version}" if package.version else "")
        log(Stage.INSTALL, "start", f"[설치] Chocolatey 패키지 설치: {label}")
        pause(1.2)
        if outcome == SeatStatus.INSTALL_FAILED and index == 0:
            message = f"설치 실패 ([설치] Chocolatey 패키지 설치): {package.name} 다운로드 중 연결이 끊겼어요 {MOCK}"
            log(Stage.INSTALL, "failed", f"[설치] Chocolatey 패키지 설치: {label}", False, message)
            reporter.finish(n, SeatStatus.INSTALL_FAILED, message=message)
            return
        log(Stage.INSTALL, "ok" if already else "changed", f"[설치] Chocolatey 패키지 설치: {label}",
            detail="이미 설치되어 있음" if already else "설치함")
    if plan.pip:
        log(Stage.INSTALL, "start", "[설치] pip 패키지 설치")
        pause(1.0)
        log(Stage.INSTALL, "ok" if already else "changed", "[설치] pip 패키지 설치", detail=", ".join(plan.pip))

    # 3) 검증
    reporter.stage(n, Stage.VERIFY)
    versions: dict[str, str] = {}
    for index, check in enumerate(plan.checks):
        log(Stage.VERIFY, "start", "[검증] 점검 명령 실행", detail=check.label)
        pause(0.4)
        if outcome == SeatStatus.VERIFY_FAILED and index == 0:
            wrong = WRONG_OUTPUTS.get(
                check.label,
                f"'{check.command.split()[0]}'은(는) 내부 또는 외부 명령, 실행할 수 있는 프로그램, 또는 배치 파일이 아닙니다.",
            )
            versions[check.label] = wrong
            message = f"{evaluate.check_failure_text(check.label, check.expect, wrong, 0)} {MOCK}"
            log(Stage.VERIFY, "failed", "[검증] 점검 명령 실행", False, message)
            reporter.finish(n, SeatStatus.VERIFY_FAILED, versions=versions, message=message)
            return
        output = FAKE_OUTPUTS.get(check.label, f"{check.label} ok")
        versions[check.label] = evaluate.version_text(output)
        log(Stage.VERIFY, "ok", "[검증] 점검 명령 실행", detail=f"{check.label}: {output}")

    example_output = ""
    if plan.needs_seat_check:
        log(Stage.VERIFY, "start", "[검증] 버전·예제 확인")
        pause(0.6)
        fake = fake_seat_check(plan)
        versions.update(evaluate.collect_versions({}, fake))
        example_output = f"{evaluate.example_summary(fake)} {MOCK}"
        log(Stage.VERIFY, "ok", "[검증] 버전·예제 확인", detail=example_output)

    if already:
        status, message = SeatStatus.ALREADY_INSTALLED, f"이미 설치되어 있어 바꾼 것 없이 검증만 했어요. {MOCK}"
    else:
        status, message = SeatStatus.SUCCESS, f"설치와 검증을 마쳤어요. {MOCK}"
    reporter.finish(n, status, versions=versions, example_output=example_output, message=message)
