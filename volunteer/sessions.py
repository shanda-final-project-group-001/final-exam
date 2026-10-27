"""会话存储：SQLite 聊天记录 + 本地文件持久化的会话状态。

职责划分（方便答辩时一句话讲清）：

- **聊天记录表 `chat_sessions` / `chat_messages`**：界面用来展示历史会话、切换会话。
  两者都写在 `volunteer_sessions.db`，与业务库 `volunteer_demo.db` 分开，
  演示数据 `python -m data.seed` 重置时不会把聊天记录清空。
- **智能体状态（LangGraph checkpointer）**：由 `agent.py` 用 `SqliteSaver` 写入
  `agent_state.db`，用来让“同一个 thread 继续追问”能接着上一轮的上下文与待确认事项。
  这里不接管 checkpointer，避免两套状态互相覆盖。

对外只暴露 SessionStore 的增删改查，Agent 与界面都通过它读写历史。
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT, load_env

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    thread_id  TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    student_id TEXT NOT NULL DEFAULT 'S001',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id TEXT PRIMARY KEY,
    thread_id  TEXT NOT NULL,
    role       TEXT NOT NULL,          -- user / assistant
    content    TEXT NOT NULL,
    trace      TEXT,                   -- 该轮工具调用轨迹（JSON）
    created_at TEXT NOT NULL,
    FOREIGN KEY (thread_id) REFERENCES chat_sessions(thread_id)
);

CREATE INDEX IF NOT EXISTS idx_messages_thread ON chat_messages(thread_id, created_at);
"""


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #

def _sessions_db() -> Path:
    """聊天记录库位置；可用 VOLUNTEER_SESSIONS_DB 覆盖（测试时指向临时目录）。"""
    import os

    load_env()
    raw = os.getenv("VOLUNTEER_SESSIONS_DB")
    path = Path(raw) if raw else ROOT / "data" / "volunteer_sessions.db"
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def state_db() -> Path:
    """LangGraph checkpointer 位置。"""
    import os

    load_env()
    raw = os.getenv("VOLUNTEER_STATE_DB")
    path = Path(raw) if raw else ROOT / "data" / "agent_state.db"
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or _sessions_db())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def new_thread_id() -> str:
    return f"t{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- #
# 会话
# --------------------------------------------------------------------------- #

class SessionStore:
    """会话与消息的读写。所有方法都返回普通 dict，方便 Streamlit session_state 保存。"""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else _sessions_db()

    # -- 会话 ------------------------------------------------------------- #
    def create(self, title: str = "新对话", student_id: str = "S001",
               thread_id: str | None = None) -> str:
        tid = thread_id or new_thread_id()
        stamp = _now()
        with closing(_connect(self.path)) as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO chat_sessions VALUES (?, ?, ?, ?, ?)",
                (tid, title, student_id, stamp, stamp),
            )
        return tid

    def list(self, student_id: str | None = None) -> list[dict[str, Any]]:
        with closing(_connect(self.path)) as conn:
            sql = (
                "SELECT s.*, (SELECT COUNT(*) FROM chat_messages m "
                "WHERE m.thread_id = s.thread_id) AS message_count "
                "FROM chat_sessions s "
            )
            params: tuple[Any, ...] = ()
            if student_id:
                sql += "WHERE s.student_id = ? "
                params = (student_id,)
            sql += "ORDER BY s.updated_at DESC"
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get(self, thread_id: str,
            student_id: str | None = None) -> dict[str, Any] | None:
        with closing(_connect(self.path)) as conn:
            sql = "SELECT * FROM chat_sessions WHERE thread_id = ?"
            params: list[Any] = [thread_id]
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def rename(self, thread_id: str, title: str,
               student_id: str | None = None) -> None:
        title = (title or "").strip()[:24] or "新对话"
        with closing(_connect(self.path)) as conn, conn:
            sql = "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE thread_id = ?"
            params: list[Any] = [title, _now(), thread_id]
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            conn.execute(sql, params)

    def touch(self, thread_id: str, student_id: str | None = None) -> None:
        with closing(_connect(self.path)) as conn, conn:
            sql = "UPDATE chat_sessions SET updated_at = ? WHERE thread_id = ?"
            params: list[Any] = [_now(), thread_id]
            if student_id:
                sql += " AND student_id = ?"
                params.append(student_id)
            conn.execute(sql, params)

    def delete(self, thread_id: str, student_id: str | None = None) -> None:
        with closing(_connect(self.path)) as conn, conn:
            if student_id:
                row = conn.execute(
                    "SELECT student_id FROM chat_sessions WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
                if row is None or row["student_id"] != student_id:
                    return
            conn.execute("DELETE FROM chat_messages WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM chat_sessions WHERE thread_id = ?", (thread_id,))

    # -- 消息 ------------------------------------------------------------- #
    def add_message(self, thread_id: str, role: str, content: str,
                    trace: list[dict[str, Any]] | None = None,
                    student_id: str | None = None) -> None:
        import json

        with closing(_connect(self.path)) as conn, conn:
            if student_id:
                owner = conn.execute(
                    "SELECT student_id FROM chat_sessions WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
                if owner is None or owner["student_id"] != student_id:
                    raise PermissionError("会话不属于当前用户")
            conn.execute(
                "INSERT INTO chat_messages VALUES (?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, thread_id, role, content,
                 json.dumps(trace or [], ensure_ascii=False) if trace else None, _now()),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE thread_id = ?",
                (_now(), thread_id),
            )

    def messages(self, thread_id: str,
                 student_id: str | None = None) -> list[dict[str, Any]]:
        import json

        with closing(_connect(self.path)) as conn:
            if student_id:
                owner = conn.execute(
                    "SELECT student_id FROM chat_sessions WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
                if owner is None or owner["student_id"] != student_id:
                    return []
            rows = conn.execute(
                "SELECT role, content, trace, created_at FROM chat_messages "
                "WHERE thread_id = ? ORDER BY created_at, rowid",
                (thread_id,),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["trace"] = json.loads(item["trace"]) if item["trace"] else []
            items.append(item)
        return items

    def auto_title(self, thread_id: str, first_user_message: str,
                   student_id: str | None = None) -> None:
        """用第一条用户消息做标题，避免列表里全是“新对话”。"""
        current = self.get(thread_id, student_id)
        if current and current["title"] not in {"新对话", ""}:
            return
        text = " ".join((first_user_message or "").split())
        self.rename(thread_id, text[:16] + ("…" if len(text) > 16 else ""), student_id)
