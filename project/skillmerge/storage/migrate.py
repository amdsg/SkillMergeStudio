from __future__ import annotations

import os
import shutil
import sqlite3
from typing import List

from ..util.errors import DomainError

CURRENT_SCHEMA_VERSION = 3
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def _read_schema() -> str:
    with open(SCHEMA_FILE, "r", encoding="utf-8") as handle:
        return handle.read()


def _backup(path: str, version: int) -> None:
    if not os.path.isfile(path):
        return
    backup = f"{path}.bak-v{version}"
    try:
        shutil.copy2(path, backup)
        backups: List[str] = sorted(
            [os.path.join(os.path.dirname(path), name) for name in os.listdir(os.path.dirname(path)) if name.startswith("index.db.bak-v")],
            key=lambda item: os.path.getmtime(item),
        )
        for stale in backups[:-2]:
            os.remove(stale)
    except OSError:
        pass


def migrate_database(conn: sqlite3.Connection, path: str) -> None:
    row = conn.execute("PRAGMA user_version").fetchone()
    version = int(row[0]) if row else 0
    if version > CURRENT_SCHEMA_VERSION:
        raise DomainError(
            "DB_VERSION_NEWER",
            f"数据库由更新版本创建（v{version}），当前程序支持 v{CURRENT_SCHEMA_VERSION}",
            "升级程序，或备份后删除 data/index.db 重新扫描",
            500,
        )
    if version == CURRENT_SCHEMA_VERSION:
        return
    if version > 0:
        _backup(path, version)
    for step in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
        if step == 1:
            try:
                _apply(conn, step)
                conn.execute(f"PRAGMA user_version={step}")
            except Exception:
                if version > 0 and os.path.isfile(f"{path}.bak-v{version}"):
                    try:
                        shutil.copy2(f"{path}.bak-v{version}", path)
                    except OSError:
                        pass
                raise
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            _apply(conn, step)
            conn.execute(f"PRAGMA user_version={step}")
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if version > 0 and os.path.isfile(f"{path}.bak-v{version}"):
                try:
                    shutil.copy2(f"{path}.bak-v{version}", path)
                except OSError:
                    pass
            raise
    check = conn.execute("PRAGMA integrity_check").fetchone()
    if not check or str(check[0]).lower() != "ok":
        raise DomainError("DB_INTEGRITY_ERROR", "数据库完整性校验失败", "从 data/index.db.bak-v* 恢复后重试", 500)


def _apply(conn: sqlite3.Connection, step: int) -> None:
    if step == 1:
        conn.executescript(_read_schema())
    elif step == 2:
        _add_column(conn, "skills", "search_blob", "TEXT NOT NULL DEFAULT ''")
        _add_column(conn, "skills", "quality_json", "TEXT NOT NULL DEFAULT '[]'")
        _add_column(conn, "artifacts", "plan_summary_json", "TEXT NOT NULL DEFAULT '{}'")
    elif step == 3:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_events (
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                phase TEXT NOT NULL,
                current INTEGER NOT NULL DEFAULT 0,
                total INTEGER,
                message TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                PRIMARY KEY (job_id, seq)
            )
            """
        )
        _add_column(conn, "scans", "coverage_json", "TEXT NOT NULL DEFAULT '[]'")
    else:
        raise DomainError("DB_MIGRATION_ERROR", f"未知迁移步骤 v{step}", "备份 data/index.db 后重新扫描", 500)


def _add_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")