"""执行过程面板的工具调用与结果配对测试。"""

from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, ToolMessage

from volunteer.agent import RunResult, VolunteerAgent


class StepPairingTest(unittest.TestCase):
    """模型并行发起多个工具时，结果应按 call_id 配对，而不是按返回顺序。"""

    def setUp(self) -> None:
        self.agent = VolunteerAgent.__new__(VolunteerAgent)
        self.result = RunResult()

    def test_parallel_results_match_call_id(self) -> None:
        self.agent._absorb({"model": {"messages": [AIMessage(
            content="",
            tool_calls=[
                {"name": "search_activities", "args": {"weekday": "周三"}, "id": "call_a"},
                {"name": "get_activity_detail", "args": {"activity_id": "A028"}, "id": "call_b"},
            ],
        )]}}, self.result)
        self.assertEqual([s.name for s in self.result.steps],
                         ["search_activities", "get_activity_detail"])

        self.agent._absorb({"tools": {"messages": [
            ToolMessage(content='{"activity_id": "A028"}', tool_call_id="call_b"),
            ToolMessage(content='{"items": []}', tool_call_id="call_a"),
        ]}}, self.result)

        self.assertEqual(self.result.steps[0].args, {"weekday": "周三"})
        self.assertEqual(self.result.steps[0].result, '{"items": []}')
        self.assertEqual(self.result.steps[1].args, {"activity_id": "A028"})
        self.assertEqual(self.result.steps[1].result, '{"activity_id": "A028"}')

    def test_unknown_call_id_falls_back_to_pending_step(self) -> None:
        self.agent._absorb({"model": {"messages": [AIMessage(
            content="",
            tool_calls=[{"name": "get_volunteer_hours", "args": {"student_id": "S001"}, "id": "call_x"}],
        )]}}, self.result)
        self.agent._absorb({"tools": {"messages": [
            ToolMessage(content='{"total_hours": 18.5}', tool_call_id="missing"),
        ]}}, self.result)

        self.assertEqual(self.result.steps[0].name, "get_volunteer_hours")
        self.assertEqual(self.result.steps[0].result, '{"total_hours": 18.5}')


if __name__ == "__main__":
    unittest.main()
