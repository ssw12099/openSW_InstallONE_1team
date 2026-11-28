"""웹 요청의 수명주기. 요청 원문 대신 해시와 검증된 계획만 SQL에 보관."""
import hashlib
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from .core import Store, interpret, validate_plan, execute_job
from .executors import MockExecutor, SSHExecutor, load_targets
from .haigpt import GatewayError
from .settings import mock_seats

SUCCESS = {"mock_verified", "mock_reused", "verified"}
FAILURE = {"connection_failed", "install_failed", "verification_failed", "internal_failed"}
REVIEW = {"outcome_unknown", "interrupted"}


def summarize(results, plan=None):
    total = len(plan["seats"]) if plan else len(results)
    statuses = [r["status"] for r in results]
    completed = sum(status in SUCCESS | FAILURE | REVIEW for status in statuses)
    return {"total": total, "completed": completed,
            "percent": round(100 * completed / total) if total else 0,
            "success": sum(status in SUCCESS for status in statuses),
            "failed": sum(status in FAILURE for status in statuses),
            "needs_review": sum(status in REVIEW for status in statuses)}


class Conflict(ValueError):
    pass


class WebJobs:
    """HTTP와 백그라운드 작업 연결. 외부 호출 중 DB 잠금을 잡지 않는다."""
    def __init__(self, path, mode="mock", interpreter=None, executor=None, delay=0.7, seats=None,
                 executor_mode="mock", targets=None):
        self.store = Store(path)
        self.mode = mode
        if executor_mode not in ("mock", "real"):
            raise ValueError("지원하지 않는 설치 모드")
        self.executor_mode = executor_mode
        self.targets = (load_targets() if targets is None else targets) if executor_mode == "real" else {}
        if executor_mode == "real" and not 1 <= len(self.targets) <= 4:
            raise ValueError("실제 설치 모드는 승인 VM을 1~4대 등록하세요.")
        self.target_hosts = {seat: target["host"] for seat, target in self.targets.items()}
        self.target_digest = (hashlib.sha256(json.dumps(self.targets, sort_keys=True).encode()).hexdigest()
                              if executor_mode == "real" else "")
        self.seats = (self.targets if executor_mode == "real" else
                      mock_seats() if seats is None else seats)
        allowed = {"1", "2", "3", "4"} if executor_mode == "real" else {"1", "2"}
        if not self.seats or not set(self.seats) <= allowed:
            raise ValueError("등록 좌석 설정이 올바르지 않습니다.")
        if executor_mode == "real" and len({target["host"] for target in self.targets.values()}) != len(self.targets):
            raise ValueError("같은 VM 주소를 두 좌석에 등록할 수 없습니다.")
        self.interpreter = interpreter or interpret
        self.executor = executor or (SSHExecutor(self.targets) if executor_mode == "real" else MockExecutor(self.seats))
        self.delay = delay
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="installone")
        self.lock = threading.Lock()
        self.connection = "모의 응답 · HaiGPT 미연결" if mode == "mock" else "HaiGPT 미연결 — 이 서버에서 아직 응답 미확인"
        with self.store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS web_requests (
                id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, digest TEXT NOT NULL,
                created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, interpreter TEXT NOT NULL,
                state TEXT NOT NULL, plan TEXT, job_id TEXT, message TEXT NOT NULL DEFAULT '')""")
            columns = {row[1] for row in db.execute("PRAGMA table_info(web_requests)")}
            if "executor" not in columns:
                db.execute("ALTER TABLE web_requests ADD COLUMN executor TEXT NOT NULL DEFAULT 'mock'")
            if "target_hosts" not in columns:
                db.execute("ALTER TABLE web_requests ADD COLUMN target_hosts TEXT NOT NULL DEFAULT '{}'")
            if "target_digest" not in columns:
                db.execute("ALTER TABLE web_requests ADD COLUMN target_digest TEXT NOT NULL DEFAULT ''")
            db.execute("""UPDATE results SET status='interrupted', detail=CASE
                WHEN job_id IN (SELECT id FROM jobs WHERE executor='real') THEN '[실제 VM] 서버 중단. VM 상태를 확인하세요.'
                ELSE '[모의] 서버 중단. 새 요청으로 다시 확인하세요.' END
                WHERE status IN ('pending','running') AND job_id IN
                (SELECT job_id FROM web_requests WHERE state IN ('queued','running'))""")
            db.execute("""UPDATE jobs SET state='interrupted' WHERE id IN
                (SELECT job_id FROM web_requests WHERE state IN ('queued','running'))""")
            db.execute("""UPDATE web_requests SET state='interrupted', message='서버 중단으로 완료 여부를 확인할 수 없습니다. 새 요청을 작성하세요.'
                WHERE state IN ('interpreting','queued','running')""")

    def close(self):
        self.pool.shutdown(wait=True)

    def submit(self, text, request_key):
        """재전송 식별자를 저장하고 해석 예약 후 요청 ID를 반환한다."""
        if not isinstance(text, str) or not text.strip() or not 1 <= len(text) <= 1000:
            raise ValueError("요청은 1~1000자로 입력하세요.")
        if not isinstance(request_key, str) or len(request_key) != 36:
            raise ValueError("요청 식별자가 올바르지 않습니다.")
        try:
            uuid.UUID(request_key)
        except ValueError:
            raise ValueError("요청 식별자가 올바르지 않습니다.") from None
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.lock, self.store.connect() as db:
            old = db.execute("SELECT * FROM web_requests WHERE request_key=?", (request_key,)).fetchone()
            if old:
                if (old["digest"] != digest or old["interpreter"] != self.mode
                        or old["executor"] != self.executor_mode or old["target_digest"] != self.target_digest):
                    raise Conflict("같은 요청 식별자로 다른 내용을 보낼 수 없습니다.")
                return old["id"]
            active = db.execute("SELECT COUNT(*) FROM web_requests WHERE state IN ('interpreting','queued','running')").fetchone()[0]
            if active >= 8:
                raise Conflict("진행 중인 요청이 많습니다. 잠시 후 다시 시도하세요.")
            task = uuid.uuid4().hex
            db.execute("""INSERT INTO web_requests
                (id,request_key,digest,interpreter,executor,target_hosts,target_digest,state)
                VALUES(?,?,?,?,?,?,?,?)""",
                       (task, request_key, digest, self.mode, self.executor_mode,
                        json.dumps(self.target_hosts), self.target_digest, "interpreting"))
        self.pool.submit(self._interpret, task, text)
        return task

    def _interpret(self, task, text):
        try:
            plan = self.interpreter(text, self.seats, self.mode)
            plan = validate_plan({"seats": list(plan.seats), "profile": plan.profile}, self.seats)
            with self.store.connect() as db:
                db.execute("UPDATE web_requests SET state='ready',plan=? WHERE id=? AND state='interpreting'",
                           (json.dumps({"seats": list(plan.seats), "profile": plan.profile}), task))
            with self.lock:
                self.connection = "HaiGPT 실제 응답·해석 검증 완료" if self.mode == "haigpt" else "모의 응답 · HaiGPT 미연결"
        except Exception as exc:
            message = str(exc) if isinstance(exc, GatewayError) or (type(exc) is ValueError and self.mode == "mock") else "해석 결과 검증 실패. 실행하지 않았습니다."
            with self.store.connect() as db:
                db.execute("UPDATE web_requests SET state='rejected',message=? WHERE id=?", (message, task))
            with self.lock:
                if self.mode == "haigpt":
                    self.connection = "HaiGPT 최근 해석 미확인 — 요청 오류 또는 보완 필요"

    def execute(self, task):
        """계획 재검증과 작업 생성을 한 트랜잭션으로 묶는다."""
        # 브라우저의 계획은 받지 않는다. DB의 미리보기 계획을 트랜잭션에서 재검증.
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM web_requests WHERE id=?", (task,)).fetchone()
            if not row:
                raise LookupError()
            if row["state"] in ("queued", "running", "finished"):
                return row["job_id"], False
            if row["state"] != "ready":
                raise Conflict("실행 가능한 확인 상태가 아닙니다.")
            if row["executor"] != self.executor_mode:
                raise Conflict("요청의 설치 모드가 현재 서버와 다릅니다. 새 요청을 작성하세요.")
            if row["target_digest"] != self.target_digest:
                raise Conflict("승인 VM 설정이 요청 확인 이후 변경되었습니다. 새 요청을 작성하세요.")
            plan = validate_plan(json.loads(row["plan"]), self.seats)
            occupied = [r[0] for r in db.execute("""SELECT DISTINCT r.seat FROM results r
                JOIN web_requests w ON w.job_id=r.job_id
                WHERE w.state IN ('queued','running') AND r.seat IN (%s)
                ORDER BY r.seat""" % ",".join("?" for _ in plan.seats), plan.seats)]
            if occupied:
                raise Conflict("실행 중인 좌석: " + ", ".join(s + "번" for s in occupied) + ". 종료 후 다시 확인하여 실행하세요.")
            job = uuid.uuid4().hex
            db.execute("INSERT INTO jobs(id,interpreter,executor,profile,state) VALUES(?,?,?,?,?)",
                       (job, row["interpreter"], self.executor_mode, plan.profile, "confirmed"))
            db.executemany("INSERT INTO results(job_id,seat,status) VALUES(?,?,?)", [(job, s, "pending") for s in plan.seats])
            db.execute("UPDATE web_requests SET state='queued',job_id=? WHERE id=?", (job, task))
        self.pool.submit(self._execute, task, job)
        return job, True

    def _execute(self, task, job):
        with self.store.connect() as db:
            db.execute("UPDATE web_requests SET state='running' WHERE id=?", (task,))
        parent = self
        class DelayedMock:
            def run(self, seat):
                time.sleep(parent.delay)
                return parent.executor.run(seat)
        try:
            execute_job(self.store, job, self.executor if self.executor_mode == "real" else DelayedMock(),
                        parallel=self.executor_mode == "real")
            with self.store.connect() as db:
                db.execute("UPDATE web_requests SET state='finished' WHERE id=?", (task,))
        except Exception:
            with self.store.connect() as db:
                detail = "[실제 VM] 작업 중단. VM 상태를 확인하세요." if self.executor_mode == "real" else "[모의] 작업 중단. 완료 여부를 확인하세요."
                db.execute("UPDATE results SET status='interrupted',detail=? WHERE job_id=? AND status IN ('pending','running')", (detail, job))
                db.execute("UPDATE jobs SET state='interrupted' WHERE id=?", (job,))
                db.execute("UPDATE web_requests SET state='interrupted',message='작업 처리 중 오류. 결과를 확인하세요.' WHERE id=?", (task,))

    def get(self, task):
        with self.store.connect() as db:
            row = db.execute("""SELECT id,created,interpreter,executor,target_hosts,state,plan,job_id,message
                FROM web_requests WHERE id=?""", (task,)).fetchone()
            if not row:
                raise LookupError()
            result = dict(row)
            result["plan"] = json.loads(result["plan"]) if result["plan"] else None
            result["results"] = [dict(r) for r in db.execute("SELECT seat,status,detail FROM results WHERE job_id=? ORDER BY seat", (row["job_id"],))]
            result["summary"] = summarize(result["results"], result["plan"])
            saved_hosts = json.loads(result.pop("target_hosts"))
            result["targets"] = {seat: saved_hosts[seat] for seat in result["plan"]["seats"]} if result["plan"] and result["executor"] == "real" else {}
            return result

    def history(self):
        with self.store.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM web_requests ORDER BY created DESC,rowid DESC LIMIT 50")]
        return [self.get(task) for task in ids]

    def legacy_history(self):
        with self.store.connect() as db:
            rows = [dict(row) for row in db.execute("""SELECT j.*,r.seat,r.status,r.detail
                FROM jobs j JOIN results r ON j.id=r.job_id
                WHERE NOT EXISTS (SELECT 1 FROM web_requests w WHERE w.job_id=j.id)
                ORDER BY j.created DESC,j.rowid DESC,r.seat LIMIT 100""")]
            groups = {}
            for row in rows:
                groups.setdefault(row["id"], []).append(row)
            for row in rows:
                row["summary"] = summarize(groups[row["id"]])
            return rows
