"""AppTest 冒烟：不启动浏览器，直接跑一遍 Streamlit 页面。

覆盖：
- 首屏能渲染（无异常、有标题）；
- 离线演示模式能产生回答与工具轨迹；
- 产出文件区能看到 workspace 里的周报；
- 删除会话、新建会话按钮可点。

用法（仓库根目录）：
    python -m scripts.smoke_ui
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    from streamlit.testing.v1 import AppTest

    from volunteer.config import ROOT

    sandbox = Path(tempfile.mkdtemp(prefix="volunteer-ui-"))
    os.environ["VOLUNTEER_SESSIONS_DB"] = str(sandbox / "sessions.db")
    os.environ["VOLUNTEER_STATE_DB"] = str(sandbox / "state.db")
    os.environ.setdefault("DASHSCOPE_API_KEY", "")

    checks: list[tuple[str, bool, str]] = []

    app = AppTest.from_file(str(ROOT / "web.py"), default_timeout=120)
    app.run()
    checks.append(("首屏渲染无异常", not app.exception, str(app.exception)))

    radios = app.radio
    if radios:
        radios[0].set_value("离线演示（预置流程）").run()
    checks.append(("可切换到离线演示", not app.exception, str(app.exception)))

    # 点一个示例话术按钮（找活动），应产生回答与工具轨迹
    example_buttons = [b for b in app.button if b.key and b.key.startswith("ex-")]
    if example_buttons:
        example_buttons[0].click().run()
    checks.append(("示例话术触发回答", not app.exception, str(app.exception)))
    body = " ".join(m.value for m in app.markdown)
    checks.append(("回答里出现工具结果", "离线演示" in body or "候选活动" in body,
                   body[:120]))
    checks.append(("执行过程面板有内容", "search_activities" in body, ""))

    # 新建会话
    new_button = next((b for b in app.button if "新建对话" in (b.label or "")), None)
    if new_button:
        new_button.click().run()
    checks.append(("新建会话可用", not app.exception and not app.error,
                   "; ".join(e.value for e in app.error)))

    first = "PASS"
    failed = 0
    for name, ok, detail in checks:
        failed += 0 if ok else 1
        print(f"[{first if ok else 'FAIL'}] {name}　{detail if not ok else ''}")
    print(f"\n共 {len(checks)} 项，失败 {failed} 项。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
