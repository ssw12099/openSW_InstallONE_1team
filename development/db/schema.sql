-- InstallONE FR-01 프로토타입 DB 구조 (SQLite)
-- 실제 DB 파일은 runtime/installone.db 에 생기고 Git에 올리지 않습니다.

-- 조교가 입력한 자연어 요청과 해석 결과
CREATE TABLE IF NOT EXISTS requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT    NOT NULL,
    parsed_json TEXT    NOT NULL,          -- ParseResult (JSON)
    parser      TEXT    NOT NULL,          -- rules / ai
    created_at  TEXT    NOT NULL
);

-- 설치 작업 (확인 후 실행한 것)
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id  INTEGER REFERENCES requests(id),
    profiles    TEXT    NOT NULL,          -- 프로필 id 목록 (JSON)
    seats       TEXT    NOT NULL,          -- 좌석 번호 목록 (JSON)
    status      TEXT    NOT NULL,          -- queued / running / done / error
    created_at  TEXT    NOT NULL,
    started_at  TEXT,
    finished_at TEXT
);

-- 좌석별 결과 (화면의 결과 표)
CREATE TABLE IF NOT EXISTS seat_results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id         INTEGER NOT NULL REFERENCES jobs(id),
    seat_no        INTEGER NOT NULL,
    seat_name      TEXT,
    mode           TEXT    NOT NULL,       -- real / mock
    status         TEXT    NOT NULL,       -- pending / running / success / already_installed /
                                           -- connect_failed / install_failed / verify_failed / error
    stage          TEXT,                   -- connect / install / verify / done
    versions       TEXT,                   -- {"Python": "Python 3.12.10", ...} (JSON)
    example_output TEXT,
    message        TEXT,
    started_at     TEXT,
    finished_at    TEXT,
    UNIQUE (job_id, seat_no)
);

-- 좌석별 실행 기록 (2순위 업데이트 장애 분석에서 그대로 사용)
CREATE TABLE IF NOT EXISTS job_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id),
    seat_no    INTEGER,
    stage      TEXT,
    kind       TEXT    NOT NULL,           -- start / ok / changed / failed / unreachable / skipped / info
    task       TEXT,
    ok         INTEGER NOT NULL,
    detail     TEXT,
    created_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_seat_results_job ON seat_results (job_id);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events (job_id, seat_no);
