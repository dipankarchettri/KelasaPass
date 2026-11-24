"""SQLite storage for the MVP (DynamoDB in the AWS deployment)."""
import json
import os
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent.parent / "data" / "kelasapass.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (id TEXT PRIMARY KEY, doc TEXT);
CREATE TABLE IF NOT EXISTS employers (id TEXT PRIMARY KEY, doc TEXT);
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, doc TEXT);
CREATE TABLE IF NOT EXISTS credentials (id TEXT PRIMARY KEY, worker_id TEXT, employer_id TEXT, doc TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, doc TEXT);
"""


class Store:
    def __init__(self, path=DB_PATH):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        self.db.executescript(SCHEMA)

    def put(self, table: str, doc: dict):
        with self.lock:
            if table == "credentials":
                self.db.execute("REPLACE INTO credentials VALUES (?,?,?,?)",
                                (doc["id"], doc["worker_id"], doc["employer_id"], json.dumps(doc, ensure_ascii=False)))
            else:
                self.db.execute(f"REPLACE INTO {table} VALUES (?,?)", (doc["id"], json.dumps(doc, ensure_ascii=False)))
            self.db.commit()
        return doc

    def get(self, table: str, id_: str):
        row = self.db.execute(f"SELECT doc FROM {table} WHERE id=?", (id_,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self, table: str) -> list[dict]:
        return [json.loads(r[0]) for r in self.db.execute(f"SELECT doc FROM {table}")]

    def credentials_for(self, worker_id: str) -> list[dict]:
        rows = self.db.execute("SELECT doc FROM credentials WHERE worker_id=?", (worker_id,))
        return [json.loads(r[0]) for r in rows]

    def log(self, event: dict):
        with self.lock:
            self.db.execute("INSERT INTO events (doc) VALUES (?)", (json.dumps(event, ensure_ascii=False),))
            self.db.commit()

    def events(self, limit=50) -> list[dict]:
        rows = self.db.execute("SELECT doc FROM events ORDER BY id DESC LIMIT ?", (limit,))
        return [json.loads(r[0]) for r in rows]

    def reset(self):
        with self.lock:
            for t in ("workers", "employers", "jobs", "credentials", "events"):
                self.db.execute(f"DELETE FROM {t}")
            self.db.commit()
