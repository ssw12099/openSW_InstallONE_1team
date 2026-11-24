"""입력 경계와 SQL 작업 이력. 외부 프로그램을 실행하지 않는 영역."""
import re
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

PROFILE = "python-lab"
VERSION = "3.14.7"


@dataclass(frozen=True)
class Plan:
    seats: tuple[str, ...]
    profile: str


def validate_plan(value, seats):
    if type(value) is not dict or set(value) != {"seats", "profile"}:
        raise ValueError("해석 결과는 seats, profile 두 필드만 가져야 합니다.")
    selected = value["seats"]
    if (type(selected) is not list or not selected or len(selected) > len(seats)
            or any(type(s) is not str or s not in seats for s in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("등록된 좌석을 중복 없이 지정하세요.")
    if value["profile"] != PROFILE:
        raise ValueError("Python 실습환경만 지원합니다.")
    return Plan(tuple(selected), PROFILE)


def interpret(request, seats, mode):
    if mode == "haigpt":
        from .haigpt import Gateway
        return Gateway().interpret(request, seats)
    if mode != "mock":
        raise ValueError("지원하지 않는 해석 모드입니다.")
    # 엄격한 전체 문장 일치: 범위·추가 프로그램·명령을 조용히 무시하지 않는다.
    match = re.fullmatch(
        r"\s*(\d+번(?:\s*,\s*\d+번)*)\s*PC에\s*(?:Python|파이썬)\s*실습환경\s*설치해\s*줘[.!]?\s*",
        request, re.IGNORECASE)
    if not match:
        raise ValueError("모의 해석 지원 형식: '1번 PC에 Python 실습환경 설치해 줘' 또는 '1번, 2번 PC에 Python 실습환경 설치해 줘'. 모호하거나 지원 외 요청은 실행하지 않습니다.")
    return validate_plan({"seats": re.findall(r"\d+", match[1]), "profile": PROFILE}, seats)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP,
                    interpreter TEXT NOT NULL, executor TEXT NOT NULL,
                    profile TEXT NOT NULL, state TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS results (
                    job_id TEXT NOT NULL REFERENCES jobs(id), seat TEXT NOT NULL,
                    status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY(job_id, seat));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.row_factory = sqlite3.Row
            with db:
                yield db
        finally:
            db.close()

    def create(self, plan, interpreter, executor):
        job = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO jobs(id,interpreter,executor,profile,state) VALUES(?,?,?,?,?)",
                       (job, interpreter, executor, plan.profile, "confirmed"))
            db.executemany("INSERT INTO results(job_id,seat,status) VALUES(?,?,?)",
                           [(job, seat, "pending") for seat in plan.seats])
        return job

    def claim(self, job):
        with self.connect() as db:
            changed = db.execute("UPDATE jobs SET state='running' WHERE id=? AND state='confirmed'", (job,)).rowcount
            if changed != 1:
                raise ValueError("이미 실행된 작업입니다. 재요청은 새 확인 절차를 거치세요.")
            return [row[0] for row in db.execute("SELECT seat FROM results WHERE job_id=? ORDER BY seat", (job,))]

    def result(self, job, seat, status, detail):
        with self.connect() as db:
            db.execute("UPDATE results SET status=?,detail=? WHERE job_id=? AND seat=?",
                       (status, detail, job, seat))

    def finish(self, job):
        with self.connect() as db:
            db.execute("UPDATE jobs SET state='finished' WHERE id=?", (job,))

    def history(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT j.*,r.seat,r.status,r.detail
                FROM jobs j JOIN results r ON j.id=r.job_id ORDER BY j.created DESC,j.rowid DESC,r.seat""")]


def execute_job(store, job, executor):
    for seat in store.claim(job):
        store.result(job, seat, "running", "")
        try:
            status, detail = executor.run(seat)
        except Exception:
            # 원격 stdout, 예외 메시지에 들어 있을 수 있는 접속정보는 저장하지 않는다.
            status, detail = "internal_failed", "내부 처리 오류. 설정과 테스트를 확인하세요."
        store.result(job, seat, status, detail)
    store.finish(job)
