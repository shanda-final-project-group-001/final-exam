"""MCP 客户端联调脚本：以 stdio 真实启动 volunteer-data 服务器。

验证内容（对应测试用例 TC-16 ~ TC-18）：
1. 服务器可被标准 MCP 客户端拉起并完成握手；
2. 只暴露 3 个只读工具，不含报名 / 取消 / 导出；
3. 三个工具的真实调用结果与 CLI 一致。

用法（仓库根目录）：
    python -m scripts.mcp_smoke
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TOOLS = {"search_activities", "get_activity_detail", "get_volunteer_hours"}


def _payload(result) -> dict:
    """把 CallToolResult 的文本内容解析回 dict。"""
    text = result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _ok(label: str, condition: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {label}{('　' + detail) if detail else ''}")
    return condition


async def run() -> bool:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "volunteer.mcp_server"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("MCP 握手完成\n")

            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            print(f"工具清单：{sorted(names)}\n")

            ok = True
            ok &= _ok("暴露 3 个工具", names == EXPECTED_TOOLS, str(sorted(names)))
            ok &= _ok("无写操作工具", not (names & {"enroll_activity", "cancel_enrollment", "export_hours_csv"}))
            ok &= _ok(
                "每个工具都有说明与参数",
                all(t.description and t.input_schema.get("properties") for t in tools.tools),
            )

            print("\n--- 调用 search_activities(weekday='周六', limit=2) ---")
            search = _payload(await session.call_tool("search_activities", {"weekday": "周六", "limit": 2}))
            print(json.dumps(search, ensure_ascii=False, indent=2))
            ok &= _ok(
                "检索返回 2 条且均为周六",
                search.get("count") == 2
                and all(item["weekday"] == "周六" for item in search.get("items", [])),
            )

            print("\n--- 调用 get_activity_detail('A001') ---")
            detail = _payload(await session.call_tool("get_activity_detail", {"activity_id": "A001"}))
            print(json.dumps(detail, ensure_ascii=False, indent=2))
            ok &= _ok("活动详情为社区长者手机课堂", detail.get("title") == "社区长者手机课堂")
            ok &= _ok("剩余名额为非负整数", isinstance(detail.get("remaining"), int) and detail["remaining"] >= 0)

            print("\n--- 调用 get_activity_detail('A999') ---")
            missing = _payload(await session.call_tool("get_activity_detail", {"activity_id": "A999"}))
            ok &= _ok("不存在的活动返回 NOT_FOUND",
                      missing.get("error", {}).get("code") == "NOT_FOUND")

            print("\n--- 调用 get_volunteer_hours('S001') ---")
            hours = _payload(await session.call_tool("get_volunteer_hours", {"student_id": "S001"}))
            print(json.dumps(hours, ensure_ascii=False, indent=2))
            ok &= _ok("S001 累计 18.5 小时", hours.get("total_hours") == 18.5)
            ok &= _ok("时长明细 6 条", len(hours.get("records", [])) == 6)

            return ok


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    passed = asyncio.run(run())
    print("\nMCP 联调通过。" if passed else "\nMCP 联调失败，请查看上面的 FAIL 项。")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
