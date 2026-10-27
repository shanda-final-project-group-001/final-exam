# 志愿星 · 现场演示文件清单

> 用途：上台前照着本表把文件放好，演示时按顺序打开。
> 核对时间：2026-10-26　演示账号：`S001`　学期：`2026-2027-1`
> 状态说明：✅ 已具备　⚠️ 本机可用但需注意　❌ 目前缺失

---

## 1. 上台必带（先装进一个“演示包”）

| 优先级 | 文件 | 用途 | 怎么打开 | 状态 |
|---|---|---|---|---|
| ★ | `presentation/presentation.html` | 11 页汇报幻灯片 | 浏览器直接打开 | ✅ |
| ★ | `presentation/_shared/` | 幻灯片的样式、翻页、图表脚本 | 必须和 `presentation.html` 一起带，保持相对位置 | ✅ |
| ★ | `docs/志愿星-双人演讲稿-6min.docx` | 打印稿或平板上的逐字稿、操作卡、问答 | Word 打开或提前打印 | ✅ 11 页 |
| ★ | `docs/speech-script.md` | 手机/平板备用稿，按关键词快速定位 | 任意 Markdown 阅读器 | ✅ |
| ★ | `docs/demo-script.md` | 演示顺序、现场故障兜底 | 手机或平板 | ✅ |
| ★ | `docs/demo-files.md` | 本清单，上台前逐项核对 | 手机或打印 | ✅ |
| ★ | `docs/recording-guide.md` | 录屏前设置、逐字旁白、录后自查 | 录屏时用；不录屏可不带 | ✅ |
| ★ | `志愿星-备份录屏-*.mp4` | 网络或界面故障时播放 | 放桌面，能 5 秒内播放 | ❌ 仓库内未找到，需录制或从仓库外 `录屏/` 放入 |

> 注意：只拷 `presentation.html` 不带 `_shared/`，幻灯片会掉样式、翻页和图表。整个 `presentation/` 文件夹一起拷最稳。

### 建议的演示包结构

```text
演示包/
├─ presentation.html
├─ _shared/
├─ 志愿星-双人演讲稿-6min.docx
├─ speech-script.md
├─ demo-script.md
├─ demo-files.md
├─ recording-guide.md
├─ 备份录屏.mp4
└─ screenshots/            # 可选，界面故障时替代展示
```

> 演示包里不要放 `.env`、`.venv/`、`data/*.db`；换机时先执行 `python -m data.seed` 重建数据。

---

## 2. 演示环境（电脑上必须能跑）

| 文件/目录 | 用途 | 状态 |
|---|---|---|
| `web.py` | Streamlit 界面入口 | ✅ |
| `volunteer/` | 智能体、工具、通用接口、操作手册、会话 | ✅ |
| `volunteer/agent.py` | 智能体编排、确认暂停、文件权限、长期记忆 | ✅ |
| `volunteer/tools_business.py` | 查活动、查冲突、报名、取消、导出时长 | ✅ |
| `volunteer/mcp_server.py` | 三个只读能力的通用接口 | ✅ |
| `volunteer/skills/activity-matching/` | 活动匹配与排序规则 | ✅ |
| `volunteer/skills/volunteer-weekly-report/` | 周报结构、模板、自检 | ✅ |
| `volunteer/sessions.py` | 会话历史与对话保存 | ✅ |
| `data/seed.py` | 一键重建演示基线 | ✅ |
| `data/schema.sql` | 数据表结构 | ✅ |
| `data/volunteer_demo.db` | 业务数据（S001 18.5 小时、A007 剩 23、A005 满员） | ✅ 本机已有；不入 Git |
| `data/agent_state.db` | 智能体执行进度、待确认报名 | ✅ 本机已有；不入 Git |
| `workspace/` | 周报和表格的输出目录 | ✅ |
| `workspace/reports/` | 周报输出目录，演示前提前打开 | ✅ |
| `.env` | 本机模型 Key | ⚠️ 只在本机用，绝不投屏、绝不提交 |
| `.env.example` | 密钥配置示例 | ✅ 可展示字段，不展示真实值 |
| `requirements.txt` | Python 依赖 | ✅ |
| `AGENTS.md` | 长期记忆文件 | ✅ 演示前确认是基线版本 |
| `scripts/check_data.py` | 数据自检 | ✅ |
| `scripts/check_agent.py` | 智能体、工具、手册、权限自检 | ✅ |
| `scripts/smoke_ui.py` | 界面启动自检 | ✅ |
| `scripts/mcp_smoke.py` | 通用接口联调自检 | ✅ 可选 |
| `scripts/smoke_tools.py` | 工具冒烟 | ✅ 可选 |
| `tests/` | 36 项单元测试 | ✅ 可选展示 |
| `Dockerfile`、`docker-compose.yml`、`.dockerignore` | 容器化兜底 | ✅ 可选，现场仍以本地启动为主 |

---

## 3. 演示前 10 分钟要打开/准备的东西

按这个顺序准备，避免上台现找：

1. **幻灯片**：浏览器打开 `presentation/presentation.html`，翻到第 1 页，确认样式、页码、翻页按钮正常。
2. **讲稿**：Word 打印稿放桌上，或平板打开 `docs/志愿星-双人演讲稿-6min.docx`。
3. **操作卡**：手机或平板打开 `docs/speech-script.md` 第 2 节；朱煜杰随身。
4. **界面**：终端执行 `streamlit run web.py`，浏览器打开 `http://localhost:8501`，缩放 100%。
5. **输出目录**：资源管理器提前打开 `workspace/` 和 `workspace/reports/`。
6. **备份录屏**：放桌面，先静音试播 3 秒，确认能放。
7. **关闭通知**：微信、QQ、邮件、系统通知全部关闭；终端滚到看不见 Key 的位置。
8. **确认基线**：`S001` 累计 18.5 小时、`A007` 剩余 23、`A005` 满员；左侧显示“在线（模型服务）”。

### 演示前命令

```powershell
.\.venv\Scripts\Activate.ps1
python -m data.seed
python -m scripts.check_data
python -m scripts.check_agent
python -m scripts.smoke_ui
streamlit run web.py
```

---

## 4. 演示过程中会生成的文件

这些不用提前准备，演示时确认能生成即可：

| 文件 | 生成时机 | 说明 |
|---|---|---|
| `workspace/reports/weekly-report-<日期>.md` | 说“把这学期志愿时长汇总成周报”之后 | 周报正文，页脚标注“演示样例” |
| `workspace/hours.csv` | 导出表格时 | 逐条时长记录，Excel 打开中文不乱码；实际文件名以界面提示为准 |
| `workspace/reports/hours-S001-2026-2027-1.csv` | 部分导出/测试路径 | 现有样例，可作为对照 |
| `data/volunteer_demo.db` | 确认报名后 | 新增报名编号 `E1041`，`A007` 剩余从 23 变 22 |
| `data/agent_state.db` | 对话和执行过程中 | 保存执行进度与待确认操作 |

> 演示结束执行 `python -m data.seed` 恢复基线，方便下一场复用。

---

## 5. 讲解与答辩材料（不投屏，放手机/平板）

| 文件 | 用途 |
|---|---|
| `docs/志愿星-双人演讲稿-6min.docx` | 6 分钟逐字稿、操作卡、问答附录 |
| `docs/speech-script.md` | 可搜索的 Markdown 主稿 |
| `docs/team-plan.md` | 分工、接口契约、里程碑、答辩分工 |
| `docs/test-plan.md` | 测试用例与执行记录，老师问测试时打开 |
| `docs/submission-checklist.md` | 提交物、安全核对、答辩互认表 |
| `README.md` | 项目总览、启动、工具、增量表格 |
| `docs/speech-script-8min.md` | 8 分钟完整版存档，需要展开细节时用 |

---

## 6. 界面故障时的替代材料（可选）

如果现场界面打不开，除了播放备份录屏，还可以打开以下截图：

| 文件 | 展示内容 |
|---|---|
| `presentation/screenshots/ui-home.png` | 首页、会话历史、运行模式 |
| `presentation/screenshots/ui-search.png` | 一句话检索与执行步骤 |
| `presentation/screenshots/ui-confirm.png` | 报名确认面板 |
| `presentation/screenshots/ui-enrolled.png` | 确认成功、报名编号 `E1041` |
| `presentation/screenshots/ui-report.png` | 周报与表格产出 |
| `presentation/screenshots/deck-cover.png` | 幻灯片封面 |
| `presentation/screenshots/deck-slide2.png` | 幻灯片第 2 页与翻页 |

---

## 7. 可选展示（老师追问“增量/测试/Docker”时）

- `README.md` 第 14 节：相对课堂练习的增量表。
- `docs/test-plan.md`：TC-01～TC-25、AC-01～AC-04、36 项测试记录。
- `tests/test_tools.py`、`tests/test_agent_steps.py`、`tests/test_cli.py`、`tests/test_mcp_server.py`：单元测试。
- `volunteer/agent.py`：智能体编排、确认暂停、权限、长期记忆。
- `volunteer/mcp_server.py`：三个只读能力的通用接口。
- `volunteer/tools_business.py`：业务工具与事务。
- `volunteer/skills/*/SKILL.md`：两份操作手册。
- `Dockerfile`、`docker-compose.yml`：容器化运行。
- `presentation/presentation.html` 按 `N` 看演讲者备注，按 `S` 进演示者模式。

---

## 8. 绝对不要投屏 / 不要提交

- `.env`：真实模型 Key。
- `.venv/`：本地虚拟环境，体积大且无展示价值。
- 终端历史里出现过 Key 的窗口。
- 微信、QQ、邮件、个人网盘等私人窗口。
- `__pycache__/`、`.git/` 等开发目录。
- 真实个人信息：演示数据全部虚构，讲解时不要暗示是学校真实记录。

---

## 9. 当前缺口与待办

| 事项 | 状态 | 说明 |
|---|---|---|
| 3 分钟备份录屏 | ❌ | 仓库内未找到 `.mp4`；按 `docs/recording-guide.md` 录制，放桌面和网盘各一份 |
| 在线模式实跑 | ⚠️ | 本机 `.env` 已配置；上台前确认左侧显示“在线（模型服务）” |
| 计时演练 | ⚠️ | 按 6 分钟版走两遍，卡 `0:35 / 1:20 / 2:30 / 5:35`，目标 `5:50–6:10` |
| 数据基线 | ✅ | `python -m data.seed` 可一键恢复 |
| 幻灯片依赖 | ✅ | `presentation/_shared/` 必须随 `presentation.html` 一起带 |
| Word 讲稿 | ✅ | 11 页，可直接打印 |
