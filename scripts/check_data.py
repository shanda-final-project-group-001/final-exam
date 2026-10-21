"""演示数据完整性检查。

用法（仓库根目录）：
    python -m scripts.check_data

全部通过时退出码为 0；任一项失败时打印原因并返回 1，可用于汇报前自检。
"""

from __future__ import annotations

import sys
from datetime import datetime

from volunteer.db import connect

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
EXPECTED = {"students": 20, "activities": 30, "hours": 6}
EXPECTED_CONFIRMED = 40


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        icon = "PASS" if ok else "FAIL"
        suffix = f"　{detail}" if detail else ""
        print(f"[{icon}] {name}{suffix}")
        if not ok:
            failures.append(name)

    try:
        conn = connect()
    except FileNotFoundError as exc:
        print(exc)
        raise SystemExit(1) from exc

    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for table in EXPECTED
        }
        for table, expected in EXPECTED.items():
            check(f"{table} 记录数 = {expected}", counts[table] == expected,
                  f"实际 {counts[table]}")

        confirmed = conn.execute(
            "SELECT COUNT(*) AS n FROM enrollments WHERE status = 'confirmed'"
        ).fetchone()["n"]
        check(f"有效报名数 = {EXPECTED_CONFIRMED}", confirmed == EXPECTED_CONFIRMED,
              f"实际 {confirmed}")

        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        check("外键完整性", not fk_errors, f"{len(fk_errors)} 条异常")

        duplicates = conn.execute(
            "SELECT student_id, activity_id, COUNT(*) AS n FROM enrollments "
            "WHERE status = 'confirmed' GROUP BY student_id, activity_id HAVING n > 1"
        ).fetchall()
        check("无重复的有效报名", not duplicates, f"{len(duplicates)} 组重复")

        oversold = conn.execute(
            "SELECT a.activity_id, a.capacity, COUNT(e.enrollment_id) AS n "
            "FROM activities a LEFT JOIN enrollments e "
            "ON e.activity_id = a.activity_id AND e.status = 'confirmed' "
            "GROUP BY a.activity_id HAVING n > a.capacity"
        ).fetchall()
        check("无超卖活动", not oversold, f"{len(oversold)} 个活动超卖")

        weekday_issues = []
        for row in conn.execute("SELECT activity_id, date, weekday FROM activities"):
            actual = WEEKDAYS[datetime.strptime(row["date"], "%Y-%m-%d").weekday()]
            if actual != row["weekday"]:
                weekday_issues.append(f"{row['activity_id']} 应为 {actual}")
        check("活动星期与日期一致", not weekday_issues, "；".join(weekday_issues))

        hours = conn.execute(
            "SELECT COALESCE(SUM(hours), 0) AS total FROM hours "
            "WHERE student_id = 'S001' AND term = '2026-2027-1' AND status = 'confirmed'"
        ).fetchone()["total"]
        check("S001 学期时长 = 18.5", abs(float(hours) - 18.5) < 1e-9, f"实际 {hours}")

        full = conn.execute(
            "SELECT a.capacity, COUNT(e.enrollment_id) AS n FROM activities a "
            "LEFT JOIN enrollments e ON e.activity_id = a.activity_id "
            "AND e.status = 'confirmed' WHERE a.activity_id = 'A005' GROUP BY a.activity_id"
        ).fetchone()
        check("A005 已满（用于演示满员）", full["n"] == full["capacity"],
              f"{full['n']}/{full['capacity']}")

        closed = conn.execute(
            "SELECT COUNT(*) AS n FROM activities WHERE status = 'closed'"
        ).fetchone()["n"]
        check("存在已结束活动（用于检索过滤）", closed == 6, f"{closed} 条")
    finally:
        conn.close()

    print()
    if failures:
        print(f"检查未通过：{len(failures)} 项，请先修复后再演示。")
        raise SystemExit(1)
    print("全部检查通过，演示数据可用。")


if __name__ == "__main__":
    main()
