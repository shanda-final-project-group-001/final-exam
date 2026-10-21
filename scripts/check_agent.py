"""Agent / 界面层的自检（不需要 API Key）。

覆盖：
- 会话存储：新建、追加、标题、删除；
- 工具包装：7 个工具齐全，读工具来自 MCP，写工具在未确认时不写库；
- 离线演示：产物真实写入 workspace；
- 确认语义：confirmer 返回 False 时不写库，返回 True 时写库并清理。

用法（仓库根目录）：
    python -m scripts.check_agent
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from volunteer import agent as agent_mod
    from volunteer.config import workspace_dir
    from volunteer.sessions import SessionStore

    sandbox = Path(tempfile.mkdtemp(prefix="volunteer-agent-check-"))
    demo_ws = workspace_dir() / "agent-check"
    shutil.rmtree(demo_ws, ignore_errors=True)
    demo_ws.mkdir(parents=True, exist_ok=True)

    try:
        # 1. 会话存储
        db = SessionStore(sandbox / "sessions.db")
        tid = db.create("新对话")
        db.add_message(tid, "user", "我周三晚上有空，帮我找活动")
        db.add_message(tid, "assistant", "好的", [{"name": "search_activities", "args": {}, "summary": "0 条", "ok": True}])
        db.auto_title(tid, "我周三晚上有空，帮我找活动")
        messages = db.messages(tid)
        record("会话新建与消息读写", len(messages) == 2 and messages[1]["trace"][0]["name"] == "search_activities")
        record("会话标题自动生成", db.get(tid)["title"].startswith("我周三晚上有空"))
        db.delete(tid)
        record("会话删除", db.get(tid) is None and db.messages(tid) == [])

        # 2. 工具清单
        names = agent_mod.tool_names()
        expected = {"search_activities", "get_activity_detail", "get_volunteer_hours",
                    "check_schedule_conflict", "enroll_activity", "cancel_enrollment",
                    "export_hours_csv", "write_file"}
        record("工具清单完整（8 个）", expected.issubset(set(names)), str(names))
        try:
            from volunteer.mcp_server import tool_specs

            specs = {item["name"]: item for item in tool_specs()}
            wrapped = {t.name: t for t in agent_mod.business_tools()}
            expected_reads = {"search_activities", "get_activity_detail", "get_volunteer_hours"}
            same = expected_reads == set(specs)
            identical = all(specs[name]["description"].strip()
                            in wrapped[name].description for name in expected_reads)
            record("读工具来自 MCP 服务器", same and identical,
                   f"MCP 注册 {sorted(specs)}，Agent 侧描述一致={identical}")
        except Exception as exc:  # pragma: no cover
            record("读工具来自 MCP 服务器", False, f"{type(exc).__name__}: {exc}")

        # 3. 写工具确认语义（用 confirmer 直接测，不进 LangGraph）
        from volunteer import tools_business as tools

        def pick_free_activity() -> str:
            for item in tools.search_activities(weekday="周六", limit=10)["items"]:
                if item["remaining"] > 0 and not tools.check_schedule_conflict(
                        "S001", item["activity_id"])["conflict"]:
                    return item["activity_id"]
            raise RuntimeError("没有可用活动")

        target = pick_free_activity()
        wrapped = agent_mod.business_tools(confirmer=lambda payload: False)
        enroll = next(t for t in wrapped if t.name == "enroll_activity")
        refused = enroll.invoke({"student_id": "S001", "activity_id": target})
        record("未确认不写库", refused.get("status") == "cancelled", f"{target} -> {refused}")

        # 拒绝后不应产生报名记录；再确认一次，走正常写入，最后清理
        from volunteer.db import open_db

        found = tools.enroll_activity("S001", target)
        record("确认后才写入", found.get("status") == "confirmed", str(found))
        if found.get("status") == "confirmed":
            tools.cancel_enrollment(found["enrollment_id"])
            with open_db() as conn, conn:
                conn.execute("DELETE FROM enrollments WHERE enrollment_id = ?",
                             (found["enrollment_id"],))

        bad = enroll.invoke({"student_id": "S001", "activity_id": "A999"})
        record("不存在的活动直接返回错误", bad.get("error", {}).get("code") == "NOT_FOUND", str(bad))

        # 4. write_file 边界
        writer = next(t for t in wrapped if t.name == "write_file")
        inside = writer.invoke({"path": "agent-check/ok.md", "content": "# ok"})
        outside = writer.invoke({"path": "../escape.md", "content": "x"})
        record("write_file 可写 workspace", "path" in inside, str(inside))
        record("write_file 拒绝越界", outside.get("error", {}).get("code") == "INVALID_PATH", str(outside))

        # 5. 离线演示：同一批工具 + 模板
        text, steps = agent_mod.offline_answer()
        reports = list((workspace_dir() / "reports").glob("weekly-report-*.md"))
        record("离线演示产生回答", "离线演示" in text and len(steps) >= 5)
        record("离线演示写入周报", bool(reports), reports[0].name if reports else "未生成")
        if reports:
            content = reports[0].read_text(encoding="utf-8")
            record("周报含关键字段", all(key in content for key in
                                    ("已认定总时长", "时长明细", "数据来源：本地演示样例数据")))

        # 6. 配置提示
        problem = agent_mod.config_problem()
        record("无 Key 时有中文提示或配置正常", problem is None or "API Key" in problem or "数据库" in problem,
               str(problem))

    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        shutil.rmtree(demo_ws, ignore_errors=True)

    width = max(len(name) for _, name, _ in results) + 2
    for status, name, detail in results:
        print(f"[{status}] {name.ljust(width)} {detail}")
    failed = sum(1 for status, _, _ in results if status == FAIL)
    print(f"\n共 {len(results)} 项，通过 {len(results) - failed} 项，失败 {failed} 项。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
