"""工具层测试：数据、查询、冲突、报名、取消、导出。"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from data.seed import seed_database
from volunteer import tools_business as tools


class ToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="volunteer-test-"))
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

    # ---------------------------- 查询 ---------------------------- #

    def test_search_by_weekday(self) -> None:
        result = tools.search_activities(weekday="周三", limit=10)
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(all(item["weekday"] == "周三" for item in result["items"]))
        self.assertTrue(all(item["remaining"] >= 0 for item in result["items"]))

    def test_search_by_category(self) -> None:
        result = tools.search_activities(category="助老", limit=10)
        self.assertGreaterEqual(result["count"], 1)
        self.assertTrue(all(item["category"] == "助老" for item in result["items"]))

    def test_search_by_keyword(self) -> None:
        result = tools.search_activities(keyword="支教", limit=10)
        self.assertGreaterEqual(result["count"], 1)
        for item in result["items"]:
            text = item["title"] + ",".join(item["tags"]) + item["description"]
            self.assertIn("支教", text)

    def test_search_excludes_closed(self) -> None:
        result = tools.search_activities(keyword="图书馆", limit=50)
        self.assertTrue(all(item["status"] == "open" for item in result["items"]))
        self.assertNotIn("A026", [item["activity_id"] for item in result["items"]])

    def test_activity_detail(self) -> None:
        detail = tools.get_activity_detail("A001")
        self.assertEqual(detail["title"], "社区长者手机课堂")
        self.assertIsInstance(detail["tags"], list)
        self.assertGreater(detail["remaining"], 0)

    def test_activity_detail_not_found(self) -> None:
        self.assertEqual(tools.get_activity_detail("A999")["error"]["code"], "NOT_FOUND")

    def test_volunteer_hours(self) -> None:
        result = tools.get_volunteer_hours("S001")
        self.assertEqual(result["total_hours"], 18.5)
        self.assertEqual(len(result["records"]), 6)
        self.assertEqual(result["term"], "2026-2027-1")

    def test_volunteer_hours_not_found(self) -> None:
        self.assertEqual(tools.get_volunteer_hours("S999")["error"]["code"], "NOT_FOUND")

    # ---------------------------- 冲突 ---------------------------- #

    def test_conflict_with_course(self) -> None:
        result = tools.check_schedule_conflict("S001", "A004")
        self.assertTrue(result["conflict"])
        self.assertEqual(result["items"][0]["type"], "course")
        self.assertEqual(result["items"][0]["name"], "数据结构")

    def test_no_conflict(self) -> None:
        result = tools.check_schedule_conflict("S001", "A001")
        self.assertFalse(result["conflict"])
        self.assertEqual(result["items"], [])

    def test_conflict_activity_not_found(self) -> None:
        result = tools.check_schedule_conflict("S001", "A999")
        self.assertEqual(result["error"]["code"], "NOT_FOUND")

    # ---------------------------- 报名 ---------------------------- #

    def test_enroll_rejects_conflict(self) -> None:
        result = tools.enroll_activity("S001", "A004")
        self.assertEqual(result["error"]["code"], "CONFLICT")

    def test_enroll_rejects_full(self) -> None:
        result = tools.enroll_activity("S001", "A005")
        self.assertEqual(result["error"]["code"], "FULL")

    def test_enroll_rejects_duplicate(self) -> None:
        result = tools.enroll_activity("S001", "A003")
        self.assertEqual(result["error"]["code"], "ALREADY_ENROLLED")

    def test_enroll_and_cancel(self) -> None:
        before = tools.get_activity_detail("A001")["remaining"]
        enrolled = tools.enroll_activity("S001", "A001")
        self.assertEqual(enrolled["status"], "confirmed")
        self.assertEqual(enrolled["remaining"], before - 1)

        cancelled = tools.cancel_enrollment(enrolled["enrollment_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["remaining"], before)

    def test_cancel_twice_is_idempotent(self) -> None:
        enrolled = tools.enroll_activity("S001", "A001")
        tools.cancel_enrollment(enrolled["enrollment_id"])
        again = tools.cancel_enrollment(enrolled["enrollment_id"])
        self.assertEqual(again["status"], "cancelled")
        self.assertIn("note", again)

    def test_cancel_not_found(self) -> None:
        self.assertEqual(tools.cancel_enrollment("E9999")["error"]["code"], "NOT_FOUND")

    # ---------------------------- 导出 ---------------------------- #

    def test_export_csv(self) -> None:
        result = tools.export_hours_csv("S001")
        self.assertEqual(result["rows"], 6)
        self.assertEqual(result["total_hours"], 18.5)
        target = self.tmp / "workspace" / "hours.csv"
        self.assertTrue(target.exists())
        raw = target.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(len(raw.decode("utf-8-sig").strip().splitlines()), 7)

    def test_export_rejects_outside_workspace(self) -> None:
        result = tools.export_hours_csv("S001", out_path="../escape.csv")
        self.assertEqual(result["error"]["code"], "INVALID_PATH")

    def test_export_rejects_non_csv(self) -> None:
        result = tools.export_hours_csv("S001", out_path="hours.txt")
        self.assertEqual(result["error"]["code"], "INVALID_PATH")


if __name__ == "__main__":
    unittest.main()
