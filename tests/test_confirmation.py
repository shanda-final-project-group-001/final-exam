"""人工确认与前端转义的安全回归测试。"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from data.seed import seed_database
from volunteer import agent as agent_mod
from volunteer import tools_business as tools
from volunteer.db import open_db


class ConfirmationSecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="volunteer-confirm-test-"))
        self.db = self.tmp / "test.db"
        seed_database(self.db)
        self._old_db = os.environ.get("VOLUNTEER_DB")
        self._old_ws = os.environ.get("WORKSPACE_DIR")
        os.environ["VOLUNTEER_DB"] = str(self.db)
        os.environ["WORKSPACE_DIR"] = str(self.tmp / "workspace")

    def tearDown(self) -> None:
        if self._old_db is None:
            os.environ.pop("VOLUNTEER_DB", None)
        else:
            os.environ["VOLUNTEER_DB"] = self._old_db
        if self._old_ws is None:
            os.environ.pop("WORKSPACE_DIR", None)
        else:
            os.environ["WORKSPACE_DIR"] = self._old_ws
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _free_activity(self) -> str:
        for item in tools.search_activities(weekday="周六", limit=10)["items"]:
            if item["remaining"] > 1 and not tools.check_schedule_conflict(
                    "S001", item["activity_id"])["conflict"]:
                return item["activity_id"]
        raise AssertionError("没有找到可用活动")

    def _enroll_tool(self, confirmer):
        wrapped = agent_mod.business_tools(confirmer=confirmer)
        return next(item for item in wrapped if item.name == "enroll_activity")

    def _confirmed_count(self, activity_id: str) -> int:
        with open_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM enrollments "
                "WHERE student_id = 'S001' AND activity_id = ? AND status = 'confirmed'",
                (activity_id,),
            ).fetchone()
        return int(row["n"])

    def test_false_dict_confirmation_does_not_write(self) -> None:
        """直接回归 C-01：resume 的 {"approved": False} 不能被 bool(dict) 当成确认。"""
        target = self._free_activity()
        before = tools.get_activity_detail(target)["remaining"]

        result = self._enroll_tool(
            lambda payload: {"approved": False, "note": ""}
        ).invoke({"student_id": "S001", "activity_id": target})

        self.assertEqual(result.get("status"), "cancelled")
        self.assertEqual(tools.get_activity_detail(target)["remaining"], before)
        self.assertEqual(self._confirmed_count(target), 0)

    def test_true_dict_confirmation_writes(self) -> None:
        target = self._free_activity()
        before = tools.get_activity_detail(target)["remaining"]

        result = self._enroll_tool(
            lambda payload: {"approved": True, "note": ""}
        ).invoke({"student_id": "S001", "activity_id": target})

        self.assertEqual(result.get("status"), "confirmed")
        self.assertEqual(tools.get_activity_detail(target)["remaining"], before - 1)
        self.assertEqual(self._confirmed_count(target), 1)

    def test_boolean_false_still_works(self) -> None:
        """保留脚本/测试里传布尔值的兼容路径。"""
        target = self._free_activity()
        result = self._enroll_tool(lambda payload: False).invoke(
            {"student_id": "S001", "activity_id": target}
        )
        self.assertEqual(result.get("status"), "cancelled")
        self.assertEqual(self._confirmed_count(target), 0)

    def test_invalid_cancel_id_is_rejected_before_confirmation(self) -> None:
        """恶意 enrollment_id 不应进入确认面板，更不能触发 HTML 渲染。"""
        seen: list[dict] = []

        def confirmer(payload):
            seen.append(payload)
            return True

        wrapped = agent_mod.business_tools(confirmer=confirmer)
        cancel = next(item for item in wrapped if item.name == "cancel_enrollment")
        result = cancel.invoke(
            {"enrollment_id": "<img src=x onerror=alert(1)>"}
        )

        self.assertEqual(result.get("error", {}).get("code"), "INVALID_ID")
        self.assertEqual(seen, [])

    def test_escape_html_payload(self) -> None:
        """确认面板用的转义函数必须把标签变成文本。"""
        from web import _escape

        self.assertEqual(
            _escape('<script>alert("x")</script>'),
            '&lt;script&gt;alert("x")&lt;/script&gt;',
        )
        self.assertEqual(_escape("A & B"), "A &amp; B")


if __name__ == "__main__":
    unittest.main()
