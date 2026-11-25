"""SQLite:存每次生长评估的月龄、测量值、分档与明细。"""

from __future__ import annotations

import json
import os
import sqlite3
import threading

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "yuer.db")


class Database:
    def __init__(self, path=None):
        self.path = path or os.environ.get("YUER_DB") or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    months INTEGER, sex TEXT, weight REAL, height REAL,
                    alerts INTEGER, detail TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
                """
            )
            self.conn.commit()

    def save(self, r):
        w = next((g["value"] for g in r["growth"] if g["metric"] == "体重"), None)
        h = next((g["value"] for g in r["growth"] if g["metric"] == "身高/身长"), None)
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO checks (months, sex, weight, height, alerts, detail) VALUES (?,?,?,?,?,?)",
                (r["months"], r["sex"], w, h, len(r["alerts"]), json.dumps(r, ensure_ascii=False)),
            )
            self.conn.commit()
            return int(cur.lastrowid)

    def latest(self, limit=10):
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, months, sex, weight, height, alerts, created_at "
                "FROM checks ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
