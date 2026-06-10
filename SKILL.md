---
name: finance-wiki
description: 财经知识 Wiki 系统。基于 Andrej Karpathy LLM Wiki 理念，将 UP 主视频文字稿增量消化为结构化 Markdown 知识库（Wiki/，双链 [[页面名]]，无 Obsidian 依赖）。涵盖投资方法论提取、每日复盘追踪、标的推荐整理、Wiki 结构自进化、时效性分层管理、Wiki 框架分析、持仓诊断、矛盾检测、交易策略建议(sug)。支持八种操作代号（rw/txtcfm/ing/qry/chk/trk/sum/sug）。触发词：财经 wiki、ingest、ing、txtcfm、审阅、审批、复盘、早盘、午盘、标的推荐、trk、chk、qry、sug Wilson、sug {持有人}、suggest、开仓、持仓分析、买什么、交易策略、观点矛盾、赛博UP主。
---

# 财经 Wiki 系统

基于 Andrej Karpathy 的 LLM Wiki 理念构建的个人财经知识库系统。三层架构：Raw/ → Wiki/ → schema.md。

---

## 操作代号体系

| 代号 | 全称 | 操作 |
|------|------|------|
| `rw` | rewrite | 校对视频文字稿：ASR 术语校正 + **补标点分段**（`scripts/rw_video.py`） |
| `txtcfm` | text confirm | **批量审批**未审阅文稿 → `review_status: approved`（`scripts/txtcfm.py`） |
| `ing` | ingest | 消化入 wiki |
| `qry` | query | 基于 wiki 回答提问 |
| `chk` | check | wiki 体检 |
| `trk` | track | 标的追踪 |
| `sum` | summarize | 跨文章归纳 |
| `sug {持有人}` | suggest | **交易策略建议**（按持有人）：持仓分析+大盘判断+开仓建议+仓位分配 |
| `sug 全员` | suggest all | **对每位持有人分别**生成 sug 并各自归档 |
| `sim 买/卖` | sim trade | **模拟持仓**：每标的 100 万起、写入 `模拟持仓.xlsx` |
| `生成稳定点` | stable point | **Git 快照**：汇总当前改动 → `commit N：…` → **`git push origin master`**（完成后必推 GitHub） |

---

## Wiki 目录结构

```
{workspace}/
├── schema.md
├── portfolio.md            ← 用户持仓（按持有人分章，sug 必读）
├── 持仓.xlsx               ← 持仓数据源（含「持有人」列，daily.bat 同步）
├── 模拟持仓.xlsx           ← sim 买/卖 模拟盘（sug 前 sync 刷新现价）
├── daily.bat               ← 每日一键流水线
├── trade_template.md       ← sug 回复模板
├── ANALYSIS_REPORT_SPEC.md ← sug / 单标的 / qry 报告统一规范
├── SugVault/               ← sug 历史报告（见下方命名规则）
├── scripts/
│   ├── sync_portfolio_from_xlsx.py
│   ├── sim_portfolio.py    ← sim 买/卖/sync
│   ├── bilibili_fetch.py   ← 仅视频字幕
│   ├── rw_video.py         ← 视频稿 rw
│   ├── txtcfm.py           ← 批量审批
│   ├── material_extract.py ← 其他材料（pdf/pptx 等）文本提取
│   ├── archive_material.py ← 其他材料 ing 后归档
│   └── archive_raw.py      ← ing 后归档（自动 track-maintain）
├── Raw/（原始稿）
│   ├── 未分析归档/          ← ing 输入：手动专栏/动态 md
│   ├── 已分析归档/          ← ing 完成后原稿归档
│   ├── 未分析其他材料/      ← ing 输入：pdf/pptx/docx/txt/md 等
│   ├── 已分析其他材料/      ← 其他材料 ing 完成后原稿归档
│   ├── 未审阅视频文稿/      ← bilibili_fetch 写入；rw 后 txtcfm 前
│   └── 已审阅视频文稿/      ← txtcfm 审批后；ing 读此目录
├── Wiki/
│   ├── 投资方法论/
│   ├── 市场分析/
│   ├── 每日复盘/
│   ├── 视频专题/            ← 已审阅视频重组页（复盘/宏观/产业/方法论）；索引 [[视频专题索引]]
│   ├── 内容源/            ← 标的总览、追踪、决策时间线、观点演进
│   ├── 其他材料/            ← 其他材料 ingest 输出
│   └── 数据/（脚本输出）
```

---

## 持仓格式

以 `portfolio.md` 为准（由 `持仓.xlsx` 同步，**含「持有人」列**）。多人共用项目时，每位持有人独立一章：

```
## 持有人：Wilson
### A 股持仓
| 标的 | 代码 | 成本（元） | 股数 | 投资成本（元） | 现价（元） | 市值（元） |
...
**Wilson 投资成本合计** / **Wilson 市值合计**
```

用户录入格式（单持有人）：

```
我的持仓（Wilson）：
- 上海电力 成本 19.9102 元 100 股
```

**投资成本 = 成本 × 股数**；**市值 = 现价 × 股数**（同步时拉取行情）；现金计入两项合计。sug 模板中金额单位用「元」，不用「万」；**须千位逗号分隔**（例 `90,000,000.00`）。`持仓.xlsx` / `模拟持仓.xlsx` 内金额列使用 Excel `#,##0.00` 显示格式（`scripts/xlsx_utils.py`）。

**`持仓.xlsx` 列**（与 `sync_portfolio_from_xlsx.py` 一致）：`标的 | 代码 | 成本 | 股数 | 持有人`；可选 **`A股对照`**（非 A 股填 6 位 A 股代码，供布林/K 线；不填则用内置 AH 表）；表末可加 **`A股现金`** 行（标的列写「A股现金」，持有人必填）。

**代码规则**：A 股 6 位；**港股** 1–5 位或 `00700.HK` / `HK00700`（如腾讯 `700`）— 同步可拉港元现价；**做 T / 布林** 对非 A 股用 A 股对照或 AH 映射，仍无则标 **无 A 股对照数据**（腾讯等纯 H 股）。

### 模拟持仓（AI 自主盘 + 手动 `sim`）

根目录 **`模拟持仓.xlsx`**，列 = `持仓.xlsx` 五列 + `现价`、`市值`、`盈亏`、`盈亏比`、`卖出？(Y/N)`、`建仓日期`、`持仓时间(天)`。**持有人 = AI**。

| 模式 | 说明 |
|------|------|
| **AI 自主**（默认） | 总资金 **500 万元**；Windows 计划任务每 **15 分钟** 跑 `ai_sim_tick.bat` → 采集 → 自动买卖 → 写日志 |
| **手动 sim** | `sim 买/卖` 仍可覆盖/干预（飞书 Bot 或 CLI） |

CLI：`python scripts/sim_portfolio.py buy …` / `sell` / `sync` / `init`  
飞书 Bot：`sim 买 …` / `sim 卖 …`

---

## AI 自主模拟盘

> **交易结果汇总**：`Wiki/数据/AI模拟交易日志.md`（每笔 tick 追加）  
> **盘中行情**：`Raw/每15分钟市场数据/YYYY-MM-DD/HHMM.json`（及同名校 `.md`）

### 资金与持仓

| 项 | 值 |
|----|-----|
| 总资金 | **5,000,000.00 元** |
| 持仓文件 | `模拟持仓.xlsx`（持有人 **AI**） |
| 最多持仓标的 | **5** 只 |
| 单标的上限 | 总资金 **25%** |
| 4033/4130 等 | **Wiki L1–L5**（[[指数纪律框架]]）；**由 Agent 读 Wiki 后**在 `buy_permission` / `EQUITY_TARGET_NORMAL` 中体现，**规则引擎不硬编码** |

### 标的池

1. `Wiki/内容源/标的追踪/` **活跃**目录（不含 `不活跃/`、`股性-*`）且能在 `fine_screen.TRACK_STOCKS` 解析代码  
2. 当日 `Wiki/数据/市场状态日报.md` **涨幅 Top3 板块内 Top5** 成分（`daily_gain`）  
3. 跌幅板块成分仅用于 **卖出/回避** 参考（`daily_loss`）

### 采集时刻（交易日 Mon–Fri）

| 阶段 | 时刻 | 说明 |
|------|------|------|
| **早盘前** | **09:15** | 策略审视 + 可选调参（读 `Wiki/数据/AI模拟盘策略.md` + 全库 Wiki） |
| **盘中** | 09:30–11:15、13:00–14:45 每 15 分钟 | 常规 tick |
| **休市 daily** | **11:30**（上午收盘）、**15:00**（全天收盘） | 跑 **`daily.bat`**（持仓同步 + 市场日报 + bilibili 等；已休市不 sim 成交） |
| **午休复盘** | **11:45** | 上午复盘 + 下午策略；**可选**调参（每日一次） |
| **收盘复盘** | **15:15** | 全天复盘 + 为次日 09:15 准备 |

计划任务：`scripts/ai_sim_register_tasks.ps1`（**19** 个 ai_sim tick + **2** 个 daily）。**调参非必须**——充分分析后可 `hold_params` 维持不变。

### 自动决策（规则引擎 + Cloud Agent 调参）

> **多数 tick 只采集 + 分析，不必成交。** 现金以 `Wiki/数据/AI模拟盘现金.json` 为准。  
> **Cloud Agent** 每 tick 注入 **Wiki 全库索引 + 策略/宏观/选股/风控/日报**（`scripts/ai_sim/wiki_context.py`）；可选写入 `Wiki/数据/AI模拟盘参数.override.json`。

脚本 `scripts/ai_sim_tick.py`（单次 tick）：

1. 采集指数 + 标的池现价 + **各标的布林七轨快照**（`boll_zone` / `boll_signal` 等）→ `Raw/每15分钟市场数据/`（早盘前/午休/收盘后亦采集最近价）  
2. **Cloud Agent**（按阶段 `pre_open|intraday|lunch|post_close`）→ 读 **AI模拟盘策略.md + Wiki 全库** → 可选调参 + **`data_requests` 补充指标 enable/disable**  
3. 读 Wiki **市场状态日报**、**宏观分析框架**（含高盛整合）、**选股框架**（含 F10/PB/PEG/PS）  
4. **买入**（可选）：须 Agent **`buy_permission.allowed=true`** + 仓位低于目标；标的按池内综合得分排序（含布林参考，**无顶轨/跌幅硬过滤**）；`MAX_BUYS_PER_TICK` 控制笔数  
5. **卖出**（可选）：止损/止盈（Agent 可调 %）或超配降仓；**无布林自动离场**  
6. 成交写入 `模拟持仓.xlsx`；日志含 **阶段标签** + **数据扩展（data_requests 调整及原因）**  
7. **飞书推送**（`FEISHU_WEBHOOK_URL`）：本 tick **新增** 日志 + 可选附件  

**数据自我扩展**：Agent JSON 含 `data_requests: [{metric, action, reason, priority}]`；registry 见 `scripts/ai_sim/supplement_registry.yaml`；已注册 metric 可 **enable/disable**（下一 tick 采集）；未注册写入 `Wiki/数据/待扩展指标.md`。**禁止** Agent 自定义 HTTP。

环境变量（项目根 `.env`）：

| 变量 | 说明 |
|------|------|
| `CURSOR_API_KEY` | Cursor Dashboard → Integrations |
| `CURSOR_CLOUD_REPO` | 可选，`owner/repo`，Agent 可读完整 Wiki |
| `AI_SIM_AGENT=0` | 关闭 Agent，仅规则引擎 |
| `AI_SIM_AGENT_TIMEOUT` | 轮询超时秒数，默认 600 |

注册计划任务（管理员 PowerShell）：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\ai_sim_register_tasks.ps1
```

手动单次：`ai_sim_tick.bat --force` 或 `python scripts/ai_sim_tick.py --force`（`--no-agent` 跳过 Cloud Agent）

### Cursor Agent 职责（人工复盘层）

- 盘前/盘后阅读 **AI模拟交易日志** + 最新 tick 数据，必要时调整 `scripts/ai_sim/config.py` 默认值  
- 重大 Wiki 变化（指数纪律转向、仓位框架调整）时在日志 **写一条「Agent 备注」**  
- **禁止**在未跑 tick 的情况下手工改 xlsx 成本/股数（除用户明确要求）

**指令格式**（持有人名不区分大小写，须与 xlsx 精确匹配）：

---
- `sug {持有人}` — 例：`sug Wilson`（**Cursor 生成**完整报告；**飞书 Bot 仅读** `SugVault/` 已有报告）
- `sug {持有人} 早盘` / `sug {持有人} 午盘` — **盘次总结**（见下方「盘次语义」），非仅归档后缀
- `sug 全员` / `sug 全员 早盘` — **Cursor**：对每位持有人分别生成；**飞书**：分别读取已有报告
- `持仓 {持有人}`、`标的池 {持有人}`、`日报 {持有人}` — Cursor / 飞书 Bot **均可读**
- 格式错误或缺少持有人（`sug` 单独出现且非「全员」）→ 回复：`请校对格式sug {持有人}，以精确搜索`（其他指令将 `sug` 换为对应动词）
- 持有人不存在 → 列出 `portfolio.md` 中的持有人列表

---

## Ingest 操作（`ing`）

主 agent 直接处理。逐篇优于批量。

**ing 启动时先扫队列**：`python scripts/ing_pending.py`（或 `--json`），依次处理专栏/动态、**已审阅视频**、其他材料，直至三项皆空。

**内容来源规则：**
- **专栏/动态/充电文** → 用户手动复制 `.md` 到 `Raw/未分析归档/` → `ing` → 完成后移入 `Raw/已分析归档/`
- **视频字幕稿** → `bilibili_fetch.py` 自动入 `Raw/未审阅视频文稿/`（**已含补标点**）→ `daily.bat` 第 7 步 `rw_video.py` 再校正 → **`txtcfm` 审批** → `ing`
- **其他材料**（研报 pdf、pptx、docx、txt 等）→ 放入 `Raw/未分析其他材料/` → `ing` → 结构化 md 写入 `Wiki/其他材料/` → 原文件移入 `Raw/已分析其他材料/`

### 其他材料 ingest（`Raw/未分析其他材料/`）

1. 扫描目录：`python scripts/material_extract.py list`（支持 `.pdf` `.pptx` `.docx` `.txt` `.md`）
2. 逐篇提取全文：`python scripts/material_extract.py extract <文件>`（或 `extract-all` 批量到 `Wiki/其他材料/_extracts/` 辅助阅读）
3. **阅读提取正文**（须覆盖到末尾），理解主题后写入 `Wiki/其他材料/{主题或文件名}.md`（frontmatter 含 `source_file`、`material_type`、`ingested_at`）
4. 更新 `index.md`、`log.md`（操作类型注明「其他材料 ingest」）
5. **归档原文件**：`python scripts/archive_material.py archive <源文件路径>`（全部完成可用 `archive-all`）
6. 与视频/专栏内容无直接双链时可链到 `Wiki/市场分析/` 或相关标的页；**勿**混入 `每日复盘/` 除非明确是 Wiki 口径

单篇步骤（专栏/动态）：
1. 扫描 `Raw/未分析归档/`（对照 `log.md` 确认未处理）
2. 阅读全文（强制确认覆盖到文件末尾）
3. 提取关键信息，写入 Wiki
4. 写入后抽查末尾 3 段是否完整
5. 自进化检查 + 时效性检查
6. **指数纪律升级检查**：若本篇含新指数点位/纠错/回补/清仓/量能条件 → 按 `schema.md` § 十·一 更新 [[指数纪律框架]] 及关联页（不可只写日更）
7. 更新 index.md、log.md
8. **归档**：`python scripts/archive_raw.py archive <路径>` → `Raw/已分析归档/`（自动 track-maintain）

### 视频字幕稿 ingest（双轨，必做）

来源：`Raw/已审阅视频文稿/`（`txtcfm` 后 `review_status: approved`）。

**`ing` 必须遍历该目录**：凡 `tasks` 含 `daily_wiki` 和/或 `video_topic` 的稿均需处理（见 `python scripts/ing_pending.py`）。

| 轨道 | 输出 | 说明 |
|------|------|------|
| **A · 日更** | `Wiki/每日复盘/YYYY-MM-DD.md` | 操作信号、指数纪律、当日板块摘要；可合并进已有日更 |
| **B · 视频专题** | `Wiki/视频专题/{复盘\|宏观\|产业\|方法论}/视频YY-MM-DD-标题.md` | 全文理解后**重组**（非粘贴字幕）；索引 hub：[[视频专题索引]] |

**视频单篇步骤（A+B 同一轮 `ing` 内完成）**：
1. `python scripts/ing_pending.py --json` 确认本篇待办（`daily_wiki` / `video_topic`）
2. 阅读 Raw **全文**至末尾
3. **轨道 A**：更新/新建对应 `[[YYYY-MM-DD]]` 日更（§ 视频 或并入正文）
4. **轨道 B**：按分类写入 `Wiki/视频专题/{category}/`（frontmatter 含 `date` `type: 视频专题` `category` `bvid` `tags` `source_raw`；正文：核心观点 → 盘面/框架 → 板块 → 纪律 → 链接）
5. 分类默认启发式见 `scripts/wiki/video_topic.py`；不确定时优先 **复盘**
6. 更新 [[视频专题索引]]（新视频追加一行）、`index.md`、`log.md`；交叉链到 [[单根K线]]、[[宏观分析框架]] 等已有页
7. **归档 Raw**：`python scripts/archive_raw.py archive <路径>` → `review_status: ingested`，留 `Raw/已审阅视频文稿/`
8. **回写专题路径**：`python scripts/wiki/video_topic.py mark --raw <路径> --wiki Wiki/视频专题/.../....md`

> 仅缺专题、日更已入库：`review_status: ingested` 且无 `wiki_topic_path` 时，`ing` 仍须补做 **轨道 B** + `mark`。

II 类文件（午盘补发/周末补充/晚间复盘）逐段对比 Wiki 页，不遗漏追加内容。

### 文稿审批（`txtcfm`）

触发条件：用户说 `txtcfm`、审阅通过、批量审批。

执行：`python scripts/txtcfm.py`（或 `--dry-run` 预览）

扫描并审批：
1. `Raw/未审阅视频文稿/` — 全部非 `approved`/`ingested` 的稿
2. `Raw/未分析归档/`（及旧 `待分析归档/`）— 无 frontmatter 的补写 `review_status: approved`

效果：`review_status: approved`、写入 `approved_at`、引用行「待审阅」→「已审阅」、**视频稿移入 `Raw/已审阅视频文稿/`**、追加 `log.md`。
**不 ingest**；审批后用户可再发 `ing`。

---

## 标的追踪（`trk` / `track-maintain`）

目录：

```
Wiki/内容源/标的追踪/           ← 活跃池标的（fine_screen.TRACK_STOCKS）且提及≥3 次
Wiki/内容源/标的追踪/不活跃标的/  ← 已有追踪页但已不在活跃池的标的
```

**自动规则**（`archive_raw.py archive` 归档时自动调用；亦可手动 `python scripts/wiki_cli.py track-maintain`）：

1. 活跃目录下、**不在** `TRACK_STOCKS` 的追踪页 → 移入 `不活跃标的/`（`股性-*` 等特殊页除外）
2. 活跃池内标的、Raw+Wiki **提及 ≥3 次** → 在活跃目录**新建**追踪页；若页在 `不活跃标的/` 则**回迁**

ing 归档时由 `archive_raw.py` 自动触发；`trk {标的}` 可读活跃/不活跃两处的专页。

CLI：`python scripts/wiki_cli.py trk 寒武纪` / `track-maintain`

---

## 市场状态日报（`daily_report.py` / `daily.bat` 第 5 步）

输出：`Wiki/数据/市场状态日报.md`（`scripts/market_daily/` 实现）

**必抓字段**（每次运行须完整写入）：

| 章节 | 内容 |
|------|------|
| **一、主要指数** | 上证/深证/创业板/科创50/北证50/沪深300/上证50/国证2000/中证500/创业板综等：**收盘、涨跌、涨跌幅、开盘、最高、最低、振幅、均价、成交额(亿)、成交量**；标注 **4033/4130** 相对位置 |
| **二、概念板块 Top3** | **涨幅 Top3** + **跌幅 Top3**（东方财富概念板块） |
| **三、板块内 Δ市值 Top5** | 每个 Top3 涨/跌板块内，按 **市值变化（非涨跌幅）** 排序的 Top5 标的 |
| **四、活跃标的追踪** | `Wiki/内容源/标的追踪/` 活跃目录（不含 `不活跃标的/`、`股性-*`）全量：**行情明细 + 逐只摘要** |
| **五、市场总结** | 结合当日数据 + `Wiki/市场分析/` + **[[指数纪律框架]]** L1–L5 + 板块轮动、追踪池表现 |

**消费方**：
- `sug … 午盘` / 收盘复盘：**必读第一节指数收盘** + 第五节总结
- `sug … 早盘`：可读前一交易日第五节 + 当日 Wiki 日更

数据源：腾讯 `qt.gtimg.cn`（指数/个股）+ 东方财富 `push2delay.eastmoney.com`（概念板块；`trust_env=False` 不走系统代理）

**金额格式**：报告内成交额、市值、Δ市值等 **金额列** 须千位逗号（`scripts/portfolio_utils.fmt_money`）。

---

## Suggest 操作（`sug {持有人}` / `sug 全员`）—— 交易策略建议

触发条件：
- `sug {持有人}`（如 `sug Wilson`）、`sug {持有人} 早盘|午盘`
- `sug 全员` 或 `sug 全员 早盘|午盘` — **按持有人循环**，每人独立生成一份报告
- 带持有人的 `开仓 {持有人}`、`买什么 {持有人}`、`持仓分析 {持有人}`、`交易策略 {持有人}`（可同样加 `早盘|午盘`）

**若仅说 `sug` / `开仓` 等而无持有人且非「全员」** → 直接回复：`请校对格式sug {持有人}，以精确搜索`（勿继续生成报告）。

**持有人校验**：与 `portfolio.md` / `持仓.xlsx` 中的持有人名精确匹配（不区分大小写）。未找到则列出可选持有人。

**`sug 全员` 执行**：读取 `scripts/portfolio.py` 的 `HOLDERS`（或 `portfolio.md` 章节），对每位持有人 **依次** 完成下方 1–7 步，每人输出一份完整报告并单独归档；回复中按持有人分段呈现。

### 盘次语义（重要）

`早盘` / `午盘` 指 **该时段结束后的回顾总结**，不是盘中前瞻指令。

| 指令 | 含义 | 建议生成时机 | 叙述视角 |
|------|------|------------|---------|
| `sug … 早盘` | **早盘总结** | 上午收盘后（约 11:30 后） | **回顾** 9:30–11:30：盘面、Wiki 早盘/上午动态、持仓涨跌、做 T 是否执行 |
| `sug … 午盘` | **午盘/收盘总结** | **全天收盘后**（约 15:00 后） | **回顾** 13:00–15:00 及全天：含 **实际收盘点位**、4033/4130 纪律 **是否已触发** |
| `sug …`（无盘次） | 当日策略 | 盘前或用户未指定盘次时 | 可为前瞻，但须标注生成时刻 |

**午盘总结禁止**写「午盘至收盘必盯」「收盘前必盯 4033」等——午盘已结束，应写 **「收盘 xxxx，相对 4033/4130 已…」**。

**早盘总结禁止**写「下午必盯」「午盘待验证」式全文；可简短一句「午后待观察 xxx」。

**第一章「大盘与 Wiki 判断」**：盘次总结须填 **该时段已发生** 的指数收盘/高低、成交额、Wiki/Raw 动态（含当日已 ingest 的 Wiki/Raw）。

**第三章持仓**：用 **该时段结束时的现价**（午盘总结 = 收盘价）。

**第四章「能不能开新仓」**：盘次总结侧重 **今日是否已操作/是否应留到次日**；4033 已破则写 **指数纪律已触发 → 应清仓/已清仓/待执行**。

**第六章风险**：盘次总结 = **今日已兑现的风险** +（可选）**次日一句**；勿把「尚未发生的收盘风险」写成当前 tense。

执行流程（单人或全员中的每一位）：
0. **同步模拟持仓**：`python scripts/sim_portfolio.py sync`（跳过 `卖出？(Y/N)=Y` 的行）
0a. **持仓批追踪（仅 `sug 全员 午盘`）**：`python scripts/outlook_tracker.py batch --universe portfolio --session 午盘` → 结论在 `Wiki/数据/股价预测追踪/复盘/`；规范见 **`ANALYSIS_REPORT_SPEC.md`**
0b. **预测复盘（§八 · 必做）**：`python scripts/outlook_tracker.py review --holder {持有人}` → 粘贴输出；规范见 **`ANALYSIS_REPORT_SPEC.md`**
1. 阅读 `portfolio.md` 中 **该持有人章节** 获取持仓（投资成本=成本×股数；市值=现价×股数；现金读该章「A 股现金」）
2. 运行 `scripts/coarse_screen.py` 和 `scripts/fine_screen.py` 获取最新数据
2b. **盘次总结**须读 `Wiki/数据/市场状态日报.md`（**第一节指数收盘**、第二–四节盘面、**第五节总结**）
3. 阅读最近 2-3 天的日更/复盘/午盘 Raw；**盘次总结**须含 **当日** 同时段 Wiki（如 `[[2026-06-05]]`）及已 ingest 动态
4. 阅读 `Wiki/内容源/决策时间线.md` 了解 Wiki 最新操作节奏（输出称 **决策时间线**）
5. 阅读 `Wiki/数据/标的池日报.md` 中 **该持有人的做T章节**（输出称 **标的池日报**）
6. 严格按 `trade_template.md` 格式输出（二、三、五章金额 **仅含该持有人**）
6b. **研判总结（§七 · 必写）**：`python scripts/analysis_report.py --holder {持有人}` 或等价调用；含七轨、补充数据（含 **vipdoc**）、1/3/7 日 **最有可能价位** + 挡位概率表；见 **`ANALYSIS_REPORT_SPEC.md`**
7. **归档**（持有人名用 xlsx 中的 canonical 拼写）：
   - 未指定盘次：`SugVault/YYYY-MM-DD_{持有人}_sug.md`（同日多次则 `YYYY-MM-DD_HHMM_{持有人}_sug.md`）
   - 指定早盘/午盘：`SugVault/YYYY-MM-DD_{持有人}_sug 早盘.md` 或 `..._sug 午盘.md`（同日多次可加 `HHMM`：`YYYY-MM-DD_HHMM_{持有人}_sug 午盘.md`）
7b. **登记预测**：`python scripts/outlook_tracker.py record --holder {持有人} --source sug --session {早盘|午盘|}`
8. **飞书推送**（配置 `FEISHU_WEBHOOK_URL` 后自动；未配置则跳过）：
   - 单人：`python scripts/feishu_notify.py --sug-done --holder {持有人}`（有盘次加 `--session 早盘|午盘`）
   - 全员：`python scripts/feishu_notify.py --sug-done --all-holders`（同样可加 `--session`）

**全员** `sug 全员` 对每位持有人 **分别** 执行 0b→7b 全流程；**`sug 全员 午盘`** 在循环前 **先执行 0a**（持仓.xlsx 全标的批追踪）。

**daily.bat** 第 6 步自动对 `Wiki/内容源/标的追踪` 执行 `batch --universe track`（复盘到期 + 无历史预测则登记，追踪自次日）。

**单标的分析报告**（`qry` 深度诊断、根目录 `*_分析.md`）：遵守 **`ANALYSIS_REPORT_SPEC.md`**（**§专业名词解释**、同业对比、补充数据含 **vipdoc**、1/3/7 日 **最有可能价位** + 概率表）；术语章用 `report_glossary.format_glossary_markdown`；归档后 `outlook_tracker record --code … --source analysis_report`（自动写入 `询问标的.json`）。

**用户对话中询问的标的**：生成分析或给建议前执行 `python scripts/outlook_tracker.py register-queried --code {code} --name {名称} --source chat`；无历史预测时可用 `record --code … --track-from-tomorrow`。

### 文稿审批（`txtcfm`）

**"不能"**：Wiki/日更口径为减仓/不追高/等冰点且冰点未到；标的池全部在布林线一轨以上；退潮期

**"建议开"**：Wiki 口径为分歧加仓/冰点低吸且冰点已现；有非科创板标的触发收敛/N字二轨信号

**"能"**：Wiki 口径为持股为主/可以开仓/上升趋势完好；有二轨附近标的且标的池优先级前 3

**其他 → "不建议"**

### 标的筛选规则
- **科创板（688xxx）自动排除**，用户买不了
- ETF 仅在 Wiki/日更明确提及时纳入，不自己编
- 优先推荐非科创板 + PE 在同板块中偏低 + 布林线收敛或二轨附近 + 标的池优先级前 3 的标的

---

## 时效性管理

短线 5d → 🟡 | 趋势 30d → 🟡 | 产业逻辑 90d → 归档 | 方法论 → 永久。

标的总览三层：🟢 近期活跃 / 📁 历史归档 / 📖 案例股。

---

## 赛博 UP 主分析能力

### 持仓诊断流程
grep 全踪迹 → 定位框架 → 保鲜期 → Wiki 框架判断 → 区分 Wiki/自己判断 → 读 portfolio.md 对应持有人章节的成本/股数

### 矛盾检测
拉态度时间线 → 标 🟢🟡🔴 → 查数据支撑 → 标沉默风险

### Wiki 框架速查表
能不能做 > 怎么做 > 做什么 | 80%贝塔+20%阿尔法 | 产业逻辑标的逻辑破坏才走 | 短线止损是纪律 | 不同周期不混用 | 风控第一

---

## B站字幕与讲稿（内嵌 bilibili-transcript）

> 原 Cursor 全局 skill `bilibili-transcript` 已合并进本项目；**日常 ingest 走下方流水线**，单链临时抓取见「单链模式」。

### 项目流水线（推荐）

| 步骤 | 脚本 | 说明 |
|------|------|------|
| 1 增量抓取 | `scripts/bilibili_fetch.py` | UP 主新视频 → `Raw/未审阅视频文稿/`（`daily.bat` 第 6 步） |
| 2 rw | `scripts/rw_video.py` | ASR 术语校正 + 补标点分段（第 7 步 `--pending-only`） |
| 3 txtcfm | `scripts/txtcfm.py` | 审批 → `Raw/已审阅视频文稿/` |
| 4 ing | 主 agent | 结构化写入 Wiki → `archive_raw.py archive` |

**重拉单视频**（充电/抢先看字幕错或空）：

```bash
python scripts/bilibili_refetch_video.py BVxxxxxxxx
python scripts/rw_video.py --refetch --pending-only
```

**实现要点**（优于通用 WebFetch `/x/player/v2`）：

- 播放器 API：**WBI** `GET /x/player/wbi/v2`（`scripts/bilibili/client.py`）
- 环境：`.env` 中 `BILIBILI_SESSDATA`（及可选 Cookie）；无 Cookie 时公开字幕可能不全
- 字幕挑选：`scripts/bilibili/transcript.py`（优先人工 zh-CN，其次 ai-zh）
- 格式化：`scripts/bilibili/rw_format.py`（`format_transcript` / `re_punctuate`）
- 同步状态：`Wiki/数据/bilibili_sync.json`

### 单链模式（临时、非 daily 流水线）

用户只给 **一个 B 站链接** 要讲稿 `.txt` 时（不进 Wiki 流水线）：

1. 从 URL 解析 `bvid`（`BV` 开头）
2. `GET https://api.bilibili.com/x/web-interface/view?bvid=` → 取 `cid`、`title`
3. 用 **WBI player**（或带 Cookie 的 `BiliClient`）取 `subtitle.subtitles`
4. 下载 `subtitle_url` JSON，拼接 `body[].content`
5. 整理：去重、补标点、语义分段；非中文则输出原文 + 中文翻译
6. 可选 Write 到工作目录；**若需入库**则仍应走 fetch → rw → txtcfm → ing

**错误处理**：`-352`/412 → 补 Cookie；`subtitles` 空 → 无字幕；多 P 默认第一 P。

---

## 关键经验

1. 不做 RAG，做 wiki
2. 逐篇优于批量
3. ingest 必须读到 Raw 末尾，写入后抽查
4. 主 agent 直接处理 ingest
5. 时效性分层
6. sug 回复严格按模板，不自由发挥；**按持有人归档至 SugVault/**
7. 科创板不推荐
8. 诚实 > 讨好
9. 视频稿：`Raw/未审阅视频文稿/` → `rw` → `txtcfm` → `Raw/已审阅视频文稿/` → **`ing`（日更 + Wiki/视频专题/）** → `video_topic.py mark`；专栏/动态 → `未分析归档/` → `ing` → `已分析归档/`
10. B 站增量抓取：`python scripts/bilibili_fetch.py`（**仅视频字幕**）
11. 每日流水线：双击 `daily.bat`（… → bilibili_fetch → **rw_video 补标点** → dry-run）
12. 飞书：`FEISHU_WEBHOOK_URL` 推送 daily 摘要；`feishu_bot.bat` 本机 Bot；Bot 指令：`sug {持有人} [早盘|午盘]`、`sug 全员`、`sim 买/卖`、`trk {标的}`、`chk`、`qry {问题}`
13. **ing 归档**时 `archive_raw.py` 自动跑 `track-maintain` 同步标的追踪目录
14. **`生成稳定点`**：审查 `git status` → 排除 `.env`/`__pycache__`/SugVault 报告 → `commit N：摘要` → **`git push origin master`**（用户约定：稳定点完成后必推 GitHub）

---

## 表述规范（对外输出 · 必守）

**面向用户的回答、分析、sug、qry、trk 解读、根目录报告等**，须锚定可核查材料并 **标明出处**：

| 语境 | 推荐用语 |
|------|----------|
| 知识库综合 | **Wiki**（链到具体页，如 [[指数纪律框架]]） |
| 当日/历史盘面 | **日更** / **[[YYYY-MM-DD]]** |
| 机构/专题材料 | **研报** / **Raw 稿** / **专栏** / **视频专题** |
| 操作节奏 | **决策时间线** / **Wiki 框架判断** |
| 标的与信号 | **标的池日报** / **标的总览** / **Wiki 追踪口径** |
| 口径不一致 | **Wiki 口径矛盾**（触发词：观点矛盾） |

**写法要求：**
1. 关键结论须标明出处（`[[2026-06-10]]`、`Raw/已分析归档/研报：…`、[[板块轮动记录]] 等）。
2. 目录 `Wiki/内容源/`、代码 `TRACK_STOCKS` 等与文案一致；勿混用旧路径。
3. `trade_template.md`、SugVault 归档、sug 飞书摘要 **同样遵守**本规范。
4. 免责声明统一为：**「以上整理自项目内 Wiki/研报/Raw，不构成投资建议。」**

---

## 飞书 Bot vs Cursor 命令对照

本机 `feishu_bot.bat` 运行时可发（**不需 Cursor**）；完整对照见项目 `README.md`。

| 命令 | 飞书 Bot | Cursor + skill | 差异要点 |
|------|:--------:|:--------------:|----------|
| `ing` / `rw` / `txtcfm` / `sum` | — | ✅ | 写 Wiki / 跑脚本；Bot 无 AI 写入 |
| `sug {持有人}` [早盘\|午盘] | 📖 读 SugVault | ✅ 生成 | Bot 无报告时提示去 Cursor |
| `sug 全员` | 📖 分段读 | ✅ 逐人生成 | |
| `持仓` / `标的池` / `日报 {持有人}` | ✅ 读 | ✅ 读 | 读 `portfolio.md`、标的池日报 |
| `trk {标的}` | ✅ 轻量 | ✅ 深度 | AI 版可刷新追踪页、态度分析 |
| `chk` | ✅ 轻量 | ✅ 深度 | AI 版可修复、降级归档 |
| `qry {问题}` | ✅ 关键词 | ✅ 综合 | AI 版多页归纳作答 |
| `sim 买/卖 {标的…}` | ✅ | ✅ | 模拟持仓；sug 前 Cursor 跑 `sim_portfolio.py sync` |
| `帮助` / `ping` | ✅ | — | Bot 专用 |

格式错误：`请校对格式{cmd} {参数}，以精确搜索`（如 `trk {标的}`、`qry {问题}`、`sug {持有人}`）

CLI 测试（与 Bot 同源）：`python scripts/wiki_cli.py trk 寒武纪` / `track-maintain` / `chk` / `qry 存储`
