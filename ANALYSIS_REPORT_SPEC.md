# 分析报告统一规范

> **适用范围**：`sug`（含全员/早盘/午盘）、根目录 `*_分析.md`、深度 `qry` 诊断、以及任何含 **研判总结** 的对外报告。
> 所有标的、所有持有人均须遵守。

---

## 1. 表述与出处

- 结论须标明 Wiki/研报/日更/Raw 出处（见 `SKILL.md` → 表述规范）。

---

## 2. 补充数据（`report_data.enrich_stock`）

| 数据项                | 来源                              |
| --------------------- | --------------------------------- |
| **缠论结构（第一优先级）** | `scripts/chan/analyze.py`（日+60min+MACD） |
| 财务                  | mootdx 最新一期                   |
| vipdoc 本地日 K       | `tdx_vipdoc`（`TDX_VIPDOC`）实现波动，用于 1/3/7 区间宽度 |
| 5分钟K                | `supplement.fetch_minute_kline` |
| RS vs 沪深300（20日） | 日K 收益率差                      |
| 北向/南向             | 实时接口或 `市场状态日报`       |

- **`gaps` 为空** → 写 **「数据覆盖：无未登记缺口」**。
- **禁止**硬编码「分钟K/RS/北向待补全」。
- 行业叙事（政策、医保等）写在正文脉络节，**不列入数据缺口**。

---

## 3. 研判总结（§七）

对 **每只持仓 + 主要候选** 各一段：

| 要素        | 要求                                                                                |
| ----------- | ----------------------------------------------------------------------------------- |
| **缠论**    | **首读**：结构/买卖点/保护位；优先于七轨与 outlook（见 [[缠论-数据接入]]）          |
| 七轨位置    | 顶/二/中/四/五/底 + 相对20MA 高低                                                   |
| 操作        | 宜/忌、能否建仓、持仓处置、权重%                                                    |
| 1日/3日/7日倾向 | 结论 + 依据 + **最有可能价位** + **区间边界较现价 ±%** + **锚点价** + **挡位概率表** + **概率加权漂移** |
| 概率说明    | 高斯权重、合计100%、**非真实概率**；标注 `技术预测参数.json` 版本           |

生成命令：

```bash
python scripts/analysis_report.py --holder Wilson
python scripts/analysis_report.py --code 600021 --name 上海电力
```

---

## 4. 单标的深度报告（额外）

- **§专业名词解释**（或「术语与对本标的的含义」）：行业/技术/财务/纪律 → interpretation；须含 **最有可能价位、vipdoc、倾向概率** 等报告内出现的用语。调用 `report_glossary.format_glossary_markdown`。
- **§基本面**：直接竞对 2–4 只 + 行业 benchmark 对比表。

---

## 5. 1日/3日/7日预测追踪与复盘（自 2026-06-10 · sug 必做）

### 5.1 流程

| 步骤             | 命令                                                                               | 时机                                                                          |
| ---------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 批处理（追踪池） | `python scripts/outlook_tracker.py batch --universe track`                       | **daily.bat 第 6 步**（`Wiki/内容源/标的追踪` 全部标的）                |
| 批处理（持仓）   | `python scripts/outlook_tracker.py batch --universe portfolio --session 午盘`    | **`sug 全员 午盘` 开始前**（`持仓.xlsx` 全部标的）                  |
| 复盘             | `python scripts/outlook_tracker.py review --holder {持有人}`                     | **每次 sug 生成前**                                                     |
| 登记             | `python scripts/outlook_tracker.py record --holder {持有人} --source sug`        | **sug 归档后**                                                          |
| 询问登记         | `python scripts/outlook_tracker.py register-queried --code {code} --name {名称}` | **用户询问单标的时**（或 `record --source analysis_report` 自动登记） |
| 校准             | `python scripts/outlook_tracker.py calibrate`                                    | review 有到期样本时自动 / 手动                                                |

**标的范围**：`Wiki/内容源/标的追踪`（含不活跃）+ `持仓.xlsx` 全部 + `询问标的.json` 中登记过的代码。

**无历史预测**：批处理或首次登记时生成快照，**追踪窗口自次日**起算（`track_from` = 登记日 + 1）。

单标的报告：

```bash
python scripts/outlook_tracker.py record --code 300482 --name 万孚生物 --source analysis_report
```

### 5.2 存储（仅预测与复盘结论）

目录：`Wiki/数据/股价预测追踪/`（不移动其他 Wiki 文件）

| 文件                                       | 用途                            |
| ------------------------------------------ | ------------------------------- |
| `预测登记.json`                          | 历次 1日/3日/7日 预测快照与复盘结果 |
| `参数.json`                              | 区间宽度/挡位权重等可校准参数   |
| `询问标的.json`                          | 用户询问过的标的注册表          |
| `复盘/YYYY-MM-DD_{track\|portfolio}_*.md` | daily / sug 批处理复盘结论      |

### 5.3 复盘指标

- **收盘落预测区间内**：到期日收盘价 ∈ [lo, hi]
- **最高概率挡位触及**：窗口内 high/low/close 接近最高 prob 挡位（±1.5%）
- **锚点偏差**：实际收盘 vs 锚点价（占预测日现价 %）

### 5.4 自动优化

`calibrate` 根据累计命中率微调：

- 区间命中率过低 → 放宽 `band_vol_scale`（vipdoc 区间宽度）
- 最高挡位命中率过低/过高 → 调整 `prob_sigma_halfband_scale` / `track_level_boost`

---

## 6. sug 章节对照（`trade_template.md`）

| 章           | 内容                               |
| ------------ | ---------------------------------- |
| 一–六       | 大盘、资产、持仓、开仓、仓位、风险 |
| **七** | 研判总结（§3）                    |
| **八** | 预测复盘（§5）                    |

---

> 免责声明：**以上整理自项目内 Wiki/研报/Raw 与行情脚本，不构成投资建议。**
