import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "installone.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()

    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS pcs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                ip_address TEXT,
                os TEXT NOT NULL DEFAULT 'Windows',
                status TEXT NOT NULL DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS installation_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request TEXT NOT NULL,
                profile TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                mode TEXT NOT NULL DEFAULT 'mock',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS installation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                pc_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                installed_version TEXT,
                verification TEXT,
                log TEXT,
                FOREIGN KEY (job_id)
                    REFERENCES installation_jobs(id),
                FOREIGN KEY (pc_id)
                    REFERENCES pcs(id)
            );
        """)

        for i in range(1, 9):
            conn.execute("""
                INSERT OR IGNORE INTO pcs
                    (id, name, os, status)
                VALUES (?, ?, ?, ?)
            """, (i, f"PC-{i:02d}", "Windows", "unknown"))

        conn.commit()

    finally:
        conn.close()


def get_pcs():
    conn = get_connection()

    try:
        rows = conn.execute(
            "SELECT * FROM pcs ORDER BY id"
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()

def create_job(request, profile, mode):
    conn = get_connection()

    try:
        cursor = conn.execute("""
            INSERT INTO installation_jobs
                (request, profile, status, mode)
            VALUES (?, ?, ?, ?)
        """, (request, profile, "running", mode))

        job_id = cursor.lastrowid
        conn.commit()

        return job_id

    finally:
        conn.close()


def save_result(
    job_id,
    pc_id,
    status,
    installed_version,
    verification,
    log
):
    conn = get_connection()

    try:
        conn.execute("""
            INSERT INTO installation_results
                (
                    job_id,
                    pc_id,
                    status,
                    installed_version,
                    verification,
                    log
                )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            pc_id,
            status,
            installed_version,
            verification,
            log
        ))

        conn.commit()

    finally:
        conn.close()


def update_job_status(job_id, status):
    conn = get_connection()

    try:
        conn.execute("""
            UPDATE installation_jobs
            SET status = ?
            WHERE id = ?
        """, (status, job_id))

        conn.commit()

    finally:
        conn.close()


def get_jobs():
    conn = get_connection()

    try:
        rows = conn.execute("""
            SELECT *
            FROM installation_jobs
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


def get_job_detail(job_id):
    conn = get_connection()

    try:
        job = conn.execute("""
            SELECT *
            FROM installation_jobs
            WHERE id = ?
        """, (job_id,)).fetchone()

        if job is None:
            return None

        results = conn.execute("""
            SELECT
                installation_results.*,
                pcs.name AS pc_name
            FROM installation_results
            JOIN pcs
                ON installation_results.pc_id = pcs.id
            WHERE job_id = ?
            ORDER BY pc_id
        """, (job_id,)).fetchall()

        return {
            **dict(job),
            "results": [dict(row) for row in results]
        }

    finally:
        conn.close()

def update_pc_info(pc_id, ip_address, os_name, status):
    conn = get_connection()

    try:
        conn.execute("""
            UPDATE pcs
            SET ip_address = ?,
                os = ?,
                status = ?
            WHERE id = ?
        """, (
            ip_address,
            os_name,
            status,
            pc_id
        ))

        conn.commit()

    finally:
        conn.close()


def get_pc(pc_id):
    conn = get_connection()

    try:
        row = conn.execute("""
            SELECT *
            FROM pcs
            WHERE id = ?
        """, (pc_id,)).fetchone()

        return dict(row) if row else None

    finally:
        conn.close()