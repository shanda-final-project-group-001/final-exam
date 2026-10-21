"""志愿星 Streamlit 界面。

启动（仓库根目录）：
    streamlit run web.py

界面分三块，与 `docs/team-plan.md` 阶段 5 的任务一一对应：
- 左侧栏：会话历史（T5.3）、演示话术（T5.5）、运行模式；
- 主区域：对话与流式输出（T5.1）+ 执行过程面板（T5.2）；
- 主区域下方：报名 / 取消的确认按钮（T5.4），未确认不会写库。

模型不可用（无 Key、断网、额度用尽）时可以切到“离线演示”，
用同一批工具跑预置流程，保证现场能演示（对应 T7.4 的兜底要求）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

from volunteer import tools_business as tools
from volunteer.agent import (
    AgentConfigError,
    VolunteerAgent,
    config_problem,
    model_settings,
    offline_answer,
    tool_names,
)
from volunteer.config import ROOT
from volunteer.sessions import SessionStore

EXAMPLES = [
    ("找活动", "我周三晚上有空，帮我找 2 个适合我的志愿活动，说说推荐理由。"),
    ("查冲突后报名", "帮我报名秋季运动会志愿保障，先看看会不会和课表冲突。"),
    ("时长汇总", "帮我查一下这学期已经认定的志愿时长。"),
    ("生成周报", "把这学期志愿时长汇总成周报，导出 CSV，写到 workspace 里。"),
    ("失败提示", "帮我报名 A999。"),
    ("取消报名", "取消我刚才的报名。"),
]

STATUS_TEXT = {
    "NOT_FOUND": "没找到",
    "CONFLICT": "时间冲突",
    "FULL": "名额已满",
    "ALREADY_ENROLLED": "已经报过名",
    "CLOSED": "报名已截止",
    "INVALID_PATH": "路径不合法",
}


# --------------------------------------------------------------------------- #
# 基础设置
# --------------------------------------------------------------------------- #

def page_config() -> None:
    st.set_page_config(
        page_title="志愿星 · 校园志愿活动智能助手",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container{padding-top:2.2rem;max-width:1180px}
        .vx-hero{padding:18px 22px;border-radius:14px;background:linear-gradient(120deg,#0f3d2e,#1f5c3f 60%,#2f6b3a);
          color:#eaf7ef;margin-bottom:14px}
        .vx-hero h1{margin:0;font-size:26px;color:#fff}
        .vx-hero p{margin:6px 0 0;font-size:14px;color:#cfe8da}
        .vx-hero.warn{background:linear-gradient(120deg,#7a4a00,#a86b13)}
        .vx-pill{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;
          background:rgba(255,255,255,.14);color:#eaf7ef;margin-right:8px}
        .vx-step{border-left:3px solid #d8dee4;padding:2px 0 2px 12px;margin:6px 0}
        .vx-step.ok{border-color:#2f9e44}
        .vx-step.err{border-color:#e03131}
        .vx-step code{font-size:12px}
        .vx-small{color:#6b7280;font-size:12px}
        .vx-trace{border-left:2px solid #d8dee4;margin:4px 0 4px 2px;padding-left:12px}
        .vx-trace .row{display:flex;gap:8px;align-items:baseline;padding:3px 0;flex-wrap:wrap}
        .vx-tag{font-family:ui-monospace,consolas,monospace;font-size:12px;background:#eef6f0;
          color:#1f6b3f;border-radius:4px;padding:1px 6px}
        .vx-args{font-size:11px;color:#8a8f98;word-break:break-all}
        .vx-ret{font-size:12px;color:#4b5563}
        .vx-note{font-size:11px;color:#b06a00}
        </style>
        """,
        unsafe_allow_html=True,
    )


def store() -> SessionStore:
    if "store" not in st.session_state:
        st.session_state.store = SessionStore()
    return st.session_state.store


def ensure_session() -> str:
    """保证当前有一个会话；首次进入自动建一个“新对话”。"""
    st_ = st.session_state
    db = store()
    if "thread_id" not in st_ or db.get(st_.thread_id) is None:
        existing = db.list()
        if existing:
            st_.thread_id = existing[0]["thread_id"]
        else:
            st_.thread_id = db.create("新对话")
    return st_.thread_id


def get_agent() -> VolunteerAgent:
    st_ = st.session_state
    thread_id = ensure_session()
    if st_.get("agent_thread") != thread_id:
        st_.agent = VolunteerAgent(student_id="S001", thread_id=thread_id)
        st_.agent_thread = thread_id
        st_.pending = None
    return st_.agent


# --------------------------------------------------------------------------- #
# 侧边栏：会话历史 + 话术 + 模式
# --------------------------------------------------------------------------- #

def sidebar() -> dict[str, object]:
    db = store()
    current = ensure_session()

    with st.sidebar:
        st.markdown("### 🛰️ 志愿星")
        st.caption("校园志愿活动智能助手 · 演示账号 S001 陈晓雨")

        st.markdown("**运行模式**")
        mode = st.radio(
            "运行模式",
            ["在线（百炼模型）", "离线演示（预置流程）"],
            index=0 if not config_problem() else 1,
            label_visibility="collapsed",
            help="在线模式需要 .env 中的百炼 Key；离线模式不调用模型，直接用同一批工具跑预置流程。",
        )

        problem = config_problem()
        if problem:
            st.warning(problem, icon="⚠️")
        else:
            settings = model_settings()
            st.caption(f"模型：{settings['model']}")

        st.divider()
        st.markdown("**会话历史**")
        if st.button("＋ 新建对话", use_container_width=True, type="primary"):
            st.session_state.thread_id = db.create("新对话")
            st.session_state.pending = None
            st.session_state.pop("agent", None)
            st.rerun()

        sessions = db.list()
        if not sessions:
            st.caption("还没有对话，点上面的按钮开始。")
        for item in sessions:
            active = item["thread_id"] == current
            col_title, col_del = st.columns([0.82, 0.18])
            label = f"{'● ' if active else ''}{item['title']}"
            if col_title.button(label, key=f"sess-{item['thread_id']}",
                                use_container_width=True,
                                type="secondary" if not active else "primary"):
                st.session_state.thread_id = item["thread_id"]
                st.session_state.pending = None
                st.session_state.pop("agent", None)
                st.rerun()
            if col_del.button("🗑", key=f"del-{item['thread_id']}", help="删除这条会话"):
                db.delete(item["thread_id"])
                if active:
                    st.session_state.pop("thread_id", None)
                    st.session_state.pop("agent", None)
                st.rerun()

        st.divider()
        st.markdown("**演示话术**")
        clicked = None
        for title, text in EXAMPLES:
            if st.button(f"· {title}", key=f"ex-{title}", use_container_width=True):
                clicked = text
        with st.expander("我用到的工具", expanded=False):
            for name in tool_names():
                st.markdown(f"- `{name}`")

    return {"mode": mode, "clicked": clicked}


# --------------------------------------------------------------------------- #
# 执行过程面板
# --------------------------------------------------------------------------- #

def render_steps(trace: list[dict]) -> None:
    if not trace:
        st.caption("本轮没有工具调用。若你期望它查数据，请换个说法再试（例如带上星期或活动名）。")
        return
    rows = []
    for index, step in enumerate(trace, start=1):
        marker = "" if step.get("ok", True) else "⚠️ "
        args = json.dumps(step.get("args", {}), ensure_ascii=False)
        note = (f"<span class='vx-note'>· {step['note']}</span>" if step.get("note") else "")
        rows.append(
            f"<div class='row'><span class='vx-small'>{index:02d}</span>"
            f"<span class='vx-tag'>{_escape(step.get('name', ''))}</span>"
            f"<span class='vx-args'>{_escape(args)}</span>{note}</div>"
            f"<div class='vx-ret'>{marker}{_escape(str(step.get('summary', '')))}</div>"
            f"<div style='border-bottom:1px dashed #e5e7eb;margin:6px 0'></div>"
        )
    st.markdown(f"<div class='vx-trace'>{''.join(rows)}</div>", unsafe_allow_html=True)


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def workspace_files() -> list[Path]:
    base = ROOT / "workspace"
    if not base.exists():
        return []
    files = [p for p in base.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:8]


def render_files() -> None:
    files = workspace_files()
    if not files:
        st.caption("workspace 里还没有产出文件。让它生成周报或导出 CSV 试试。")
        return
    for path in files:
        st.download_button(
            label=f"⬇ {path.relative_to(ROOT).as_posix()}",
            data=path.read_bytes(),
            file_name=path.name,
            key=f"dl-{path.as_posix()}",
        )


# --------------------------------------------------------------------------- #
# 确认面板
# --------------------------------------------------------------------------- #

def render_confirm() -> None:
    pending = st.session_state.get("pending")
    if not pending:
        return
    title = pending.get("title", "待确认操作")
    st.markdown(
        f"<div class='vx-hero' style='background:linear-gradient(120deg,#7a4a00,#a86b13)'>"
        f"<h1>⚠️ 需要你确认：{title}</h1>"
        f"<p>{pending.get('summary','')}</p></div>",
        unsafe_allow_html=True,
    )
    col_ok, col_no, _ = st.columns([1, 1, 3])
    if col_ok.button("确认执行", type="primary", use_container_width=True, key="confirm-yes"):
        run(lambda agent: agent.resume(True))
    if col_no.button("取消操作", use_container_width=True, key="confirm-no"):
        run(lambda agent: agent.resume(False))


# --------------------------------------------------------------------------- #
# 运行一轮
# --------------------------------------------------------------------------- #

def save_turn(role: str, content: str, trace: list[dict] | None = None) -> None:
    db = store()
    db.add_message(st.session_state.thread_id, role, content, trace)
    if role == "user":
        db.auto_title(st.session_state.thread_id, content)


def run(call) -> None:
    """调用智能体并把结果落到会话里；所有异常都转成中文提示。"""
    thread_id = ensure_session()
    agent = get_agent()
    placeholder = st.empty()
    with placeholder.container():
        st.info("正在执行：规划 → 调用工具 → 组织回答……", icon="⏳")
    try:
        result = call(agent)
    except AgentConfigError as exc:
        placeholder.empty()
        st.error(str(exc), icon="🔑")
        return
    except Exception as exc:  # 兜底：不把英文堆栈丢给用户
        placeholder.empty()
        st.error(f"执行出错：{type(exc).__name__}：{exc}", icon="❌")
        return
    placeholder.empty()

    if result.error:
        st.error(result.error, icon="❌")
        save_turn("assistant", f"【执行失败】{result.error}", result.trace())
    elif result.interrupted and result.pending:
        st.session_state.pending = result.pending
        note = result.text or f"需要确认后才会执行：{result.pending.get('title')}"
        save_turn("assistant", note, result.trace())
    else:
        st.session_state.pending = None
        text = result.text or "（模型没有给出文本，请查看执行过程面板）"
        save_turn("assistant", text, result.trace())

    st.session_state.last_trace = result.trace()
    st.rerun()


def submit(text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    save_turn("user", text)
    st.session_state.last_trace = []
    if st.session_state.get("mode") == "离线演示（预置流程）":
        answer, trace = offline_answer()
        save_turn("assistant", answer, trace)
        st.session_state.last_trace = trace
        st.rerun()
        return
    run(lambda agent: agent.send(text))


# --------------------------------------------------------------------------- #
# 主界面
# --------------------------------------------------------------------------- #

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    page_config()
    controls = sidebar()
    st.session_state.mode = controls["mode"]

    st.markdown(
        "<div class='vx-hero'>"
        "<h1>志愿星 · 校园志愿活动智能助手</h1>"
        "<p><span class='vx-pill'>找活动</span><span class='vx-pill'>查冲突</span>"
        "<span class='vx-pill'>确认报名</span><span class='vx-pill'>汇总时长</span>"
        "<span class='vx-pill'>生成周报</span></p>"
        "<p>一句话说需求，智能体自己规划步骤并调用工具；涉及写库的操作会先停下来问你。</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    thread_id = ensure_session()
    db = store()
    messages = db.messages(thread_id)
    agent = get_agent()

    # 刷新或切换会话后，把图里仍挂起的确认恢复出来
    if not st.session_state.get("pending") and st.session_state.get("mode") != "离线演示（预置流程）":
        try:
            st.session_state.pending = agent.pending()
        except AgentConfigError:
            pass

    chat_col, side_col = st.columns([0.66, 0.34], gap="large")

    with chat_col:
        if not messages:
            st.info("这里还是空的。可以点左侧的话术，或直接问：“我周三晚上有空，有哪些志愿活动？”", icon="💬")
        for index, message in enumerate(messages):
            with st.chat_message("user" if message["role"] == "user" else "assistant"):
                st.markdown(message["content"])
                if message["role"] == "assistant" and message["trace"]:
                    with st.expander(f"执行过程 · {len(message['trace'])} 步", expanded=(index == len(messages) - 1)):
                        render_steps(message["trace"])
        render_confirm()
        prompt = st.chat_input("说说你的需求，例如：周三晚上有什么助老活动？")
        if controls["clicked"]:
            submit(controls["clicked"])
        elif prompt:
            submit(prompt)

    with side_col:
        st.markdown("#### 执行过程")
        trace = st.session_state.get("last_trace") or (messages[-1]["trace"] if messages else [])
        if trace:
            render_steps(trace)
        else:
            st.caption("发起一轮对话后，这里会逐步显示工具名、参数与返回摘要。")

        st.divider()
        st.markdown("#### 产出文件")
        render_files()

        st.divider()
        st.markdown("#### 数据自检")
        if st.button("跑一遍业务工具", use_container_width=True):
            checks = {
                "开放活动数": tools.search_activities(limit=50)["count"],
                "S001 时长": tools.get_volunteer_hours("S001")["total_hours"],
                "A005 剩余": tools.get_activity_detail("A005")["remaining"],
                "A999 返回": tools.get_activity_detail("A999").get("error", {}).get("code"),
            }
            for key, value in checks.items():
                label = STATUS_TEXT.get(str(value), str(value))
                st.write(f"- {key}：`{label}`")


if __name__ == "__main__":
    main()
