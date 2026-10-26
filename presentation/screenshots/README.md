# 界面截图

2026-10-26 在 Docker 干净容器（`http://localhost:8501`）中用 Edge 无头浏览器实测并截图。
所有姓名、学号、活动与时长均为虚构演示数据。

| 文件 | 场景 | 关键内容 |
|---|---|---|
| `ui-home.png` | 首页 | 侧边栏会话历史、演示话术、运行模式；主区域欢迎提示 |
| `ui-search.png` | 一句话检索 | “我周三晚上有空，帮我找 2 个适合我的志愿活动”；右侧完整工具轨迹 |
| `ui-confirm.png` | 报名确认 | 橙色“需要你确认”面板；`enroll_activity` 暂停，库中尚未写入 |
| `ui-enrolled.png` | 确认成功 | 点击“确认执行”后返回 `status=confirmed`、报名编号 `E1041` |
| `ui-report.png` | 周报产出 | 周报 Markdown 与 CSV 写入 `workspace/reports/`，含 critic 审阅结果 |
| `deck-cover.png` | 幻灯片封面 | 11 页、组员姓名学号、底部页码与翻页按钮 |
| `deck-slide2.png` | 幻灯片第 2 页 | 翻页后页码变为 2/11，“上一页”按钮解除禁用 |

说明：

- `ui-confirm.png` 与 `ui-enrolled.png` 来自同一次干净容器运行：确认前 S001/A007 无记录，确认后只新增一条 `E1041`。
- 在同一数据库对已报名活动再次提交会返回 `ALREADY_ENROLLED`，这是幂等提示，不是确认流程失败。
- `ui-report.png` 的执行面板保留真实轨迹，其中 `ls /workspace` 被文件权限拦截属于预期边界；周报与 CSV 仍由白名单内的 `write_file` / `export_hours_csv` 正常生成。
