# 志愿星 · 测试用例表（v1）

> 负责人：朱煜杰　评审：林至言
> 适用范围：数据层、工具层、MCP 与命令行业务闭环
> 目的：保证现场演示时每条主路径都有确定的预期结果，失败时能给出可读提示

## 0. 测试前置

```powershell
python -m data.seed
python -m scripts.check_data
```

`check_data` 全部 PASS 后再执行下表。所有命令均在仓库根目录运行。

## 1. 功能与异常用例

| ID | 场景 | 命令 | 预期结果 | 对应要求 |
|---|---|---|---|---|
| TC-01 | 按星期检索 | `python -m volunteer.cli search --weekday 周三 --limit 3` | 返回 3 条周三活动，含剩余名额 | 工具被真实调用 |
| TC-02 | 按类别 + 关键词检索 | `python -m volunteer.cli search --category 助老 --keyword 手机` | 只返回“社区长者手机课堂”，已结束活动不出现 | 查询接口可用 |
| TC-03 | 课表冲突 | `python -m volunteer.cli conflict S001 A004` | `conflict=true`，列出“数据结构 周三 18:00-19:40” | 路径 B 业务规则 |
| TC-04 | 名额已满 | `python -m volunteer.cli enroll S001 A005 --yes` | 返回 `FULL`，中文提示“名额已满”，不写库 | 失败可解释 |
| TC-05 | 重复报名 | `python -m volunteer.cli enroll S001 A003 --yes` | 返回 `ALREADY_ENROLLED`，并给出原报名编号 | 幂等与数据一致性 |
| TC-06 | 活动不存在 | `python -m volunteer.cli detail A999` | 返回 `NOT_FOUND`，提示活动编号 | 输入边界 |
| TC-07 | 正常报名 | `python -m volunteer.cli enroll S001 A001 --yes` | 返回 `confirmed` 与新报名编号，剩余名额减 1 | 写操作事务 |
| TC-08 | 取消报名 | `python -m volunteer.cli cancel <TC-07 的编号> --yes` | 返回 `cancelled`，剩余名额恢复 | 危险操作可控 |
| TC-09 | 取消不存在的报名 | `python -m volunteer.cli cancel E9999 --yes` | 返回 `NOT_FOUND`，不修改任何数据 | 错误处理 |
| TC-10 | 导出时长 | `python -m volunteer.cli export S001` | 生成 `workspace/hours.csv`，6 条记录 / 18.5 小时，Excel 打开无乱码 | 明确产出物 |
| TC-11 | 导出路径越界 | `python -m volunteer.cli export S001 --out ../escape.csv` | 返回 `INVALID_PATH`，不写 `workspace` 之外 | 权限隔离 |
| TC-12 | 导出非 CSV | `python -m volunteer.cli export S001 --out hours.txt` | 返回 `INVALID_PATH` | 输入校验 |

## 2. 交互与确认用例

| ID | 场景 | 操作 | 预期结果 |
|---|---|---|---|
| TC-13 | 报名时拒绝确认 | 运行 `python -m volunteer.cli enroll S001 A001`，在 `[y/N]` 输入 `n` | 提示“已取消操作，未写入数据库”，重新查询剩余名额不变 |
| TC-14 | 非交互环境未加 `--yes` | 在脚本或管道中运行报名命令 | 拒绝执行并提示“如确认执行请加 --yes” |
| TC-15 | 重复取消 | 对同一编号执行两次 `cancel --yes` | 第二次返回 `cancelled` 并附带“此前已取消”说明，不报错 |

## 3. MCP 用例

| ID | 场景 | 操作 | 预期结果 |
|---|---|---|---|
| TC-16 | 工具清单 | 启动 `python -m volunteer.mcp_server`，客户端连接 | 列出 `search_activities`、`get_activity_detail`、`get_volunteer_hours` 三个工具 |
| TC-17 | 通过 MCP 检索 | 客户端调用 `search_activities(weekday="周六")` | 返回与 CLI 一致的 JSON 结构 |
| TC-18 | MCP 只读边界 | 检查工具清单 | 不含报名、取消、导出等写操作 |

> TC-16～TC-18 已由 `python -m scripts.mcp_smoke` 自动执行：脚本以 stdio 真实拉起服务器，完成握手、列工具并调用三个工具。

## 4. Agent 层联调用例（林至言执行，朱煜杰记录）

| ID | 场景 | 输入 | 预期结果 |
|---|---|---|---|
| TC-19 | 一句话多步 | “我是 S001，周三晚上有空，帮我找 2 个活动” | 至少调用 1 次检索工具，结果与 CLI 一致 |
| TC-20 | 冲突拦截 | “帮我报名秋季运动会志愿保障” | 调用冲突检查，明确告知冲突课程，不直接报名 |
| TC-21 | 报名确认 | “帮我报名社区长者手机课堂” | 界面弹出确认，确认后才调用 `enroll_activity` |
| TC-22 | 周报产出 | “把我这学期时长汇总成周报” | 调用时长查询与导出，`workspace/` 下出现 Markdown 与 CSV |
| TC-23 | 模型不调用工具 | 观察执行面板 | 若模型只回复文字而无工具调用，视为失败并记录提示词问题 |
| TC-24 | 错误透传 | “帮我报名 A999” | 模型转述 `NOT_FOUND` 的中文提示，不编造活动 |

## 4.1 Agent 层自检（不需要 Key，可随时执行）

| ID | 命令 | 预期结果 |
|---|---|---|
| AC-01 | `python -m scripts.check_agent` | 14 项全 PASS：会话读写、8 个工具、MCP 定义一致、未确认不写库、write_file 越界拦截、离线周报 |
| AC-02 | `python -m scripts.smoke_ui` | 6 项全 PASS：首屏渲染、切离线、示例话术出结果、执行面板有内容、新建会话 |
| AC-03 | `python -m volunteer.agent --offline` | 打印 6 步工具调用，`workspace/reports/` 出现当天周报 |
| AC-04 | `python -m volunteer.agent --tools` | 列出 8 个工具，前三个与 `python -m volunteer.mcp_server` 一致 |

## 5. 演示前检查清单

- [ ] `python -m data.seed` 可重复执行，数据恢复到基线
- [ ] `python -m scripts.check_data` 全部 PASS
- [ ] TC-01～TC-12 逐条通过，失败提示为中文
- [ ] `python -m volunteer.cli demo` 六步全部成功
- [ ] MCP 客户端能看到 3 个工具
- [ ] 录制备份视频时覆盖 TC-03、TC-07、TC-10 三条

## 6. 结果记录

| 日期 | 执行人 | 通过 / 总数 | 失败项 | 处理 |
|---|---|---|---|---|
| 2026-10-21 | 朱煜杰 | 单元测试 30/30；CLI 抽查 TC-01/03/04/07/10/11/12 通过；MCP 联调 TC-16～18 通过 | — | 通过 |
| 2026-10-21 | 朱煜杰 | Agent 自检 AC-01 14/14、AC-02 6/6、AC-03、AC-04 通过 | — | 通过 |
| 2026-10-21 | 朱煜杰 | TC-19～TC-24 全部通过（火山方舟 deepseek-v4.1-flash） | — | 通过 |

### TC-19～TC-24 实测记录

| ID | 实际工具链 | 结果 |
|---|---|---|
| TC-19 | `search_activities(weekday=周三, limit=20)` → 返回 6 条开放活动，按匹配规则排序 | 通过 |
| TC-20 | `get_activity_detail(A004)` → `check_schedule_conflict(A004)`，指出与“数据结构”冲突，未调用报名 | 通过 |
| TC-21 | 两轮对话后 `enroll_activity` 暂停，`pending` 返回报名详情；`resume(True)` 后名额 10→9 | 通过 |
| TC-22 | `get_volunteer_hours` → `export_hours_csv` → `write_file` → `task(report-critic)`，产出周报与 CSV | 通过 |
| TC-23 | 每轮均出现工具调用，执行面板有完整轨迹，无“只回复不调工具”现象 | 通过 |
| TC-24 | `get_activity_detail(A999)` 返回 `NOT_FOUND`，模型如实转述且未编造活动 | 通过 |

联调中发现并修复两处问题：

1. 并行工具调用的结果按返回顺序错配（执行面板会显示错误的参数与结果）。已改为按 `call_id` 配对，并补充回归测试 `tests/test_agent_steps.py`。
2. `.env` 中 `WORKSPACE_DIR=workspace` 是相对路径，导致 `check_agent` 在 `relative_to` 处报错。已在 `config.py` 统一按仓库根目录解析相对路径。
