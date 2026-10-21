"""SQLite 连接与通用查询辅助。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import db_path


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """打开数据库连接；数据库不存在时给出可操作的中文提示。"""
    target = Path(path) if path is not None else db_path()
    if not target.exists():
        raise FileNotFoundError(
            f"数据库不存在：{target}\n请先在仓库根目录运行：python -m data.seed"
        )
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


@contextmanager
def open_db(path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """只读场景使用，退出时自动关闭连接。"""
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def error(code: str, message: str) -> dict[str, Any]:
    """工具统一错误结构。"""
    return {"error": {"code": code, "message": message}}
