# 志愿星 · 提交清单核对（T8.4）

> 核对时间：2026-10-22　核对人：林至言　复核：朱煜杰
> 用途：提交当晚按本表从上到下过一遍，任何一项"❌"都不提交。

## 1. 提交物

| # | 提交物 | 位置 | 状态 | 备注 |
|---|---|---|---|---|
| 1 | 代码仓库 | https://github.com/shanda-final-project-group-001/final-exam | ✅ 已推送，`main` 与 `origin/main` 一致 | 工作区无未提交改动 |
| 2 | `README.md` | 仓库根目录 | ✅ | 场景、架构、技术栈、目录、工具、启动、测试、进度、合规齐全 |
| 3 | HTML 幻灯片 | `presentation/presentation.html` | ✅ 11 页，含演讲者备注（`N` 键看备注、`S` 键进演示者模式） | 浏览器直接打开即可，无需联网 |
| 4 | 分工与测试文档 | `docs/team-plan.md`、`docs/test-plan.md` | ✅ | 口径已与代码对齐 |
| 5 | 备份录屏 | 仓库外 `录屏/志愿星-备份录屏-*.mp4` | ❌ 待录制 | 操作卡与逐字旁白见 `docs/recording-guide.md` |
| 6 | 模型 Key | 各人本地 `.env` | ⚠️ 由本人填 | 仓库内只有 `.env.example` 占位符 |

## 2. 代码与安全核对

| 项 | 命令 | 结果 |
|---|---|---|
| `.env` 未进 Git | `git ls-files \| grep -c "^\.env$"` | 0 ✅ |
| 无真实手机号 | 正则扫 `1[3-9]\d{9}` | 0 命中 ✅ |
| 无泄露的 Key | 正则扫 `sk-…` / `ark-…` | 0 命中 ✅ |
| 无 `.venv`、`.db`、`workspace` 产物入库 | `git ls-files` 共 55 个文件 | ✅ 均为源码与文档 |
| `AGENTS.md` 为基线版本 | `git status --short` | 空 ✅ |
| 演示数据可重建 | `python -m data.seed` | ✅ |

## 3. 功能核对（2026-10-22 实跑）

| 项 | 结果 |
|---|---|
| `check_data` 11 项 | 全部 PASS ✅ |
| 单元测试 | 41/41 通过（新增 5 条确认/XSS 安全回归）✅ |
| `check_agent` | 14/14 PASS ✅ |
| `smoke_ui` | 6/6 PASS ✅ |
| `mcp_smoke` | 通过（3 个只读工具，stdio 真实联调）✅ |
| `volunteer.cli demo` | 六步成功 ✅ |
| `agent --offline` | 6 步工具调用，周报写入 `workspace/reports/` ✅ |
| TC-01～TC-15 | 逐条实跑符合预期（TC-14/TC-15 曾抛堆栈，已修复并补回归）✅ |
| `streamlit run web.py` | `/_stcore/health` 返回 200，界面可打开 ✅ |

## 4. 仍未完成（提交前必须处理）

| 事项 | 负责人 | 说明 |
|---|---|---|
| 3 分钟备份录屏 | 朱煜杰 | 照 `docs/recording-guide.md` 念，一遍过；录完按第 3 节自查 |
| 在线模式实跑一次 | 林至言 | 把 `.env` 第一行换成真实 Key，跑通一条话术后**把 Key 删掉**再提交 |
| 计时演练 | 共同 | 按 `speech-script.md` 的 6 分钟版走两遍，卡 0:35 / 1:20 / 2:30 / 5:35 四个检查点，总时长落在 5:50–6:10 |
| Docker 构建验证 | 朱煜杰（可选） | 已完成：镜像约 1.04 GB、容器 healthy、在线/离线链路均正常；现场仍以 `streamlit run web.py` 为主，Docker 作备选 |

## 5. 提交前 30 分钟动作

```powershell
.\.venv\Scripts\Activate.ps1
python -m data.seed
python -m scripts.check_data
python -m unittest discover -s tests
python -m scripts.check_agent
python -m scripts.smoke_ui
streamlit run web.py
```

然后：打开 `presentation.html` 翻一遍（确认字体没掉）→ 打开 `workspace/` 备好展示目录 → 关闭通知 → 提交。

## 6. 两人答辩互认（评分常问）

| 问题 | 主答 | 必须能指到的文件 |
|---|---|---|
| 主路径会调哪些工具 | 林 | `volunteer/agent.py` 的 `SYSTEM_PROMPT` 与工具挂载段 |
| Skill 与系统提示词的区别 | 林 | `volunteer/skills/*/SKILL.md`、`agent.py` 的 Skills 中间件 |
| 冲突怎么判断 | 朱 | `volunteer/tools_business.py` 的 `check_schedule_conflict` |
| 名额为什么不会算错 | 朱 | `_remaining()` 与 `enroll_activity` 的事务 |
| MCP 与普通工具的区别 | 朱 | `volunteer/mcp_server.py`（3 个只读工具被 Agent 复用） |
| 密钥与文件权限 | 林 | `.gitignore`、`agent.py` 的 `permissions`、`write_file` 越界拦截 |
| 长期记忆怎么证明不是编的 | 朱 | `AGENTS.md` + `team-plan.md` §7.4 的现场复现步骤 |
| 相对课堂 demo 的增量 | 共同 | `README.md` §14 的表格逐行指文件 |
