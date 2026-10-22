"""志愿星命令行业务工具（不依赖大模型，可独立使用）。

用途：
1. 作为路径 B 中“可独立使用的普通功能”，验证业务闭环；
2. 作为现场演示的兜底方案：模型或网络异常时仍能完成查询、报名、统计与导出；
3. 供 Agent 层对照工具的真实返回。

用法（仓库根目录）：
    python -m volunteer.cli search --weekday 周三 --limit 3
    python -m volunteer.cli detail A001
    python -m volunteer.cli hours S001
    python -m volunteer.cli conflict S001 A004
    python -m volunteer.cli enroll S001 A001
    python -m volunteer.cli cancel E1001 --yes
    python -m volunteer.cli export S001 --out hours.csv
    python -m volunteer.cli demo

任意子命令加 --json 可输出原始 JSON：
    python -m volunteer.cli --json hours S001
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

from data.seed import seed_database
from volunteer import tools_business as tools
from volunteer.config import ROOT

TERM = tools.TERM_DEFAULT
_JSON = False


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #

def _error_text(result: dict) -> str | None:
    err = result.get("error")
    if not err:
        return None
    return f"失败 [{err.get('code')}] {err.get('message')}"


def _print_json(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _emit(result: dict, show) -> bool:
    if _JSON:
        _print_json(result)
        return "error" not in result
    return show(result)


def _line(char: str = "-", width: int = 64) -> None:
    print(char * width)


def _show_search(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    if not result["items"]:
        print("没有符合条件的活动。可放宽星期、类别或关键词后重试。")
        return True
    for item in result["items"]:
        print(
            f"[{item['activity_id']}] {item['title']} | {item['category']} | "
            f"{item['date']} {item['weekday']} {item['start_time']}-{item['end_time']}"
        )
        print(
            f"      地点：{item['location']}　剩余：{item['remaining']}/{item['capacity']}　"
            f"认定：{item['credit_hours']} 小时　{'/'.join(item['tags'])}"
        )
    print(f"共 {result['count']} 条")
    return True


def _show_detail(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    print(f"{result['title']}（{result['activity_id']}）")
    print(f"类别：{result['category']}　时间：{result['date']} {result['weekday']} "
          f"{result['start_time']}-{result['end_time']}")
    print(f"地点：{result['location']}　组织方：{result['organizer']}")
    print(f"名额：{result['enrolled_count']}/{result['capacity']}，剩余 {result['remaining']}")
    print(f"认定时长：{result['credit_hours']} 小时　状态：{result['status']}")
    print(f"说明：{result['description']}")
    return True


def _show_hours(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    print(f"学生 {result['student_id']}　学期 {result['term']}　累计 {result['total_hours']} 小时")
    _line()
    for record in result["records"]:
        print(f"{record['date']}  {record['title']}（{record['activity_id']}）  {record['hours']} 小时")
    if not result["records"]:
        print("本学期暂无已认定记录。")
    return True


def _show_conflict(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    if not result["conflict"]:
        print(f"时间可用：{result['activity_id']} 与课表、已报名活动均不冲突。")
        return True
    print(f"发现冲突：{result['activity_id']}")
    for item in result["items"]:
        label = "课程" if item["type"] == "course" else "活动"
        print(f"  - {label}：{item['name']}　{item['weekday']} {item['start_time']}-{item['end_time']}")
    print(f"建议：{result['suggestion']}")
    return True


def _show_enroll(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        for item in result.get("conflicts", []):
            print(f"  - 冲突：{item['name']} {item['start_time']}-{item['end_time']}")
        return False
    print(f"报名成功：{result['enrollment_id']}　活动 {result['activity_id']}　"
          f"该活动剩余 {result['remaining']} 个名额")
    return True


def _show_cancel(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    note = f"（{result['note']}）" if result.get("note") else ""
    activity = result.get("activity_id", "—")
    remaining = result.get("remaining")
    tail = f"剩余 {remaining} 个名额" if remaining is not None else "名额未变化"
    print(f"已取消：{result['enrollment_id']}{note}　活动 {activity} {tail}")
    return True


def _show_export(result: dict) -> bool:
    message = _error_text(result)
    if message:
        print(message)
        return False
    print(f"已导出 {result['rows']} 条记录，合计 {result['total_hours']} 小时")
    print(f"文件：{result['path']}")
    return True


# --------------------------------------------------------------------------- #
# 命令
# --------------------------------------------------------------------------- #

def _confirm(prompt: str, yes: bool) -> bool:
    if yes:
        return True
    # isatty 在某些 Windows 终端/重定向下并不可靠，因此还要兜住 EOF 与中断
    try:
        if not sys.stdin.isatty():
            print("当前不是交互终端，如确认执行请加 --yes")
            return False
        answer = input(f"{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("当前不是交互终端，如确认执行请加 --yes")
        return False
    return answer in {"y", "yes"}


def cmd_search(args: argparse.Namespace) -> bool:
    return _emit(
        tools.search_activities(args.weekday, args.category, args.keyword, args.limit),
        _show_search,
    )


def cmd_detail(args: argparse.Namespace) -> bool:
    return _emit(tools.get_activity_detail(args.activity_id), _show_detail)


def cmd_hours(args: argparse.Namespace) -> bool:
    return _emit(tools.get_volunteer_hours(args.student_id, args.term), _show_hours)


def cmd_conflict(args: argparse.Namespace) -> bool:
    return _emit(
        tools.check_schedule_conflict(args.student_id, args.activity_id),
        _show_conflict,
    )


def cmd_enroll(args: argparse.Namespace) -> bool:
    detail = tools.get_activity_detail(args.activity_id)
    if "error" in detail:
        return _emit(detail, _show_detail)
    if not _JSON:
        print(f"即将报名：{detail['title']}（{detail['activity_id']}）　"
              f"{detail['date']} {detail['start_time']}-{detail['end_time']}　{detail['location']}")
    if not _confirm("确认报名该活动？", args.yes):
        print("已取消操作，未写入数据库。")
        return False
    return _emit(tools.enroll_activity(args.student_id, args.activity_id), _show_enroll)


def cmd_cancel(args: argparse.Namespace) -> bool:
    if not _confirm(f"确认取消报名 {args.enrollment_id}？", args.yes):
        print("已取消操作，未修改数据库。")
        return False
    return _emit(tools.cancel_enrollment(args.enrollment_id), _show_cancel)


def cmd_export(args: argparse.Namespace) -> bool:
    return _emit(
        tools.export_hours_csv(args.student_id, args.term, args.out),
        _show_export,
    )


def cmd_demo(args: argparse.Namespace) -> bool:
    """在临时数据库上跑完整闭环，不污染演示数据。"""
    sandbox = Path(tempfile.mkdtemp(prefix="volunteer-demo-"))
    demo_ws = ROOT / "workspace" / "demo"
    shutil.rmtree(demo_ws, ignore_errors=True)
    demo_ws.mkdir(parents=True, exist_ok=True)

    old_db = os.environ.get("VOLUNTEER_DB")
    old_ws = os.environ.get("WORKSPACE_DIR")
    try:
        db_file = sandbox / "demo.db"
        seed_database(db_file)
        os.environ["VOLUNTEER_DB"] = str(db_file)
        os.environ["WORKSPACE_DIR"] = str(demo_ws)

        ok = True
        print(f"演示学生：S001 陈晓雨　学期：{TERM}　（临时数据库，不修改演示数据）\n")

        print("步骤 1/6　检索周六的助老活动")
        ok &= _show_search(tools.search_activities(weekday="周六", category="助老", limit=3))
        _line()

        print("步骤 2/6　检查 A001 与课表是否冲突")
        ok &= _show_conflict(tools.check_schedule_conflict("S001", "A001"))
        _line()

        print("步骤 3/6　报名 A001")
        enrolled = tools.enroll_activity("S001", "A001")
        ok &= _show_enroll(enrolled)
        _line()

        print("步骤 4/6　汇总本学期时长")
        ok &= _show_hours(tools.get_volunteer_hours("S001"))
        _line()

        print("步骤 5/6　导出时长 CSV")
        ok &= _show_export(tools.export_hours_csv("S001"))
        _line()

        print("步骤 6/6　取消刚才的报名（恢复名额）")
        if enrolled.get("status") == "confirmed":
            ok &= _show_cancel(tools.cancel_enrollment(enrolled["enrollment_id"]))
        else:
            print("报名未成功，跳过取消。")
            ok = False

        _line("=")
        print("演示完成。" if ok else "演示中存在失败步骤，请查看上面的错误提示。")
        return ok
    finally:
        if old_db is None:
            os.environ.pop("VOLUNTEER_DB", None)
        else:
            os.environ["VOLUNTEER_DB"] = old_db
        if old_ws is None:
            os.environ.pop("WORKSPACE_DIR", None)
        else:
            os.environ["WORKSPACE_DIR"] = old_ws
        shutil.rmtree(sandbox, ignore_errors=True)


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m volunteer.cli",
        description="志愿星命令行业务工具（不依赖大模型）",
    )
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="检索开放活动")
    p.add_argument("--weekday", help="中文星期，如 周三")
    p.add_argument("--category", help="类别，如 助老")
    p.add_argument("--keyword", help="标题/标签关键词")
    p.add_argument("--limit", type=int, default=5, help="返回条数，默认 5")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("detail", help="活动详情")
    p.add_argument("activity_id")
    p.set_defaults(func=cmd_detail)

    p = sub.add_parser("hours", help="学期时长汇总")
    p.add_argument("student_id")
    p.add_argument("--term", default=TERM)
    p.set_defaults(func=cmd_hours)

    p = sub.add_parser("conflict", help="检查时间冲突")
    p.add_argument("student_id")
    p.add_argument("activity_id")
    p.set_defaults(func=cmd_conflict)

    p = sub.add_parser("enroll", help="报名活动（需确认）")
    p.add_argument("student_id")
    p.add_argument("activity_id")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    p.set_defaults(func=cmd_enroll)

    p = sub.add_parser("cancel", help="取消报名（需确认）")
    p.add_argument("enrollment_id")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("export", help="导出时长 CSV 到 workspace")
    p.add_argument("student_id")
    p.add_argument("--term", default=TERM)
    p.add_argument("--out", default="hours.csv", help="相对 workspace 的文件名")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("demo", help="在临时数据库上跑完整闭环")
    p.set_defaults(func=cmd_demo)

    return parser


def main() -> None:
    global _JSON
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args()
    _JSON = args.json
    try:
        ok = args.func(args)
    except FileNotFoundError as exc:
        print(exc)
        raise SystemExit(1) from exc
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
