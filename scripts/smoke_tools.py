"""工具层冒烟脚本：逐个人工调用并打印 JSON。

用法（仓库根目录）：
    python -m scripts.smoke_tools

注意：会创建一条报名并立即取消，重复运行结果一致。
"""

from __future__ import annotations

import json
import sys

from volunteer import tools_business as tools


def show(title: str, result: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    show("1. 检索周三活动（limit=3）", tools.search_activities(weekday="周三", limit=3))
    show("2. 活动详情 A001", tools.get_activity_detail("A001"))
    show("3. 时长汇总 S001", tools.get_volunteer_hours("S001"))
    show("4. 冲突检查 S001 / A004（应冲突）", tools.check_schedule_conflict("S001", "A004"))
    show("5. 冲突检查 S001 / A001（应可用）", tools.check_schedule_conflict("S001", "A001"))

    enrolled = tools.enroll_activity("S001", "A001")
    show("6. 报名 A001", enrolled)
    if enrolled.get("status") == "confirmed":
        show("7. 取消报名", tools.cancel_enrollment(enrolled["enrollment_id"]))
    else:
        print("\n（跳过取消：报名未成功，便于重复运行）")

    show("8. 导出时长 CSV", tools.export_hours_csv("S001"))


if __name__ == "__main__":
    main()
