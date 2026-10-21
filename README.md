# 志愿星 · 校园志愿活动智能助手

《开源 AI 技术实践》期末项目：面向在校学生与院系青协，用自然语言完成「找活动 → 查时间冲突 → 确认报名 → 汇总志愿时长 → 生成周报」的完整闭环。

- 选题路径：**路径 A（技术栈完整）**，业务侧按路径 B 的闭环组织
- 小组成员：林至言（f25011330）、朱煜杰（f25011243）
- 当前阶段：数据层、工具层、MCP 与测试已完成；Agent、Skills、界面由林至言开发中
- 汇报材料：[presentation.html](presentation/presentation.html)；分工见 [docs/team-plan.md](docs/team-plan.md)；测试见 [docs/test-plan.md](docs/test-plan.md)

## 1. 问题与场景

校园志愿活动分散在群通知、表格和口头传达里：学生找不到适合自己的活动，报名后容易和课表撞车，学期末还要手工统计时长；组织方也缺少统一的报名与名额视图。

| 角色 | 需求 | 本项目的回应 |
|---|---|---|
| 学生 | 按时间、兴趣找活动并报名 | 自然语言检索、冲突检查、确认后报名 |
| 学生 | 学期末统计时长、交给辅导员 | 一键汇总并导出 CSV / 周报 |
| 青协与组织方 | 名额、报名情况可核对 | 名额实时计算、报名事务、幂等取消 |

**一句话主路径**：说出空闲时间和偏好，系统检索活动、检查课表冲突、确认后写入报名，并生成时长周报。

## 2. 推荐演示话术

| # | 话术 | 预期工具调用 | 观察点 |
|---|---|---|---|
| 1 | “我是 S001，周三晚上有空，帮我找 2 个适合我的志愿活动。” | `search_activities(weekday="周三")` | 执行面板出现检索调用，结果含剩余名额 |
| 2 | “帮我报名社区长者手机课堂。” | `check_schedule_conflict` → 确认 → `enroll_activity` | 未确认前不写库；确认后剩余名额减 1 |
| 3 | “我周三晚上不是有课吗？为什么还推荐秋季运动会？” | `check_schedule_conflict("S001","A004")` | 明确列出“数据结构 周三 18:00–19:40”冲突，不编造 |
| 4 | “把我这学期志愿时长汇总，生成周报并导出表格。” | `get_volunteer_hours` → Skill → `export_hours_csv` | `workspace/` 出现 Markdown 与 CSV，合计 18.5 小时 |
| 5 | “取消刚才那条报名。” | 确认 → `cancel_enrollment` | 取消后名额恢复，重复取消返回幂等提示 |

> 演示主账号固定为 `S001 陈晓雨`、学期 `2026-2027-1`。演讲与现场演示分工见 [docs/team-plan.md](docs/team-plan.md)。

## 3. 总体架构

```mermaid
flowchart LR
    U[学生 / 青协] --> UI[Streamlit 界面]
    UI --> A[Deep Agents 智能体]
    A --> SK[Skills<br/>匹配规则 / 周报模板]
    A --> T[自定义工具<br/>冲突 / 报名 / 取消 / 导出]
    A --> M[MCP 服务器<br/>volunteer-data]
    A -.-> LLM[百炼 Qwen<br/>OpenAI 兼容]
    T --> DB[(SQLite<br/>虚构数据)]
    M --> DB
    A --> W[(workspace<br/>周报 / CSV)]
```

分层职责：

| 层 | 职责 | 状态 |
|---|---|---|
| 界面层 | 对话、流式输出、执行过程面板、确认弹窗 | 未开始（林至言） |
| 智能体层 | 规划、选择工具、组织回答、子代理与记忆 | 未开始（林至言） |
| 能力层 | 自定义工具、MCP 服务器、Skills | 工具与 MCP 已完成；Skills 未开始 |
| 数据层 | SQLite 表结构、虚构样例、名额与冲突计算 | 已完成（朱煜杰） |
| 产出层 | 周报 Markdown、时长 CSV，限制在 `workspace/` | CSV 已完成；周报未开始 |

## 4. 技术栈

| 层次 | 选型 | 负责人 |
|---|---|---|
| 模型 | 阿里百炼 Qwen，OpenAI 兼容接口 | 林至言 |
| Agent 框架 | LangChain Deep Agents（LangGraph 运行时） | 林至言 |
| 界面 | Streamlit | 林至言 |
| 工具与 MCP | Python 标准库 + MCP Python SDK（`mcp>=2.0.0`） | 朱煜杰 |
| 数据 | SQLite（`sqlite3`，无外部服务） | 朱煜杰 |
| 产出 | Markdown 周报、UTF-8-SIG CSV | 共同 |
| 测试 | `unittest`，含 MCP stdio 真实联调 | 朱煜杰 |

## 5. 目录结构

```text
final-exam/
├─ data/                  # 建表 SQL、虚构样例数据与初始化脚本
│  ├─ schema.sql
│  └─ seed.py
├─ volunteer/             # 业务代码
│  ├─ config.py           # 路径与环境变量
│  ├─ db.py               # SQLite 连接与统一错误结构
│  ├─ tools_business.py   # 7 个业务工具（3 读 + 3 写 + 1 导出）
│  ├─ cli.py              # 独立命令行工具（不依赖大模型）
│  └─ mcp_server.py       # MCP 服务器 volunteer-data（3 个只读工具）
├─ scripts/
│  ├─ smoke_tools.py      # 工具冒烟脚本
│  ├─ check_data.py       # 演示数据完整性检查
│  └─ mcp_smoke.py        # MCP stdio 联调（真实拉起服务器）
├─ tests/
│  ├─ test_tools.py       # 工具层单元测试
│  └─ test_mcp_server.py  # MCP 服务器测试
├─ workspace/             # 运行产出（不提交）
├─ docs/
│  ├─ team-plan.md        # 分工与协作方案
│  └─ test-plan.md        # 测试用例表
└─ presentation/          # HTML 汇报幻灯片
```

## 6. 数据层

| 表 | 关键字段 | 说明 |
|---|---|---|
| `students` | student_id、name、grade、major、interests、available_slots | 学生画像与空闲时段 |
| `courses` | student_id、name、weekday、start_time、end_time、weeks | 课表，用于冲突检测 |
| `activities` | activity_id、title、category、date、weekday、start_time、end_time、capacity、credit_hours、status | 活动与名额 |
| `enrollments` | enrollment_id、student_id、activity_id、status、created_at | 报名，`cancelled` 保留记录 |
| `hours` | student_id、activity_id、hours、term、status | 已认定时长 |

设计要点：

- 剩余名额不落库，由 `capacity - 已确认报名数` 实时计算，避免数据漂移
- 报名在单个事务内完成，依次校验学生、活动状态、重复报名、名额、时间冲突
- 取消为软删除（`status='cancelled'`），重复取消幂等
- 星期由日期推导，导入时校验一致性

演示数据全部虚构：20 名学生、30 条活动（24 开放 / 6 已结束）、40 条报名、6 条时长记录。

| 固定事实 | 用途 |
|---|---|
| `S001` 累计 18.5 小时 | 周报与导出的预期结果 |
| `S001` 周三 18:00–19:40“数据结构” | 演示课表冲突 |
| `A005` 名额 2 且已满 | 演示 `FULL` 失败提示 |
| `A026` 等 6 条已结束活动 | 验证检索只返回开放活动 |

## 7. 工具与 MCP 契约

**MCP 服务器 `volunteer-data`（3 个只读工具）**

| 工具 | 返回要点 |
|---|---|
| `search_activities(weekday, category, keyword, limit)` | 活动列表、剩余名额、标签数组 |
| `get_activity_detail(activity_id)` | 详情、剩余名额、组织方 |
| `get_volunteer_hours(student_id, term)` | 学期总时长与明细 |

**自定义工具（4 个，供 Agent 编排）**

| 工具 | 行为 |
|---|---|
| `check_schedule_conflict(student_id, activity_id)` | 返回是否冲突；冲突项区分课程与已报名活动 |
| `enroll_activity(student_id, activity_id)` | 事务内报名；拒绝冲突、满员、重复、已结束 |
| `cancel_enrollment(enrollment_id)` | 软删除，幂等 |
| `export_hours_csv(student_id, term, out_path)` | 只允许写入 `workspace/`，UTF-8-SIG |

**统一错误结构**

```json
{"error": {"code": "CONFLICT", "message": "时间冲突：数据结构"}}
```

错误码：`NOT_FOUND`、`CONFLICT`、`FULL`、`ALREADY_ENROLLED`、`CLOSED`、`INVALID_PATH`。

**Skills（规划，林至言实现）**

| Skill | 作用 |
|---|---|
| `activity-matching` | 匹配与排序规则：时段、类别、兴趣、剩余名额 |
| `volunteer-weekly-report` | 周报结构与措辞，含 `template.md` |

## 8. 安装与运行

环境要求：Python 3.10 及以上（开发环境 3.13）、Windows PowerShell 或 CMD。

```powershell
# 1. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 安装依赖
python -m pip install -r requirements.txt

# 3. 生成虚构演示数据（创建 data/volunteer_demo.db）
python -m data.seed

# 4. 逐个调用工具并打印 JSON
python -m scripts.smoke_tools

# 5. 数据完整性检查（汇报前自检）
python -m scripts.check_data

# 6. 命令行走完整业务闭环（临时数据库，不污染演示数据）
python -m volunteer.cli demo

# 7. MCP 联调：真实启动 stdio 服务器并调用 3 个工具
python -m scripts.mcp_smoke

# 8. 全部单元测试（工具层 + MCP）
python -m unittest discover -s tests -v
```

独立命令行走查（不依赖大模型，可作为断网兜底）：

```powershell
python -m volunteer.cli search --weekday 周三 --limit 3
python -m volunteer.cli detail A001
python -m volunteer.cli hours S001
python -m volunteer.cli conflict S001 A004
python -m volunteer.cli enroll S001 A001          # 交互确认
python -m volunteer.cli enroll S001 A001 --yes    # 跳过确认
python -m volunteer.cli cancel E1001 --yes
python -m volunteer.cli export S001 --out hours.csv
python -m volunteer.cli --json hours S001
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

> MCP 使用 stdio 传输，服务器不向 stdout 打印日志；调试信息写 stderr。

配置：复制 `.env.example` 为 `.env` 并填入百炼 Key。`.env` 已在 `.gitignore` 中，不要提交。

## 9. 项目进度

| 模块 | 状态 | 负责人 | 说明 |
|---|---|---|---|
| 数据层与样例数据 | 已完成 | 朱煜杰 | 可重复初始化，含自检脚本 |
| 7 个业务工具 | 已完成 | 朱煜杰 | 确定性实现，统一错误码 |
| MCP 服务器 | 已完成 | 朱煜杰 | 3 个只读工具，stdio 联调通过 |
| 命令行闭环 | 已完成 | 朱煜杰 | 含报名确认、取消、导出 |
| 测试 | 已完成 | 朱煜杰 | 28 项单元测试 + 联调脚本 |
| Agent 编排 | 未开始 | 林至言 | Deep Agents、百炼接入 |
| Skills | 未开始 | 林至言 | 2 个 Skill |
| Streamlit 界面 | 未开始 | 林至言 | 对话、执行面板、确认弹窗 |
| 会话保存 | 未开始 | 林至言 | SQLite checkpointer |
| 周报 Markdown | 未开始 | 共同 | 依赖 Skill |
| HTML 幻灯片 | 初稿完成 | 共同 | 待补真实截图 |
| 备份录屏 | 未开始 | 朱煜杰 | 依赖界面完成 |

**对照路径 A 最低配置（满足 5 项即达标）**

| # | 要求 | 状态 |
|---|---|---|
| 1 | OpenAI 兼容模型 | 未开始 |
| 2 | 开源 Agent 框架 | 未开始 |
| 3 | ≥2 自定义工具或 1 个 MCP（≥2 工具） | 已完成（7 + 3） |
| 4 | ≥1 个 Agent Skill | 未开始 |
| 5 | 可交互界面 | 未开始 |
| 6 | 多轮对话与会话保存 | 未开始 |
| 7 | 明确产出物 | 部分（CSV 已完成） |

## 10. 相对课堂 demo 的增量

| 课堂实验 | 复用的能力 | 本项目的落地 |
|---|---|---|
| demo_1 | Streamlit、RAG 思路 | 界面（规划中） |
| demo_2 | OpenAI 兼容、Tool Calling、流式 | 工具协议与流式输出（规划中） |
| demo_3 / demo_4 | 百炼接入、密钥管理 | 模型接入、`.env` 隔离 |
| demo_5 | Deep Agents、Skills、MCP、记忆 | 骨架参考；自建 MCP 与业务工具 |

增量不是换皮：新场景、自建 `volunteer-data` MCP（3 个工具）、4 个自定义工具、确定性数据层、可独立使用的命令行闭环。

## 11. 合规与隐私

- 全部数据为虚构样例，不使用真实学号、手机号、成绩
- 不提供代写、作弊、监控或人肉检索能力
- 报名与取消需人工确认；Agent 只允许写 `workspace/`
- 密钥只放 `.env`，不进入 Git；`.env.example` 仅含占位符
- 涉及制度与政策的问题，回答中提示“以官方最新文件为准”

## 12. 已知限制

- Agent 与界面尚未接入，当前只能通过命令行与 MCP 客户端使用
- 名额并发为单机 SQLite 事务级保证，未做多实例锁
- 活动数据为静态样例，未接入真实教务或志愿系统
- `mcp` 2.x 与 1.x 的 API 不同（本项目按 2.x 编写），环境需统一版本

## 13. 文档索引

| 文档 | 内容 |
|---|---|
| [docs/team-plan.md](docs/team-plan.md) | 角色、接口契约、WBS、里程碑、汇报与 Q&A 分工 |
| [docs/test-plan.md](docs/test-plan.md) | 18 条工具/MCP 用例、6 条 Agent 联调用例、演示前检查清单 |
| [presentation/presentation.html](presentation/presentation.html) | 11 页汇报幻灯片（含演讲者备注） |
