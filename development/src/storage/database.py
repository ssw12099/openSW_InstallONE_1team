import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src.common.config import ROOT
DATA = Path(os.getenv('DEPLOY_DATA_DIR', str(ROOT / 'runtime'))).resolve()
FILES = DATA / 'files'

@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'deploy.sqlite3', timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    FILES.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.execute('PRAGMA journal_mode = WAL')
        c.executescript((ROOT / 'db' / 'schema.sql').read_text(encoding='utf-8'))
        if 'operation' not in {r['name'] for r in c.execute('PRAGMA table_info(jobs)')}:
            c.execute("ALTER TABLE jobs ADD COLUMN operation TEXT NOT NULL DEFAULT 'download'")
