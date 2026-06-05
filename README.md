# F:\AIGC\Stocks\CyberAdvisor\Wiki\博主赛博青哥 Wiki

> 基于财经博主「青枫浦上Q」全部公开内容的 AI 知识库 + 交易决策系统。
> 把你的 AI 助手变成赛博青哥。

---

## 这是什么

一套完整的投资辅助系统：

- **Wiki 知识库**：博主 2025.10~2026.05 全部方法论 + 121 天每日复盘 + 标的全追踪
- **选股脚本**：全市场粗筛 → 博主 F10 框架精筛 → 七轨布林线扫描
- **交易策略**：持仓诊断 + 开仓建议 + 做 T 策略 + 每日市场状态
- **模拟持仓（sim）**：按博主建议虚拟建仓/平仓，100 万起/标的，独立于真实 `持仓.xlsx`
- **AI 集成**：配套 skill 文件，AI 助手直接加载

---

## 快速开始（3 步）

### 1. 安装依赖

```bash
pip install -r requirements.txt
python -m mootdx bestip
```

> 需要国内 IP（mootdx 连通达信服务器）。若 `bestip` 测速失败导致 `BESTIP` 为空，可手动编辑 `~/.mootdx/config.json`，在 `BESTIP.HQ` 填入可用服务器，例如 `["110.41.147.114", 7709]`。

### 2. 安装 skill

把项目根目录的 `SKILL.md` 放到你的 AI 助手的 skill 目录：


| 助手          | skill 目录                                             |
| ----------- | ---------------------------------------------------- |
| Cursor      | `C:\Users\{用户名}\.cursor\skills-cursor\finance-wiki\` |
| Claude Code | `~/.claude/skills/finance-wiki/`                     |
| Codex       | `~/.codex/skills/finance-wiki/`                      |


skill 加载后，你的 AI 助手会拥有这些能力。

### 3. 配置你的持仓

**推荐**：编辑根目录 `持仓.xlsx`（列：**持有人**、标的、代码、成本、股数），或 **在飞书电子表格维护「持仓」**，由 `daily.bat` 自动下载覆盖本地文件后同步。


| 持有人    | 标的   | 代码     | 成本      | 股数  |
| ------ | ---- | ------ | ------- | --- |
| Wilson | 上海电力 | 600021 | 19.9102 | 100 |


现金行：`A股现金` 写在标的列，金额写在成本列，**持有人列必填**。

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
sug Wilson              # 交易策略（Cursor 生成 → SugVault；飞书 Bot 读已有报告）
sug Wilson 早盘          # 归档为 YYYY-MM-DD_Wilson_sug 早盘.md
sug Wilson 午盘          # 归档为 YYYY-MM-DD_Wilson_sug 午盘.md
sug 全员                 # Cursor：分别生成；飞书：分别读取已有报告
持仓 Wilson              # 查看该持有人持仓（Cursor / 飞书均可）
标的池 Wilson            # 博主池 + 该持有人做T（Cursor / 飞书均可）
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

### 4. 模拟持仓（可选）

根目录 **`模拟持仓.xlsx`** 用于按博主信号**虚拟跟单**，与真实持仓分离。列 = `持仓.xlsx` 五列 + `现价`、`市值`、`盈亏`、`盈亏比`、`卖出？(Y/N)`、`建仓日期`、`持仓时间(天)`；持有人固定为 **模拟**。

| 指令 | 行为 |
|------|------|
| `sim 买 利通电子，江波龙` | 默认 **100 万元/标的**；买不到（须 >100 股）则自动升至 200 万、300 万…；**成本**锁定 |
| `sim 卖 利通电子` | 按卖出时刻市价冻结盈亏，标记 `卖出？(Y/N)=Y`，**整行不再更新** |
| `sim rebuild` | 按最新预算规则重算**未卖出**持仓（已卖出行冻结） |

CLI：

```bash
python scripts/sim_portfolio.py init          # 创建空表
python scripts/sim_portfolio.py buy 利通电子   # 模拟买入
python scripts/sim_portfolio.py sell 利通电子  # 模拟卖出
python scripts/sim_portfolio.py sync          # 刷新未卖出行的现价/盈亏
python scripts/wiki_cli.py sim-sync           # 同上
```

Cursor 对话或飞书 Bot 均可：`sim 买 …` / `sim 卖 …`。生成 `sug` 前 Cursor 会自动跑 `sim_portfolio.py sync`（跳过已标记卖出的行）。表末有 **合计** 行汇总投资成本、市值与组合盈亏比。

---

## 怎么用

### 每日操作

**一键流水线**（双击根目录 `daily.bat`，在新终端依次执行 **7 步**）：

| 步 | 脚本 | 说明 |
|---|------|------|
| 1 | `feishu_download_portfolio.py` | 飞书云表格 → 覆盖本地 `持仓.xlsx`（未配置则跳过/失败可忽略） |
| 2 | `sync_portfolio_from_xlsx.py` | `持仓.xlsx` → `portfolio.md` / `trade_template.md` |
| 3 | `coarse_screen.py` | 全市场粗筛 |
| 4 | `fine_screen.py` | 精筛 + 博主标的池 + 布林线 → `Wiki/数据/博主标的池日报.md` |
| 5 | **`daily_report.py`** | **市场状态日报** → `Wiki/数据/市场状态日报.md`（指数、板块 Top10、追踪标的、Wiki 对照总结） |
| 6–7 | `bilibili_fetch.py` | 抓取新视频字幕 + `--dry-run` 预览 |

**是的**：`daily.bat` **会自动运行** `daily_report.py`（第 5 步），无需单独双击。跑完后可选 Webhook 推送摘要。

约 15–25 分钟（含 `daily_report` 板块成分股抓取，约 1 分钟）。完成后对 AI 说 **`sug {持有人}`**（如 `sug Wilson`）或 **`sug 全员`**；盘次总结用 `sug Wilson 午盘`（须先跑完 daily，以便读取 `市场状态日报.md` 第一节收盘）。未指定盘次写入 `SugVault/YYYY-MM-DD_{持有人}_sug.md`，指定早盘/午盘则写入 `..._sug 早盘.md` / `..._sug 午盘.md`。

### 飞书对接


| 能力         | 配置                                   | 说明                        |
| ---------- | ------------------------------------ | ------------------------- |
| **群推送**    | `FEISHU_WEBHOOK_URL`                 | `daily.bat` 跑完后自动推送摘要到飞书群 |
| **本机 Bot** | `FEISHU_APP_*` + 双击 `feishu_bot.bat` | `sug Wilson [早盘\|午盘]`、`sim 买/卖`、持仓、标的池等 |


**推送（推荐先做）**：飞书群 → 自定义机器人 → 复制 Webhook → 写入 `.env` 的 `FEISHU_WEBHOOK_URL` → `python scripts/feishu_notify.py --test`

**本机 Bot**：飞书开放平台创建应用 → 开机器人 + `im.message.receive_v1` 事件 → Request URL 指向 `http://<公网>:8765/feishu/event` → 填 `.env` → 运行 `feishu_bot.bat`

**Bot 权限（私聊 / 群聊分开）**：

- 私聊：`im:message.p2p_msg:readonly`
- 群聊 @：`im:message.group_at_msg:readonly`（须先把**应用机器人**拉进群，再 @ 发指令）
- 回复：`im:message:send_as_bot`
- 改权限后 **创建版本并发布**

> 电脑关机后 Bot 不可用。`ing`、AI 深度 `qry`/`chk`/`sug` **生成**仍走 Cursor；`trk`/`chk`/`qry`/`sug`/`持仓`/`标的池` **读取**已支持飞书 Bot。详见下表。

**云持仓（daily 自动下载）**：在 `.env` 配置 `FEISHU_PORTFOLIO_URL`（飞书电子表格链接）或 `FEISHU_PORTFOLIO_NAME=持仓`；`daily.bat` 第一步会先覆盖本地 `持仓.xlsx`。权限：`drive:export:readonly`、发版。

### 飞书 Bot vs Cursor 命令对照

前提：**飞书 Bot** = 本机运行 `feishu_bot.bat` 且电脑在线；**Cursor** = 安装 `SKILL.md` 后在 IDE 对话。群 **Webhook 推送**不含交互命令，仅 `daily.bat` 完成后发摘要。


| 命令                       | 飞书 Bot | Cursor + skill | 说明                                                     |
| ------------------------ | ------ | -------------- | ------------------------------------------------------ |
| `ing`                    | —      | ✅ 生成           | 消化 Raw 入 Wiki；Bot 无 AI 写作能力                            |
| `rw`                     | —      | ✅ / 脚本         | 视频稿 ASR 校正；`python scripts/rw_video.py --pending-only` |
| `txtcfm`                 | —      | ✅ / 脚本         | 批量审批；视频稿移入 `Raw/已审阅视频文稿/`                              |
| `sum`                    | —      | ✅ 生成           | 跨文章归纳；仅 Cursor                                         |
| `**sug {持有人}`**          | 📖 读   | ✅ **生成**       | Bot 读 `SugVault/` **时间最新**一份（含早盘/午盘）；指定盘次则精确匹配         |
| `**sug {持有人} 早盘/午盘`**    | 📖 读   | ✅ **生成**       | 按盘次文件名匹配归档                                             |
| `**sug 全员`**             | 📖 读   | ✅ **生成**       | Bot 按持有人分段读已有；Cursor 逐人生成并归档                           |
| `持仓 {持有人}`               | ✅ 读    | ✅ 读            | 读 `portfolio.md` 对应章节                                  |
| `标的池 {持有人}` / `日报 {持有人}` | ✅ 读    | ✅ 读            | 读标的池日报 + 该持有人做 T 章节                                    |
| `trk {标的}`               | ✅ 轻量   | ✅ 深度           | Bot：追踪页 + grep；Cursor：可刷新页、态度分析                        |
| `chk`                    | ✅ 轻量   | ✅ 深度           | Bot：待 ing 计数、断链/时效抽样；Cursor：可修复、归档                     |
| `qry {问题}`               | ✅ 轻量   | ✅ 深度           | Bot：Wiki 关键词检索；Cursor：多页综合作答                           |
| `sim 买/卖 {标的…}`        | ✅ 写    | ✅ 写            | 模拟持仓 `模拟持仓.xlsx`；Cursor `sug` 前自动 `sim sync`              |
| `帮助` / `ping`            | ✅      | —              | Bot 连通测试与指令列表                                          |
| `daily.bat`              | —      | —              | 双击运行；完成后 Webhook **推送**摘要（非 Bot 对话）                    |


图例：**✅ 生成** = AI 新建/更新内容；**📖 读** = 读本地已有文件；**✅ 读** = 双方均可查询；**—** = 不支持。

**典型日流程**：`daily.bat` → Webhook 收摘要 → Cursor 说 `sug Wilson` 生成报告 → 飞书 Bot 发 `sug Wilson` 随时复读。

CLI 自测（与 Bot 同源）：`python scripts/wiki_cli.py trk 寒武纪` / `chk` / `qry 存储`

手动逐步跑：

```bash
cd scripts
python coarse_screen.py
python fine_screen.py
python daily_report.py    # 也可单独跑，输出 Wiki/数据/市场状态日报.md
```

### 抓取博主 B 站新内容

在项目根目录配置 `.env`（参考 `.env.example`，Cookie 勿提交 git），然后：

```bash
cd scripts
python bilibili_fetch.py              # 仅抓取视频字幕（2026-05-14 及之后）
python bilibili_fetch.py --dry-run    # 预览不写文件
```

- **视频字幕**（自动）→ `Raw/未审阅视频文稿/` → `**rw`** → `**txtcfm`**（→ `已审阅视频文稿/`）→ `**ing**`
- **专栏 / 动态 / 充电文**（手动）→ 复制为 `.md` 放入 `Raw/未分析归档/` → 对 AI 说 `**ing`**
- **ing 完成后** → 原稿移入 `Raw/已分析归档/`（可用 `python archive_raw.py archive 路径`）
- 视频同步状态：`Wiki/数据/bilibili_sync.json`

> 专栏/充电文不再自动抓取（B 站 API 易限流）。仅视频走 `bilibili_fetch.py`。

### 消化博主的文字稿


| 来源           | 流程                                                                    |
| ------------ | --------------------------------------------------------------------- |
| 专栏/动态（手动 md） | `Raw/未分析归档/` → `**ing`** → Wiki + `Raw/已分析归档/`                        |
| 视频字幕稿        | `Raw/未审阅视频文稿/` → `**rw`** → `**txtcfm**` → `Raw/已审阅视频文稿/` → `**ing**` |


### 操作代号速查（Cursor 为主）


| 命令                | 作用                                             | 怎么跑                                                  |
| ----------------- | ---------------------------------------------- | ---------------------------------------------------- |
| `ing`             | 消化 `Raw/未分析归档/` 与 `Raw/已审阅视频文稿/` 中未处理稿，更新 Wiki | Cursor 对话                                            |
| `txtcfm`          | 批量审批未审阅文稿；视频稿移入 `Raw/已审阅视频文稿/`                 | Cursor 或 `python scripts/txtcfm.py`                  |
| `rw`              | 校对视频文字稿（ASR + 补标点分段）                           | Cursor 或 `python scripts/rw_video.py --pending-only` |
| `sug {持有人}`       | 持仓分析 + 大盘判断 + 开仓建议 + 仓位分配                      | **仅 Cursor 生成**；飞书 Bot 只读已有                          |
| `sug {持有人} 早盘/午盘` | 同上，归档文件名带盘次                                    | 同上                                                   |
| `sug 全员`          | 对每位持有人分别生成 sug 并各自归档                           | **仅 Cursor**                                         |
| `qry {问题}`        | 基于 Wiki 回答                                     | Cursor 深度；飞书 Bot 关键词检索                               |
| `trk {标的}`        | 博主对该标的的全痕迹                                     | Cursor 可刷新；飞书 Bot 读追踪页                               |
| `chk`             | Wiki 体检                                        | Cursor 可修复；飞书 Bot 只读抽样                               |
| `sum`             | 跨文章归纳                                          | 仅 Cursor                                             |
| `sim 买/卖 {标的…}` | 模拟持仓（100 万起/标的）                               | Cursor / 飞书 Bot；CLI 见上文 **模拟持仓**                      |


飞书 Bot 可读命令见上表 **[飞书 Bot vs Cursor](#飞书-bot-vs-cursor-命令对照)**。

---

## 状态圆点图例（🟢🟡🔴）

Wiki、sug 报告、`fine_screen` 输出的标的池日报里会出现彩色圆点。**同一颗 🔴 在不同场景含义不同**，请按「在哪看到」对号入座。

### 🔴 红色圆点：分场景含义


| 场景          | 常见位置                                      | 🔴 表示                           | 建议                                    |
| ----------- | ----------------------------------------- | ------------------------------- | ------------------------------------- |
| **标的时效**    | `Wiki/博主/标的总览.md` 状态列                     | **已过期** — 保鲜期已过且博主近期未再提及        | 勿当「现价推荐」；用 `trk {标的}` / `qry` 查最新态度   |
| **归档区标的**   | 标的总览 · 📁 历史归档                            | **已过期** — 同上，或早期机构研报标的（距今数月）    | 仅作研究博主信息源，不可直接跟买                      |
| **归档区标的**   | 标的总览 · 📁 历史归档                            | **待更新** — 逻辑仍有效但缺少近期 ingest 刷新  | 等新视频/复盘 `ing` 后再看，或 Cursor `trk` 手动更新 |
| **博主操作信号**  | `Wiki/博主/博主决策时间线.md` 类型列                  | **防守/减仓类信号** — 如退潮确认、恐慌、风控、紧急减仓 | 对照当日 [[每日复盘]]；偏防守，勿与「标的过期」混淆          |
| **布林七轨**    | `Wiki/数据/博主标的池日报.md`、`fine_screen.py` 信号列 | **破顶轨-离场** — 现价 ≥ 七轨顶轨，偏离过大     | 不宜追高；持仓考虑减/做 T，等回踩再评估                 |
| **板块/地缘标签** | 部分 `Wiki/每日复盘/` 表格                        | **分类色标**（如地缘博弈中的板块分组）           | 语境标签，**不是**标的过期或卖点                    |
| **Wiki 体检** | Cursor `chk` 修复日志 / `Wiki/log.md`         | **严重项待修**（内部维护用语）               | 走 Cursor `chk` 让 AI 修复断链、降级过期标的       |


### 全套圆点速查（按出现频率）


| 圆点  | 标的总览            | 决策时间线       | 布林信号 / 标的池            | 含义概要          |
| --- | --------------- | ----------- | --------------------- | ------------- |
| 🟢  | 当前推荐 / 活跃       | 进攻、加仓、方向判断  | 收敛形态；**适合做 T 出**      | 有效、偏积极        |
| 🟡  | 待确认（保鲜期将尽或态度不明） | 观望、减仓预警、纪律  | N 字二轨候选；**收敛中不适合做 T** | 谨慎、待验证        |
| 🔴  | 已过期 / 待更新       | 退潮、减仓、风控、恐慌 | **破顶轨-离场**            | 过期或偏空/离场（视场景） |
| ⚫   | 博主看空            | —           | —                     | 博主明确不再看好      |
| 🔵  | —               | —           | 底轨附近-关注               | 超跌区，可观察不接飞刀   |
| ⚪   | —               | —           | 正常                    | 无特殊布林信号       |


**保鲜期**（决定 🟢 何时变 🟡/🔴）：短线 **5 个交易日** → 趋势 **30 日** → 产业逻辑 **90 日** → 方法论 **永久**。细则见 `schema.md` 第十二节、`Wiki/博主/标的总览.md` 页眉。

**sug 报告**里个股行多用 🟢/🟡 标注技术形态与做 T 建议，一般不用 🔴；若见 🔴 优先看是否来自「布林破顶轨」或 Wiki 标的状态引用。

---

## 文件说明

```
CyberAdvisor/
├── daily.bat                ← 每日一键流水线（双击；含 daily_report.py）
├── feishu_bot.bat           ← 飞书 Bot 本机服务
├── 持仓.xlsx                ← 真实持仓数据源（同步到 portfolio / trade_template）
├── 模拟持仓.xlsx            ← sim 买/卖 虚拟盘（持有人=模拟）
├── SKILL.md                 ← AI skill 文件（必须安装）
├── portfolio.md             ← 多人持仓（按持有人分章，sug 读取）
├── trade_template.md        ← sug 回复模板
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
│   ├── 博主/
│   └── 数据/                ← 脚本输出（市场状态日报、标的池日报、粗筛 CSV…）
└── scripts/
    ├── feishu_download_portfolio.py  ← 飞书云文档 → 持仓.xlsx
    ├── wiki_cli.py          ← trk / chk / qry / sim-sync / track-maintain
    ├── wiki/                ← Wiki 轻量查询模块
    ├── sim_portfolio.py     ← sim 买/卖/sync/rebuild
    ├── feishu_notify.py     ← 飞书 Webhook 推送
    ├── feishu_bot.py        ← 飞书 Bot 事件服务
    ├── feishu/              ← 飞书 SDK 模块
    ├── sync_portfolio_from_xlsx.py  ← 持仓.xlsx → portfolio / trade_template
    ├── portfolio.py         ← 持仓配置（脚本用）
    ├── coarse_screen.py
    ├── fine_screen.py
    ├── daily_report.py      ← 市场状态日报入口
    ├── market_daily/        ← 日报抓取与 Markdown 生成
    ├── bilibili_fetch.py    ← B 站视频字幕（仅视频）
    ├── rw_video.py          ← 视频稿 rw 校对
    ├── txtcfm.py            ← 批量审批未审阅文稿
    └── archive_raw.py       ← Raw 归档迁移（ing 后自动 track-maintain）
```

---

## 选股逻辑

基于博主「青哥」的投资框架：

1. **粗筛**：全市场 5000 只 → PE>0、PB<10、市值>50亿、非极端异动 → ~2000 只
2. **精筛**：ROE>10%、毛利率>20%、PEG 排序 → ~15 只
3. **布林线**：七轨布林线扫描，标记收敛/N字二轨/破顶轨信号
4. **博主标的池**：单独跟踪博主本人推荐的核心标的

---

## 需要自己改的

- `持仓.xlsx` / `portfolio.md` / `scripts/portfolio.py`：你的**真实**持仓
- `模拟持仓.xlsx`：sim 虚拟盘（可选；`sim_portfolio.py init` 创建）
- `trade_template.md`：sug 模板中的示例行（与 portfolio 同步）
- `fine_screen.py` 里的 `BLOGGER_STOCKS`：博主的标的池

---

## （可选）用 Obsidian 浏览 Wiki

安装 [Obsidian](https://obsidian.md)，打开本项目根目录作为 vault。

---

## 致谢

- 博主「青枫浦上Q」的内容体系
- [Andrej Karpathy 的 LLM Wiki 理念](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [a-stock-data](https://github.com/simonlin1212/a-stock-data) A 股数据接口

