"""SQLite 저장·조회. 테이블 구조는 db/schema.sql에 있습니다."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterable, Iterator

from ..common.config import DB_SCHEMA_FILE, get_settings
from ..common.models import ParseResult, Seat, SeatEvent, SeatStatus, Stage

_write_lock = threading.Lock()  # 여러 좌석 스레드가 동시에 쓸 때 순서를 맞춤

SEAT_FIELDS = {"status", "stage", "versions", "example_output", "message", "started_at", "finished_at"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def _db(write: bool = False) -> Iterator[sqlite3.Connection]:
    lock = _write_lock if write else None
    if lock:
        lock.acquire()
    conn = _connect()
    try:
        yield conn
        if write:
            conn.commit()
    finally:
        conn.close()
        if lock:
            lock.release()


def init_db() -> None:
    with _db(write=True) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(DB_SCHEMA_FILE.read_text(encoding="utf-8"))


# ── 요청 ─────────────────────────────────────────────
def create_request(text: str, result: ParseResult) -> int:
    with _db(write=True) as conn:
        cur = conn.execute(
            "INSERT INTO requests (text, parsed_json, parser, created_at) VALUES (?, ?, ?, ?)",
            (text, result.model_dump_json(), result.parser, now()),
        )
        return int(cur.lastrowid)


def request_exists(request_id: int) -> bool:
    with _db() as conn:
        return conn.execute("SELECT 1 FROM requests WHERE id = ?", (request_id,)).fetchone() is not None


# ── 작업 ─────────────────────────────────────────────
def create_job(request_id: int | None, seats: list[Seat], profiles: list[str]) -> int:
    created = now()
    with _db(write=True) as conn:
        cur = conn.execute(
            "INSERT INTO jobs (request_id, profiles, seats, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
            (request_id, json.dumps(profiles), json.dumps([s.number for s in seats]), created),
        )
        job_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO seat_results (job_id, seat_no, seat_name, mode, status) VALUES (?, ?, ?, ?, ?)",
            [(job_id, s.number, s.name, s.mode.value, SeatStatus.PENDING.value) for s in seats],
        )
        return job_id


def set_job_status(job_id: int, status: str) -> None:
    column = {"running": "started_at", "done": "finished_at", "error": "finished_at"}.get(status)
    with _db(write=True) as conn:
        if column:
            conn.execute(f"UPDATE jobs SET status = ?, {column} = ? WHERE id = ?", (status, now(), job_id))
        else:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))


def close_interrupted(message: str, exclude: Iterable[int] = ()) -> list[int]:
    """'대기·진행 중'으로 남은 작업(서버가 도중에 꺼진 경우)과 그 좌석들을 오류로 마감합니다."""
    skip = set(exclude)
    with _db(write=True) as conn:
        rows = conn.execute("SELECT id FROM jobs WHERE status IN ('queued', 'running')").fetchall()
        ids = [row["id"] for row in rows if row["id"] not in skip]
        if not ids:
            return []
        stamp, marks = now(), ", ".join("?" * len(ids))
        conn.execute(
            f"UPDATE seat_results SET status = ?, stage = ?, message = ?, finished_at = ?"
            f" WHERE job_id IN ({marks}) AND status IN (?, ?)",
            (SeatStatus.ERROR.value, Stage.DONE.value, message, stamp, *ids,
             SeatStatus.PENDING.value, SeatStatus.RUNNING.value),
        )
        conn.execute(f"UPDATE jobs SET status = 'error', finished_at = ? WHERE id IN ({marks})", (stamp, *ids))
    return ids


def update_seat(job_id: int, seat_no: int, **fields: Any) -> None:
    unknown = set(fields) - SEAT_FIELDS
    if unknown:
        raise ValueError(f"알 수 없는 좌석 필드: {unknown}")
    if "versions" in fields and fields["versions"] is not None:
        fields["versions"] = json.dumps(fields["versions"], ensure_ascii=False)
    for key, value in list(fields.items()):
        if hasattr(value, "value"):  # Enum → 문자열
            fields[key] = value.value
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with _db(write=True) as conn:
        conn.execute(
            f"UPDATE seat_results SET {assignments} WHERE job_id = ? AND seat_no = ?",
            (*fields.values(), job_id, seat_no),
        )


def add_event(job_id: int, event: SeatEvent) -> None:
    with _db(write=True) as conn:
        conn.execute(
            "INSERT INTO job_events (job_id, seat_no, stage, kind, task, ok, detail, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                event.seat_no,
                event.stage.value if event.stage else None,
                event.kind,
                event.task,
                1 if event.ok else 0,
                event.detail[:4000],
                now(),
            ),
        )


# ── 조회 ─────────────────────────────────────────────
def _seat_row(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["versions"] = json.loads(item["versions"]) if item.get("versions") else {}
    return item


def get_job(job_id: int) -> dict[str, Any] | None:
    with _db() as conn:
        job = conn.execute(
            "SELECT j.*, r.text AS request_text, r.parser AS parser FROM jobs j"
            " LEFT JOIN requests r ON r.id = j.request_id WHERE j.id = ?",
            (job_id,),
        ).fetchone()
        if job is None:
            return None
        seats = conn.execute(
            "SELECT * FROM seat_results WHERE job_id = ? ORDER BY seat_no", (job_id,)
        ).fetchall()
    result = dict(job)
    result["profiles"] = json.loads(result["profiles"])
    result["seats"] = [_seat_row(s) for s in seats]
    counts: dict[str, int] = {}
    for seat in result["seats"]:
        counts[seat["status"]] = counts.get(seat["status"], 0) + 1
    result["counts"] = counts
    return result


def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT j.id, j.status, j.created_at, j.finished_at, j.profiles, r.text AS request_text"
            " FROM jobs j LEFT JOIN requests r ON r.id = j.request_id ORDER BY j.id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        counts = conn.execute(
            "SELECT job_id, status, COUNT(*) AS n FROM seat_results"
            " WHERE job_id IN (SELECT id FROM jobs ORDER BY id DESC LIMIT ?) GROUP BY job_id, status",
            (limit,),
        ).fetchall()
    by_job: dict[int, dict[str, int]] = {}
    for row in counts:
        by_job.setdefault(row["job_id"], {})[row["status"]] = row["n"]
    jobs = []
    for row in rows:
        item = dict(row)
        item["profiles"] = json.loads(item["profiles"])
        item["counts"] = by_job.get(item["id"], {})
        jobs.append(item)
    return jobs


def get_events(job_id: int, seat_no: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
    query = "SELECT * FROM job_events WHERE job_id = ?"
    params: list[Any] = [job_id]
    if seat_no is not None:
        query += " AND seat_no = ?"
        params.append(seat_no)
    query += " ORDER BY id LIMIT ?"
    params.append(limit)
    with _db() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]
