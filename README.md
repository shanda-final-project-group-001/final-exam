# 志愿星 · 校园志愿活动智能助手

《开源 AI 技术实践》期末项目。面向在校学生与院系青协，用自然语言完成“找活动 → 查冲突 → 确认报名 → 汇总时长 → 生成周报”的闭环。

- 选题路径：**路径 A（技术栈完整）**，业务侧按路径 B 组织
- 小组：林至言（f25011330）、朱煜杰（f25011243）
- 当前状态：数据 / 工具 / Agent / Skills / Streamlit 界面全部完成，可通过离线演示在无 Key 环境下完整跑通

## 技术栈

| 层次 | 选型 | 负责人 |
|---|---|---|
| 数据与工具 | SQLite、Python 标准库、MCP Python SDK | 朱煜杰 |
| 模型 | 阿里百炼（OpenAI 兼容接口） | 林至言 |
| Agent 框架 | LangChain Deep Agents（含 Skills / Memory / 子代理） | 林至言 |
| 界面 | Streamlit（流式对话 + 执行过程面板 + 会话历史） | 林至言 |
| 产出物 | Markdown 周报、CSV 时长表（写入 `workspace/`） | 共同 |

## 目录结构

```text
final-exam/
├─ data/                  # 建表 SQL、虚构样例数据与初始化脚本
│  ├─ schema.sql
│  ├─ seed.py
│  ├─ volunteer_demo.db   # 业务库（seed 生成，不提交）
│  ├─ volunteer_sessions.db  # 聊天记录（界面用，不提交）
│  └─ agent_state.db      # LangGraph 检查点（续聊用，不提交）
├─ volunteer/             # 业务代码
│  ├─ config.py           # 路径与环境变量
│  ├─ db.py               # SQLite 连接与统一错误结构
│  ├─ tools_business.py   # 7 个业务工具（3 读 + 3 写 + 1 导出）
│  ├─ cli.py              # 独立命令行工具（不依赖大模型）
│  ├─ mcp_server.py       # MCP 服务器 volunteer-data（3 个只读工具）
│  ├─ agent.py            # 智能体：模型接入、Deep Agent、人工确认、离线演示
│  ├─ sessions.py         # 会话与消息持久化
│  └─ skills/             # 两个 Skill
│     ├─ activity-matching/SKILL.md
│     └─ volunteer-weekly-report/{SKILL.md,template.md}
├─ scripts/
│  ├─ smoke_tools.py      # 工具冒烟脚本
│  └─ check_data.py       # 演示数据完整性检查
├─ tests/test_tools.py    # 工具层单元测试
├─ workspace/             # 运行产出（不提交）
├─ web.py                 # Streamlit 界面入口
├─ AGENTS.md              # 长期记忆（只存偏好，不存个人信息）
├─ docs/
│  ├─ team-plan.md        # 分工与协作方案
│  └─ test-plan.md        # 测试用例表
└─ presentation/          # HTML 汇报幻灯片
```

## 环境要求

- Python 3.10 及以上（开发环境为 3.13）
- Windows PowerShell 或 CMD

## 安装与启动

```powershell
# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
python -m pip install -r requirements.txt

# 3. 配置模型（复制后填入自己的百炼 Key）
Copy-Item .env.example .env
notepad .env

# 4. 生成虚构演示数据（会创建 data/volunteer_demo.db）
python -m data.seed

# 5. 冒烟：逐个调用工具并打印 JSON
python -m scripts.smoke_tools

# 6. 数据完整性检查（汇报前自检）
python -m scripts.check_data

# 7. 命令行走完整业务闭环（临时数据库，不污染演示数据）
python -m volunteer.cli demo

# 7. 运行工具层测试
python -m unittest discover -s tests -v
python -m scripts.check_agent
python -m scripts.smoke_ui

# 9. 不启动界面，直接在终端跑一遍离线演示流程
python -m volunteer.agent --offline

# 10. 启动界面
streamlit run web.py
```

> 第一次用 `streamlit` 若提示找不到命令，用 `.\.venv\Scripts\python.exe -m streamlit run web.py` 效果相同。
> 没有 Key 也能演示：界面左侧把“运行模式”切到 **离线演示（预置流程）**，它会用同一批工具跑预置流程并真实写出周报。

启动 MCP 服务器（stdio）：

```powershell
python -m volunteer.mcp_server
```

在支持 MCP 的客户端中配置：

```json
{
  "mcpServers": {
    "volunteer-data": {
      "command": "python",
      "args": ["-m", "volunteer.mcp_server"],
      "cwd": "<仓库根目录>"
    }
  }
}
```

> 注意：MCP 使用 stdio 传输，服务器不会向 stdout 打印日志；调试信息请写 stderr。

## 命令行工具（不依赖大模型）

`volunteer/cli.py` 把同一套业务能力做成可独立使用的命令行，用于路径 B 的“普通功能”验证，也是模型或网络异常时的演示兜底。

```powershell
python -m volunteer.cli search --weekday 周三 --limit 3
python -m volunteer.cli detail A001
python -m volunteer.cli hours S001
python -m volunteer.cli conflict S001 A004
python -m volunteer.cli enroll S001 A001          # 交互确认
python -m volunteer.cli enroll S001 A001 --yes    # 跳过确认
python -m volunteer.cli cancel E1001 --yes
python -m volunteer.cli export S001 --out hours.csv
python -m volunteer.cli --json hours S001         # 输出原始 JSON
python -m volunteer.cli demo                      # 临时库跑完整六步闭环
```

危险操作默认要求确认；非交互环境必须显式加 `--yes`。

## 工具清单

| 工具 | 类型 | 说明 |
|---|---|---|
| `search_activities(weekday, category, keyword, limit)` | 读 / MCP | 按星期、类别、关键词检索开放活动，返回剩余名额 |
| `get_activity_detail(activity_id)` | 读 / MCP | 活动详情与剩余名额 |
| `get_volunteer_hours(student_id, term)` | 读 / MCP | 学期时长汇总与明细 |
| `check_schedule_conflict(student_id, activity_id)` | 写前校验 | 课表与已报名活动的时间冲突 |
| `enroll_activity(student_id, activity_id)` | 写（需确认） | 事务内报名，拒绝冲突 / 满员 / 重复 |
| `cancel_enrollment(enrollment_id)` | 写（需确认） | 取消报名，幂等 |
| `export_hours_csv(student_id, term, out_path)` | 产出 | 写入 `workspace/`，UTF-8-SIG 编码 |
| `write_file(path, content)` | 产出（编排层） | 写周报等 Markdown，只允许 `workspace/` |

前三个在 `volunteer/mcp_server.py` 中注册；`agent.py` 直接读取 MCP 服务器注册的那一份定义挂到模型上，
所以“Agent 用的读工具”和“别的 MCP 客户端看到的工具”是同一套（`python -m volunteer.agent --tools` 可查看）。

错误统一返回：

```json
{"error": {"code": "CONFLICT", "message": "时间冲突：数据结构"}}
```

错误码：`NOT_FOUND`、`CONFLICT`、`FULL`、`ALREADY_ENROLLED`、`CLOSED`、`INVALID_PATH`。

## 智能体与 Skill

```powershell
python -m volunteer.agent --tools            # 打印挂载的工具清单
python -m volunteer.agent --ask "我周三晚上有空，有哪些活动"   # 需要 Key
python -m volunteer.agent --offline          # 不需要 Key，跑预置流程并写周报
```

| 组件 | 位置 | 作用 |
|---|---|---|
| 系统提示 | `volunteer/agent.py` 的 `SYSTEM_PROMPT` | 角色、工具边界、回答风格；每轮拼上学生档案 |
| Skills | `volunteer/skills/**` | 由 Deep Agents 的 Skills 中间件发现并写进提示词，模型需要时才 `read_file` 读取 |
| 子代理 critic | `critic_instructions()` | 写完周报后交由它核对数字与格式（固定输出“结论 / 问题”两行） |
| 长期记忆 | `AGENTS.md` | Memory 中间件自动注入；只放偏好，不放个人信息 |
| 人工确认 | `enroll_activity` / `cancel_enrollment` | 工具内部 `interrupt`，界面点“确认执行”才继续 |
| 文件权限 | `build_agent()` 的 `permissions` | 只写 `/workspace/**`；`.env`、`.venv`、`data/` 禁读写 |
| 会话 | `data/agent_state.db` + `data/volunteer_sessions.db` | 前者是 LangGraph 检查点（续聊），后者是聊天记录（历史列表） |

两个 Skill 的差别（答辩常问）：

- `activity-matching`：**怎么挑**——硬条件过滤、五维评分、输出模板。
- `volunteer-weekly-report`：**怎么写**——章节顺序、数字来源、自检清单、页脚声明。
- 系统提示负责“必须调用工具、不能编造”这类**行为约束**；Skill 负责“业务规则与写作规范”这类**知识**，
  体积大、只在相应场景读取，不占每一轮的上下文。

## 演示话术（5 条）

| # | 话术 | 预期看到的工具链 |
|---|---|---|
| 1 | 我周三晚上有空，帮我找 2 个适合我的志愿活动 | `read_file(SKILL.md)` → `search_activities(weekday=周三)` → `get_activity_detail` |
| 2 | 帮我报名秋季运动会志愿保障，先看看会不会和课表冲突 | `check_schedule_conflict(A004)` → `enroll_activity` ⟶ **暂停等确认** |
| 3 | 帮我报名 A999 | `get_activity_detail(A999)` → 转述 `NOT_FOUND`，不编造活动 |
| 4 | 把这学期志愿时长汇总成周报，导出 CSV | `get_volunteer_hours` → `export_hours_csv` → `read_file(template.md)` → `write_file` → `task(report-critic)` |
| 5 | 取消我刚才的报名 | `cancel_enrollment` ⟶ **暂停等确认**；确认后名额恢复 |

失败提示演示：说“报名晚自习陪伴辅导（A005）”，会得到 `FULL` 的中文提示，不写库。

## 配置

复制 `.env.example` 为 `.env`，填入自己的百炼 Key。`.env` 已被 `.gitignore` 排除，**不要提交**。

| 变量 | 必填 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | 是 | 百炼 Key（`sk-...`）；也接受 `OPENAI_API_KEY` |
| `OPENAI_BASE_URL` | 否 | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `MODEL_NAME` | 否 | 默认 `qwen3.7-plus`；换模型只改这一行 |
| `MODEL_TEMPERATURE` | 否 | 默认 `0.2`，演示时保持低温度更稳定 |
| `MODEL_DISABLE_THINKING` | 否 | 默认 `1`，关闭推理模型的“思考”开关，避免工具参数被写进思维链 |
| `VOLUNTEER_DB` | 否 | 业务库路径，默认 `data/volunteer_demo.db` |
| `WORKSPACE_DIR` | 否 | 产出目录，默认 `workspace` |
| `VOLUNTEER_SESSIONS_DB` | 否 | 聊天记录库，默认 `data/volunteer_sessions.db` |
| `VOLUNTEER_STATE_DB` | 否 | 检查点库，默认 `data/agent_state.db` |

## 相对课堂 demo 的增量

- 新的校园志愿业务场景与完整业务闭环，不是 demo_5 换皮
- 自建 `volunteer-data` MCP 服务器（3 个只读工具），Agent 直接复用其注册定义
- 确定性数据层：名额实时计算、报名事务、冲突检测、幂等取消
- 两个自写 Skill + `write_file` 产出写入 `workspace/`，路径做目录限制
- 报名 / 取消走 `interrupt` 人工确认；Deep Agents 文件权限拒绝 `.env`、`.venv`、`data/`
- 会话双库设计：检查点续聊 + 聊天记录切历史；离线演示可在无 Key 环境完整跑通

## 待完成（林至言）

- [x] Deep Agents 编排、两个 Skill、Streamlit 界面
- [x] 多轮会话保存与执行过程面板
- [x] 报名 / 取消的人工确认
- [x] 周报 Markdown 生成
- [x] 补充 `.env` 配置说明与 5 条演示话术
- [ ] 联调记录：TC-19 ~ TC-24 填入 `docs/test-plan.md`（需要真实 Key 后执行）
