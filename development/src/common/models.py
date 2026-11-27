"""모듈끼리 주고받는 데이터 형식 (구상도의 interfaces 역할).

흐름: ai(ParseResult) → app(작업 생성) → installer(InstallPlan 실행) → verification(판정) → storage(저장)
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SeatMode(str, Enum):
    REAL = "real"  # 실제 Windows VM (WinRM)
    MOCK = "mock"  # 흐름 확인용 모의 좌석


class SeatStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ALREADY_INSTALLED = "already_installed"
    CONNECT_FAILED = "connect_failed"
    INSTALL_FAILED = "install_failed"
    VERIFY_FAILED = "verify_failed"
    ERROR = "error"  # 서버 쪽 문제 (Ansible 없음, 계정 미설정 등)


FINAL_STATUSES = {
    SeatStatus.SUCCESS,
    SeatStatus.ALREADY_INSTALLED,
    SeatStatus.CONNECT_FAILED,
    SeatStatus.INSTALL_FAILED,
    SeatStatus.VERIFY_FAILED,
    SeatStatus.ERROR,
}


class Stage(str, Enum):
    CONNECT = "connect"
    INSTALL = "install"
    VERIFY = "verify"
    DONE = "done"


class Seat(BaseModel):
    number: int  # 좌석 번호 (YAML에서 no는 false로 읽혀서 number를 씁니다)
    name: str
    mode: SeatMode = SeatMode.MOCK
    host: str | None = None
    # 모의 좌석이 어떤 결과를 낼지 (실패 화면 확인용)
    mock_result: SeatStatus = SeatStatus.SUCCESS


class ChocoPackage(BaseModel):
    name: str
    version: str | None = None


class Check(BaseModel):
    """좌석에서 실행할 점검 명령. 출력에 expect가 들어 있어야 통과."""

    label: str
    command: str
    expect: str = ""


class Profile(BaseModel):
    """설치 프로필. AI는 이 id 중에서만 고르고 설치 명령을 새로 만들지 않습니다."""

    id: str
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)  # 이 프로필이 포함하는 다른 프로필
    choco: list[ChocoPackage] = Field(default_factory=list)
    pip: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)  # verification/seat_check.py의 예제 이름
    imports: list[str] = Field(default_factory=list)  # import 되는지 확인할 파이썬 패키지


class ParseResult(BaseModel):
    """ai 모듈의 출력: 자연어 요청 해석 결과."""

    seats: list[int] = Field(default_factory=list)
    profiles: list[str] = Field(default_factory=list)
    unsupported: list[str] = Field(default_factory=list)  # 목록에 없는 도구
    reason: str = ""
    parser: str = "rules"  # rules / ai
    provider: str | None = None
    warnings: list[str] = Field(default_factory=list)


class InstallPlan(BaseModel):
    """선택한 프로필들을 합친 실행 계획 (installer 입력)."""

    profiles: list[str]
    choco: list[ChocoPackage] = Field(default_factory=list)
    pip: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)

    @property
    def needs_seat_check(self) -> bool:
        return bool(self.examples or self.imports)


class SeatEvent(BaseModel):
    """좌석별 실행 기록 한 줄 (storage의 job_events). 2순위 장애 분석의 원자료."""

    seat_no: int
    stage: Stage | None = None
    kind: str  # start / ok / changed / failed / unreachable / skipped / info
    task: str = ""
    ok: bool = True
    detail: str = ""
