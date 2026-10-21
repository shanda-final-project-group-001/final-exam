"""MCP 服务器测试：工具清单、只读边界与调用结果。"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from data.seed import seed_database
from volunteer.mcp_server import mcp

EXPECTED = {"search_activities", "get_activity_detail", "get_volunteer_hours"}


class McpServerTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="volunteer-mcp-"))
        self.db = self.tmp / "test.db"
        seed_database(self.db)
        self._old_db = os.environ.get("VOLUNTEER_DB")
        os.environ["VOLUNTEER_DB"] = str(self.db)

    def tearDown(self) -> None:
        if self._old_db is None:
            os.environ.pop("VOLUNTEER_DB", None)
        else:
            os.environ["VOLUNTEER_DB"] = self._old_db
        shutil.rmtree(self.tmp, ignore_errors=True)

    async def _call(self, name: str, args: dict) -> dict:
        result = await mcp.call_tool(name, args)
        self.assertFalse(result.is_error, f"{name} 返回错误：{result.content}")
        return json.loads(result.content[0].text)

    async def test_tool_list(self) -> None:
        tools = await mcp.list_tools()
        self.assertEqual({tool.name for tool in tools}, EXPECTED)

    async def test_tools_have_description_and_schema(self) -> None:
        for tool in await mcp.list_tools():
            self.assertTrue(tool.description, f"{tool.name} 缺少说明")
            self.assertTrue(tool.input_schema.get("properties"), f"{tool.name} 缺少参数定义")

    async def test_read_only_boundary(self) -> None:
        names = {tool.name for tool in await mcp.list_tools()}
        self.assertFalse(
            names & {"enroll_activity", "cancel_enrollment", "export_hours_csv"}
        )

    async def test_search(self) -> None:
        data = await self._call("search_activities", {"weekday": "周六", "limit": 2})
        self.assertEqual(data["count"], 2)
        self.assertTrue(all(item["weekday"] == "周六" for item in data["items"]))
        self.assertTrue(all(item["status"] == "open" for item in data["items"]))

    async def test_detail(self) -> None:
        data = await self._call("get_activity_detail", {"activity_id": "A001"})
        self.assertEqual(data["title"], "社区长者手机课堂")
        self.assertIsInstance(data["tags"], list)
        self.assertIsInstance(data["remaining"], int)
        self.assertGreaterEqual(data["remaining"], 0)

    async def test_detail_not_found(self) -> None:
        data = await self._call("get_activity_detail", {"activity_id": "A999"})
        self.assertEqual(data["error"]["code"], "NOT_FOUND")

    async def test_hours(self) -> None:
        data = await self._call("get_volunteer_hours", {"student_id": "S001"})
        self.assertEqual(data["total_hours"], 18.5)
        self.assertEqual(len(data["records"]), 6)
        self.assertEqual(data["term"], "2026-2027-1")

    async def test_hours_not_found(self) -> None:
        data = await self._call("get_volunteer_hours", {"student_id": "S999"})
        self.assertEqual(data["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
