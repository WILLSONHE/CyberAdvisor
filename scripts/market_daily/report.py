"""市场状态日报：Markdown 生成与 Wiki 框架对照总结。"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from portfolio_utils import fmt_money

from market_daily.fetch import (
    BoardQuote,
    IndexQuote,
    StockQuote,
    fetch_board_mcap_top_stocks,
    fetch_concept_boards,
    fetch_indices,
    fetch_stocks_by_codes,
)
from market_daily.history_store import append_daily_snapshot
from market_daily.supplement import build_supplement, indices_to_snapshot

ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT.parent / "Wiki"
TRACK_DIR = WIKI / "博主" / "标的追踪"
WIKI_MARKET = WIKI / "市场分析"
WIKI_METHOD = WIKI / "投资方法论"

# 概念板块涨/跌榜数量；各板块内 Δ市值标的数量
CONCEPT_BOARD_TOP = 3
BOARD_MCAP_STOCK_TOP = 5

# 博主机械化纪律线（与 Wiki 一致）
LINE_CLEAR = 4033
LINE_FULL = 4130


def _list_active_track_names() -> list[str]:
    if not TRACK_DIR.is_dir():
        return []
    names: list[str] = []
    for f in os.listdir(TRACK_DIR):
        if not f.endswith(".md") or f.startswith("股性-"):
            continue
        names.append(f[:-3])
    return sorted(names)


def _code_map() -> dict[str, str]:
    try:
        import sys

        scripts = str(ROOT)
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from fine_screen import BLOGGER_STOCKS

        return dict(BLOGGER_STOCKS)
    except Exception:
        return {}


def _read_wiki_snippet(path: Path, max_lines: int = 35) -> str:
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    body: list[str] = []
    for line in lines:
        if line.startswith("#"):
            if body:
                break
            body.append(line)
            continue
        if line.strip() == "---" and len(body) > 3:
            break
        body.append(line)
        if len(body) >= max_lines:
            break
    return "\n".join(body).strip()


def _fmt_index_table(indices: list[IndexQuote]) -> list[str]:
    lines = [
        "| 指数 | 代码 | 收盘 | 涨跌 | 涨跌幅 | 开盘 | 最高 | 最低 | 振幅 | 均价 | 成交额(亿) | 成交量(手) |",
        "|------|------|------|------|--------|------|------|------|------|------|------------|------------|",
    ]
    for q in indices:
        lines.append(
            f"| {q.name} | {q.code} | {q.close:.2f} | {q.change:+.2f} | {q.change_pct:+.2f}% "
            f"| {q.open:.2f} | {q.high:.2f} | {q.low:.2f} | {q.amplitude_pct:.2f}% "
            f"| {q.avg_price:.2f} | {fmt_money(q.turnover_yi)} | {q.volume:,} |"
        )
    return lines


def _fmt_board_table(boards: list[BoardQuote], title: str) -> list[str]:
    lines = [f"### {title}", "", "| 板块 | 代码 | 涨跌幅 | 涨跌点数 | 板块总市值(亿) |", "|------|------|--------|----------|----------------|"]
    for b in boards:
        lines.append(f"| {b.name} | {b.code} | {b.change_pct:+.2f}% | {b.change_pts:+.2f} | {fmt_money(b.mcap_yi)} |")
    lines.append("")
    return lines


def _fmt_stock_detail(q: StockQuote) -> str:
    return (
        f"收 {q.price:.2f}（{q.change_pct:+.2f}%）开 {q.open:.2f} 高 {q.high:.2f} 低 {q.low:.2f} "
        f"额 {fmt_money(q.turnover_yi)}亿 换手 {q.turnover_rate_pct:.2f}% PE {q.pe_ttm:.1f} PB {q.pb:.2f} "
        f"市值 {fmt_money(q.mcap_yi)}亿 Δ市值 {fmt_money(q.mcap_change_yi, signed=True)}亿"
    )


def _fmt_track_table(quotes: dict[str, StockQuote], names: list[str], code_map: dict[str, str]) -> list[str]:
    lines = [
        "| 标的 | 代码 | 收盘 | 涨跌幅 | 开盘 | 最高 | 最低 | 振幅 | 成交额(亿) | 换手 | PE | PB | 总市值(亿) | Δ市值(亿) |",
        "|------|------|------|--------|------|------|------|------|------------|------|-----|-----|------------|-----------|",
    ]
    for name in names:
        code = code_map.get(name, "")
        q = quotes.get(code.zfill(6)) if code else None
        if not q:
            lines.append(f"| {name} | {code or '—'} | — | — | — | — | — | — | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| {name} | {q.code} | {q.price:.2f} | {q.change_pct:+.2f}% | {q.open:.2f} | {q.high:.2f} | {q.low:.2f} "
            f"| {q.amplitude_pct:.2f}% | {fmt_money(q.turnover_yi)} | {q.turnover_rate_pct:.2f}% | {q.pe_ttm:.1f} | {q.pb:.2f} "
            f"| {fmt_money(q.mcap_yi)} | {fmt_money(q.mcap_change_yi, signed=True)} |"
        )
    return lines


def _generate_summary(
    indices: list[IndexQuote],
    gain_boards: list[BoardQuote],
    loss_boards: list[BoardQuote],
    track_quotes: dict[str, StockQuote],
    track_names: list[str],
    code_map: dict[str, str],
) -> list[str]:
    sh = next((q for q in indices if q.symbol == "sh000001"), None)
    cyb = next((q for q in indices if q.symbol == "sz399006"), None)
    bj = next((q for q in indices if q.symbol == "bj899050"), None)

    lines = ["## 五、市场总结（结合 Wiki 框架）", ""]

    # --- 5.1 指数与纪律 ---
    lines.append("### 5.1 指数与机械化纪律")
    if sh:
        if sh.close < LINE_CLEAR:
            disc = f"**已触发**：上证收盘 **{sh.close:.2f}** < {LINE_CLEAR} 清仓线（低 {LINE_CLEAR - sh.close:.2f} 点）"
        elif sh.close >= LINE_FULL:
            disc = f"**已触发**：上证收盘 **{sh.close:.2f}** ≥ {LINE_FULL} 满仓线"
        else:
            disc = f"上证收盘 **{sh.close:.2f}**，处于 {LINE_CLEAR}–{LINE_FULL} 区间（未破线）"
        lines.append(f"- {disc}（L1 机械层；完整 L1–L5 见 [[指数纪律框架]]）")
        if sh.close < LINE_CLEAR:
            lines.append(
                f"- **L3 纠错回补**：4120 站稳或 60 分钟及以上明确底部前，叙事上不轻易回补硬科技"
            )
            lines.append(
                f"- **L4 结构**：4000 整数关 → 3950；**L5**：量能/缩量为企稳核心前提"
            )
        lines.append(
            f"- 全日：开 {sh.open:.2f} → 高 {sh.high:.2f} / 低 {sh.low:.2f} → 收 {sh.close:.2f}，"
            f"跌 {sh.change:.2f}（{sh.change_pct:+.2f}%），成交额约 **{fmt_money(sh.turnover_yi)} 亿元**"
        )
    if cyb and sh:
        lines.append(
            f"- **结构分化**：创业板 {cyb.change_pct:+.2f}% vs 上证 {sh.change_pct:+.2f}%"
            + (f"；北证50 {bj.change_pct:+.2f}%" if bj else "")
        )
    lines.append("")

    # --- 5.2 板块 vs 博主 ---
    lines.append("### 5.2 板块轮动对照")
    if gain_boards:
        top3 = "、".join(b.name for b in gain_boards[:3])
        lines.append(f"- **概念涨幅前三**：{top3}")
    if loss_boards:
        bot3 = "、".join(b.name for b in loss_boards[:3])
        lines.append(f"- **概念跌幅前三**：{bot3}")
    rot = _read_wiki_snippet(WIKI_MARKET / "板块轮动记录.md", 25)
    if rot:
        lines.append("- **博主当日主线（Wiki）**：上游材料 + 机器人日内胜出（见 [[板块轮动记录]] 2026-06-05 节）")
        if gain_boards:
            robot_hit = any("机器人" in b.name for b in gain_boards[:CONCEPT_BOARD_TOP])
            lines.append(
                f"- 盘面概念榜{'**含**机器人相关板块走强' if robot_hit else '与博主「机器人胜出」需人工核对概念名称'}，"
                f"与 [[2026-06-05]] 11:51 动态对照"
            )
    lines.append("")

    # --- 5.3 追踪池 ---
    lines.append("### 5.3 活跃追踪标的池表现")
    perf: list[tuple[str, float]] = []
    for name in track_names:
        code = code_map.get(name)
        if not code:
            continue
        q = track_quotes.get(code.zfill(6))
        if q:
            perf.append((name, q.change_pct))
    if perf:
        perf.sort(key=lambda x: x[1], reverse=True)
        avg = sum(p for _, p in perf) / len(perf)
        best = perf[0]
        worst = perf[-1]
        lines.append(f"- 活跃追踪 **{len(perf)}** 只，平均涨跌 **{avg:+.2f}%**")
        lines.append(f"- 最强：**{best[0]}** {best[1]:+.2f}% | 最弱：**{worst[0]}** {worst[1]:+.2f}%")
        up = sum(1 for _, p in perf if p > 0)
        lines.append(f"- 上涨 {up} / 下跌 {len(perf) - up}（对照 [[标的总览]]、[[博主标的池日报]]）")
    lines.append("")

    # --- 5.4 方法论 ---
    lines.append("### 5.4 投资方法论要点对照")
    lines.append("- **指数纪律**：L1 4033/4130 机械层 + L3 4120/60 分钟回补 + L4 4000→3950 + L5 缩量（[[指数纪律框架]]）")
    lines.append("- **仓位管理**：4033 破线 → L1 机械防守；**回补须 L3**，非仅站回 4033（[[仓位管理]]）")
    lines.append("- **情绪周期**：缩量调整末期的定性需 **收盘确认**；破 4033 则进入 L1 防守窗口（[[情绪周期与操作节奏]]）")
    lines.append("- **选股框架**：主线仍在 AI 基建/国产算力产业逻辑，但 **点位纪律 > 板块叙事**（[[选股框架]]）")
    lines.append("")

    # --- 5.5 一句 ---
    lines.append("### 5.5 今日一句")
    if sh and sh.close < LINE_CLEAR:
        tail = ""
        if perf:
            avg = sum(p for _, p in perf) / len(perf)
            robot_hint = "机器人偏强" if gain_boards and "机器人" in gain_boards[0].name else "板块分化"
            tail = f"；{robot_hint}，追踪池均值 {avg:+.2f}%"
        lines.append(
            f"> 上证收 **{sh.close:.2f}** 破 **{LINE_CLEAR}**（L1）；回补看 **4120/60 分钟底**（L3），结构 **4000→3950**、**缩量** 验证企稳{tail}。"
        )
    elif sh:
        lines.append(f"> 上证 **{sh.close:.2f}** 守于 {LINE_CLEAR} 之上，结构分化，按博主主线持仓观察。")
    lines.append("")

    # Wiki 摘录
    lines.append("### 附：Wiki 框架摘录（自动生成，非 LLM）")
    for label, path in [
        ("板块轮动（最新）", WIKI_MARKET / "板块轮动记录.md"),
        ("风控逻辑", WIKI_METHOD / "风控逻辑.md"),
        ("仓位管理", WIKI_METHOD / "仓位管理.md"),
    ]:
        snip = _read_wiki_snippet(path, 18)
        if snip:
            lines.append(f"<details><summary>{label}</summary>\n\n{snip}\n\n</details>\n")

    return lines


def build_report() -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        "# 市场状态日报",
        "",
        f"> 更新时间：{now}",
        f"> 数据源：腾讯 gtimg（指数/个股）+ 东方财富 push2delay（概念板块）",
        f"> 规范：见 `SKILL.md` → **市场状态日报必抓字段**",
        "",
    ]

    # 1. 指数
    lines.append("## 一、主要指数")
    lines.append("")
    indices = fetch_indices()
    if indices:
        lines.extend(_fmt_index_table(indices))
        sh = next((q for q in indices if q.symbol == "sh000001"), None)
        if sh:
            lines.append("")
            if sh.close < LINE_CLEAR:
                lines.append(f"> ⚠️ 上证收盘 **{sh.close:.2f}** 低于清仓线 **{LINE_CLEAR}**（差 {LINE_CLEAR - sh.close:.2f} 点）")
            elif sh.close >= LINE_FULL:
                lines.append(f"> 🟢 上证收盘 **{sh.close:.2f}** 达到/超过满仓线 **{LINE_FULL}**")
            else:
                lines.append(f"> 上证处于 **{LINE_CLEAR}–{LINE_FULL}** 区间")
    else:
        lines.append("（指数数据获取失败）")
    lines.append("")

    # 2. 板块涨跌幅
    lines.append(f"## 二、概念板块涨跌幅 Top{CONCEPT_BOARD_TOP}")
    lines.append("")
    gain_boards, loss_boards = fetch_concept_boards(top_n=CONCEPT_BOARD_TOP)
    if gain_boards:
        lines.extend(_fmt_board_table(gain_boards, f"涨幅 Top{CONCEPT_BOARD_TOP}"))
    else:
        lines.append("（涨幅榜获取失败）\n")
    if loss_boards:
        lines.extend(_fmt_board_table(loss_boards, f"跌幅 Top{CONCEPT_BOARD_TOP}"))
    else:
        lines.append("（跌幅榜获取失败）\n")

    lines.append(f"## 三、板块内市值变化 Top{BOARD_MCAP_STOCK_TOP}")
    lines.append("")
    lines.append("> Δ市值 = 总市值 × 涨跌幅 / (100+涨跌幅)，单位：**亿元**（东方财富成分股 + 腾讯行情补充）")
    lines.append("")

    def _board_mcap_section(boards: list[BoardQuote], heading: str) -> None:
        lines.append(f"### {heading}")
        lines.append("")
        for b in boards[:CONCEPT_BOARD_TOP]:
            stocks = fetch_board_mcap_top_stocks(b, top_n=BOARD_MCAP_STOCK_TOP)
            if not stocks:
                continue
            lines.append(f"#### {b.name}（{b.code}，板块 {b.change_pct:+.2f}%）")
            lines.append("")
            lines.append("| 标的 | 代码 | Δ市值(亿) | 涨跌幅 | 收盘 | 总市值(亿) | 成交额(亿) |")
            lines.append("|------|------|-----------|--------|------|------------|------------|")
            for q, _ in stocks:
                lines.append(
                    f"| {q.name} | {q.code} | {fmt_money(q.mcap_change_yi, signed=True)} | {q.change_pct:+.2f}% "
                    f"| {q.price:.2f} | {fmt_money(q.mcap_yi)} | {fmt_money(q.turnover_yi)} |"
                )
            lines.append("")

    if gain_boards:
        _board_mcap_section(gain_boards, f"3.1 涨幅 Top{CONCEPT_BOARD_TOP} 板块内")
    if loss_boards:
        _board_mcap_section(loss_boards, f"3.2 跌幅 Top{CONCEPT_BOARD_TOP} 板块内")

    # 4. 活跃追踪标的
    lines.append("## 四、活跃标的追踪（Wiki/博主/标的追踪/）")
    lines.append("")
    track_names = _list_active_track_names()
    code_map = _code_map()
    codes = [code_map[n] for n in track_names if n in code_map]
    track_quotes = fetch_stocks_by_codes(codes)
    lines.append(f"> 共 **{len(track_names)}** 只（不含 `不活跃标的/`、`股性-*`）")
    lines.append("")
    if track_names:
        lines.extend(_fmt_track_table(track_quotes, track_names, code_map))
        lines.append("")
        lines.append("### 逐只摘要")
        lines.append("")
        for name in track_names:
            code = code_map.get(name)
            q = track_quotes.get(code.zfill(6)) if code else None
            if q:
                lines.append(f"- **{name}**：{_fmt_stock_detail(q)}")
            else:
                lines.append(f"- **{name}**：行情缺失（代码 {code or '—'}）")
    else:
        lines.append("（无活跃追踪页）")
    lines.append("")

    # 5. 总结
    lines.extend(_generate_summary(indices, gain_boards, loss_boards, track_quotes, track_names, code_map))

    # 6. 补充数据摘要 + 写入历史 JSON
    lines.append("## 六、补充数据摘要")
    lines.append("")
    try:
        sup = build_supplement(include_overnight=True, kline_limit=8)
        nb = sup.get("northbound") or {}
        if nb:
            lines.append(
                f"- **北向净流入**：{nb.get('north_net_yi', '—')} 亿元 | "
                f"**南向**：{nb.get('south_net_yi', '—')} 亿元"
            )
        overnight = sup.get("overnight") or []
        if overnight:
            parts = [f"{q['name']} {q['change_pct']:+.2f}%" for q in overnight[:4]]
            lines.append(f"- **隔夜外盘**：{' | '.join(parts)}")
        k60 = sup.get("kline_60m") or {}
        sh_bars = (k60.get("000001") or {}).get("bars") or []
        if sh_bars:
            last = sh_bars[-1]
            lines.append(
                f"- **上证 60min 最新**：{last.get('time','')} 收 {last['close']:.2f} "
                f"（低 {last['low']:.2f} 高 {last['high']:.2f}）"
            )
        lines.append("")
        lines.append(f"> 完整序列见 `Wiki/数据/市场历史摘要.json`；tick 含 `supplement` 字段。")
        date_str = datetime.now().strftime("%Y-%m-%d")
        append_daily_snapshot(
            date=date_str,
            indices=indices_to_snapshot(indices),
            northbound={
                "north_net_yi": nb.get("north_net_yi"),
                "south_net_yi": nb.get("south_net_yi"),
            },
            source="daily_report",
        )
    except Exception as e:
        lines.append(f"（补充数据获取失败：{e}）")
        lines.append("")

    lines.append("")
    lines.append("---")
    lines.append("*由 `scripts/daily_report.py` 生成；sug 午盘/复盘请优先读本文件第一节（指数收盘）。*")

    return "\n".join(lines)
