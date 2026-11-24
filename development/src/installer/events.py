"""Ansible(ansible-runner) 이벤트를 좌석별 상태로 바꿉니다.

작업 이름 머리말로 단계를 구분합니다: [연결] / [설치] / [검증]
- 접속 자체가 안 됨(unreachable) 또는 [연결] 작업 실패 → 연결 실패
- [설치] 작업 실패 → 설치 실패
- [검증] 작업 실패(버전·예제 불일치 포함) → 검증 실패
- 모두 통과했는데 설치 단계에서 바뀐 게 없음 → 이미 설치됨
"""
from __future__ import annotations

from typing import Any

from ..common.models import SeatEvent, SeatStatus, Stage
from ..verification import evaluate

STAGE_PREFIXES = {"[연결]": Stage.CONNECT, "[설치]": Stage.INSTALL, "[검증]": Stage.VERIFY}
FAIL_STATUS = {
    Stage.CONNECT: SeatStatus.CONNECT_FAILED,
    Stage.INSTALL: SeatStatus.INSTALL_FAILED,
    Stage.VERIFY: SeatStatus.VERIFY_FAILED,
}
FAIL_WORD = {Stage.CONNECT: "연결 실패", Stage.INSTALL: "설치 실패", Stage.VERIFY: "검증 실패"}
CHECK_TASK = "[검증] 점검 명령 실행"
SEAT_CHECK_TASK = "[검증] 버전·예제 확인"


def stage_of(task: str) -> Stage | None:
    for prefix, stage in STAGE_PREFIXES.items():
        if task.startswith(prefix):
            return stage
    return None


def short(text: Any, limit: int = 300) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def item_label(item_result: dict[str, Any]) -> str:
    item = item_result.get("item")
    if isinstance(item, dict):
        return str(item.get("label") or item.get("name") or item)
    return str(item)


def item_failed(item: dict[str, Any]) -> bool:
    """반복 작업의 항목 하나가 실패했는지.

    ansible-core 2.19부터는 이벤트 속 항목 결과에 'failed' 키가 빠지고,
    failed_when 결과나 'exception' 키로만 실패가 드러나서 셋 다 확인합니다.
    """
    if item.get("failed") is not None:
        return bool(item["failed"])
    if "failed_when_result" in item:
        return bool(item["failed_when_result"])
    return bool(item.get("unreachable")) or "exception" in item


def failure_message(res: dict[str, Any]) -> str:
    for item in res.get("results") or []:  # 반복 작업이면 실패한 항목을 찾음
        if isinstance(item, dict) and item_failed(item):
            detail = item.get("msg") or item.get("stderr") or item.get("stdout")
            return f"{item_label(item)}: {short(detail)}"
    return short(res.get("msg") or res.get("stderr") or res.get("stdout") or res.get("module_stderr"))


class SeatTracker:
    """좌석 하나의 이벤트를 모아 최종 상태를 정합니다."""

    def __init__(self, seat_no: int) -> None:
        self.seat_no = seat_no
        self.stage: Stage | None = None
        self.failed_status: SeatStatus | None = None
        self.message = ""
        self.seen = False
        self.install_ran = False
        self.install_changed = False
        self.check_outputs: dict[str, str] = {}
        self.check_problems: list[str] = []
        self.seat_check: dict[str, Any] | None = None

    def _event(self, stage: Stage | None, kind: str, task: str, ok: bool = True, detail: str = "") -> SeatEvent:
        return SeatEvent(seat_no=self.seat_no, stage=stage, kind=kind, task=task, ok=ok, detail=detail)

    def handle(self, event_type: str, data: dict[str, Any]) -> SeatEvent | None:
        task = str(data.get("task") or "")
        stage = stage_of(task)
        res = data.get("res") or {}
        self.seen = True

        if event_type == "runner_on_start":
            if self.failed_status is None and stage is not None:
                self.stage = stage
            return self._event(stage, "start", task)

        if event_type == "runner_on_ok":
            changed = bool(res.get("changed"))
            if stage == Stage.INSTALL:
                self.install_ran = True
                self.install_changed = self.install_changed or changed
            detail = self._collect(task, res) or short(res.get("msg") or res.get("stdout") or res.get("ping"))
            return self._event(stage, "changed" if changed else "ok", task, True, detail)

        if event_type == "runner_on_failed":
            if data.get("ignore_errors"):
                return self._event(stage, "ignored", task, True, failure_message(res))
            self._collect(task, res)
            self.failed_status = FAIL_STATUS.get(stage, SeatStatus.INSTALL_FAILED) if stage else SeatStatus.INSTALL_FAILED
            self.message = self._failure_text(task, stage, res)
            return self._event(stage, "failed", task, False, self.message)

        if event_type == "runner_on_unreachable":
            self.failed_status = SeatStatus.CONNECT_FAILED
            self.message = f"좌석에 접속할 수 없어요: {short(res.get('msg'))}"
            return self._event(Stage.CONNECT, "unreachable", task, False, self.message)

        if event_type == "runner_on_skipped":
            return self._event(stage, "skipped", task)

        return None

    def _collect(self, task: str, res: dict[str, Any]) -> str:
        """검증 작업 결과를 모으고, 기록에 남길 요약을 돌려줍니다."""
        if task == CHECK_TASK:
            lines = []
            for item in res.get("results") or []:
                if not isinstance(item, dict) or item.get("skipped"):
                    continue
                check = item.get("item") if isinstance(item.get("item"), dict) else {}
                label = item_label(item)
                output = str(item.get("stdout") or "")
                self.check_outputs[label] = output
                if item_failed(item):
                    self.check_problems.append(
                        evaluate.check_failure_text(label, check.get("expect", ""), output, item.get("rc"))
                    )
                lines.append(f"{label}: {evaluate.first_line(output) or '출력 없음'}")
            return " / ".join(lines)
        if task == SEAT_CHECK_TASK:
            parsed = evaluate.parse_seat_check(str(res.get("stdout") or ""))
            if parsed is not None:
                self.seat_check = parsed
                return evaluate.example_summary(parsed)
        return ""

    def _failure_text(self, task: str, stage: Stage | None, res: dict[str, Any]) -> str:
        if task == CHECK_TASK and self.check_problems:
            return "; ".join(self.check_problems)
        if task == SEAT_CHECK_TASK:
            return "; ".join(evaluate.seat_check_problems(self.seat_check))
        word = FAIL_WORD.get(stage, "실패") if stage else "실패"
        return f"{word} ({task}): {failure_message(res)}"

    def final(self) -> dict[str, Any]:
        versions = evaluate.collect_versions(self.check_outputs, self.seat_check)
        example = evaluate.example_summary(self.seat_check)
        if self.failed_status is not None:
            status, message = self.failed_status, self.message
        elif not self.seen:
            status, message = SeatStatus.ERROR, "이 좌석의 실행 기록이 없어요."
        elif self.install_ran and not self.install_changed:
            status, message = SeatStatus.ALREADY_INSTALLED, "이미 설치되어 있어 바꾼 것 없이 검증만 했어요."
        else:
            status, message = SeatStatus.SUCCESS, "설치와 검증을 마쳤어요."
        return {"status": status, "versions": versions, "example_output": example, "message": message}
