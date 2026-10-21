"""志愿星智能体：模型接入、Deep Agent 组装、人工确认、子代理审阅、会话保存。

这一层是林至言负责的“编排层”。它只通过 `tools_business` 暴露的函数与数据交互，
不直接读写 SQLite 业务表，符合 `docs/team-plan.md` 第 3.3 节的边界约定。

分工速记（答辩时可以直接讲）：

| 关注点 | 实现位置 |
|---|---|
| 模型接入（OpenAI 兼容） | `build_model()` |
| 多步规划（write_todos） | Deep Agents 内置的 todo 中间件 |
| 能力来源 | 本地工具（写/导出）+ MCP 服务器（只读查询） |
| 流程知识 | `skills/` 下两个 Skill，按需由 `read_file` 读取 |
| 危险操作 | `enroll_activity` / `cancel_enrollment` 被包装成 `interrupt` 工具 |
| 长期记忆 | 仓库根目录 `AGENTS.md`，每轮拼进系统提示 |
| 会话保存 | SQLite checkpointer（`data/agent_state.db`）+ `sessions.py` 的聊天记录 |
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from . import tools_business as tools
from .config import DEFAULT_DB, ROOT, load_env, workspace_dir
from .sessions import state_db

TERM_DEFAULT = tools.TERM_DEFAULT
SKILLS_DIR = ROOT / "volunteer" / "skills"
AGENTS_FILE = ROOT / "AGENTS.md"
CONFIRM_PREFIX = "确认执行："

# 模型调用可能失败的异常类型。延迟导入，缺依赖时也能给出中文提示。
def _model_errors() -> tuple[type[BaseException], ...]:
    errors: list[type[BaseException]] = [TimeoutError, ConnectionError, OSError]
    try:
        import openai

        errors += [openai.APIError, openai.APIConnectionError, openai.APITimeoutError]
    except Exception:  # pragma: no cover - 未安装时忽略
        pass
    return tuple(errors)


class AgentConfigError(RuntimeError):
    """配置缺失（例如没有 Key），信息可直接展示给用户。"""


class AgentCallError(RuntimeError):
    """模型调用失败，保留原始异常便于排查。"""


# --------------------------------------------------------------------------- #
# 模型
# --------------------------------------------------------------------------- #

def model_settings() -> dict[str, str]:
    """读取并校验模型配置。缺 Key 时抛出中文提示。"""
    load_env()
    api_key = (os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    base_url = (os.getenv("OPENAI_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
    model = (os.getenv("MODEL_NAME") or "qwen3.7-plus").strip()
    temperature = (os.getenv("MODEL_TEMPERATURE") or "0.2").strip()
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "temperature": temperature,
    }


def config_problem() -> str | None:
    """返回人类可读的配置问题；配置正常时返回 None。"""
    settings = model_settings()
    if not settings["api_key"] or settings["api_key"].startswith("sk-your"):
        return ("未检测到模型 API Key。请把 `.env.example` 复制为 `.env`，"
                "并在 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` 填入自己的 Key；"
                "没有 Key 时可用“离线演示”模式查看预置结果。")
    if not DEFAULT_DB.exists():
        return "数据库不存在，请先在仓库根目录运行 `python -m data.seed`"
    return None


def build_model():
    """OpenAI 兼容接口；换平台或模型只改 `.env` 里的 BASE_URL 与 MODEL_NAME。"""
    from langchain_openai import ChatOpenAI

    settings = model_settings()
    if not settings["api_key"]:
        raise AgentConfigError(config_problem() or "缺少 API Key")
    try:
        temperature = float(settings["temperature"])
    except ValueError:
        temperature = 0.2

    kwargs: dict[str, Any] = dict(
        model=settings["model"],
        api_key=settings["api_key"],
        base_url=settings["base_url"],
        temperature=temperature,
        timeout=90,
        max_retries=1,
    )
    # 部分推理模型默认开启“思考”，会把工具调用的参数写进思维链导致调用为空，
    # 这里按需关闭；模型不支持该参数时自动降级。
    if os.getenv("MODEL_DISABLE_THINKING", "1") != "0":
        kwargs["extra_body"] = {"enable_thinking": False}
    try:
        return ChatOpenAI(**kwargs)
    except TypeError:  # pragma: no cover - 老版本 SDK
        kwargs.pop("extra_body", None)
        return ChatOpenAI(**kwargs)


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #

def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _safe_path(name: str, base: Path) -> Path | None:
    target = (base / name).resolve()
    return target if target.is_relative_to(base.resolve()) else None


def business_tools(confirmer: Callable[[dict[str, Any]], Any] | None = None) -> list[Any]:
    """返回 Agent 可用的 8 个业务工具（3 个经 MCP + 4 个本地 + 1 个写文件）。

    读工具由 `mcp_server.py` 里的同一个 `MCPServer` 实例导出：
    工具名、描述、参数 schema 全部来自 MCP 注册的那一份定义，
    所以 Agent 侧看到的就是“MCP 服务器暴露的能力”，与 `python -m volunteer.mcp_server`
    装进别的客户端时完全一致（答辩时可以现场对照 `mcp.list_tools()`）。

    Args:
        confirmer: 可选的外部确认回调（形如 `confirmer(payload) -> bool`）。
            提供时写操作先调它；不提供时在 LangGraph 图里用 `interrupt` 暂停。
            保留这个参数是为了在脚本 / 测试里复用同一套确认语义。
    """
    from langchain_core.tools import StructuredTool

    try:
        from .mcp_server import tool_specs

        read_specs = tool_specs()
        if not read_specs:
            raise RuntimeError("MCP 服务器未注册工具")
    except Exception:  # pragma: no cover - 缺 mcp 依赖时退回本地函数
        read_specs = [
            {"name": fn.__name__, "description": fn.__doc__ or "", "fn": fn}
            for fn in (tools.search_activities, tools.get_activity_detail,
                       tools.get_volunteer_hours)
        ]

    def _confirm(payload: dict[str, Any], summary: str) -> dict[str, Any] | None:
        """返回 None 表示继续执行；返回 dict 表示拒绝并把它当作工具结果。"""
        from langgraph.types import interrupt

        decision = bool(confirmer(payload)) if confirmer else interrupt(payload)
        if decision:
            return None
        return {"status": "cancelled", "note": f"用户取消了本次操作：{summary}"}

    def check_schedule_conflict(student_id: str, activity_id: str) -> dict[str, Any]:
        """检查活动是否与该学生的课表或已报名活动冲突（只读，直接返回结果）。"""
        return _jsonable(tools.check_schedule_conflict(student_id, activity_id))

    def enroll_activity(student_id: str, activity_id: str) -> dict[str, Any]:
        """为学生报名活动。会先暂停等待人工确认，用户确认后才写库。

        调用前应先调用 check_schedule_conflict 并阅读 activity-matching Skill 的规则。
        """
        detail = tools.get_activity_detail(activity_id)
        if "error" in detail:
            return _jsonable(detail)
        blocked = _confirm(
            {
                "action": "enroll",
                "title": f"报名「{detail['title']}」",
                "summary": (f"{detail['date']} {detail['weekday']} "
                            f"{detail['start_time']}-{detail['end_time']} · "
                            f"{detail['location']} · 认定 {detail['credit_hours']} 小时"),
                "student_id": student_id,
                "activity_id": activity_id,
                "detail": detail,
            },
            "报名",
        )
        if blocked is not None:
            return blocked
        return _jsonable(tools.enroll_activity(student_id, activity_id))

    def cancel_enrollment(enrollment_id: str) -> dict[str, Any]:
        """取消一条报名记录。会先暂停等待人工确认。"""
        blocked = _confirm(
            {
                "action": "cancel",
                "title": f"取消报名 {enrollment_id}",
                "summary": "取消后名额会释放给其他同学，再次报名需重新确认。",
                "enrollment_id": enrollment_id,
            },
            "取消报名",
        )
        if blocked is not None:
            return blocked
        return _jsonable(tools.cancel_enrollment(enrollment_id))

    def export_hours_csv(student_id: str, term: str = TERM_DEFAULT,
                         out_path: str = "hours.csv") -> dict[str, Any]:
        """把学生本学期志愿时长导出为 CSV，写入 workspace 目录。"""
        return _jsonable(tools.export_hours_csv(student_id, term, out_path))

    def write_file(path: str, content: str) -> dict[str, Any]:
        """把文本内容写入 workspace 内的文件（周报等产出物都用它）。

        Args:
            path: 相对 workspace 的路径，例如 "reports/weekly-report-2026-10-21.md"。
            content: 完整文件内容。
        """
        base = workspace_dir()
        target = _safe_path(path, base)
        if target is None:
            return {"error": {"code": "INVALID_PATH", "message": "只能写入 workspace 目录"}}
        if target.suffix.lower() not in {".md", ".txt", ".csv", ".json"}:
            return {"error": {"code": "INVALID_PATH", "message": "只允许写 .md/.txt/.csv/.json"}}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        try:
            shown = target.relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            shown = target.as_posix()
        return {"path": shown, "bytes": len(content.encode("utf-8"))}

    write_tool = StructuredTool.from_function(
        write_file,
        name="write_file",
        description=write_file.__doc__,
    )

    # 读工具直接沿用 MCP 服务器注册的那一份定义（名字、描述、参数 schema、底层函数），
    # Agent 侧看到的就是 `python -m volunteer.mcp_server` 装进别的客户端时的能力集合。
    converted_reads = [
        StructuredTool.from_function(spec["fn"], name=spec["name"],
                                     description=spec["description"])
        for spec in read_specs
    ]

    return [
        *converted_reads,
        StructuredTool.from_function(check_schedule_conflict),
        StructuredTool.from_function(enroll_activity),
        StructuredTool.from_function(cancel_enrollment),
        StructuredTool.from_function(export_hours_csv),
        write_tool,
    ]


def tool_names() -> list[str]:
    """给界面和测试用的工具清单（不构造模型）。"""
    return [item.name if hasattr(item, "name") else str(item) for item in business_tools()]


# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #

SYSTEM_PROMPT = """你是「志愿星」，校园志愿活动智能助手，服务对象是 {name}（{student_id}）。

## 你负责的闭环
找活动 → 查冲突 → 确认报名 → 汇总时长 → 生成周报。每一步都必须通过工具完成，
不允许凭印象回答活动编号、时间、名额或时长。

## 工具边界
- 只读查询（search_activities / get_activity_detail / get_volunteer_hours）来自 MCP 服务器 volunteer-data。
- 写操作（enroll_activity / cancel_enrollment）会暂停等待人工确认，确认前不要告诉用户“已报名成功”。
- export_hours_csv 与 write_file 只能写 workspace 目录。
- 工具返回 {{"error": {{"code", "message"}}}} 时，原样转述 code 与中文 message，不要编造替代结果。

## 流程知识
- 用户找活动时，先读取 `/volunteer/skills/activity-matching/SKILL.md`（read_file，limit=1000），
  按其中的评分与输出格式作答。
- 用户要周报或时长汇总时，先读取 `/volunteer/skills/volunteer-weekly-report/SKILL.md` 与
  `/volunteer/skills/volunteer-weekly-report/template.md`，再按模板写文件。
- 两个 Skill 的规则是硬约束：条数、评分、表格字段和页脚声明都不能自行删减。
- 文件工具用绝对虚拟路径：Skill 在 `/volunteer/skills/` 下，产出写 `/workspace/...`。

## 回答风格
- 简体中文，先给结论再给理由；推荐活动不超过 3 条，每条带 activity_id。
- 时间写法统一 `MM-DD 周X HH:MM-HH:MM`。
- 涉及时长认定规则时提示“以学校官方最新文件为准”。
- 不确定时先调用工具查证；查不到就说查不到，并给出可执行的下一步。

## 长期记忆
- 记忆内容只以 `/AGENTS.md` 的真实文本为准。复述或对比时，不得补写文件里没有的偏好、
  时段或历史；文件里没写就回答“没有记录”。
- 用户说“记住……”时，先用 read_file 读取原文，再用 edit_file 追加到「用户偏好」小节；
  只追加，不改写无关内容，并在回复里说明实际写入了哪几条。
{memory}
"""


# Deep Agents 0.7 自带 Skills / Memory 中间件，会把 SKILL.md 目录与 AGENTS.md 注入提示。
# 为了避免同一份内容出现两遍（既吃 token 又浪费上下文），默认交给中间件处理；
# 设置 VOLUNTEER_INLINE_MEMORY=1 可退回“自己拼进系统提示”的方式，方便对比讲解。
INLINE_MEMORY_ENV = "VOLUNTEER_INLINE_MEMORY"


DEFAULT_MEMORY = "（暂无用户偏好记录）"


def load_memory() -> str:
    """读取 AGENTS.md，作为长期记忆注入系统提示。"""
    if not AGENTS_FILE.exists():
        return DEFAULT_MEMORY
    text = AGENTS_FILE.read_text(encoding="utf-8").strip()
    return text or DEFAULT_MEMORY


def student_profile(student_id: str) -> dict[str, str]:
    """读取演示学生档案（姓名、兴趣、空闲时段），仅用于提示词，不写库。"""
    from .db import open_db

    try:
        with open_db() as conn:
            row = conn.execute(
                "SELECT name, major, interests, available_slots FROM students "
                "WHERE student_id = ?", (student_id,)
            ).fetchone()
    except FileNotFoundError:
        row = None
    if not row:
        return {"name": "同学", "student_id": student_id, "major": "", 
                "interests": "", "available_slots": ""}
    return {
        "name": row["name"],
        "student_id": student_id,
        "major": row["major"],
        "interests": row["interests"],
        "available_slots": row["available_slots"],
    }


def build_system_prompt(student_id: str) -> str:
    """组装系统提示：角色 + 工具边界 + 流程知识 + 学生档案（+ 可选的内联记忆）。"""
    profile = student_profile(student_id)
    inline = os.getenv(INLINE_MEMORY_ENV, "0") == "1"
    memory = load_memory() if inline else "（长期记忆由 Deep Agents 的 Memory 中间件从 /AGENTS.md 注入）"
    prompt = SYSTEM_PROMPT.format(
        name=profile["name"], student_id=student_id, memory=memory
    )
    if profile.get("interests") or profile.get("available_slots"):
        prompt += (f"\n当前学生档案：专业 {profile['major']}；兴趣 {profile['interests']}；"
                   f"常空时段 {profile['available_slots']}。")
    return prompt


def critic_instructions() -> str:
    return """你是周报审阅员（critic）。只做三件事：
1. 核对数字：概览总时长必须等于明细小时数之和，活动次数与明细行数一致。
2. 核对格式：每条明细都有活动编号、日期格式统一为 YYYY-MM-DD、页脚含“数据来源：本地演示样例数据”。
3. 找编造内容：排名、学分、评价、未查询过的活动编号，出现即为问题。

输出固定为两行：
结论：通过 / 需修改
问题：若通过写“无”；否则逐条列出“字段 + 问题 + 建议”，不超过 5 条。"""


# --------------------------------------------------------------------------- #
# 组装
# --------------------------------------------------------------------------- #

def build_agent(student_id: str = "S001", checkpointer: Any = None,
                subagents: bool = True, with_tools: bool = True):
    """创建 Deep Agent。

    Args:
        student_id: 当前演示账号，默认 S001。
        checkpointer: LangGraph 检查点保存器；传入 SqliteSaver 即可支持续聊。
        subagents: 是否挂载 critic 子代理（T3.3）。
        with_tools: 是否挂载业务工具。关掉用于纯提示词调试。
    """
    from deepagents import create_deep_agent
    from deepagents.backends.filesystem import FilesystemBackend
    from deepagents.middleware.filesystem import FilesystemPermission

    model = build_model()
    backend = FilesystemBackend(root_dir=str(ROOT), virtual_mode=True)

    agent_subagents = []
    if subagents:
        agent_subagents.append({
            "name": "report-critic",
            "description": "周报审阅员。写完周报后把草稿交给它核对数字与格式，再交给用户。",
            "system_prompt": critic_instructions(),
        })

    # 权限：业务产出只能写 workspace；AGENTS.md 单独放开写权限，用于积累长期偏好；
    # skills/ 只读；`.env` / `.venv` / 数据库显式拒绝，避免模型读到密钥或改业务数据。
    permissions = [
        FilesystemPermission(operations=["read", "write"], paths=["/workspace/**"], mode="allow"),
        FilesystemPermission(operations=["read", "write"], paths=["/AGENTS.md"], mode="allow"),
        FilesystemPermission(operations=["read"], paths=["/volunteer/skills/**"], mode="allow"),
        FilesystemPermission(operations=["read", "write"],
                             paths=["/.env", "/.env.*", "/.venv/**", "/data/**"],
                             mode="deny"),
        FilesystemPermission(operations=["read", "write"], paths=["/**"], mode="deny"),
    ]

    return create_deep_agent(
        model=model,
        tools=business_tools() if with_tools else [],
        system_prompt=build_system_prompt(student_id),
        subagents=agent_subagents,
        backend=backend,
        permissions=permissions,
        # 让 Deep Agents 自带的 Skill 机制发现两个 SKILL.md：它会把这些文件的路由
        # 写进提示词，模型再用 read_file 读取——这就是“Skill 何时被读取”的证据。
        skills=["/volunteer/skills/"],
        memory=["/AGENTS.md"],
        checkpointer=checkpointer,
        name="volunteer-agent",
    )


def sqlite_checkpointer():
    """SQLite 检查点：重启后同一个 thread 仍能续聊。"""
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    conn = sqlite3.connect(state_db(), check_same_thread=False)
    return SqliteSaver(conn)


# --------------------------------------------------------------------------- #
# 运行
# --------------------------------------------------------------------------- #

@dataclass
class Step:
    """执行过程面板的一行。"""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    ok: bool = True
    note: str = ""
    call_id: str = ""

    def summary(self, width: int = 80) -> str:
        text = self.result
        if isinstance(text, dict):
            if "error" in text:
                text = text["error"].get("message", "")
            elif "items" in text and "count" in text:
                text = f"{text['count']} 条候选"
            elif "conflict" in text:
                names = "、".join(item.get("name", "") for item in text.get("items", []))
                text = ("冲突：" + names) if text["conflict"] else "时间可用"
            elif "path" in text and "total_hours" in text:
                text = f"已写 {text['path']}，{text.get('rows', 0)} 条，合计 {text['total_hours']} 小时"
            elif "total_hours" in text:
                text = f"累计 {text['total_hours']} 小时，{len(text.get('records', []))} 条记录"
            elif "status" in text:
                text = "，".join(f"{k}={v}" for k, v in text.items()
                                 if k in {"status", "enrollment_id", "remaining", "note",
                                          "path", "rows", "total_hours"})
            else:
                text = json.dumps(text, ensure_ascii=False)
        elif not isinstance(text, str):
            text = json.dumps(text, ensure_ascii=False, default=str)
        text = " ".join(str(text).split())
        return text if len(text) <= width else text[:width] + "…"


@dataclass
class RunResult:
    """一轮对话的结果：最终文本 + 工具轨迹 + 待确认事项。"""

    text: str = ""
    steps: list[Step] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    interrupted: bool = False
    error: str | None = None

    def trace(self) -> list[dict[str, Any]]:
        items = []
        for step in self.steps:
            items.append({
                "name": step.name,
                "args": _jsonable(step.args),
                "summary": step.summary(),
                "ok": step.ok,
                "note": step.note,
            })
        return items


def _interrupt_payload(state: Any) -> dict[str, Any] | None:
    """从 LangGraph 状态里取出中断负载。"""
    for task in getattr(state, "tasks", ()) or ():
        for item in getattr(task, "interrupts", ()) or ():
            value = getattr(item, "value", None)
            if isinstance(value, dict):
                return value
    return None


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _tool_args(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and "input" in payload and isinstance(payload["input"], dict):
        return payload["input"]
    return payload if isinstance(payload, dict) else {}


class VolunteerAgent:
    """把 Deep Agent 包一层，给界面提供稳定的调用方式。"""

    def __init__(self, student_id: str = "S001", thread_id: str = "main",
                 checkpointer: Any = None) -> None:
        self.student_id = student_id
        self.thread_id = thread_id
        self._checkpointer = checkpointer
        self._agent: Any = None
        self._error: str | None = None

    # -- 生命周期 --------------------------------------------------------- #
    def ensure(self) -> Any:
        if self._agent is not None:
            return self._agent
        if self._error:
            raise AgentConfigError(self._error)
        problem = config_problem()
        if problem:
            self._error = problem
            raise AgentConfigError(problem)
        try:
            self._checkpointer = self._checkpointer or sqlite_checkpointer()
            self._agent = build_agent(self.student_id, self._checkpointer)
        except AgentConfigError:
            raise
        except Exception as exc:  # pragma: no cover - 依赖缺失
            self._error = f"智能体初始化失败：{type(exc).__name__}: {exc}"
            raise AgentConfigError(self._error) from exc
        return self._agent

    @property
    def config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    # -- 对话 ------------------------------------------------------------- #
    def send(self, text: str) -> RunResult:
        agent = self.ensure()
        return self._invoke(agent, {"messages": [{"role": "user", "content": text}]})

    def resume(self, approved: bool, note: str = "") -> RunResult:
        from langgraph.types import Command

        agent = self.ensure()
        payload = {"approved": approved, "note": note}
        return self._invoke(agent, Command(resume=payload))

    def pending(self) -> dict[str, Any] | None:
        """查看当前是否有等待确认的操作（重启后也能查到）。"""
        try:
            agent = self.ensure()
            return _interrupt_payload(agent.get_state(self.config))
        except Exception:
            return None

    def _invoke(self, agent: Any, payload: Any) -> RunResult:
        result = RunResult()
        try:
            for chunk in agent.stream(payload, config=self.config, stream_mode="updates"):
                self._absorb(chunk, result)
        except Exception as exc:  # 模型或网络异常
            result.error = self.friendly_error(exc)
            return result

        state = agent.get_state(self.config)
        pending = _interrupt_payload(state)
        result.pending = pending
        result.interrupted = pending is not None
        if not result.text and not result.interrupted and not result.error:
            result.text = self._last_ai_text(state)
        return result

    def _absorb(self, chunk: Any, result: RunResult) -> None:
        if not isinstance(chunk, dict):
            return
        for node, update in chunk.items():
            if not isinstance(update, dict):
                continue
            # 模型回答可能出现在任何节点，取最后一条非空文本
            for message in update.get("messages", []) or []:
                if type(message).__name__ in {"AIMessage", "AIMessageChunk"}:
                    text = _message_text(message).strip()
                    if text:
                        result.text = text
            for message in update.get("tools", []) or []:
                result.text = result.text  # 工具结果不进气泡
            messages = update.get("messages") or []
            for message in messages:
                kind = type(message).__name__
                if kind == "ToolMessage":
                    step = self._match_step(message, result.steps)
                    step.result = message.content
                    step.ok = '"error"' not in str(message.content)[:40]
                elif kind in {"AIMessage", "AIMessageChunk"}:
                    for call in getattr(message, "tool_calls", []) or []:
                        result.steps.append(Step(name=call.get("name", "?"),
                                                 args=_tool_args(call.get("args")),
                                                 call_id=call.get("id") or ""))

    @staticmethod
    def _match_step(message: Any, steps: list[Step]) -> Step:
        call_id = getattr(message, "tool_call_id", None)
        if call_id:
            for step in reversed(steps):
                if step.call_id == call_id:
                    return step
        for step in reversed(steps):
            if step.result is None:
                return step
        step = Step(name=getattr(message, "name", "tool"), note="未匹配到调用参数")
        steps.append(step)
        return step

    @staticmethod
    def _last_ai_text(state: Any) -> str:
        for message in reversed(getattr(state, "values", {}).get("messages", []) or []):
            if type(message).__name__ in {"AIMessage", "AIMessageChunk"}:
                text = _message_text(message).strip()
                if text:
                    return text
        return ""

    @staticmethod
    def friendly_error(exc: BaseException) -> str:
        if isinstance(exc, AgentConfigError):
            return str(exc)
        errors = _model_errors()
        if isinstance(exc, errors):
            return (f"模型调用失败（{type(exc).__name__}）。请检查网络、模型服务额度与 "
                    f"`.env` 中的模型名；也可以切到“离线演示”模式。")
        return f"执行出错（{type(exc).__name__}）：{exc}"


# --------------------------------------------------------------------------- #
# 离线演示
# --------------------------------------------------------------------------- #

def offline_scenario() -> list[dict[str, Any]]:
    """不依赖模型的预置演示：与前端四个话术一一对应。

    实现方式就是按顺序调用同 8 个工具，因此结果和在线模式完全一致，
    网络或额度异常时可以顶替现场演示。写操作一律不写库。

    Returns:
        [{"label", "name", "args", "result"}, ...]
    """
    items: list[dict[str, Any]] = []

    def add(label: str, name: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        items.append({"label": label, "name": name, "args": args, "result": result})

    search_args = {"weekday": "周三", "limit": 5}
    add("检索周三活动", "search_activities", search_args,
        tools.search_activities(**search_args))

    detail_args = {"activity_id": "A010"}
    add("查看推荐活动详情", "get_activity_detail", detail_args,
        tools.get_activity_detail(**detail_args))

    conflict_args = {"student_id": "S001", "activity_id": "A004"}
    add("检查运动会志愿与课表冲突", "check_schedule_conflict", conflict_args,
        tools.check_schedule_conflict(**conflict_args))

    add("报名需要人工确认，离线模式不写库", "enroll_activity",
        {"student_id": "S001", "activity_id": "A004"},
        {"status": "cancelled", "note": "离线演示不写库，在线模式下会弹出确认"})

    hours_args = {"student_id": "S001", "term": TERM_DEFAULT}
    add("汇总本学期时长", "get_volunteer_hours", hours_args,
        tools.get_volunteer_hours(**hours_args))

    csv_args = {"student_id": "S001", "term": TERM_DEFAULT, "out_path": "offline-hours.csv"}
    add("导出时长 CSV", "export_hours_csv", csv_args,
        tools.export_hours_csv(**csv_args))
    return items


def format_offline_report(hours: dict[str, Any], csv_path: str = "") -> str:
    """离线模式下用模板生成一份周报文本（不调用模型，规则与 Skill 一致）。"""
    template = (SKILLS_DIR / "volunteer-weekly-report" / "template.md").read_text(encoding="utf-8")
    records = hours.get("records", [])
    rows = "\n".join(
        f"| {index} | {item['date']} | {item['title']} | {item['activity_id']} | "
        f"{item['hours']} | {item['status']} |"
        for index, item in enumerate(records, start=1)
    ) or "| — | 暂无 | 暂无 | — | 0 | — |"
    categories = {item["title"].split("（")[0][:2] for item in records}
    dates = sorted(item["date"] for item in records)
    filled = (template
              .replace("{{student_id}}", hours.get("student_id", "S001"))
              .replace("{{term}}", hours.get("term", TERM_DEFAULT))
              .replace("{{date_range}}", f"{dates[0]} ~ {dates[-1]}" if dates else "暂无")
              .replace("{{generated_at}}", datetime.now().strftime("%Y-%m-%d %H:%M"))
              .replace("{{total_hours}}", str(hours.get("total_hours", 0)))
              .replace("{{activity_count}}", str(len(records)))
              .replace("{{category_count}}", str(len(categories)))
              .replace("{{max_hours}}", str(max((r["hours"] for r in records), default=0)))
              .replace("{{records_table}}", rows)
              .replace("{{summary}}", f"本学期共 {len(records)} 次活动，合计 "
                                      f"{hours.get('total_hours', 0)} 小时（离线预置结果）。")
              .replace("{{suggestions}}", "可继续在“找活动”中筛选开放活动，注意避开课表时间。")
              .replace("{{csv_path}}", csv_path or "未导出"))
    return filled


def save_report(text: str, name: str | None = None) -> Path:
    """写周报到 workspace/reports/，返回绝对路径。"""
    base = workspace_dir() / "reports"
    base.mkdir(parents=True, exist_ok=True)
    target = base / (name or f"weekly-report-{datetime.now():%Y-%m-%d}.md")
    target.write_text(text, encoding="utf-8")
    return target


def offline_answer() -> tuple[str, list[dict[str, Any]]]:
    """离线演示：返回（回答文本，步骤列表）。"""
    items = offline_scenario()
    hours = next(item["result"] for item in items if item["name"] == "get_volunteer_hours")
    csv_result = next(item["result"] for item in items if item["name"] == "export_hours_csv")
    report = format_offline_report(hours, csv_result.get("path", ""))
    path = save_report(report)

    search = next(item["result"] for item in items if item["name"] == "search_activities")
    lines = ["（离线演示：未调用大模型，以下由预置流程调用同一批工具得到，数据真实可核对。）", ""]
    if search.get("items"):
        lines.append("周三开放的候选活动：")
        for row in search["items"][:3]:
            lines.append(f"- [{row['activity_id']}] {row['title']} "
                         f"{row['date'][5:]} {row['weekday']} "
                         f"{row['start_time']}-{row['end_time']}，余 {row['remaining']}/{row['capacity']}")
    conflict = next(item["result"] for item in items if item["name"] == "check_schedule_conflict")
    if conflict.get("conflict"):
        names = "、".join(entry["name"] for entry in conflict["items"])
        lines.append(f"\nA004 与课表冲突：{names}，因此没有直接报名。")
    lines.append(f"\n本学期已认定 {hours.get('total_hours')} 小时，共 {len(hours.get('records', []))} 条记录，"
                 f"周报已写入 `{path.relative_to(ROOT).as_posix()}`。")
    steps = [{"name": item["name"], "args": item["args"],
              "summary": Step(name=item["name"], result=item["result"]).summary(),
              "ok": "error" not in str(item["result"])[:20], "note": item["label"]}
             for item in items]
    return "\n".join(lines), steps


# --------------------------------------------------------------------------- #
# 自检（命令行）
# --------------------------------------------------------------------------- #

def _main(argv: list[str] | None = None) -> int:
    import argparse

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(prog="python -m volunteer.agent",
                                     description="志愿星智能体自检")
    parser.add_argument("--tools", action="store_true", help="只打印工具清单")
    parser.add_argument("--offline", action="store_true", help="运行离线演示流程")
    parser.add_argument("--ask", help="向智能体提一个问题（需要 .env 中的 Key）")
    args = parser.parse_args(argv)

    if args.tools:
        for name in tool_names():
            print(f"- {name}")
        return 0
    if args.offline:
        text, steps = offline_answer()
        print(text)
        print("\n工具调用：")
        for step in steps:
            print(f"  {step['name']} {step['args']} -> {step['summary']}")
        return 0
    if args.ask:
        agent = VolunteerAgent()
        result = agent.send(args.ask)
        print(result.text)
        if result.pending:
            print(f"\n[待确认] {result.pending.get('title')}")
        if result.error:
            print(f"\n[错误] {result.error}")
            return 1
        print("\n工具调用：")
        for step in result.steps:
            print(f"  {step.name} {step.args} -> {step.summary()}")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
