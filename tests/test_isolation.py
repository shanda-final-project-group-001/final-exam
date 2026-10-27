"""学生绑定、会话归属与访问口令的回归测试。"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from data.seed import seed_database
from volunteer import agent as agent_mod
from volunteer import tools_business as tools
from volunteer.sessions import SessionStore


class StudentBindingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="volunteer-isolation-test-"))
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

    def test_agent_cannot_touch_other_student(self) -> None:
        wrapped = {t.name: t for t in agent_mod.business_tools()}

        enroll = wrapped["enroll_activity"].invoke(
            {"student_id": "S002", "activity_id": "A007"}
        )
        self.assertEqual(enroll.get("error", {}).get("code"), "FORBIDDEN")

        hours = wrapped["get_volunteer_hours"].invoke(
            {"student_id": "S002", "term": "2026-2027-1"}
        )
        self.assertEqual(hours.get("error", {}).get("code"), "FORBIDDEN")

        # E1002 属于 S002；当前绑定 S001，必须在确认前拒绝。
        before = tools.get_activity_detail("A005")["remaining"]
        cancel = wrapped["cancel_enrollment"].invoke({"enrollment_id": "E1002"})
        self.assertEqual(cancel.get("error", {}).get("code"), "FORBIDDEN")
        self.assertEqual(tools.get_activity_detail("A005")["remaining"], before)


class SessionOwnershipTest(unittest.TestCase):
    def test_sessions_are_filtered_by_owner(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="volunteer-session-owner-"))
        try:
            store = SessionStore(tmp / "sessions.db")
            s1 = store.create("S001 的会话", student_id="S001")
            s2 = store.create("S002 的会话", student_id="S002")
            store.add_message(s1, "user", "S001 消息", student_id="S001")
            store.add_message(s2, "user", "S002 消息", student_id="S002")

            self.assertEqual([item["thread_id"] for item in store.list("S001")], [s1])
            self.assertIsNone(store.get(s2, "S001"))
            self.assertEqual(store.messages(s2, "S001"), [])

            store.delete(s2, "S001")
            self.assertIsNotNone(store.get(s2, "S002"))

            with self.assertRaises(PermissionError):
                store.add_message(s2, "user", "越权消息", student_id="S001")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class AccessCodeTest(unittest.TestCase):
    def test_access_code_compare(self) -> None:
        from web import access_code_ok

        self.assertTrue(access_code_ok("demo-code", "demo-code"))
        self.assertFalse(access_code_ok("wrong", "demo-code"))
        self.assertFalse(access_code_ok("", ""))
        self.assertFalse(access_code_ok("demo-code", ""))


if __name__ == "__main__":
    unittest.main()
