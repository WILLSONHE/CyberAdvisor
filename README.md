# 赛博青哥 Wiki

> 基于财经博主「青枫浦上Q」全部公开内容的 AI 知识库 + 交易决策系统。
> 把你的 AI 助手变成赛博青哥。

---

## 这是什么

一套完整的投资辅助系统：
- **Wiki 知识库**：博主 2025.10~2026.05 全部方法论 + 121 天每日复盘 + 标的全追踪
- **选股脚本**：全市场粗筛 → 博主 F10 框架精筛 → 七轨布林线扫描
- **交易策略**：持仓诊断 + 开仓建议 + 做 T 策略 + 每日市场状态
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

| 助手 | skill 目录 |
|------|-----------|
| Cursor | `C:\Users\{用户名}\.cursor\skills-cursor\finance-wiki\` |
| Claude Code | `~/.claude/skills/finance-wiki/` |
| Codex | `~/.codex/skills/finance-wiki/` |

skill 加载后，你的 AI 助手会拥有这些能力。

### 3. 配置你的持仓

**推荐**：编辑根目录 `持仓.xlsx`（列：**持有人**、标的、代码、成本、股数），或 **在飞书电子表格维护「持仓」**，由 `daily.bat` 自动下载覆盖本地文件后同步。

| 持有人 | 标的 | 代码 | 成本 | 股数 |
|--------|------|------|------|------|
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

**多人指令格式**（Cursor / 飞书 Bot 一致，持有人名不区分大小写，须与 xlsx 精确匹配）：

```
sug Wilson          # 交易策略 → SugVault/YYYY-MM-DD_Wilson_sug.md
持仓 Wilson          # 查看该持有人持仓
标的池 Wilson        # 博主池 + 该持有人做T
```

格式错误时回复：`请校对格式sug {持有人}，以精确搜索`

示例录入：

```
我的持仓（Wilson）：
- 上海电力 成本 19.9102 元 100 股
- ST美丽 成本 1.9920 元 2500 股
- 电光科技 成本 34.7286 元 300 股
```

成交额 = 成本 × 股数（投资成本）；市值 = 现价 × 股数（同步时自动拉取）。`sug Wilson` 时以 `portfolio.md` 中 Wilson 章节为准。

---

## 怎么用

### 每日操作

**一键流水线**（双击根目录 `daily.bat`，在新终端依次执行）：

1. 从 `持仓.xlsx` 同步持仓（可先由飞书云文档下载覆盖）
2. `coarse_screen.py` → `fine_screen.py` → `daily_report.py`
3. `bilibili_fetch.py`（字幕）→ `bilibili_fetch.py --dry-run`（预览）

约 15–20 分钟。完成后对 AI 说 **`sug {持有人}`**（如 `sug Wilson`），得到交易策略报告；报告会写入 `SugVault/YYYY-MM-DD_{持有人}_sug.md`。

### 飞书对接

| 能力 | 配置 | 说明 |
|------|------|------|
| **群推送** | `FEISHU_WEBHOOK_URL` | `daily.bat` 跑完后自动推送摘要到飞书群 |
| **本机 Bot** | `FEISHU_APP_*` + 双击 `feishu_bot.bat` | 飞书里发 `sug Wilson` / `持仓 Wilson` / `标的池 Wilson` / `帮助` |

**推送（推荐先做）**：飞书群 → 自定义机器人 → 复制 Webhook → 写入 `.env` 的 `FEISHU_WEBHOOK_URL` → `python scripts/feishu_notify.py --test`

**本机 Bot**：飞书开放平台创建应用 → 开机器人 + `im.message.receive_v1` 事件 → Request URL 指向 `http://<公网>:8765/feishu/event` → 填 `.env` → 运行 `feishu_bot.bat`

**Bot 权限（私聊 / 群聊分开）**：
- 私聊：`im:message.p2p_msg:readonly`
- 群聊 @：`im:message.group_at_msg:readonly`（须先把**应用机器人**拉进群，再 @ 发指令）
- 回复：`im:message:send_as_bot`
- 改权限后 **创建版本并发布**

> 电脑关机后 Bot 不可用；完整 AI（ing/qry）仍走 Cursor。

**云持仓（daily 自动下载）**：在 `.env` 配置 `FEISHU_PORTFOLIO_URL`（飞书电子表格链接）或 `FEISHU_PORTFOLIO_NAME=持仓`；`daily.bat` 第一步会先覆盖本地 `持仓.xlsx`。权限：`drive:export:readonly`、发版。

手动逐步跑：

```bash
cd scripts
python coarse_screen.py
python fine_screen.py
python daily_report.py
```

### 抓取博主 B 站新内容

在项目根目录配置 `.env`（参考 `.env.example`，Cookie 勿提交 git），然后：

```bash
cd scripts
python bilibili_fetch.py              # 仅抓取视频字幕（2026-05-14 及之后）
python bilibili_fetch.py --dry-run    # 预览不写文件
```

- **视频字幕**（自动）→ `Wiki/待审阅视频文稿/` → **`rw`** → **`txtcfm`** → **`ing`**
- **专栏 / 动态 / 充电文**（手动）→ 复制为 `.md` 放入 `Raw/未分析归档/` → 对 AI 说 **`ing`**
- **ing 完成后** → 原稿移入 `Raw/已分析归档/`（可用 `python archive_raw.py archive 路径`）
- 视频同步状态：`Wiki/数据/bilibili_sync.json`

> 专栏/充电文不再自动抓取（B 站 API 易限流）。仅视频走 `bilibili_fetch.py`。

### 消化博主的文字稿

| 来源 | 流程 |
|------|------|
| 专栏/动态（手动 md） | `Raw/未分析归档/` → **`ing`** → Wiki + `Raw/已分析归档/` |
| 视频字幕稿 | `Wiki/待审阅视频文稿/` → **`rw`** → **`txtcfm`** → **`ing`** |

### 操作代号速查

| 你说 | AI 做什么 |
|------|----------|
| `ing` | 消化 `Raw/未分析归档/` 中未处理稿，更新 Wiki，完成后移入 `已分析归档/` |
| `sug {持有人}` | 按持有人：持仓分析 + 大盘判断 + 开仓建议 + 仓位分配 |
| `qry {问题}` | 基于 Wiki 知识库回答 |
| `trk {标的}` | 拉取某只标的的博主全痕迹 |
| `chk` | Wiki 健康检查 |
| `rw` | 校对视频文字稿（ASR 校正 + **补标点分段**） | `python scripts/rw_video.py --pending-only` |
| `txtcfm` | **批量审批**未审阅文稿（全部通过） | `python scripts/txtcfm.py` |

---

## 文件说明

```
CyberAdvisor/
├── daily.bat                ← 每日一键流水线（双击）
├── feishu_bot.bat           ← 飞书 Bot 本机服务
├── 持仓.xlsx                ← 持仓数据源（同步到 portfolio / trade_template）
├── SKILL.md                 ← AI skill 文件（必须安装）
├── portfolio.md             ← 多人持仓（按持有人分章，sug 读取）
├── trade_template.md        ← sug 回复模板
├── SugVault/                ← sug 历史报告（YYYY-MM-DD_{持有人}_sug.md）
├── schema.md                ← Wiki 操作规范
├── Raw/                     ← 原始文字稿
│   ├── 未分析归档/          ← 手动放入待 ing 的 md（专栏/动态）
│   └── 已分析归档/          ← ing 完成后的原稿备份
├── Wiki/
│   ├── 待审阅视频文稿/      ← 视频字幕稿待审区
│   ├── 投资方法论/
│   ├── 市场分析/
│   ├── 每日复盘/
│   ├── 博主/
│   └── 数据/                ← 脚本输出
└── scripts/
    ├── feishu_download_portfolio.py  ← 飞书云文档 → 持仓.xlsx
    ├── feishu_notify.py     ← 飞书 Webhook 推送
    ├── feishu_bot.py        ← 飞书 Bot 事件服务
    ├── feishu/              ← 飞书 SDK 模块
    ├── sync_portfolio_from_xlsx.py  ← 持仓.xlsx → portfolio / trade_template
    ├── portfolio.py         ← 持仓配置（脚本用）
    ├── coarse_screen.py
    ├── fine_screen.py
    ├── bilibili_fetch.py    ← B 站视频字幕（仅视频）
    ├── rw_video.py          ← 视频稿 rw 校对
    ├── txtcfm.py            ← 批量审批未审阅文稿
    └── archive_raw.py       ← Raw 归档迁移
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

- `持仓.xlsx` / `portfolio.md` / `scripts/portfolio.py`：你的持仓
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
