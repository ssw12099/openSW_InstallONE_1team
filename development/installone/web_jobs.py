"""웹 요청의 수명주기. 요청 원문 대신 해시와 검증된 계획만 SQL에 보관."""
import hashlib
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from .core import Store, interpret, validate_plan, execute_job
from .executors import MockExecutor
from .haigpt import GatewayError

SEATS = {"1": {}, "2": {}}


class Conflict(ValueError):
    pass


class WebJobs:
    """HTTP와 백그라운드 작업 연결. 외부 호출 중 DB 잠금을 잡지 않는다."""
    def __init__(self, path, mode="mock", interpreter=None, executor=None, delay=0.7):
        self.store = Store(path)
        self.mode = mode
        self.interpreter = interpreter or interpret
        self.executor = executor or MockExecutor()
        self.delay = delay
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="installone")
        self.lock = threading.Lock()
        self.connection = "모의 응답 · HaiGPT 미연결" if mode == "mock" else "HaiGPT 미연결 — 이 서버에서 아직 응답 미확인"
        with self.store.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS web_requests (
                id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL, digest TEXT NOT NULL,
                created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, interpreter TEXT NOT NULL,
                state TEXT NOT NULL, plan TEXT, job_id TEXT, message TEXT NOT NULL DEFAULT '')""")
            db.execute("""UPDATE results SET status='interrupted', detail='[모의] 서버 중단. 새 요청으로 다시 확인하세요.'
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
                if old["digest"] != digest or old["interpreter"] != self.mode:
                    raise Conflict("같은 요청 식별자로 다른 내용을 보낼 수 없습니다.")
                return old["id"]
            active = db.execute("SELECT COUNT(*) FROM web_requests WHERE state IN ('interpreting','queued','running')").fetchone()[0]
            if active >= 8:
                raise Conflict("진행 중인 요청이 많습니다. 잠시 후 다시 시도하세요.")
            task = uuid.uuid4().hex
            db.execute("INSERT INTO web_requests(id,request_key,digest,interpreter,state) VALUES(?,?,?,?,?)",
                       (task, request_key, digest, self.mode, "interpreting"))
        self.pool.submit(self._interpret, task, text)
        return task

    def _interpret(self, task, text):
        try:
            plan = self.interpreter(text, SEATS, self.mode)
            plan = validate_plan({"seats": list(plan.seats), "profile": plan.profile}, SEATS)
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
            plan = validate_plan(json.loads(row["plan"]), SEATS)
            job = uuid.uuid4().hex
            db.execute("INSERT INTO jobs(id,interpreter,executor,profile,state) VALUES(?,?,?,?,?)",
                       (job, row["interpreter"], "mock", plan.profile, "confirmed"))
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
                time.sleep(parent.delay)  # 모의 진행 상태 관찰용 지연. 실제 설치 아님.
                return parent.executor.run(seat)
        try:
            execute_job(self.store, job, DelayedMock())
            with self.store.connect() as db:
                db.execute("UPDATE web_requests SET state='finished' WHERE id=?", (task,))
        except Exception:
            with self.store.connect() as db:
                db.execute("UPDATE web_requests SET state='interrupted',message='작업 처리 중 오류. 결과를 확인하세요.' WHERE id=?", (task,))

    def get(self, task):
        with self.store.connect() as db:
            row = db.execute("SELECT id,created,interpreter,state,plan,job_id,message FROM web_requests WHERE id=?", (task,)).fetchone()
            if not row:
                raise LookupError()
            result = dict(row)
            result["plan"] = json.loads(result["plan"]) if result["plan"] else None
            result["results"] = [dict(r) for r in db.execute("SELECT seat,status,detail FROM results WHERE job_id=? ORDER BY seat", (row["job_id"],))]
            result["executor"] = "mock"
            return result

    def history(self):
        with self.store.connect() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM web_requests ORDER BY created DESC,rowid DESC LIMIT 50")]
        return [self.get(task) for task in ids]

    def legacy_history(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute("""SELECT j.*,r.seat,r.status,r.detail
                FROM jobs j JOIN results r ON j.id=r.job_id
                WHERE NOT EXISTS (SELECT 1 FROM web_requests w WHERE w.job_id=j.id)
                ORDER BY j.created DESC,j.rowid DESC,r.seat LIMIT 100""")]
