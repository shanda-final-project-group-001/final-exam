"""MCP 服务器：volunteer-data

把活动检索、活动详情、时长查询三个只读能力暴露为标准 MCP 工具，
供 Agent 或其他 MCP 客户端复用。

本地调试（stdio）：
    python -m volunteer.mcp_server

也可在支持 MCP 的客户端中配置：
    command = "python"
    args = ["-m", "volunteer.mcp_server"]
    cwd = 仓库根目录
"""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from . import tools_business as tools

mcp = MCPServer("volunteer-data")


@mcp.tool()
def search_activities(
    weekday: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    limit: int = 5,
) -> dict:
    """检索开放中的校园志愿活动。

    Args:
        weekday: 中文星期，如 "周三"；为空表示不限。
        category: 类别，如 "助老"、"环保"；为空表示不限。
        keyword: 标题/标签/说明关键词；为空表示不限。
        limit: 返回条数，1-50。
    """
    return tools.search_activities(weekday, category, keyword, limit)


@mcp.tool()
def get_activity_detail(activity_id: str) -> dict:
    """查询单个活动的详细信息与剩余名额。

    Args:
        activity_id: 活动编号，如 "A001"。
    """
    return tools.get_activity_detail(activity_id)


@mcp.tool()
def get_volunteer_hours(student_id: str, term: str = "2026-2027-1") -> dict:
    """汇总某学生某学期的已认定志愿时长。

    Args:
        student_id: 学号，如 "S001"。
        term: 学期，默认 "2026-2027-1"。
    """
    return tools.get_volunteer_hours(student_id, term)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    mcp.run()


def tool_specs() -> list[dict]:
    """列出服务器注册的工具定义（名称、参数 schema、描述、底层函数）。

    供 Agent 层“按 MCP 的定义挂载工具”，也让测试能直接核对服务器暴露了哪些能力。
    只读工具注册在 `mcp` 上，这里是唯一真相来源，避免 Agent 与 MCP 两处各写一份描述。
    """
    manager = getattr(mcp, "_tool_manager", None)
    tools = getattr(manager, "_tools", {}) if manager else {}
    return [
        {
            "name": item.name,
            "description": item.description or "",
            "parameters": item.parameters,
            "fn": item.fn,
        }
        for item in tools.values()
    ]


if __name__ == "__main__":
    main()
