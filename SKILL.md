---
name: finance-wiki
description: 财经知识 Wiki 系统。基于 Andrej Karpathy LLM Wiki 理念，将财经博主的视频文字稿增量消化为结构化 Obsidian markdown 知识库。涵盖投资方法论提取、每日复盘追踪、标的推荐整理、Wiki 结构自进化、时效性分层管理、博主框架分析、持仓诊断、矛盾检测、交易策略建议(sug)。支持八种操作代号（rw/txtcfm/ing/qry/chk/trk/sum/sug）。触发词：财经 wiki、ingest、ing、txtcfm、审阅、审批、复盘、早盘、午盘、标的推荐、trk、chk、qry、sug Wilson、sug {持有人}、suggest、开仓、持仓分析、买什么、交易策略、博主矛盾、赛博UP主。
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
├── SugVault/               ← sug 历史报告（见下方命名规则）
├── scripts/
│   ├── sync_portfolio_from_xlsx.py
│   ├── sim_portfolio.py    ← sim 买/卖/sync
│   ├── bilibili_fetch.py   ← 仅视频字幕
│   ├── rw_video.py         ← 视频稿 rw
│   ├── txtcfm.py           ← 批量审批
│   └── archive_raw.py      ← ing 后归档
├── Raw/（原始稿）
│   ├── 未分析归档/          ← ing 输入：手动专栏/动态 md
│   ├── 已分析归档/          ← ing 完成后原稿归档
│   ├── 未审阅视频文稿/      ← bilibili_fetch 写入；rw 后 txtcfm 前
│   └── 已审阅视频文稿/      ← txtcfm 审批后；ing 读此目录
├── Wiki/
│   ├── 投资方法论/
│   ├── 市场分析/
│   ├── 每日复盘/
│   ├── 博主/
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

**投资成本 = 成本 × 股数**；**市值 = 现价 × 股数**（同步时拉取行情）；现金计入两项合计。sug 模板中金额单位用「元」，不用「万」。

### 模拟持仓（`sim 买` / `sim 卖`）

根目录 **`模拟持仓.xlsx`**，列 = `持仓.xlsx` 五列 + `现价`、`市值`、`盈亏`、`盈亏比`、`卖出？(Y/N)`、`建仓日期`、`持仓时间(天)`。持有人固定为 **模拟**。

| 指令 | 行为 |
|------|------|
| `sim 买 利通电子，江波龙，…` | 默认 **100 万元/标的**；若 100 万买不到（须 >100 股）则自动升至 **200 万、300 万…**（100 万整数倍）；**成本**锁定，**现价**随 sync 变动 |
| `sim rebuild` / `python scripts/sim_portfolio.py rebuild` | 按最新预算规则与市价重算**未卖出**持仓（已卖出行冻结） |
| `sim 卖 利通电子` | 按卖出时刻市场价冻结 **现价** 及盈亏，标记 `卖出？(Y/N)=Y`，**整行不再更新** |
| （sug 前自动） | `python scripts/sim_portfolio.py sync` — 刷新未卖出行的现价/盈亏 |
| 表末 **合计** | 空一行后汇总：**成本**=投资成本合计、**市值**=市值合计、**盈亏比**=组合总体盈亏比 |

CLI：`python scripts/sim_portfolio.py buy 利通电子` / `sell` / `sync` / `init`  
飞书 Bot：`sim 买 …` / `sim 卖 …`

**指令格式**（持有人名不区分大小写，须与 xlsx 精确匹配）：

---
- `sug {持有人}` — 例：`sug Wilson`（**Cursor 生成**完整报告；**飞书 Bot 仅读** `SugVault/` 已有报告）
- `sug {持有人} 早盘` / `sug {持有人} 午盘` — 指定盘次归档（见下方命名）
- `sug 全员` / `sug 全员 早盘` — **Cursor**：对每位持有人分别生成；**飞书**：分别读取已有报告
- `持仓 {持有人}`、`标的池 {持有人}`、`日报 {持有人}` — Cursor / 飞书 Bot **均可读**
- 格式错误或缺少持有人（`sug` 单独出现且非「全员」）→ 回复：`请校对格式sug {持有人}，以精确搜索`（其他指令将 `sug` 换为对应动词）
- 持有人不存在 → 列出 `portfolio.md` 中的持有人列表

---

## Ingest 操作（`ing`）

主 agent 直接处理。逐篇优于批量。

**内容来源规则：**
- **专栏/动态/充电文** → 用户手动复制 `.md` 到 `Raw/未分析归档/` → `ing` → 完成后移入 `Raw/已分析归档/`
- **视频字幕稿** → `bilibili_fetch.py` 自动入 `Raw/未审阅视频文稿/` → `rw` → **`txtcfm` 审批**（→ `Raw/已审阅视频文稿/`）→ `ing`

### 文稿审批（`txtcfm`）

触发条件：用户说 `txtcfm`、审阅通过、批量审批。

执行：`python scripts/txtcfm.py`（或 `--dry-run` 预览）

扫描并审批：
1. `Raw/未审阅视频文稿/` — 全部非 `approved`/`ingested` 的稿
2. `Raw/未分析归档/`（及旧 `待分析归档/`）— 无 frontmatter 的补写 `review_status: approved`

效果：`review_status: approved`、写入 `approved_at`、引用行「待审阅」→「已审阅」、**视频稿移入 `Raw/已审阅视频文稿/`**、追加 `log.md`。
**不 ingest**；审批后用户可再发 `ing`。

单篇步骤：
1. 扫描 `Raw/未分析归档/` 与 `Raw/已审阅视频文稿/`（`review_status: approved` 优先；对照 `log.md` 确认未处理）
2. 阅读全文（强制确认覆盖到文件末尾）
3. 提取关键信息，写入 Wiki
4. 写入后抽查末尾 3 段是否完整
5. 自进化检查 + 时效性检查
6. 更新 index.md、log.md
7. **归档**：`python archive_raw.py archive <该 md 路径>` 移入 `Raw/已分析归档/`（或等效 move）
8. **标的追踪维护**：`python scripts/wiki_cli.py track-maintain`（见下方「标的追踪」）

II 类文件（午盘补发/周末补充/晚间复盘）逐段对比 Wiki 页，不遗漏追加内容。

---

## 标的追踪（`trk` / `track-maintain`）

目录：

```
Wiki/博主/标的追踪/           ← 活跃池标的（fine_screen.BLOGGER_STOCKS）且提及≥3 次
Wiki/博主/标的追踪/不活跃标的/  ← 已有追踪页但已不在活跃池的标的
```

**自动规则**（`python scripts/wiki_cli.py track-maintain`）：

1. 活跃目录下、**不在** `BLOGGER_STOCKS` 的追踪页 → 移入 `不活跃标的/`（`股性-*` 等特殊页除外）
2. 活跃池内标的、Raw+Wiki **提及 ≥3 次** → 在活跃目录**新建**追踪页；若页在 `不活跃标的/` 则**回迁**

每次 `ing` 完成后应跑 `track-maintain`；`trk {标的}` 可读活跃/不活跃两处的专页。

CLI：`python scripts/wiki_cli.py trk 寒武纪` / `track-maintain`

---

## Suggest 操作（`sug {持有人}` / `sug 全员`）—— 交易策略建议

触发条件：
- `sug {持有人}`（如 `sug Wilson`）、`sug {持有人} 早盘|午盘`
- `sug 全员` 或 `sug 全员 早盘|午盘` — **按持有人循环**，每人独立生成一份报告
- 带持有人的 `开仓 {持有人}`、`买什么 {持有人}`、`持仓分析 {持有人}`、`交易策略 {持有人}`（可同样加 `早盘|午盘`）

**若仅说 `sug` / `开仓` 等而无持有人且非「全员」** → 直接回复：`请校对格式sug {持有人}，以精确搜索`（勿继续生成报告）。

**持有人校验**：与 `portfolio.md` / `持仓.xlsx` 中的持有人名精确匹配（不区分大小写）。未找到则列出可选持有人。

**`sug 全员` 执行**：读取 `scripts/portfolio.py` 的 `HOLDERS`（或 `portfolio.md` 章节），对每位持有人 **依次** 完成下方 1–7 步，每人输出一份完整报告并单独归档；回复中按持有人分段呈现。

执行流程（单人或全员中的每一位）：
0. **同步模拟持仓**：`python scripts/sim_portfolio.py sync`（跳过 `卖出？(Y/N)=Y` 的行）
1. 阅读 `portfolio.md` 中 **该持有人章节** 获取持仓（投资成本=成本×股数；市值=现价×股数；现金读该章「A 股现金」）
2. 运行 `scripts/coarse_screen.py` 和 `scripts/fine_screen.py` 获取最新数据
3. 阅读最近 2-3 天的博主早盘/复盘/午盘补发 Raw 文件
4. 阅读 `Wiki/博主/博主决策时间线.md` 了解博主最新节奏
5. 阅读 `Wiki/数据/博主标的池日报.md` 中 **该持有人的做T章节**（`## 持有人：XXX — 持仓做T`）
6. 严格按 `trade_template.md` 格式输出（二、三、五章金额 **仅含该持有人**）
7. **归档**（持有人名用 xlsx 中的 canonical 拼写）：
   - 未指定盘次：`SugVault/YYYY-MM-DD_{持有人}_sug.md`（同日多次则 `YYYY-MM-DD_HHMM_{持有人}_sug.md`）
   - 指定早盘/午盘：`SugVault/YYYY-MM-DD_{持有人}_sug 早盘.md` 或 `..._sug 午盘.md`（同日多次可加 `HHMM`：`YYYY-MM-DD_HHMM_{持有人}_sug 午盘.md`）

### 回复规则

**"不能"**：博主说减仓/不追高/等冰点且冰点未到；标的池全部在布林线一轨以上；退潮期

**"建议开"**：博主说分歧加仓/冰点低吸且冰点已现；有非科创板标的触发收敛/N字二轨信号

**"能"**：博主说持股为主/可以开仓/上升趋势完好；有二轨附近标的且优先级前 3

**其他 → "不建议"**

### 标的筛选规则
- **科创板（688xxx）自动排除**，用户买不了
- ETF 仅在博主明确提及时纳入，不自己编
- 优先推荐非科创板 + PE 在同板块中偏低 + 布林线收敛或二轨附近 + 博主优先级前 3 的标的

---

## 时效性管理

短线 5d → 🟡 | 趋势 30d → 🟡 | 产业逻辑 90d → 归档 | 方法论 → 永久。

标的总览三层：🟢 近期活跃 / 📁 历史归档 / 📖 案例股。

---

## 赛博 UP 主分析能力

### 持仓诊断流程
grep 全踪迹 → 定位框架 → 保鲜期 → 博主框架判断 → 区分博主/自己判断 → 读 portfolio.md 对应持有人章节的成本/股数

### 矛盾检测
拉态度时间线 → 标 🟢🟡🔴 → 查数据支撑 → 标沉默风险

### 博主框架速查表
能不能做 > 怎么做 > 做什么 | 80%贝塔+20%阿尔法 | 产业逻辑标的逻辑破坏才走 | 短线止损是纪律 | 不同周期不混用 | 风控第一

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
9. 视频稿：`Raw/未审阅视频文稿/` → `rw` → `txtcfm` → `Raw/已审阅视频文稿/` → `ing`；专栏/动态 → `未分析归档/` → `ing` → `已分析归档/`
10. B 站增量抓取：`python scripts/bilibili_fetch.py`（**仅视频字幕**）
11. 每日流水线：双击 `daily.bat`（持仓.xlsx 同步 → 选股 → 日报 → bilibili）
12. 飞书：`FEISHU_WEBHOOK_URL` 推送 daily 摘要；`feishu_bot.bat` 本机 Bot；Bot 指令：`sug {持有人} [早盘|午盘]`、`sug 全员`、`sim 买/卖`、`trk {标的}`、`chk`、`qry {问题}`
13. **ing 后**跑 `python scripts/wiki_cli.py track-maintain` 同步标的追踪目录

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
