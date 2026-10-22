"""志愿星业务工具（朱煜杰负责的数据与工具层）。

设计原则：
- 所有工具是确定性实现，返回可 JSON 序列化的 dict；
- 错误统一为 {"error": {"code", "message"}}；
- 写操作在事务内完成，报名前同时校验课表冲突、重复报名与名额。

Agent 层可直接 import 这些函数，或用 as_langchain_tools() 包装。
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import ROOT, workspace_dir
from .db import connect, error, open_db, to_dicts

TERM_DEFAULT = "2026-2027-1"


# --------------------------------------------------------------------------- #
# 内部辅助
# --------------------------------------------------------------------------- #

def _minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
    return _minutes(start_a) < _minutes(end_b) and _minutes(start_b) < _minutes(end_a)


def _activity(conn, activity_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM activities WHERE activity_id = ?", (activity_id,)
    ).fetchone()
    return dict(row) if row else None


def _remaining(conn, activity_id: str, capacity: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM enrollments "
        "WHERE activity_id = ? AND status = 'confirmed'",
        (activity_id,),
    ).fetchone()
    return max(0, capacity - row["n"])


def _student_exists(conn, student_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
    ).fetchone()
    return row is not None


def _conflicts(conn, student_id: str, activity: dict[str, Any]) -> list[dict[str, Any]]:
    """返回课表与已报名活动的时间冲突。"""
    items: list[dict[str, Any]] = []

    courses = conn.execute(
        "SELECT name, weekday, start_time, end_time FROM courses "
        "WHERE student_id = ? AND weekday = ?",
        (student_id, activity["weekday"]),
    ).fetchall()
    for course in courses:
        if _overlap(activity["start_time"], activity["end_time"],
                    course["start_time"], course["end_time"]):
            items.append({
                "type": "course",
                "name": course["name"],
                "weekday": course["weekday"],
                "start_time": course["start_time"],
                "end_time": course["end_time"],
            })

    enrolled = conn.execute(
        "SELECT a.activity_id, a.title, a.date, a.start_time, a.end_time "
        "FROM enrollments e JOIN activities a ON a.activity_id = e.activity_id "
        "WHERE e.student_id = ? AND e.status = 'confirmed' AND a.date = ? "
        "AND a.activity_id <> ?",
        (student_id, activity["date"], activity["activity_id"]),
    ).fetchall()
    for row in enrolled:
        if _overlap(activity["start_time"], activity["end_time"],
                    row["start_time"], row["end_time"]):
            items.append({
                "type": "activity",
                "activity_id": row["activity_id"],
                "name": row["title"],
                "date": row["date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
            })

    return items


# --------------------------------------------------------------------------- #
# 读操作（MCP 服务器同样暴露这三个）
# --------------------------------------------------------------------------- #

def search_activities(
    weekday: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """按星期、类别或关键词检索开放中的志愿活动。

    Args:
        weekday: 中文星期，如 "周三"；为空表示不限。
        category: 活动类别，如 "助老"；为空表示不限。
        keyword: 标题或标签关键词；为空表示不限。
        limit: 返回条数，1-50，默认 5。
    """
    limit = max(1, min(50, int(limit)))
    sql = [
        "SELECT a.*, (a.capacity - COALESCE(SUM(CASE WHEN e.status = 'confirmed' "
        "THEN 1 ELSE 0 END), 0)) AS remaining",
        "FROM activities a",
        "LEFT JOIN enrollments e ON e.activity_id = a.activity_id",
        "WHERE a.status = 'open'",
    ]
    params: list[Any] = []
    if weekday:
        sql.append("AND a.weekday = ?")
        params.append(weekday)
    if category:
        sql.append("AND a.category = ?")
        params.append(category)
    if keyword:
        sql.append("AND (a.title LIKE ? OR a.tags LIKE ? OR a.description LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    sql.append("GROUP BY a.activity_id ORDER BY a.date, a.start_time LIMIT ?")
    params.append(limit)

    with open_db() as conn:
        rows = to_dicts(conn.execute(" ".join(sql), params).fetchall())

    for row in rows:
        row["tags"] = [tag for tag in row["tags"].split(",") if tag]
        row["remaining"] = int(row["remaining"])
    return {"items": rows, "count": len(rows)}


def get_activity_detail(activity_id: str) -> dict[str, Any]:
    """查询单个活动的详细信息与剩余名额。

    Args:
        activity_id: 活动编号，如 "A001"。
    """
    with open_db() as conn:
        activity = _activity(conn, activity_id)
        if activity is None:
            return error("NOT_FOUND", f"未找到活动 {activity_id}")
        activity["remaining"] = _remaining(conn, activity_id, activity["capacity"])
        activity["tags"] = [tag for tag in activity["tags"].split(",") if tag]
    return activity


def get_volunteer_hours(
    student_id: str, term: str = TERM_DEFAULT
) -> dict[str, Any]:
    """汇总某学生某学期的已认定志愿时长。

    Args:
        student_id: 学号，如 "S001"。
        term: 学期，默认 "2026-2027-1"。
    """
    with open_db() as conn:
        if not _student_exists(conn, student_id):
            return error("NOT_FOUND", f"未找到学生 {student_id}")
        rows = conn.execute(
            "SELECT h.activity_id, a.title, a.date, h.hours, h.status "
            "FROM hours h JOIN activities a ON a.activity_id = h.activity_id "
            "WHERE h.student_id = ? AND h.term = ? AND h.status = 'confirmed' "
            "ORDER BY a.date",
            (student_id, term),
        ).fetchall()
        records = to_dicts(rows)
    total = round(sum(float(item["hours"]) for item in records), 1)
    return {
        "student_id": student_id,
        "term": term,
        "total_hours": total,
        "records": records,
    }


# --------------------------------------------------------------------------- #
# 写操作
# --------------------------------------------------------------------------- #

def check_schedule_conflict(student_id: str, activity_id: str) -> dict[str, Any]:
    """检查活动是否与该学生的课表或已报名活动冲突。

    Args:
        student_id: 学号，如 "S001"。
        activity_id: 活动编号，如 "A004"。
    """
    with open_db() as conn:
        if not _student_exists(conn, student_id):
            return error("NOT_FOUND", f"未找到学生 {student_id}")
        activity = _activity(conn, activity_id)
        if activity is None:
            return error("NOT_FOUND", f"未找到活动 {activity_id}")
        items = _conflicts(conn, student_id, activity)

    return {
        "conflict": bool(items),
        "activity_id": activity_id,
        "items": items,
        "suggestion": "该时段已有安排，建议换一个活动或另选时间" if items else "时间可用",
    }


def enroll_activity(student_id: str, activity_id: str) -> dict[str, Any]:
    """为学生在事务中创建报名记录；冲突、满员、重复报名会被拒绝。

    Args:
        student_id: 学号，如 "S001"。
        activity_id: 活动编号，如 "A001"。
    """
    conn = connect()
    try:
        with conn:
            if not _student_exists(conn, student_id):
                return error("NOT_FOUND", f"未找到学生 {student_id}")
            activity = _activity(conn, activity_id)
            if activity is None:
                return error("NOT_FOUND", f"未找到活动 {activity_id}")
            if activity["status"] != "open":
                return error("CLOSED", f"活动 {activity_id} 已结束报名")

            duplicate = conn.execute(
                "SELECT enrollment_id FROM enrollments "
                "WHERE student_id = ? AND activity_id = ? AND status = 'confirmed'",
                (student_id, activity_id),
            ).fetchone()
            if duplicate:
                return error("ALREADY_ENROLLED", f"已报名该活动（{duplicate['enrollment_id']}）")

            if _remaining(conn, activity_id, activity["capacity"]) <= 0:
                return error("FULL", f"活动 {activity_id} 名额已满")

            conflicts = _conflicts(conn, student_id, activity)
            if conflicts:
                names = "、".join(item["name"] for item in conflicts)
                return {
                    **error("CONFLICT", f"时间冲突：{names}"),
                    "conflicts": conflicts,
                }

            row = conn.execute(
                "SELECT MAX(CAST(SUBSTR(enrollment_id, 2) AS INTEGER)) AS n FROM enrollments"
            ).fetchone()
            next_id = f"E{(row['n'] or 1000) + 1}"
            created = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                "INSERT INTO enrollments VALUES (?, ?, ?, 'confirmed', ?)",
                (next_id, student_id, activity_id, created),
            )
            remaining = _remaining(conn, activity_id, activity["capacity"])
        return {
            "status": "confirmed",
            "enrollment_id": next_id,
            "student_id": student_id,
            "activity_id": activity_id,
            "remaining": remaining,
        }
    finally:
        conn.close()


def cancel_enrollment(enrollment_id: str) -> dict[str, Any]:
    """取消一条报名记录（幂等：已取消时返回 cancelled）。

    Args:
        enrollment_id: 报名编号，如 "E1001"。
    """
    with open_db() as conn:
        row = conn.execute(
            "SELECT * FROM enrollments WHERE enrollment_id = ?", (enrollment_id,)
        ).fetchone()
        if row is None:
            return error("NOT_FOUND", f"未找到报名记录 {enrollment_id}")
        if row["status"] == "cancelled":
            # 幂等分支也要返回与正常分支同构的字段，避免调用方按 activity_id / remaining 取值时报错
            activity = _activity(conn, row["activity_id"])
            remaining = (
                _remaining(conn, row["activity_id"], activity["capacity"]) if activity else None
            )
            return {
                "status": "cancelled",
                "enrollment_id": enrollment_id,
                "activity_id": row["activity_id"],
                "remaining": remaining,
                "note": "该报名此前已取消",
            }
        with conn:
            conn.execute(
                "UPDATE enrollments SET status = 'cancelled' WHERE enrollment_id = ?",
                (enrollment_id,),
            )
        activity = _activity(conn, row["activity_id"])
        remaining = _remaining(conn, row["activity_id"], activity["capacity"]) if activity else None
    return {
        "status": "cancelled",
        "enrollment_id": enrollment_id,
        "activity_id": row["activity_id"],
        "remaining": remaining,
    }


def export_hours_csv(
    student_id: str,
    term: str = TERM_DEFAULT,
    out_path: str = "hours.csv",
) -> dict[str, Any]:
    """把某学生某学期的志愿时长导出为 CSV（UTF-8-SIG，Excel 可直接打开）。

    Args:
        student_id: 学号，如 "S001"。
        term: 学期，默认 "2026-2027-1"。
        out_path: 相对 workspace 的文件名，如 "hours.csv"。
    """
    data = get_volunteer_hours(student_id, term)
    if "error" in data:
        return data

    base = workspace_dir().resolve()
    name = Path(out_path)
    if name.suffix.lower() != ".csv":
        return error("INVALID_PATH", "导出文件必须是 .csv")
    if name.is_absolute():
        target = name.resolve()
    else:
        parts = name.parts
        if parts and parts[0].lower() == "workspace":
            name = Path(*parts[1:])
        target = (base / name).resolve()

    if not target.is_relative_to(base):
        return error("INVALID_PATH", "只能写入 workspace 目录")

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["activity_id", "title", "date", "hours", "status"]
        )
        writer.writeheader()
        for record in data["records"]:
            writer.writerow({
                "activity_id": record["activity_id"],
                "title": record["title"],
                "date": record["date"],
                "hours": record["hours"],
                "status": record["status"],
            })

    try:
        shown = target.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        shown = target.as_posix()
    return {
        "path": shown,
        "rows": len(data["records"]),
        "total_hours": data["total_hours"],
    }


# --------------------------------------------------------------------------- #
# LangChain 适配（Agent 层可选使用）
# --------------------------------------------------------------------------- #

def as_langchain_tools() -> list[Any]:
    """把 4 个写/导出工具包装成 LangChain Tool；未安装依赖时给出明确提示。"""
    try:
        from langchain_core.tools import tool
    except ImportError as exc:  # pragma: no cover - 仅在 Agent 阶段需要
        raise RuntimeError(
            "未安装 langchain-core，请先执行 pip install langchain-core"
        ) from exc

    return [
        tool(check_schedule_conflict),
        tool(enroll_activity),
        tool(cancel_enrollment),
        tool(export_hours_csv),
    ]
