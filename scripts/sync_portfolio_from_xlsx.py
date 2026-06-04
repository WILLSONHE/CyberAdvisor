#!/usr/bin/env python3
"""
从根目录 持仓.xlsx 同步持仓到 portfolio.md、scripts/portfolio.py、trade_template.md。

持仓.xlsx 格式（首个工作表）：
| 标的 | 代码 | 成本 | 股数 |
| 上海电力 | 600021 | 19.9102 | 100 |

可选第二块「现金」（同一 sheet 下方或列 项目/金额）：
| 项目 | 金额 |
| A股现金 | 2.90 |

用法:
  python sync_portfolio_from_xlsx.py
  python sync_portfolio_from_xlsx.py --init   # 从当前 portfolio 生成模板 xlsx
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import datetime

import pandas as pd

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


def _read_holdings(path: str) -> tuple[list[dict], float]:
    df = pd.read_excel(path, sheet_name=0, header=0)
    df.columns = [str(c).strip() for c in df.columns]
    c_name = _find_col(list(df.columns), COL_ALIASES["name"])
    c_code = _find_col(list(df.columns), COL_ALIASES["code"])
    c_cost = _find_col(list(df.columns), COL_ALIASES["cost"])
    c_shares = _find_col(list(df.columns), COL_ALIASES["shares"])
    if not all([c_name, c_code, c_cost, c_shares]):
        raise ValueError(
            f"持仓.xlsx 缺少列，需要：标的、代码、成本、股数。当前列：{list(df.columns)}"
        )

    cash = 0.0
    holdings: list[dict] = []
    for _, row in df.iterrows():
        name = row.get(c_name)
        if pd.isna(name):
            continue
        name_s = str(name).strip()
        if name_s in ("项目", "类型") or "现金" in name_s:
            continue
        code = row.get(c_code)
        cost = row.get(c_cost)
        shares = row.get(c_shares)
        if pd.isna(code) or pd.isna(cost) or pd.isna(shares):
            # 现金行：标的列写「A股现金」等
            if "现金" in name_s and not pd.isna(cost):
                cash = float(cost)
            elif "现金" in name_s and c_shares and not pd.isna(shares):
                cash = float(shares)
            continue
        holdings.append(
            {
                "name": name_s,
                "code": str(code).strip().replace(".0", "") if str(code).endswith(".0") else str(code).strip(),
                "cost": round(float(cost), 4),
                "shares": int(float(shares)),
            }
        )

    # 尝试读取「现金」专用区域（项目/金额 两列）
    c_item = _find_col(list(df.columns), ("项目", "类型", "item"))
    c_amt = _find_col(list(df.columns), ("金额", "amount", "数值"))
    if c_item and c_amt:
        for _, row in df.iterrows():
            item = row.get(c_item)
            if pd.isna(item):
                continue
            if "现金" in str(item):
                val = row.get(c_amt)
                if not pd.isna(val):
                    cash = float(val)
                    break

    if not holdings:
        raise ValueError("持仓.xlsx 中未读到有效持仓行")
    return holdings, cash


def _write_portfolio_md(holdings: list[dict], cash: float) -> None:
    total = sum(h["cost"] * h["shares"] for h in holdings)
    lines = [
        "# 我的持仓",
        "",
        "> AI 执行 `sug` 时读取本文件。成交额 = 成本 × 股数（含交易成本）。",
        "",
        "## A 股持仓",
        "",
        "| 标的 | 代码 | 成本（元） | 股数 | 成交额（元） |",
        "|------|------|-----------|------|-------------|",
    ]
    for h in holdings:
        amt = round(h["cost"] * h["shares"], 2)
        lines.append(
            f"| {h['name']} | {h['code']} | {h['cost']} | {h['shares']} | {amt:.2f} |"
        )
    lines.extend(
        [
            "",
            f"**A 股持仓合计：{total:.2f} 元**",
            "",
            "## 现金与其他",
            "",
            "| 类型 | 金额（元） |",
            "|------|-----------|",
            f"| A 股现金 | {cash:.2f} |",
            "| 美股/黄金/其他 | （无） |",
            "",
            f"**总资产：{total + cash:.2f} 元**",
            "",
            "## 快捷录入格式",
            "",
            "```",
            "我的持仓：",
        ]
    )
    for h in holdings:
        lines.append(f"- {h['name']} 成本 {h['cost']} 元 {h['shares']} 股")
    lines.extend(["```", ""])
    with open(PORTFOLIO_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _write_portfolio_py(holdings: list[dict], cash: float) -> None:
    rows = ",\n".join(
        f'    {{"name": "{h["name"]}", "code": "{h["code"]}", '
        f'"cost": {h["cost"]}, "shares": {h["shares"]}}}'
        for h in holdings
    )
    text = f'''"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDINGS = [
{rows},
]

CASH_CNY = {cash}  # A 股现金（元）
'''
    with open(PORTFOLIO_PY, "w", encoding="utf-8") as f:
        f.write(text)


def _write_trade_template(holdings: list[dict]) -> None:
    if not os.path.isfile(TRADE_TEMPLATE):
        raise FileNotFoundError(TRADE_TEMPLATE)
    text = open(TRADE_TEMPLATE, encoding="utf-8").read()
    rows = []
    for h in holdings:
        amt = round(h["cost"] * h["shares"], 2)
        rows.append(
            f"| {h['name']} | {h['shares']} | {h['cost']} | {amt:.2f} | [xx] | [+x%] | [xx] | [轨道] | [态度] | [操作] |"
        )
    block = "\n".join(rows)
    new_text, n = re.subn(
        r"\| 标的   \| 股数.*?\n(\| [^\n]+\|\n)+",
        "| 标的   | 股数   | 成本      | 成交额      | 现价   | 浮盈    | PE   | 布林线  | 博主态度 | 操作   |\n"
        f"| ---- | ---- | ------- | -------- | ---- | ----- | ---- | ---- | ---- | ---- |\n"
        f"{block}\n",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if n == 0:
        raise RuntimeError("trade_template.md 中未找到「三、你的持仓」表格，请检查模板")
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    note = f"\n> 持仓示例行由 `持仓.xlsx` 同步（{stamp}）。\n"
    if "持仓示例行由" not in new_text:
        new_text = new_text.replace(
            "持仓数据以 `portfolio.md` 为准",
            f"持仓数据以 `portfolio.md` 为准（`持仓.xlsx` → 本文件示例行）",
            1,
        )
    with open(TRADE_TEMPLATE, "w", encoding="utf-8") as f:
        f.write(new_text)


def init_xlsx() -> None:
    import sys

    sys.path.insert(0, os.path.dirname(__file__))
    from portfolio import CASH_CNY, HOLDINGS

    rows = [
        {
            "标的": h["name"],
            "代码": h["code"],
            "成本": h["cost"],
            "股数": h["shares"],
        }
        for h in HOLDINGS
    ]
    rows.append({"标的": "A股现金", "代码": "", "成本": CASH_CNY, "股数": ""})
    pd.DataFrame(rows).to_excel(XLSX_PATH, index=False)
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
    holdings, cash = _read_holdings(XLSX_PATH)
    _write_portfolio_md(holdings, cash)
    _write_portfolio_py(holdings, cash)
    _write_trade_template(holdings)
    print(f"已同步 {len(holdings)} 条持仓 → portfolio.md / portfolio.py / trade_template.md")


if __name__ == "__main__":
    main()
