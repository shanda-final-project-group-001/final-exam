# 志愿星 · 校园志愿活动智能助手

《开源 AI 技术实践》期末项目。面向在校学生与院系青协，用自然语言完成“找活动 → 查冲突 → 确认报名 → 汇总时长 → 生成周报”的闭环。

- 选题路径：**路径 A（技术栈完整）**，业务侧按路径 B 组织
- 小组：林至言（f25011330）、朱煜杰（f25011243）
- 当前状态：数据层与工具层已完成；Agent / UI / Skills 由林至言继续开发

## 技术栈

| 层次 | 选型 | 负责人 |
|---|---|---|
| 数据与工具 | SQLite、Python 标准库、MCP Python SDK | 朱煜杰 |
| 模型 | 阿里百炼（OpenAI 兼容接口） | 林至言 |
| Agent 框架 | LangChain Deep Agents | 林至言 |
| 界面 | Streamlit（待接入） | 林至言 |
| 产出物 | Markdown 周报、CSV 时长表（写入 `workspace/`） | 共同 |

## 目录结构

```text
final-exam/
├─ data/                  # 建表 SQL、虚构样例数据与初始化脚本
│  ├─ schema.sql
│  └─ seed.py
├─ volunteer/             # 业务代码
│  ├─ config.py           # 路径与环境变量
│  ├─ db.py               # SQLite 连接与统一错误结构
│  ├─ tools_business.py   # 7 个业务工具（3 读 + 3 写 + 1 导出）
│  └─ mcp_server.py       # MCP 服务器 volunteer-data（3 个只读工具）
├─ scripts/smoke_tools.py # 工具冒烟脚本
├─ tests/test_tools.py    # 工具层单元测试
├─ workspace/             # 运行产出（不提交）
├─ docs/team-plan.md      # 分工与协作方案
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

# 3. 生成虚构演示数据（会创建 data/volunteer_demo.db）
python -m data.seed

# 4. 冒烟：逐个调用工具并打印 JSON
python -m scripts.smoke_tools

# 5. 运行工具层测试
python -m unittest discover -s tests -v
```

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

## 工具清单

| 工具 | 类型 | 说明 |
|---|---|---|
| `search_activities(weekday, category, keyword, limit)` | 读 / MCP | 按星期、类别、关键词检索开放活动，返回剩余名额 |
| `get_activity_detail(activity_id)` | 读 / MCP | 活动详情与剩余名额 |
| `get_volunteer_hours(student_id, term)` | 读 / MCP | 学期时长汇总与明细 |
| `check_schedule_conflict(student_id, activity_id)` | 写前校验 | 课表与已报名活动的时间冲突 |
| `enroll_activity(student_id, activity_id)` | 写 | 事务内报名，拒绝冲突 / 满员 / 重复 |
| `cancel_enrollment(enrollment_id)` | 写 | 取消报名，幂等 |
| `export_hours_csv(student_id, term, out_path)` | 产出 | 写入 `workspace/`，UTF-8-SIG 编码 |

错误统一返回：

```json
{"error": {"code": "CONFLICT", "message": "时间冲突：数据结构"}}
```

错误码：`NOT_FOUND`、`CONFLICT`、`FULL`、`ALREADY_ENROLLED`、`CLOSED`、`INVALID_PATH`。

## 演示数据

全部为虚构数据，不使用真实学号、手机号与成绩。

- 20 名学生：`S001` ~ `S020`，其中 `S001 陈晓雨` 为演示主账号
- 30 条活动：`A001` ~ `A030`，25 条开放、5 条已结束
- 40 条报名记录、6 条时长记录（`S001` 累计 18.5 小时）
- `A005` 名额为 2 且已满，用于演示“满员”失败提示
- `S001` 周三 18:00–19:40 有“数据结构”课，用于演示“时间冲突”

## 配置

复制 `.env.example` 为 `.env`，填入自己的百炼 Key。`.env` 已被 `.gitignore` 排除，**不要提交**。

## 相对课堂 demo 的增量

- 新的校园志愿业务场景与完整业务闭环，不是 demo_5 换皮
- 自建 `volunteer-data` MCP 服务器（3 个工具）与 4 个编排层业务工具
- 确定性数据层：名额实时计算、报名事务、冲突检测、幂等取消
- 产出物写入 `workspace/`，并对导出路径做目录限制

## 待完成（林至言）

- [ ] Deep Agents 编排、两个 Skill、Streamlit 界面
- [ ] 多轮会话保存与执行过程面板
- [ ] 报名 / 取消的人工确认
- [ ] 周报 Markdown 生成
- [ ] 补充 `.env` 配置说明与 5 条演示话术
