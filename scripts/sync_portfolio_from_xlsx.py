#!/usr/bin/env python3
"""
从根目录 持仓.xlsx 同步持仓到 portfolio.md、scripts/portfolio.py、trade_template.md。

持仓.xlsx 格式（首个工作表）：
| 标的 | 代码 | 成本 | 股数 | 持有人 |
| 上海电力 | 600021 | 19.9102 | 100 | Wilson |

可选列 **A股对照**（非 A 股持仓填写 6 位 A 股代码，供布林/K 线；不填则用内置 AH 表）：
| 中国平安 | 02318 | 50.0 | 200 | Wilson | 601318 |

可选现金行（同一 sheet，标的列写「A股现金」，持有人列必填）：
| A股现金 | | 2.90 | | Wilson |

用法:
  python sync_portfolio_from_xlsx.py
  python sync_portfolio_from_xlsx.py --init   # 从当前 portfolio 生成模板 xlsx
"""
from __future__ import annotations

import argparse
import os
import re
from collections import OrderedDict
from datetime import datetime

import pandas as pd

from portfolio_utils import enrich_holdings_with_prices, fmt_money, normalize_stock_code, parse_code_from_excel_cell
from xlsx_utils import format_portfolio_xlsx, PORTFOLIO_INT_COLS, PORTFOLIO_MONEY_COLS

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
XLSX_PATH = os.path.join(ROOT, "持仓.xlsx")
PORTFOLIO_MD = os.path.join(ROOT, "portfolio.md")
PORTFOLIO_PY = os.path.join(ROOT, "scripts", "portfolio.py")
TRADE_TEMPLATE = os.path.join(ROOT, "trade_template.md")

COL_ALIASES = {
    "name": ("标的", "名称", "name", "股票"),
    "code": ("代码", "code", "证券代码"),
    "cost": ("成本", "成本价", "cost", "买入价"),
    "shares": ("股数", "数量", "shares", "持仓数量"),
    "holder": ("持有人", "holder", "账户", "账号", "用户"),
    "a_proxy": ("A股对照", "A股代码", "a_share", "a_code", "对照A股"),
}


def _find_col(cols: list[str], keys: tuple[str, ...]) -> str | None:
    norm = {str(c).strip().lower(): c for c in cols}
    for k in keys:
        if k.lower() in norm:
            return norm[k.lower()]
    for c in cols:
        cs = str(c).strip()
        for k in keys:
            if k in cs:
                return c
    return None


def _digits_only(code: str) -> str:
    return re.sub(r"\D", "", str(code).strip())


def _norm_code(code) -> str:
    return parse_code_from_excel_cell(code)


def _read_holdings(path: str) -> tuple[list[dict], dict[str, float], list[str]]:
    # 代码列必须按文本读，否则 000010→10.0 会被误判为港股 00010
    df = pd.read_excel(path, sheet_name=0, header=0, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    c_name = _find_col(list(df.columns), COL_ALIASES["name"])
    c_code = _find_col(list(df.columns), COL_ALIASES["code"])
    c_cost = _find_col(list(df.columns), COL_ALIASES["cost"])
    c_shares = _find_col(list(df.columns), COL_ALIASES["shares"])
    c_holder = _find_col(list(df.columns), COL_ALIASES["holder"])
    c_a_proxy = _find_col(list(df.columns), COL_ALIASES["a_proxy"])
    if not all([c_name, c_code, c_cost, c_shares, c_holder]):
        raise ValueError(
            f"持仓.xlsx 缺少列，需要：标的、代码、成本、股数、持有人。当前列：{list(df.columns)}"
        )

    cash_by_holder: dict[str, float] = {}
    holdings: list[dict] = []
    holder_order: list[str] = []

    def _track_holder(holder: str) -> None:
        if holder and holder not in holder_order:
            holder_order.append(holder)

    for _, row in df.iterrows():
        name = row.get(c_name)
        if pd.isna(name):
            continue
        name_s = str(name).strip()
        if name_s in ("项目", "类型"):
            continue

        holder_raw = row.get(c_holder)
        if pd.isna(holder_raw) or not str(holder_raw).strip():
            if "现金" in name_s:
                continue
            raise ValueError(f"持仓行「{name_s}」缺少持有人")
        holder = str(holder_raw).strip()
        _track_holder(holder)

        code = row.get(c_code)
        cost = row.get(c_cost)
        shares = row.get(c_shares)

        if "现金" in name_s:
            val = cost if not pd.isna(cost) else shares
            if not pd.isna(val):
                cash_by_holder[holder] = cash_by_holder.get(holder, 0.0) + float(val)
            continue

        if pd.isna(code) or pd.isna(cost) or pd.isna(shares):
            continue

        entry: dict = {
            "holder": holder,
            "name": name_s,
            "code": _norm_code(code),
            "cost": round(float(cost), 4),
            "shares": int(float(shares)),
        }
        if c_a_proxy and not pd.isna(row.get(c_a_proxy)) and str(row.get(c_a_proxy)).strip():
            from portfolio_utils import classify_market, normalize_stock_code

            raw_proxy = str(row.get(c_a_proxy)).strip()
            if classify_market(raw_proxy) in ("sh", "sz", "bj"):
                entry["a_share_proxy"] = normalize_stock_code(raw_proxy)
        holdings.append(entry)

    # 兼容「项目/金额」现金块（无持有人则忽略）
    c_item = _find_col(list(df.columns), ("项目", "类型", "item"))
    c_amt = _find_col(list(df.columns), ("金额", "amount", "数值"))
    if c_item and c_amt and c_holder:
        for _, row in df.iterrows():
            item = row.get(c_item)
            if pd.isna(item) or "现金" not in str(item):
                continue
            holder_raw = row.get(c_holder)
            val = row.get(c_amt)
            if pd.isna(holder_raw) or pd.isna(val):
                continue
            holder = str(holder_raw).strip()
            _track_holder(holder)
            cash_by_holder[holder] = cash_by_holder.get(holder, 0.0) + float(val)
            break

    if not holdings:
        raise ValueError("持仓.xlsx 中未读到有效持仓行")
    if not holder_order:
        holder_order = sorted({h["holder"] for h in holdings})

    return holdings, cash_by_holder, holder_order


def _group_by_holder(holdings: list[dict]) -> OrderedDict[str, list[dict]]:
    grouped: OrderedDict[str, list[dict]] = OrderedDict()
    for h in holdings:
        grouped.setdefault(h["holder"], []).append(h)
    return grouped


def _write_portfolio_md(holdings: list[dict], cash_by_holder: dict[str, float], holders: list[str]) -> None:
    grouped = _group_by_holder(holdings)
    holder_list = ", ".join(holders)
    synced_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# 持仓总览",
        "",
        "> 多人持仓。Cursor 生成 sug、飞书 Bot 读取已有 sug；`持仓 {持有人}` / `标的池 {持有人}` 均只读对应章节。",
        f"> 现价同步于 {synced_at}；**投资成本** = 成本×股数，**市值** = 现价×股数，现金计入两项合计。",
        "",
        f"**持有人列表**：{holder_list}",
        "",
    ]
    grand_cost = 0.0
    grand_mkt = 0.0
    for holder in holders:
        rows = grouped.get(holder, [])
        stock_cost = sum(h["cost"] * h["shares"] for h in rows)
        stock_mkt = sum(h["market_value"] for h in rows if h.get("market_value") is not None)
        cash = cash_by_holder.get(holder, 0.0)
        cost_total = stock_cost + cash
        mkt_total = stock_mkt + cash if stock_mkt or not rows else None
        grand_cost += cost_total
        if mkt_total is not None:
            grand_mkt += mkt_total
        lines.extend(
            [
                f"## 持有人：{holder}",
                "",
                "### A 股持仓",
                "",
                "| 标的 | 代码 | 成本（元） | 股数 | 投资成本（元） | 现价（元） | 市值（元） |",
                "|------|------|-----------|------|---------------|-----------|-----------|",
            ]
        )
        for h in rows:
            cost_amt = round(h["cost"] * h["shares"], 2)
            price = h.get("price")
            mkt = h.get("market_value")
            price_s = f"{price:.2f}" if price is not None else "—"
            mkt_s = fmt_money(mkt) if mkt is not None else "—"
            lines.append(
                f"| {h['name']} | {h['code']} | {h['cost']} | {h['shares']} | "
                f"{fmt_money(cost_amt)} | {price_s} | {mkt_s} |"
            )
        lines.extend(
            [
                "",
                f"**{holder} A 股持仓投资成本：{fmt_money(stock_cost)} 元**",
            ]
        )
        if any(h.get("market_value") is not None for h in rows):
            lines.append(f"**{holder} A 股持仓市值：{fmt_money(stock_mkt)} 元**")
        lines.extend(
            [
                "",
                "### 现金与其他",
                "",
                "| 类型 | 金额（元） |",
                "|------|-----------|",
                f"| A 股现金 | {fmt_money(cash)} |",
                "| 美股/黄金/其他 | （无） |",
                "",
                f"**{holder} 投资成本合计：{fmt_money(cost_total)} 元**",
            ]
        )
        if mkt_total is not None:
            lines.append(f"**{holder} 市值合计：{fmt_money(mkt_total)} 元**")
        lines.extend(
            [
                "",
                "#### 快捷录入",
                "",
                "```",
                f"我的持仓（{holder}）：",
            ]
        )
        for h in rows:
            lines.append(f"- {h['name']} 成本 {h['cost']} 元 {h['shares']} 股")
        lines.extend(["```", ""])

    lines.append(f"**全员投资成本合计：{fmt_money(grand_cost)} 元**")
    if grand_mkt:
        lines.append(f"**全员市值合计：{fmt_money(grand_mkt)} 元**")
    lines.append("")
    with open(PORTFOLIO_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_portfolio_py(holdings: list[dict], cash_by_holder: dict[str, float], holders: list[str]) -> None:
    def _holding_line(h: dict) -> str:
        base = (
            f'    {{"holder": "{h["holder"]}", "name": "{h["name"]}", "code": "{h["code"]}", '
            f'"cost": {h["cost"]}, "shares": {h["shares"]}'
        )
        price = h.get("price")
        mkt = h.get("market_value")
        if price is not None:
            base += f', "price": {price}, "market_value": {mkt}'
        if h.get("a_share_proxy"):
            base += f', "a_share_proxy": "{h["a_share_proxy"]}"'
        return base + "}"

    rows = ",\n".join(_holding_line(h) for h in holdings)
    cash_lines = ",\n".join(f'    "{k}": {v}' for k, v in cash_by_holder.items())
    holder_lines = ", ".join(f'"{h}"' for h in holders)
    total_cash = sum(cash_by_holder.values())
    text = f'''"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = [{holder_lines}]

HOLDINGS = [
{rows},
]

CASH_BY_HOLDER = {{
{cash_lines}
}}

CASH_CNY = {total_cash}  # 全员 A 股现金合计（元）
'''
    with open(PORTFOLIO_PY, "w", encoding="utf-8") as f:
        f.write(text)


def _write_trade_template(holdings: list[dict]) -> None:
    if not os.path.isfile(TRADE_TEMPLATE):
        raise FileNotFoundError(TRADE_TEMPLATE)
    text = open(TRADE_TEMPLATE, encoding="utf-8").read()
    rows = []
    for h in holdings:
        cost_amt = round(h["cost"] * h["shares"], 2)
        price = h.get("price")
        price_s = f"{price:.2f}" if price is not None else "[xx]"
        if price is not None and h.get("market_value") is not None:
            pnl = (h["market_value"] / cost_amt - 1) * 100 if cost_amt else 0
            pnl_s = f"{pnl:+.1f}%"
        else:
            pnl_s = "[+x%]"
        rows.append(
            f"| {h['name']} | {h['shares']} | {h['cost']} | {fmt_money(cost_amt)} | "
            f"{price_s} | {pnl_s} | [xx] | [轨道] | [态度] | [操作] |"
        )
    block = "\n".join(rows)
    new_text, n = re.subn(
        r"\| 标的   \| 股数.*?\n(\| [^\n]+\|\n)+",
        "| 标的   | 股数   | 成本      | 成交额      | 现价   | 浮盈    | PE   | 布林线  | Wiki 追踪口径 | 操作   |\n"
        f"| ---- | ---- | ------- | -------- | ---- | ----- | ---- | ---- | ---- | ---- |\n"
        f"{block}\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        raise RuntimeError("trade_template.md 中未找到「三、你的持仓」表格，请检查模板")
    with open(TRADE_TEMPLATE, "w", encoding="utf-8") as f:
        f.write(new_text)


def init_xlsx() -> None:
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from portfolio import CASH_BY_HOLDER, HOLDERS, HOLDINGS

    rows = [
        {
            "标的": h["name"],
            "代码": h["code"],
            "成本": h["cost"],
            "股数": h["shares"],
            "持有人": h.get("holder") or (HOLDERS[0] if HOLDERS else ""),
        }
        for h in HOLDINGS
    ]
    for holder in HOLDERS:
        cash = CASH_BY_HOLDER.get(holder, 0.0)
        rows.append({"标的": "A股现金", "代码": "", "成本": cash, "股数": "", "持有人": holder})
    pd.DataFrame(rows).to_excel(XLSX_PATH, index=False)
    format_portfolio_xlsx(XLSX_PATH)
    print(f"已生成模板：{XLSX_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description="从 持仓.xlsx 同步持仓")
    ap.add_argument("--init", action="store_true", help="生成 持仓.xlsx 模板")
    args = ap.parse_args()
    if args.init:
        init_xlsx()
        return
    if not os.path.isfile(XLSX_PATH):
        print(f"未找到 {XLSX_PATH}，正在生成模板…")
        init_xlsx()
        print("请编辑 持仓.xlsx 后重新运行。")
        return
    holdings, cash_by_holder, holders = _read_holdings(XLSX_PATH)
    print("正在拉取现价…")
    holdings = enrich_holdings_with_prices(holdings)
    _write_portfolio_md(holdings, cash_by_holder, holders)
    _write_portfolio_py(holdings, cash_by_holder, holders)
    _write_trade_template(holdings)
    print(
        f"已同步 {len(holdings)} 条持仓（{len(holders)} 位持有人）"
        f" → portfolio.md / portfolio.py / trade_template.md"
    )
    format_portfolio_xlsx(XLSX_PATH)


if __name__ == "__main__":
    main()
