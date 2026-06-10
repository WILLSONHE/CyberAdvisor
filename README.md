# 赛博股票咨询 Wiki（CyberAdvisor）

> 基于公开内容的 AI 知识库 + 交易决策系统。 

---

## 这是什么

一套完整的投资辅助系统：

- **Wiki 知识库**：Wiki 2025.10~2026.05 全部方法论 + 121 天每日复盘 + 标的全追踪
- **选股脚本**：全市场粗筛 → F10 框架精筛 → 七轨布林线扫描
- **交易策略**：持仓诊断 + 开仓建议 + 做 T 策略 + 每日市场状态
- **AI 模拟持仓**：500 万自主盘，盘中每 15 分钟采集 + 自动买卖（`ai_sim_tick.bat`）
- **AI 集成**：配套 skill 文件，AI 助手直接加载

---

## 快速开始（3 步）

### 1. 安装依赖

```bash
pip install -r requirements.txt
python -m mootdx bestip
```

> 需要国内 IP（mootdx 连通达信服务器）。若 `bestip` 测速失败导致 `BESTIP` 为空，可手动编辑 `~/.mootdx/config.json`，在 `BESTIP.HQ` 填入可用服务器，例如 `["110.41.147.114", 7709]`。

### 2. 加载 skill（Cursor 推荐）

**在本仓库内对话即可**：Agent 读取项目根目录 `[SKILL.md](SKILL.md)`（含 rw/ing/sug 等操作代号与 B 站流水线说明）。

其他助手可将 `SKILL.md` 复制到各自 skill 目录，或把其要点写入 Project Rules；**不依赖 Obsidian**。

### 3. 配置你的持仓

**推荐**：编辑根目录 `持仓.xlsx`（列：**持有人**、标的、代码、成本、股数），或 **在飞书电子表格维护「持仓」**，由 `daily.bat` 自动下载覆盖本地文件后同步。


| 持有人    | 标的   | 代码     | 成本      | 股数  |
| ------ | ---- | ------ | ------- | --- |
| Wilson | 上海电力 | 600021 | 19.9102 | 100 |


现金行：`A股现金` 写在标的列，金额写在成本列，**持有人列必填**。

**Excel 显示**：`持仓.xlsx` / `模拟持仓.xlsx` 保存时自动套用千位分隔数字格式（`#,##0.00`）；单元格内仍是数值，便于计算。

**代码列**：

- **A 股**：6 位，如 `600021`
- **港股**：1–5 位或 `00700.HK` / `HK00700`（如腾讯 `700`）；同步可拉 **港元现价**
- **A股对照**（可选列）：非 A 股标的填写 6 位 A 股代码，供 **布林做 T / K 线** 使用；不填则查内置 AH 对照表，仍无则标「无 A 股对照数据」

飞书云持仓（`.env` 任选一种）：

```env
# 推荐：粘贴浏览器里打开的表格链接
FEISHU_PORTFOLIO_URL=https://xxx.feishu.cn/sheets/shtxxxxxxxx

# 或按名称在云盘搜索（名称为「持仓」或「持仓.xlsx」）
# FEISHU_PORTFOLIO_NAME=持仓
```

需应用权限：`drive:export:readonly`（导出表格）、`drive:drive:readonly`（按名称搜索时）。改权限后 **发版**。

测试：`python scripts/feishu_download_portfolio.py --dry-run`

也可直接编辑 `portfolio.md`（及 `scripts/portfolio.py`），按 `## 持有人：XXX` 分章。

**多人指令格式**（持有人名不区分大小写，须与 xlsx 精确匹配）：

```
sug Wilson              # 读 SugVault 已有报告
sug Wilson 早盘          # 读归档 YYYY-MM-DD_Wilson_sug 早盘.md
sug Wilson 午盘          # 读归档 YYYY-MM-DD_Wilson_sug 午盘.md
sug 全员                 # 分段读取各持有人已有报告
sug 全员 午盘            # 同上，匹配午盘归档文件名
agent sug 全员 午盘      # Cloud Agent 异步生成（每人一份 .md 附件）
持仓 Wilson              # 查看该持有人持仓（Cursor / 飞书均可）
标的池 Wilson            # 核心标的池 + 该持有人做T（Cursor / 飞书均可）
sim 买 利通电子，江波龙    # 模拟买入（100 万起/标的）
sim 卖 利通电子            # 模拟卖出并冻结盈亏
```

格式错误时回复：`请校对格式sug {持有人}，以精确搜索`。完整能力对照见下文 **[飞书 Bot vs Cursor](#飞书-bot-vs-cursor-命令对照)**。

示例录入：

```
我的持仓（Wilson）：
- 上海电力 成本 19.9102 元 100 股
- ST美丽 成本 1.9920 元 2500 股
- 电光科技 成本 34.7286 元 300 股
```

成交额 = 成本 × 股数（投资成本）；市值 = 现价 × 股数（同步时自动拉取）。`sug Wilson` 时以 `portfolio.md` 中 Wilson 章节为准。

### 4. AI 模拟持仓（500 万自主盘）

根目录 `**模拟持仓.xlsx**`，持有人 **AI**，总资金 **500 万元**。盘中由计划任务每 **15 分钟** 执行 `ai_sim_tick.bat`（**09:30–11:15、13:00–14:45**；**11:30 / 15:00 休市改跑 `daily.bat`**）：**采集 → Cloud Agent 分析/调参 → 规则引擎买卖（有信号才成交）** → 写入 `**Wiki/数据/AI模拟交易日志.md`**。行情快照：`Raw/每15分钟市场数据/`。

首次启用 Cloud Agent：复制 `.env.example` 为 `.env`，填入 `CURSOR_API_KEY`（[Cursor Integrations](https://cursor.com/dashboard/integrations)）。


| 操作     | 说明                                                                                     |
| ------ | -------------------------------------------------------------------------------------- |
| 注册计划任务 | 管理员 PowerShell：`.\scripts\ai_sim_register_tasks.ps1`（19× sim tick + 11:30/15:00 daily） |
| 手动跑一次  | `.\ai_sim_tick.bat --force`；加 `--no-agent` 跳过 Cloud Agent                              |
| 归零重启   | `python scripts/ai_sim_reset.py`                                                       |
| 手动干预   | `sim 买/卖 …`（飞书 Bot 或 CLI，见 `sim_portfolio.py`）                                         |


**布林七轨 + vipdoc + 1/3/7 最有可能价**（`scripts/bollinger_utils.py` / `scripts/tdx_vipdoc.py`）：采集 tick 时写入 `boll_zone`、`vipdoc`（本地日 K σ）、`outlook_1d/3d/7d`；Agent 与规则引擎须参考；`.env` 可设 `TDX_VIPDOC=C:\zd_zsone\vipdoc`。

```powershell
# 项目根目录（PowerShell 须加 .\）
.\ai_sim_tick.bat --force

# 或在 scripts 目录
cd scripts
python ai_sim_tick.py --force
# 或 .\ai_sim_tick.bat --force
```

规范见 `SKILL.md` → **AI 自主模拟盘**。

---

## 怎么用

### 每日操作

**一键流水线**（双击根目录 `daily.bat`，在新终端依次执行 **8 步**；计划任务 **11:30 / 15:00** 自动跑 `daily.bat _run _nopause`）：


| 步   | 脚本                             | 说明                                                                   |
| --- | ------------------------------ | -------------------------------------------------------------------- |
| 1   | `feishu_download_portfolio.py` | 飞书云表格 → 覆盖本地 `持仓.xlsx`（未配置则跳过/失败可忽略）                                 |
| 2   | `sync_portfolio_from_xlsx.py`  | `持仓.xlsx` → `portfolio.md` / `trade_template.md`                     |
| 3   | `coarse_screen.py`             | 全市场粗筛                                                                |
| 4   | `fine_screen.py`               | 精筛 + 核心标的池 + 布林线 → `Wiki/数据/标的池日报.md`                                |
| 5   | `daily_report.py`          | **市场状态日报** → `Wiki/数据/市场状态日报.md` |
| 6   | `outlook_tracker.py batch` | 追踪标的批预测 |
| 7   | `bilibili_fetch.py`            | 抓取新视频字幕 |
| 8   | `rw_video.py --pending-only`   | 待审阅稿补标点 |
| 9   | `bilibili_fetch.py --dry-run`  | 预览 |
| —   | `sim_portfolio.py sync`        | 刷新模拟持仓现价（可选） |
| —   | `feishu_notify.py --pipeline-done` | Webhook 推送摘要（可选） |
| —   | `feishu_auto_sug.py --after-daily` | **自动** `agent sug 全员`（须 `FEISHU_AUTO_SUG=1`；按时段选早盘/午盘） |


**是的**：`daily.bat` **会自动运行** `daily_report.py`（第 5 步），无需单独双击。跑完后可选 Webhook 推送摘要。

约 15–25 分钟（含 `daily_report`、**标的追踪批预测** `outlook_tracker batch --universe track`，约 1–3 分钟）。完成后：

- **读报告**：飞书 `sug Wilson` / `sug 全员 午盘`（读 SugVault 已有归档）
- **生成报告**：Cursor `sug {持有人}`，或飞书 `agent sug 全员 午盘`
- **自动生成**（可选）：`.env` 设 `FEISHU_AUTO_SUG=1` + `CURSOR_API_KEY`，`daily.bat` 在 **11:30–13:00** 自动跑 `sug 全员 早盘`，**15:00 后** 自动跑 `sug 全员 午盘`，写入 `SugVault/` 并 Webhook 通知

每次 sug **前先** `review --holder …`，**归档后** `record`（数据目录 `Wiki/数据/股价预测追踪/`，见 `ANALYSIS_REPORT_SPEC.md`）。

### Cloud Agent 与本机数据（为何不是「直接读文件夹」）

| 组件 | 运行位置 | 能否读本机 vipdoc / 模拟持仓 |
| --- | --- | --- |
| **飞书 Bot**（`feishu_bot.bat`） | 你的电脑 | ✅ 本机脚本读 xlsx、vipdoc、Wiki，**嵌入 prompt** 再发给 Cloud Agent |
| **Cloud Agent**（`agent …` / AI 模拟盘 tick） | Cursor 云端 | ❌ 不能打开 `C:\zd_zsone\vipdoc`；只能看 prompt 内嵌数据 + 可选 GitHub 仓库 |
| **Cursor IDE**（`sug Wilson`） | 你的电脑 | ✅ 直接读全项目 |

**GitHub（`CURSOR_CLOUD_REPO`）是可选的**：给 Cloud Agent 补 Wiki 全文镜像；**不能**替代 vipdoc（GitHub 上没有 `.day` 文件）。本机 Bot / `ai_sim_tick` 在调用 Agent **之前**会抓取 vipdoc σ、1/3/7 最有可能价、`模拟持仓.xlsx` 摘要并写入 prompt 或 tick JSON。

`.env` 示例：

```env
TDX_VIPDOC=C:\zd_zsone\vipdoc
CURSOR_API_KEY=...
FEISHU_AUTO_SUG=1          # daily.bat 完成后自动 sug 全员
# CURSOR_CLOUD_REPO=...    # 可选，见下文「私有 GitHub」
```

### 私有 GitHub + Cloud Agent（能否上传 vipdoc / 持仓？）

**技术上可以，但不建议把整盘本机（含 vipdoc、持仓）推上 GitHub 来解决访问问题。**

| 问题 | 说明 |
| --- | --- |
| Cloud Agent 能读私有库吗？ | 可以。`.env` 设 `CURSOR_CLOUD_REPO=owner/repo`，并在 **Cursor 账号里授权 GitHub 应用**访问该私有仓库；Agent 会在云端 clone 该库并读文件。 |
| Private = 只有我和用户？ | **不等于。** 私有库 = GitHub 上仅授权协作者可见；但 **Cursor 云端**在跑 Agent 时会处理仓库内容与 prompt（受 [Cursor 隐私政策](https://cursor.com/privacy) / 套餐条款约束）。这不是「数据只留在本机」。 |
| 上传 vipdoc 合适吗？ | **不合适。** 体积大（GB 级 `.day`）、二进制、日更；Git 难维护。现有方案已在本机算好 σ/区间再嵌入 prompt，效果足够。 |
| 上传 `持仓.xlsx` / SugVault？ | **有隐私风险。** 即使 private repo，也会进入 GitHub + Cursor 处理链路；`.gitignore` 应继续排除 `.env`、真实持仓（若必须上库，用**单独私有库**且仅加可信协作者）。 |
| 多持有人「用户」隔离？ | GitHub 协作者 = 整库可见，**不能**按持有人行级隔离。更稳妥：**敏感持仓只留本机**，Cloud Agent 靠本机 Bot **嵌入 prompt**；Wiki 方法论可放 `CyberAdvisor` 公开/私有库。 |

**推荐分工：**

1. **`CyberAdvisor` 仓库（现有）**：Wiki、脚本；`CURSOR_CLOUD_REPO` 指向它 → Agent 读方法论与日更。
2. **敏感数据（持仓、vipdoc、`.env`）**：仅本机；由 `feishu_bot` / `ai_sim_tick` / `FEISHU_AUTO_SUG` 在调用 Agent **前**读取并写入 prompt。
3. **校验私有库是否被 Cursor 接受**：`python scripts/ai_sim_check_env.py --live`（会消耗少量 Agent 配额）。

若合规要求「持仓不得出本机」，则 **不要** 把持仓/vipdoc 推 GitHub；继续用当前「本机预抓取 + prompt」方案，或仅在 Cursor IDE 本地生成 `sug`。

### 飞书对接


| 能力         | 配置                                   | 说明                        |
| ---------- | ------------------------------------ | ------------------------- |
| **群推送**    | `FEISHU_WEBHOOK_URL`                 | `daily.bat` 跑完后自动推送摘要；`FEISHU_AUTO_SUG=1` 时 sug 完成后也推送 |
| **本机 Bot** | `FEISHU_APP_*` + 双击 `feishu_bot.bat` | `sug` 读 SugVault；`agent sug …` 异步生成 |


**推送（推荐先做）**：飞书群 → 自定义机器人 → 复制 Webhook → 写入 `.env` 的 `FEISHU_WEBHOOK_URL` → `python scripts/feishu_notify.py --test`

**本机 Bot**：飞书开放平台创建应用 → 开机器人 + `im.message.receive_v1` 事件 → Request URL 指向 `http://<公网>:8765/feishu/event` → 填 `.env` → 运行 `feishu_bot.bat`

**Wiki 文件**（飞书 Bot）：

```
策略文件              # Wiki 目录树（每日复盘/ 不展开文件列表）
打开 仓位管理          # 发送 Wiki/投资方法论/仓位管理.md
打开 每日复盘/2026-06-05
```

发送 `.md` 需权限 `**im:resource**`（「获取与上传图片或文件资源」）。

**Bot 权限（私聊 / 群聊分开）**：

- 私聊：`im:message.p2p_msg:readonly`
- 群聊 @：`im:message.group_at_msg:readonly`（须先把**应用机器人**拉进群，再 @ 发指令）
- 回复 / 发消息：`im:message:send_as_bot`（或 `im:message`）
- **发送文件**（`打开 …`）：`im:resource` — 中文名 **「获取与上传图片或文件资源」**
  - 路径：开放平台 → 你的应用 → **权限管理** → 搜索 **上传文件** 或 **im:resource** → 开通 → **创建版本并发布**
- 改权限后 **创建版本并发布**

> 电脑关机后 Bot 不可用。`ing` 仍走 Cursor；**`agent …`** 触发 Cloud Agent；`sug`/`qry` 为本地读。

**云持仓（daily 自动下载）**：在 `.env` 配置 `FEISHU_PORTFOLIO_URL`（飞书电子表格链接）或 `FEISHU_PORTFOLIO_NAME=持仓`；`daily.bat` 第一步会先覆盖本地 `持仓.xlsx`。权限：`drive:export:readonly`、发版。

### 飞书 Bot vs Cursor 命令对照

前提：**飞书 Bot** = 本机运行 `feishu_bot.bat` 且电脑在线；**Cursor** = 安装 `SKILL.md` 后在 IDE 对话。群 **Webhook 推送**不含交互命令，仅 `daily.bat` 完成后发摘要。

**`agent …` 仅飞书 Bot**（须 `.env` 配 `CURSOR_API_KEY`；Cloud Agent 在 Cursor 云端运行，本机 Bot 先抓取 vipdoc/持仓等嵌入 prompt）。Cursor IDE 对话**不需要**也不识别 `agent` 前缀。


| 命令                       | 飞书 Bot | Cursor + skill | 说明                                                     |
| ------------------------ | ------ | -------------- | ------------------------------------------------------ |
| `ing`                    | —      | ✅ 生成           | 消化 Raw 入 Wiki；Bot 无 AI 写作能力                            |
| `rw`                     | —      | ✅ / 脚本         | 视频稿 ASR 校正；`python scripts/rw_video.py --pending-only` |
| `txtcfm`                 | —      | ✅ / 脚本         | 批量审批；视频稿移入 `Raw/已审阅视频文稿/`                              |
| `sum`                    | —      | ✅ 生成           | 跨文章归纳；仅 Cursor                                         |
| `sug {持有人}`          | 📖 读 SugVault | ✅ **生成**       | Bot 只读已有归档；生成请用 Cursor 或 `agent sug …` |
| `sug {持有人} 早盘/午盘`    | 📖 读 | ✅ 生成 | 读 `SugVault/` 对应盘次文件名 |
| `sug 全员`             | 📖 分段读 | ✅ 逐人生成 | 读各持有人已有报告 |
| `sug 全员 早盘/午盘`       | 📖 分段读 | ✅ 逐人生成 | 读午盘/早盘归档；`FEISHU_AUTO_SUG=1` 时 daily 可自动写入 |
| **`agent sug {持有人}`** | ✅ 异步生成 | — | Cloud Agent；`.md` 附件 + 本机 Temp；**不写** SugVault |
| **`agent sug {持有人} 早盘/午盘`** | ✅ 异步生成 | — | 同上，prompt 含本机 vipdoc/模拟持仓快照 |
| **`agent sug 全员 [早盘/午盘]`** | ✅ 异步生成 × N | — | 每位持有人各一份附件 |
| **`agent qry {问题}`** | ✅ 异步生成 | — | 深度 Wiki 作答（Markdown 附件） |
| **`agent {自由任务}`** | ✅ 异步生成 | — | 如 `agent 给我一份新易盛的分析报告` |
| `agent`（无参数）           | ✅ 帮助 | — | 列出上述 agent 子命令 |
| `持仓 {持有人}`               | ✅ 读    | ✅ 读            | 读 `portfolio.md` 对应章节                                  |
| `标的池 {持有人}` / `日报 {持有人}` | ✅ 读    | ✅ 读            | 读标的池日报 + 该持有人做 T 章节                                    |
| `trk {标的}`               | ✅ 轻量   | ✅ 深度           | Bot：追踪页 + grep；Cursor：可刷新页、态度分析                        |
| `chk`                    | ✅ 轻量   | ✅ 深度           | Bot：待 ing 计数、断链/时效抽样；Cursor：可修复、归档                     |
| `qry {问题}`               | ✅ 轻量   | ✅ 深度           | Bot：本地 Wiki 关键词检索（非 Cloud Agent） |
| `策略文件`                   | ✅ 读    | —              | Bot：Wiki 目录树（`每日复盘/` 不列文件）                             |
| `打开 {路径或文件名}`            | ✅ 读    | —              | Bot：发送 Wiki `.md` 原文件（如 `打开 仓位管理`）                     |
| `sim 买/卖 {标的…}`          | ✅ 写    | ✅ 写            | 模拟持仓 `模拟持仓.xlsx`；Cursor `sug` 前自动 `sim sync`           |
| `帮助` / `ping`            | ✅      | —              | Bot 连通测试与指令列表（含 agent 说明）                          |
| `daily.bat`              | —      | —              | 双击运行；Webhook 推送；可选 `FEISHU_AUTO_SUG=1` 自动 agent sug 全员 |


图例：**✅ 生成** = AI 新建/更新内容；**📖 读** = 读本地已有文件；**✅ 读** = 双方均可查询；**—** = 不支持。**异步生成** = 先回复「已提交」，3–10 分钟后 `.md` 附件。

**典型日流程**：`daily.bat`（11:30/15:00 计划任务）→ Webhook 收摘要 → 若 `FEISHU_AUTO_SUG=1` 自动写入 `SugVault/` → 飞书 `sug 全员 午盘` 阅读，或 `agent sug 全员 午盘` 手动触发生成。

CLI 自测（与 Bot 同源）：`python scripts/wiki_cli.py trk 寒武纪` / `chk` / `qry 存储`

手动逐步跑：

```bash
cd scripts
python coarse_screen.py
python fine_screen.py
python daily_report.py    # 也可单独跑，输出 Wiki/数据/市场状态日报.md
```

### 抓取 B 站 B 站新内容

在项目根目录配置 `.env`（参考 `.env.example`，Cookie 勿提交 git），然后：

```bash
cd scripts
python bilibili_fetch.py              # 仅抓取视频字幕（2026-05-14 及之后）
python bilibili_fetch.py --dry-run    # 预览不写文件
```

- **视频字幕**（自动）→ `Raw/未审阅视频文稿/` → `**rw`** → `**txtcfm`**（→ `已审阅视频文稿/`）→ `**ing`**
- **专栏 / 动态 / 充电文**（手动）→ 复制为 `.md` 放入 `Raw/未分析归档/` → 对 AI 说 `**ing`**
- **ing 完成后** → 原稿移入 `Raw/已分析归档/`（可用 `python archive_raw.py archive 路径`）
- 视频同步状态：`Wiki/数据/bilibili_sync.json`

> 专栏/充电文不再自动抓取（B 站 API 易限流）。仅视频走 `bilibili_fetch.py`。

### 消化的文字稿


| 来源           | 流程                                                                    |
| ------------ | --------------------------------------------------------------------- |
| 专栏/动态（手动 md） | `Raw/未分析归档/` → `**ing`** → Wiki + `Raw/已分析归档/`                        |
| 视频字幕稿        | `Raw/未审阅视频文稿/` → `**rw`** → `**txtcfm`** → `Raw/已审阅视频文稿/` → `**ing`** |


### 操作代号速查（Cursor 为主）


| 命令                | 作用                                             | 怎么跑                                                  |
| ----------------- | ---------------------------------------------- | ---------------------------------------------------- |
| `ing`             | 消化 `Raw/未分析归档/` 与 `Raw/已审阅视频文稿/` 中未处理稿，更新 Wiki | Cursor 对话                                            |
| `txtcfm`          | 批量审批未审阅文稿；视频稿移入 `Raw/已审阅视频文稿/`                 | Cursor 或 `python scripts/txtcfm.py`                  |
| `rw`              | 校对视频文字稿（ASR + 补标点分段）                           | Cursor 或 `python scripts/rw_video.py --pending-only` |
| `sug {持有人}`       | 持仓分析 + 大盘判断 + 开仓建议 + 仓位分配                      | **Cursor 生成** → SugVault；飞书 Bot 用 `sug` 只读 |
| `sug {持有人} 早盘/午盘` | 同上，归档文件名带盘次                                    | 同上                                                   |
| `sug 全员` / `sug 全员 午盘` | 对每位持有人分别生成/读取 sug                           | Cursor 生成；飞书 `sug` 读 / `agent sug` 生成          |
| `qry {问题}`        | 基于 Wiki 回答                                     | Cursor 深度；飞书 `qry` 轻量检索 / `agent qry` Cloud Agent |
| `trk {标的}`        | Wiki 对该标的的全痕迹                                  | Cursor 可刷新；飞书 Bot 读追踪页                               |
| `chk`             | Wiki 体检                                        | Cursor 可修复；飞书 Bot 只读抽样                               |
| `sum`             | 跨文章归纳                                          | 仅 Cursor                                             |
| `sim 买/卖 {标的…}`   | 模拟持仓（100 万起/标的）                                | Cursor / 飞书 Bot；CLI 见上文 **模拟持仓**                     |

**飞书 Bot 专用（须 `agent` 前缀 + `CURSOR_API_KEY`）**：

| 命令 | 作用 |
| --- | --- |
| `agent sug {持有人} [早盘/午盘]` | Cloud Agent 异步生成 sug（附件；不写 SugVault） |
| `agent sug 全员 午盘` | 全员各一份 |
| `agent qry {问题}` | 深度 Wiki 问答 |
| `agent 给我一份{标的}的分析报告` | 单标的深度报告（本机嵌入 vipdoc） |


飞书 Bot 可读命令见上表 **[飞书 Bot vs Cursor](#飞书-bot-vs-cursor-命令对照)**。

---

## 状态圆点图例（🟢🟡🔴）

Wiki、sug 报告、`fine_screen` 输出的标的池日报里会出现彩色圆点。**同一颗 🔴 在不同场景含义不同**，请按「在哪看到」对号入座。

### 🔴 红色圆点：分场景含义


| 场景          | 常见位置                                    | 🔴 表示                           | 建议                                    |
| ----------- | --------------------------------------- | ------------------------------- | ------------------------------------- |
| **标的时效**    | `Wiki/内容源/标的总览.md` 状态列                  | **已过期** — 保鲜期已过且近期未再提及          | 勿当「现价推荐」；用 `trk {标的}` / `qry` 查最新态度   |
| **归档区标的**   | 标的总览 · 📁 历史归档                          | **已过期** — 同上，或早期机构研报标的（距今数月）    | 仅作研究历史信息源，不可直接跟买                      |
| **归档区标的**   | 标的总览 · 📁 历史归档                          | **待更新** — 逻辑仍有效但缺少近期 ingest 刷新  | 等新视频/复盘 `ing` 后再看，或 Cursor `trk` 手动更新 |
| **操作信号**    | `Wiki/内容源/决策时间线.md` 类型列                 | **防守/减仓类信号** — 如退潮确认、恐慌、风控、紧急减仓 | 对照当日 [[每日复盘]]；偏防守，勿与「标的过期」混淆          |
| **布林七轨**    | `Wiki/数据/标的池日报.md`、`fine_screen.py` 信号列 | **破顶轨-离场** — 现价 ≥ 七轨顶轨，偏离过大     | 不宜追高；持仓考虑减/做 T，等回踩再评估                 |
| **板块/地缘标签** | 部分 `Wiki/每日复盘/` 表格                      | **分类色标**（如地缘博弈中的板块分组）           | 语境标签，**不是**标的过期或卖点                    |
| **Wiki 体检** | Cursor `chk` 修复日志 / `Wiki/log.md`       | **严重项待修**（内部维护用语）               | 走 Cursor `chk` 让 AI 修复断链、降级过期标的       |


### 全套圆点速查（按出现频率）


| 圆点  | 标的总览            | 决策时间线       | 布林信号 / 标的池            | 含义概要          |
| --- | --------------- | ----------- | --------------------- | ------------- |
| 🟢  | 当前推荐 / 活跃       | 进攻、加仓、方向判断  | 收敛形态；**适合做 T 出**      | 有效、偏积极        |
| 🟡  | 待确认（保鲜期将尽或态度不明） | 观望、减仓预警、纪律  | N 字二轨候选；**收敛中不适合做 T** | 谨慎、待验证        |
| 🔴  | 已过期 / 待更新       | 退潮、减仓、风控、恐慌 | **破顶轨-离场**            | 过期或偏空/离场（视场景） |
| ⚫   | Wiki 看空         | —           | —                     | Wiki 明确不再看好   |
| 🔵  | —               | —           | 底轨附近-关注               | 超跌区，可观察不接飞刀   |
| ⚪   | —               | —           | 正常                    | 无特殊布林信号       |


**保鲜期**（决定 🟢 何时变 🟡/🔴）：短线 **5 个交易日** → 趋势 **30 日** → 产业逻辑 **90 日** → 方法论 **永久**。细则见 `schema.md` 第十二节、`Wiki/内容源/标的总览.md` 页眉。

**sug 报告**里个股行多用 🟢/🟡 标注技术形态与做 T 建议，一般不用 🔴；若见 🔴 优先看是否来自「布林破顶轨」或 Wiki 标的状态引用。

---

## 文件说明

```
CyberAdvisor/
├── daily.bat                ← 每日一键流水线（双击；含 daily_report.py）
├── feishu_bot.bat           ← 飞书 Bot 本机服务
├── 持仓.xlsx                ← 真实持仓数据源（同步到 portfolio / trade_template）
├── ai_sim_tick.bat          ← AI 模拟盘 15 分钟 tick
├── 模拟持仓.xlsx            ← AI 自主盘（500 万；持有人=AI）
├── SKILL.md                 ← AI skill 文件（必须安装）
├── portfolio.md             ← 多人持仓（按持有人分章，sug 读取）
├── trade_template.md        ← sug 回复模板（§七研判 + §八预测复盘）
├── ANALYSIS_REPORT_SPEC.md  ← sug / 单标的 / qry 报告统一规范
├── SugVault/                ← sug 历史（默认 YYYY-MM-DD_{持有人}_sug.md；早盘/午盘加后缀）
├── schema.md                ← Wiki 操作规范
├── Raw/                     ← 原始文字稿
│   ├── 未分析归档/          ← 手动放入待 ing 的 md（专栏/动态）
│   ├── 已分析归档/          ← ing 完成后的原稿备份
│   ├── 未审阅视频文稿/      ← bilibili_fetch 写入
│   └── 已审阅视频文稿/      ← txtcfm 审批后
├── Wiki/
│   ├── 投资方法论/
│   ├── 市场分析/
│   ├── 每日复盘/
│   ├── 内容源/              ← 标的总览、追踪、决策时间线
│   └── 数据/                ← 脚本输出（市场状态日报、标的池日报、粗筛 CSV…）
└── scripts/
    ├── feishu_download_portfolio.py  ← 飞书云文档 → 持仓.xlsx
    ├── wiki_cli.py          ← trk / chk / qry / sim-sync / track-maintain
    ├── wiki/                ← Wiki 轻量查询模块
    ├── ai_sim/              ← AI 自主模拟（采集/策略/日志）
    ├── ai_sim_tick.py       ← 单次 tick 入口
    ├── sim_portfolio.py     ← sim 买/卖/sync（手动干预）
    ├── feishu_auto_sug.py     ← daily 完成后自动 agent sug 全员
    ├── feishu_notify.py     ← 飞书 Webhook 推送
    ├── feishu_bot.py        ← 飞书 Bot 事件服务
    ├── feishu/              ← 飞书 SDK 模块（commands / wiki_local / drive）
    ├── sync_portfolio_from_xlsx.py  ← 持仓.xlsx → portfolio / trade_template
    ├── portfolio_utils.py     ← fmt_money、港股/AH 对照、行情拉取
    ├── portfolio.py         ← 持仓配置（脚本用）
    ├── coarse_screen.py
    ├── fine_screen.py
    ├── daily_report.py      ← 市场状态日报入口
    ├── market_daily/        ← 日报抓取与 Markdown 生成
    ├── bilibili_fetch.py    ← B 站视频字幕（仅视频）
    ├── rw_video.py          ← 视频稿 rw 校对
    ├── txtcfm.py            ← 批量审批未审阅文稿
    └── xlsx_utils.py          ← 持仓/模拟持仓 Excel 千位数字格式
```

---

## 选股逻辑

基于 Wiki「青哥」的投资框架：

1. **粗筛**：全市场 5000 只 → PE>0、PB<10、市值>50亿、非极端异动 → ~2000 只
2. **精筛**：ROE>10%、毛利率>20%、PEG 排序 → ~15 只
3. **布林线**：七轨布林线扫描，标记收敛/N字二轨/破顶轨信号
4. **核心标的池**：单独跟踪内容源推荐的核心标的

---

## 需要自己改的

- `持仓.xlsx` / `portfolio.md` / `scripts/portfolio.py`：你的**真实**持仓
- `模拟持仓.xlsx`：sim 虚拟盘（可选；`sim_portfolio.py init` 创建）
- `trade_template.md`：sug 模板中的示例行（与 portfolio 同步）
- `fine_screen.py` 里的 `TRACK_STOCKS`：标的池

---

## 浏览 Wiki

`Wiki/` 为标准 Markdown + `[[双链]]`，用 Cursor、VS Code 或任意编辑器即可；**无需 Obsidian**。

---

## 致谢

- Wiki「青枫浦上Q」的内容体系
- [Andrej Karpathy 的 LLM Wiki 理念](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [a-stock-data](https://github.com/simonlin1212/a-stock-data) A 股数据接口

