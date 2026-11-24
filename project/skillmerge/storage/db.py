from __future__ import annotations

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterable, List, Optional


class Database:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            from .migrate import migrate_database

            conn = self._connect()
            migrate_database(conn, self.path)
            self._initialized = True

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def connection(self) -> sqlite3.Connection:
        if not self._initialized:
            self.initialize()
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            finally:
                self._local.conn = None

    def close_all(self) -> None:
        self.close()

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> List[sqlite3.Row]:
        return list(self.connection().execute(sql, tuple(params)).fetchall())

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
        return self.connection().execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.query_one(sql, params)
        return row[0] if row is not None else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        return self.connection().execute(sql, tuple(params))

    @contextmanager
    def write_tx(self):
        conn = self.connection()
        last_error = None
        for delay in (0.05, 0.15, 0.45):
            try:
                conn.execute("BEGIN IMMEDIATE")
                break
            except sqlite3.OperationalError as exc:
                last_error = exc
                if "locked" not in str(exc).lower():
                    raise
                time.sleep(delay)
        else:
            raise last_error  # type: ignore[misc]
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise

    def execute_script(self, script: str) -> None:
        self.connection().executescript(script)

    def table_columns(self, table: str) -> List[str]:
        rows = self.query_all(f"PRAGMA table_info({table})")
        return [str(row["name"]) for row in rows]

    def user_version(self) -> int:
        row = self.query_one("PRAGMA user_version")
        return int(row[0]) if row else 0

    def set_user_version(self, version: int) -> None:
        self.execute(f"PRAGMA user_version={int(version)}")