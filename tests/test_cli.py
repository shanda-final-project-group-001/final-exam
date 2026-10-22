"""命令行层回归测试：人工确认的兜底与取消结果的展示。

这两个用例对应 2026-10-22 端到端演练中发现的真实缺陷：
1. 非交互环境（stdin 被重定向）下 `isatty()` 可能仍返回 True，`input()` 抛 EOFError，
   直接把英文堆栈甩给用户；
2. 重复取消时工具返回的字典缺 `activity_id` / `remaining`，CLI 取字段抛 KeyError。
"""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

from volunteer import cli


class ConfirmTest(unittest.TestCase):
    def test_non_tty_refuses_without_yes(self) -> None:
        fake_stdin = io.StringIO("y\n")
        with mock.patch.object(cli.sys, "stdin", fake_stdin):
            out = io.StringIO()
            with redirect_stdout(out):
                allowed = cli._confirm("确认报名该活动？", yes=False)
        self.assertFalse(allowed)
        self.assertIn("--yes", out.getvalue())
        self.assertNotIn("Traceback", out.getvalue())

    def test_eof_is_caught_and_refused(self) -> None:
        with mock.patch.object(cli.sys.stdin, "isatty", return_value=True), \
                mock.patch("builtins.input", side_effect=EOFError):
            out = io.StringIO()
            with redirect_stdout(out):
                allowed = cli._confirm("确认报名该活动？", yes=False)
        self.assertFalse(allowed)
        self.assertIn("--yes", out.getvalue())

    def test_yes_flag_skips_prompt(self) -> None:
        with mock.patch("builtins.input", side_effect=AssertionError("不该询问")):
            self.assertTrue(cli._confirm("确认？", yes=True))


class ShowCancelTest(unittest.TestCase):
    def test_legacy_payload_without_activity_id(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            ok = cli._show_cancel({"status": "cancelled", "enrollment_id": "E1041", "note": "该报名此前已取消"})
        self.assertTrue(ok)
        text = out.getvalue()
        self.assertIn("E1041", text)
        self.assertIn("名额未变化", text)

    def test_full_payload_prints_remaining(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            ok = cli._show_cancel(
                {"status": "cancelled", "enrollment_id": "E1041", "activity_id": "A001", "remaining": 10}
            )
        self.assertTrue(ok)
        self.assertIn("剩余 10 个名额", out.getvalue())


if __name__ == "__main__":
    unittest.main()
