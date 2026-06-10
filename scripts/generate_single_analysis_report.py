#!/usr/bin/env python3
"""生成根目录单标的深度分析报告（含 §专业名词解释、§七完整 outlook、vipdoc 补充数据）。"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(SCRIPT_DIR, "..")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bollinger_utils import bollinger_for_code, build_stock_verdict
from fine_screen import get_finance_data
from report_data import enrich_stock, format_enrichment_markdown, format_gaps_markdown
from report_glossary import format_glossary_markdown

DAILY_REPORT = os.path.join(ROOT, "Wiki", "数据", "市场状态日报.md")
LINE_CLEAR = 4033.0


def _parse_sh_index() -> tuple[float | None, str]:
    if not os.path.isfile(DAILY_REPORT):
        return None, ""
    text = open(DAILY_REPORT, encoding="utf-8").read()
    m = re.search(r"\|\s*上证指数\s*\|\s*000001\s*\|\s*([\d,]+\.?\d*)", text)
    sh = float(m.group(1).replace(",", "")) if m else None
    upd = re.search(r"更新时间[：:]\s*([\d-]+\s+[\d:]+)", text)
    as_of = upd.group(1).strip() if upd else ""
    return sh, as_of


def _holder_block(code: str) -> str:
    from portfolio import HOLDINGS

    rows = [h for h in HOLDINGS if str(h.get("code", "")).zfill(6) == str(code).zfill(6)]
    if not rows:
        return "（非 `portfolio.md` 登记持仓；本报告为询问/追踪标的。）"
    lines = ["| 持有人 | 成本 | 股数 | 现价/市值 | 浮盈 |", "|--------|------|------|-----------|------|"]
    for h in rows:
        cost = h.get("cost")
        shares = h.get("shares")
        price = h.get("price")
        mv = h.get("market_value")
        pnl = (price / cost - 1) * 100 if cost and price else None
        lines.append(
            f"| {h.get('holder')} | {cost} | {shares} | {price} / {mv} | "
            f"{pnl:+.1f}% |" if pnl is not None else f"| {h.get('holder')} | {cost} | {shares} | — | — |"
        )
    return "\n".join(lines)


def generate(
    code: str,
    *,
    name: str,
    company_blurb: str = "",
    peers_note: str = "",
    out_path: str | None = None,
) -> str:
    code = str(code).zfill(6)
    today = date.today().isoformat()
    sh, daily_as_of = _parse_sh_index()
    index_ok = sh is None or sh >= LINE_CLEAR
    b = bollinger_for_code(code)
    if not b or b.get("error"):
        raise SystemExit(f"无法计算 {code} 布林：{b.get('error') if b else '无数据'}")

    has_pos = "Wilson" in _holder_block(code) or "刘岚" in _holder_block(code)
    verdict = build_stock_verdict(
        code, name=name, has_position=has_pos, index_ok_buy=index_ok
    )
    enr = enrich_stock(code, name=name)
    b["finance"] = enr.get("finance") or get_finance_data(code)
    glossary = format_glossary_markdown(b, outlook=verdict.get("outlook"), name=name)
    enrich_md = format_enrichment_markdown(enr)
    gaps_md = format_gaps_markdown(enr.get("gaps") or [])

    fin = b.get("finance") or {}
    vip = enr.get("vipdoc") or b.get("vipdoc") or {}
    sh_line = f"**{sh:,.2f}**" if sh else "—"
    discipline = (
        "指数允许考虑建仓（须叠加 Wiki 纪律）"
        if index_ok
        else f"**已破 L1 {LINE_CLEAR:.0f}** → 机械降仓/禁新开仓"
    )

    lines = [
        f"# {name}（{code}）分析报告",
        "",
        f"> 生成时间：{today}  ",
        f"> 数据：mootdx / **vipdoc 本地日 K** / `Wiki/数据/市场状态日报.md`"
        + (f"（{daily_as_of}）" if daily_as_of else ""),
        "",
        "---",
        "",
        "## 一、大盘与 Wiki 纪律",
        "",
        "| 项目 | 数据 |",
        "|------|------|",
        f"| 上证收盘 | {sh_line} |",
        f"| L1 清仓线 | **{LINE_CLEAR:.0f}** |",
        f"| 纪律定调 | {discipline} |",
        "",
        f"**对本标的**：{'L1 破线环境下不宜新开仓/战略加仓；存量以技术位做 T 或持有评估。' if not index_ok else '指数未破 L1，仍须叠加 Wiki 主线与个股七轨位置。'}",
        "",
        "---",
        "",
        "## 二、公司脉络",
        "",
        company_blurb or f"**{name}**（{code}）：见 Wiki/研报补充；本 tick 未 ingest 专页。",
        "",
        "---",
        "",
        "## 三、基本面与同业对比",
        "",
        "### 3.1 财务快照（mootdx 最新一期）",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 营收 | {fin.get('revenue', '—')} 亿 |",
        f"| 净利 | {fin.get('net_profit', '—')} 亿 |",
        f"| ROE | {fin.get('roe', '—')}% |",
        f"| 毛利率 | {fin.get('gross_margin', '—')}% |",
        f"| 净利率 | {fin.get('net_margin', '—')}% |",
        "",
        peers_note or "（竞对对比表待补；可 `fine_screen` 拉取同业 PE/布林。）",
        "",
        "---",
        "",
        glossary.strip(),
        "",
        "---",
        "",
        "## 五、持仓诊断",
        "",
        _holder_block(code),
        "",
        "---",
        "",
        "## 六、操作节奏（技术 + 纪律）",
        "",
        f"- 七轨位置：**{b.get('zone')}** | 信号 **{b.get('signal')}** | 带宽 {b.get('bandwidth_pct')}%",
        f"- vipdoc 近 {vip.get('lookback', 20)} 日 σ **{vip.get('stdev_pct', '—')}%** → 1/3/7 日区间宽度参考",
        "",
        "---",
        "",
        "## 七、研判总结",
        "",
        verdict["markdown"],
        "",
        "---",
        "",
        "## 八、补充数据",
        "",
        enrich_md.replace("### 补充数据（" + name, "### 补充数据").replace(f"{name} {code}）", f"{name} {code}）"),
        "",
        gaps_md.strip(),
        "",
        "---",
        "",
        "## 九、预测登记",
        "",
        f"```bash",
        f"python scripts/outlook_tracker.py record --code {code} --name {name} --source analysis_report",
        f"```",
        "",
        "> **免责声明**：以上整理自项目内 Wiki/研报/Raw 与行情脚本，不构成投资建议。",
        "",
    ]
    md = "\n".join(lines)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
    return md


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--blurb", default="")
    ap.add_argument("--peers", default="")
    args = ap.parse_args()
    out = args.out or os.path.join(ROOT, f"{date.today().isoformat()}_{args.name}_分析.md")
    generate(args.code, name=args.name, company_blurb=args.blurb, peers_note=args.peers, out_path=out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
