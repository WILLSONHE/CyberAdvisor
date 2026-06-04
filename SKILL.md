---
name: finance-wiki
description: 财经知识 Wiki 系统。基于 Andrej Karpathy LLM Wiki 理念，将财经博主的视频文字稿增量消化为结构化 Obsidian markdown 知识库。涵盖投资方法论提取、每日复盘追踪、标的推荐整理、Wiki 结构自进化、时效性分层管理、博主框架分析、持仓诊断、矛盾检测、交易策略建议(sug)。支持八种操作代号（rw/txtcfm/ing/qry/chk/trk/sum/sug）。触发词：财经 wiki、ingest、ing、txtcfm、审阅、审批、复盘、早盘、午盘、标的推荐、trk、chk、qry、sug、suggest、开仓、持仓分析、买什么、交易策略、博主矛盾、赛博UP主。
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
| `sug` | suggest | **交易策略建议**：持仓分析+大盘判断+开仓建议+仓位分配 |

---

## Wiki 目录结构

```
{workspace}/
├── schema.md
├── portfolio.md            ← 用户持仓（sug 必读）
├── 持仓.xlsx               ← 持仓数据源（daily.bat 同步）
├── daily.bat               ← 每日一键流水线
├── trade_template.md       ← sug 回复模板
├── SugVault/               ← sug 历史报告（YYYY-MM-DD_sug.md）
├── scripts/
│   ├── sync_portfolio_from_xlsx.py
│   ├── bilibili_fetch.py   ← 仅视频字幕
│   ├── rw_video.py         ← 视频稿 rw
│   ├── txtcfm.py           ← 批量审批
│   └── archive_raw.py      ← ing 后归档
├── Raw/（原始稿）
│   ├── 未分析归档/          ← ing 输入：手动专栏/动态 md
│   └── 已分析归档/          ← ing 完成后原稿归档
├── Wiki/
│   ├── 待审阅视频文稿/     ← 视频字幕稿待审区（bilibili_fetch 自动写入）
│   ├── 投资方法论/
│   ├── 市场分析/
│   ├── 每日复盘/
│   ├── 博主/
│   └── 数据/（脚本输出）
```

---

## 持仓格式

以 `portfolio.md` 为准。用户录入格式：

```
我的持仓：
- 上海电力 成本 19.9102 元 100 股
- ST美丽 成本 1.9920 元 2500 股
- 电光科技 成本 34.7286 元 300 股
```

**成交额 = 成本 × 股数**（含交易成本）。sug 模板中金额单位用「元」，不用「万」。

---

## Ingest 操作（`ing`）

主 agent 直接处理。逐篇优于批量。

**内容来源规则：**
- **专栏/动态/充电文** → 用户手动复制 `.md` 到 `Raw/未分析归档/` → `ing` → 完成后移入 `Raw/已分析归档/`
- **视频字幕稿** → `bilibili_fetch.py` 自动入 `Wiki/待审阅视频文稿/` → `rw` → **`txtcfm` 审批** → `ing`

### 文稿审批（`txtcfm`）

触发条件：用户说 `txtcfm`、审阅通过、批量审批。

执行：`python scripts/txtcfm.py`（或 `--dry-run` 预览）

扫描并审批：
1. `Wiki/待审阅视频文稿/` — 全部非 `approved`/`ingested` 的稿
2. `Raw/未分析归档/`（及旧 `待分析归档/`）— 无 frontmatter 的补写 `review_status: approved`

效果：`review_status: approved`、写入 `approved_at`、引用行「待审阅」→「已审阅」、追加 `log.md`。
**不移动文件、不 ingest**；审批后用户可再发 `ing`。

单篇步骤：
1. 扫描 `Raw/未分析归档/` 与 `Wiki/待审阅视频文稿/`（`review_status: approved` 优先；对照 `log.md` 确认未处理）
2. 阅读全文（强制确认覆盖到文件末尾）
3. 提取关键信息，写入 Wiki
4. 写入后抽查末尾 3 段是否完整
5. 自进化检查 + 时效性检查
6. 更新 index.md、log.md
7. **归档**：`python archive_raw.py archive <该 md 路径>` 移入 `Raw/已分析归档/`（或等效 move）

II 类文件（午盘补发/周末补充/晚间复盘）逐段对比 Wiki 页，不遗漏追加内容。

---

## Suggest 操作（`sug`）—— 交易策略建议

触发条件：用户说 `sug`、`开仓`、`买什么`、`持仓分析`、`交易策略`。

执行流程：
1. 阅读 `portfolio.md` 获取持仓（成本×股数=成交额）
2. 运行 `scripts/coarse_screen.py` 和 `scripts/fine_screen.py` 获取最新数据
3. 阅读最近 2-3 天的博主早盘/复盘/午盘补发 Raw 文件
4. 阅读 `Wiki/博主/博主决策时间线.md` 了解博主最新节奏
5. 阅读 `Wiki/数据/博主标的池日报.md` 获取布林线信号
6. 严格按 `trade_template.md` 格式输出
7. **归档**：将完整回复写入 `SugVault/YYYY-MM-DD_sug.md`（同日多次则 `YYYY-MM-DD_HHMM_sug.md`）

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
grep 全踪迹 → 定位框架 → 保鲜期 → 博主框架判断 → 区分博主/自己判断 → 读 portfolio.md 成本/股数

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
6. sug 回复严格按模板，不自由发挥；**同时写入 SugVault/**
7. 科创板不推荐
8. 诚实 > 讨好
9. 视频稿：待审区 → `rw` → `txtcfm` → `ing`；**专栏/动态仅手动 md + 未分析归档**；ing 后移已分析归档
10. B 站增量抓取：`python scripts/bilibili_fetch.py`（**仅视频字幕**）
11. 每日流水线：双击 `daily.bat`（持仓.xlsx 同步 → 选股 → 日报 → bilibili）
