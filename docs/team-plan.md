# 志愿星 · 小组分工与协作方案

> 项目：校园志愿活动智能助手（志愿活动匹配 + 时长周报）
> 小组：林至言（f25011330）、朱煜杰（f25011243）
> 版本：v0.2（2026-10-22）　状态：主路径已冻结，进入汇报准备
> 依据：`presentation/presentation.html` 的 11 页结构与《期末考查要求》

---

## 1. 分工原则

1. **按可交付物分工，不按“页数/文件数”平分。** 每项任务只有一个负责人（DRI），另一人做评审和备份。
2. **先冻结接口，再并行开发。** 数据与工具契约（第 3 节）冻结后，两人可同时写代码，不互相等待。
3. **文件所有权清晰。** 同一文件同一时间只有一个人改，减少合并冲突。
4. **交叉理解，不做黑盒。** 每人都要能讲清对方的核心代码，答辩时不能被问倒。
5. **计划是活的。** 本文档按里程碑更新；砍功能时优先砍加分项，不砍主路径。

---

## 2. 角色与负责范围

| 角色 | 林至言（f25011330） | 朱煜杰（f25011243） |
|---|---|---|
| 定位 | 智能体与交付负责人 | 数据与工具负责人 |
| 主责 | Agent 编排、模型接入、Skill、Streamlit 界面、README/PPT、汇报主讲 | 数据模型与样例数据、MCP 服务器、业务工具、测试、现场演示操作 |
| 备份 | 能运行并解释 MCP 与工具 | 能运行并解释 Agent 与 Skill |
| 代码范围 | `volunteer/agent.py`、`volunteer/skills/**`、`web.py`、`requirements.txt`、`README.md`、`presentation/**` | `data/**`、`volunteer/mcp_server.py`、`volunteer/tools_business.py`、`tests/**`、`scripts/**` |
| 共同 | 接口契约、联调、测试用例评审、讲稿、Q&A | 同左 |

> 角色可按实际能力互换，但**接口契约与文件所有权必须唯一**。

---

## 3. 接口契约（并行开发的前提）

### 3.1 数据模型（朱煜杰起草，两人评审后冻结）

| 表 | 关键字段 |
|---|---|
| `students` | student_id、name、grade、major、interests、available_slots |
| `activities` | activity_id、title、category、date、start_time、end_time、location、capacity、credit_hours、tags、description、organizer、status |
| `enrollments` | enrollment_id、student_id、activity_id、status、created_at |
| `hours` | record_id、student_id、activity_id、hours、term、status |
| `courses` | course_id、student_id、name、weekday、start_time、end_time、weeks |

数据全部虚构：20 名学生、30 条活动、40 条报名、15 条课表记录。禁止使用真实学号、手机号、成绩。

> 口径说明：`activities` 表**不存** `enrolled_count`，「已报名数 / 剩余名额」由 `capacity - 已确认报名数` 实时计算，
> 只在 `get_activity_detail` 等工具返回值里出现，避免计数漂移。契约与实现以 `data/schema.sql` 为准。

### 3.2 工具签名（v1）

```text
search_activities(weekday=None, category=None, keyword=None, limit=5)
  -> {"items": [{"activity_id","title","date","start_time","end_time",
                 "location","category","remaining","credit_hours","tags"}]}

get_activity_detail(activity_id)
  -> {"activity_id","title","description","organizer","capacity",
      "enrolled_count","remaining","credit_hours","requirements"} 
     | {"error": {"code": "NOT_FOUND", "message": "..."}}

get_volunteer_hours(student_id, term="2026-2027-1")
  -> {"student_id","term","total_hours",
      "records": [{"activity_id","title","date","hours","status"}]}

check_schedule_conflict(student_id, activity_id)
  -> {"conflict": bool,
      "items": [{"course","weekday","start_time","end_time"}],
      "suggestion": "..."}

enroll_activity(student_id, activity_id)
  -> {"status": "confirmed", "enrollment_id": "E1024"}
     | {"error": {"code": "CONFLICT|FULL|ALREADY_ENROLLED|NOT_FOUND", "message": "..."}}

cancel_enrollment(enrollment_id)
  -> {"status": "cancelled"} | {"error": {"code": "NOT_FOUND", "message": "..."}}

export_hours_csv(student_id, term, out_path="workspace/hours.csv")
  -> {"path": "...", "rows": 6}
```

**约定**：所有工具必须返回可 JSON 序列化的字典；错误用 `error.code` + 中文 `message`；不抛未捕获异常。

### 3.3 分工边界

- 朱煜杰实现 `search_activities`、`get_activity_detail`、`get_volunteer_hours`（MCP 服务器）和 `check_schedule_conflict`、`enroll_activity`、`cancel_enrollment`、`export_hours_csv`（本地工具）。
- 林至言只通过上述签名调用，不直接读写数据库。
- 契约变更必须两人确认，并在本文档第 9 节记录。

---

## 4. 工作分解（WBS）

### 阶段 0 · 立项与仓库（10/21）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T0.1 | 一句话场景、路径 A/B 声明 | 共同 | 对照 PPT | 与 PPT 第 1、4 页一致 |
| T0.2 | 仓库初始化、目录结构、`.gitignore`、`.env.example` | 林 | 朱评审 | 不含 `.env`、`.venv`、数据库 |
| T0.3 | Issue/看板、分支规则 | 朱 | 林配合 | 每人知道在哪里领任务 |

### 阶段 1 · 数据与契约（10/22）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T1.1 | 建表、样例数据、初始化脚本 | 朱 | 林验收字段 | `python -m data.seed` 可重建数据库 |
| T1.2 | 工具契约 v1 文档 | 朱 | 林评审签名 | 双方签字冻结，写入第 3 节 |
| T1.3 | 项目目录骨架与配置模块 | 林 | 朱评审 | `config.py` 读 `.env`，缺 Key 有中文提示 |

### 阶段 2 · 业务能力（10/22–10/23）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T2.1 | MCP 服务器 `volunteer-data`（3 工具） | 朱 | 林用客户端连一次 | 终端能看到 3 个工具被调用 |
| T2.2 | 本地业务工具 4 个 | 朱 | 林写调用示例 | 每个工具有单测或 CLI 自测 |
| T2.3 | 报名/取消的人工确认（`interrupt`） | 林 | 朱提供状态机语义 | 不确认不写库，取消可回滚 |
| T2.4 | 工具错误码与中文提示 | 朱 | 林验收 | 8 类异常均有可读提示 |

### 阶段 3 · 智能体（10/23–10/24）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T3.1 | 百炼模型接入（OpenAI 兼容） | 林 | 朱验证断网兜底 | `.env` 配 Key 即可切换模型 |
| T3.2 | Deep Agent 组装、系统提示、`write_todos` | 林 | 朱按用例验收 | 一句话触发 ≥3 次工具调用 |
| T3.3 | 子代理 `critic` 审阅周报 | 林 | 朱提供反例 | critic 能指出缺失字段 |
| T3.4 | 长期记忆 `AGENTS.md` | 林 | 朱检查隐私 | 只存偏好，不存真实个人信息 |
| T3.5 | 会话保存（SQLite checkpointer + 历史表） | 林 | 朱做重启验证 | 重启后能继续上一轮对话 |

### 阶段 4 · Skills（10/24）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T4.1 | `activity-matching`：匹配与排序规则 | 林 | 朱提供业务规则 | 规则可被日志证明被读取 |
| T4.2 | `volunteer-weekly-report` + `template.md` | 林 | 朱提供字段清单 | 产物含总时长、明细、说明 |
| T4.3 | Skill 与系统提示词的边界说明 | 林 | 朱提问验证 | 能现场回答“两者区别” |

### 阶段 5 · 界面（10/24–10/25）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T5.1 | Streamlit 对话 + 流式输出 | 林 | 朱体验 | 首字可见，不整段等待 |
| T5.2 | 执行过程面板 | 林 | 朱核对工具名 | 每次调用显示名称、参数、摘要 |
| T5.3 | 历史会话切换 | 林 | 朱做多轮验证 | 新建/切换/继续均可用 |
| T5.4 | 报名确认弹窗 | 林 | 朱验收 | 确认前后状态可对比 |
| T5.5 | 空状态、示例话术、错误提示 | 林 | 朱挑错 | 无英文堆栈直接暴露给用户 |

### 阶段 6 · 产出与工程化（10/25）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T6.1 | 周报 Markdown 写入 `workspace/` | 林 | 朱检查格式 | 文件名带日期，内容可复核 |
| T6.2 | 时长 CSV 导出 | 朱 | 林验收编码 | Excel 打开中文不乱码（utf-8-sig） |
| T6.3 | `requirements.txt`、启动脚本、Windows 命令 | 林 | 朱在干净环境复现 | README 命令可复制执行 |
| T6.4 | README（介绍、栈、启动、话术、增量） | 林主笔 | 朱补数据/工具章节 | 对照要求第 5 节逐项齐全 |
| T6.5 | Docker / 一键脚本（加分，可选） | 朱 | 林验收 | 失败可回退，不影响主路径 |

### 阶段 7 · 测试与演示（10/25–10/26）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T7.1 | 测试用例表（8 类） | 朱 | 林评审 | 每条有预期与失败提示 |
| T7.2 | 端到端演练 ≥3 次 | 共同 | 互相挑错 | 主路径连续两次无卡顿 |
| T7.3 | 备份录屏（≤3 分钟） | 朱录制 | 林旁白 | 覆盖工具调用与产出文件 |
| T7.4 | 断网/超时兜底 | 朱 | 林验收 | 可切 Ollama 或预置结果并说明 |

### 阶段 8 · 材料与答辩（10/25–10/26）

| ID | 任务 | DRI | 协作/验收 | 完成标准 |
|---|---|---|---|---|
| T8.1 | PPT 更新（截图、数据、贡献说明） | 林 | 朱校对 | 8–12 页，架构图可看懂 |
| T8.2 | 6 分钟双人逐字稿 + Q&A 参考答案（8 分钟完整版存档） | 共同 | 计时演练 | 不超时，每人都有发言；主稿见 [speech-script.md](speech-script.md)，完整版见 [speech-script-8min.md](speech-script-8min.md) |
| T8.3 | Q&A 题库与分工 | 共同 | 交叉提问 | 每题有指定主答人 |
| T8.4 | 提交清单核对 | 朱 | 林复核 | 仓库、HTML、录屏、Key 检查 |

---

## 5. 里程碑与门禁

| 里程碑 | 目标 | 门禁（不通过则不进入下一阶段） |
|---|---|---|
| M1（10/23） | 主路径第一次跑通一次工具调用 | 终端能看到工具名与返回；无硬编码假回答 |
| M2（10/25） | 完整演示路径可走通 | 四条话术全部跑通；产出文件真实生成 |
| M3（10/26） | 冻结与备份 | 代码冻结、录屏完成、README 命令复现成功 |
| M4（汇报当晚） | 提交与汇报 | 上课前提交；两人都能指认 2–3 处关键代码 |

**冻结后只修 bug，不加功能。** 若在第二场（11/3），10/28–11/2 只做稳定性和讲稿打磨。

---

## 6. 协作机制

### 6.1 Git 与分支

- `main` 始终保持可运行；禁止直接 push。
- 分支命名：`feat/data-mcp`、`feat/agent-ui`、`fix/xxx`。
- 提交信息：`feat(tools): 增加时间冲突检查`、`fix(ui): 修正确认弹窗状态`。
- 每个 PR 由另一人评审，至少 1 次通过后合并；合并前本地跑一遍主路径。

### 6.2 文件所有权

| 文件/目录 | 唯一修改人 |
|---|---|
| `data/**`、`volunteer/mcp_server.py`、`volunteer/tools_business.py`、`tests/**`、`scripts/**` | 朱煜杰 |
| `volunteer/agent.py`、`volunteer/skills/**`、`web.py`、`requirements.txt`、`README.md`、`presentation/**` | 林至言 |
| `AGENTS.md`、`.env.example` | 林至言（朱评审） |
| 接口契约、讲稿、Q&A | 共同，改动需在群内说明 |

### 6.3 同步节奏

- 每次开发前 15 分钟站会，只回答三问：昨天完成什么、今天做什么、被什么卡住。
- 卡住超过 30 分钟先在群里说明；超过 2 小时就简化方案或换实现。
- 每天结束前各自 push 到功能分支，保证对方能拉到最新代码。

### 6.4 变更管理

- 本文档第 9 节记录变更：日期、内容、原因、影响。
- 新增需求先问：是否影响主路径？是否能在冻结日前完成？不能则进“后续改进”。
- 砍功能顺序：RAG 制度问答 → 子代理 critic → Docker → 长期记忆（核心链路最后动）。

---

## 7. 汇报分工

### 7.1 8 分钟结构

| 时间 | 内容 | 主讲 | 操作 |
|---|---|---|---|
| 0:00–0:50 | 封面、问题与用户 | 林至言 | — |
| 0:50–1:50 | 一句话主路径、五层架构 | 林至言 | 指架构图 |
| 1:50–2:40 | 工具 / MCP / Skill 分工 | 朱煜杰 | 指三类能力卡片 |
| 2:40–3:10 | 与课堂实验的关系、增量 | 朱煜杰 | 打开对应文件 |
| 3:10–3:30 | 思政与合规、数据边界 | 朱煜杰 | — |
| 3:30–3:50 | 切换到演示环境 | 朱煜杰 | 启动 Streamlit |
| 3:50–7:20 | 现场演示：检索 → 冲突 → 确认 → 周报 | 朱煜杰操作，林至言讲解 | 展示执行面板与产物 |
| 7:20–8:00 | 不足与后续、致谢 | 林至言 | — |

> 逐字稿（含演示中的分工台词、操作卡、故障口令与 Q&A 参考答案）见 [speech-script.md](speech-script.md)（6 分钟版）；需要展开细节时用 [speech-script-8min.md](speech-script-8min.md)（8 分钟完整版）。上表是 8 分钟满配结构，6 分钟版把前段压到 2:20、演示压到 3:05。

### 7.2 Q&A 主答分工

| 问题类型 | 主答 | 备份 |
|---|---|---|
| 为什么用 Deep Agents / 多步规划怎么做 | 林 | 朱 |
| Skill 和系统提示词有什么区别 | 林 | 朱 |
| 工具不调用、模型会怎样 | 朱 | 林 |
| MCP 服务器和普通工具的区别 | 朱 | 林 |
| 数据表结构、冲突怎么判断 | 朱 | 林 |
| 密钥为什么不能进 Git、权限怎么隔离 | 林 | 朱 |
| 长期记忆存在哪、怎么证明不是模型编的 | 朱 | 林 |
| 增量在哪里、参考了哪些课堂代码 | 共同 | — |

### 7.3 两人都必须能回答

1. 这个项目解决了谁的什么问题？
2. 一句话主路径会触发哪些工具？
3. Skill 放在哪里、什么时候被读取？
4. 报名为什么需要二次确认？
5. 如果模型胡说一个活动，系统怎么防？
6. 你们相对 demo_5 具体加了什么？

### 7.4 参考答案：怎么证明长期记忆不是模型编的

**问题**：你们的“长期记忆”是不是就是把几句话塞进提示词，模型随口编的？

**现场可复现的答法**（朱主答，约 40 秒）：

1. 记忆存在仓库根目录的 `AGENTS.md`，由 Deep Agents 的 Memory 中间件每轮注入；文件可写，
   但业务产出仍被限制在 `workspace/`。
2. 先看事实：`AGENTS.md` 的「用户偏好」只有 4 条（校内优先、周末优先、先结论后理由、
   冲突只讲事实），**没有常空时段**。
   > 区分：学生画像（专业、兴趣、常空时段）来自 `students` 表，由系统提示每轮注入，
   > 与 `AGENTS.md` 长期记忆是两回事。老师问“常空时段哪来的”，回答是画像表。
3. 当场提问（限定只依据记忆文件）：

```powershell
python -m volunteer.agent --ask "只依据长期记忆文件 AGENTS.md，里面是否记录了我的常空时段？没有就直说没有。"
```

   实际回答是「`/AGENTS.md` 里没有记录常空时段」，并逐条列出文件中真实存在的 4 条偏好；
   模型还会主动纠正自己上一轮“已经写入”的错误说法。
4. 再演示写入：说“请记住：我周三晚上有空”，执行面板出现 `read_file` → `edit_file`，
   `git diff -- AGENTS.md` 能看到新增的那一行；演示后 `git checkout -- AGENTS.md` 恢复基线。

**可以强调的两点**：

- 回答前确实读了文件（`read_file /AGENTS.md` 在执行面板可见），不是靠上下文猜；
- 系统提示明确要求“只引用文件真实文本，没有就回答没有记录”，所以模型会承认“没记录”，
  这正是它没有编造的证据。

---

## 8. 风险与预案

| 风险 | 影响 | 预案 | 负责人 |
|---|---|---|---|
| 模型接口超时/额度不足 | 演示卡住 | 预置结果 + 切本地 Ollama；备份录屏 | 朱 |
| 课堂网络不可用 | 无法调用云端 | 提前下载录屏；本地模型兜底 | 朱 |
| 一人临时缺席 | 演示缺操作者 | 另一人能独立跑完整流程 | 共同 |
| 工具返回不稳定 | 结果不可信 | 工具全部确定性实现，模型只负责选工具与措辞 | 朱 |
| 范围膨胀 | 冻结日做不完 | 按 6.4 的顺序砍功能 | 共同 |
| 合并冲突 | 进度受阻 | 文件所有权 + 小步 PR | 共同 |
| 真实个人信息泄露 | 违规 | 只用虚构数据；提交前全局搜索学号/手机号 | 林 |

---

## 9. 变更记录

| 日期 | 版本 | 变更内容 | 原因 | 影响 |
|---|---|---|---|---|
| 2026-10-21 | v0.1 | 初版：角色、契约、WBS、里程碑、汇报分工 | 定题后需要并行开发 | 建立接口与文件边界 |
| 2026-10-22 | v0.2 | ① 数据契约注明 `activities` 不落库 `enrolled_count`（剩余名额实时计算）；② 新增 `docs/recording-guide.md`（录屏操作卡 + 逐字旁白）、`docs/submission-checklist.md`（提交清单）、`demo-script.md` §6（讲稿计时）；③ 修复 CLI 两处缺陷：非交互确认抛 `EOFError` 堆栈、重复取消 `KeyError`，新增 `tests/test_cli.py` 5 条回归，单测 30→35；④ Dockerfile 将 `data.seed` 移到启动命令，容器化仍未构建验证（本机无 Docker） | 干净环境复跑发现文档与实现口径不一致、TC-14/TC-15 实测暴露缺陷 | 契约以 `data/schema.sql` 为准；录屏仍待人工录制 |

---

## 10. 完成定义（Definition of Done）

- [x] `README.md` 的 Windows 命令在干净环境可复现（2026-10-22 于 Python 3.13 + requirements.txt 全量复跑）
- [x] 一句话触发 ≥5 次工具调用，执行过程可见（离线演示 6 步；在线 TC-19～TC-24 见 test-plan）
- [x] 报名与取消均有确认，未确认不写库（`check_agent` 断言覆盖）
- [x] 周报 `.md` 与时长 `.csv` 真实写入 `workspace/`
- [x] 两个 Skill 各有 `SKILL.md`，周报含模板
- [x] 会话可保存、可继续（`check_agent` 会话读写用例）
- [x] Agent 只能写 `workspace/`，读不到 `.env`（`write_file` 越界返回 `INVALID_PATH`）
- [x] 四条演示话术全部跑通，含失败提示（CLI 实跑 + 在线联调记录）
- [ ] 备份录屏 ≤3 分钟（操作卡与旁白见 `docs/recording-guide.md`，待录制）
- [x] HTML 幻灯片 8–12 页，含架构图与合规说明（11 页 + 演讲者备注）
- [x] 仓库无密钥、无真实个人信息、无 `.venv`（正则扫描 0 命中，`.env` 未被追踪）
- [ ] 两人都能指认并解释对方 2–3 处关键代码（见 `docs/submission-checklist.md` §6，汇报前互考）
