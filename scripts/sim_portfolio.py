#!/usr/bin/env python3
"""
模拟持仓：sim 买 / sim 卖 / sync。

根目录 模拟持仓.xlsx 列（在 持仓.xlsx 基础上扩展）：
  标的 | 代码 | 成本 | 股数 | 持有人 | 现价 | 市值 | 盈亏 | 盈亏比 | 卖出？(Y/N) | 建仓日期 | 持仓时间(天)

表末：空一行 + 「合计」行（成本=投资成本合计，市值=市值合计，盈亏比=组合总体盈亏比）。

用法:
  python sim_portfolio.py init
  python sim_portfolio.py buy 利通电子 江波龙
  python sim_portfolio.py sell 利通电子
  python sim_portfolio.py sync
  python sim_portfolio.py handle "sim 买 利通电子，江波龙"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date, datetime

import pandas as pd

from portfolio_utils import fetch_spot_price, fmt_money, normalize_stock_code, parse_code_from_excel_cell
from xlsx_utils import write_dataframe_xlsx, SIM_INT_COLS, SIM_MONEY_COLS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
SIM_XLSX = os.path.join(ROOT, "模拟持仓.xlsx")
PORTFOLIO_XLSX = os.path.join(ROOT, "持仓.xlsx")
COARSE_CSV = os.path.join(ROOT, "Wiki", "数据", "粗筛结果.csv")

SIM_HOLDER = "AI"  # AI 自主模拟盘（总资金 500 万，见 ai_sim/）
BUDGET_PER_STOCK = 1_000_000  # 100 万为预算单位；不足则自动升至 200 万、300 万…
MAX_BUDGET_MULTIPLIER = 20  # 最高 2000 万，防止极端高价股死循环
MIN_SHARES = 100  # 必须 > 100，即至少 200 股（100 股整数倍）

BASE_COLS = ("标的", "代码", "成本", "股数", "持有人")
EXTRA_COLS = ("现价", "市值", "盈亏", "盈亏比", "卖出？(Y/N)", "建仓日期", "持仓时间(天)")
ALL_COLS = BASE_COLS + EXTRA_COLS

SOLD_COL = "卖出？(Y/N)"
SUMMARY_LABEL = "合计"
BUY_VERBS = frozenset({"买", "买入", "buy"})
SELL_VERBS = frozenset({"卖", "卖出", "sell"})


def _is_sold(val) -> bool:
    if pd.isna(val):
        return False
    return str(val).strip().upper() == "Y"


def _norm_code(code) -> str:
    if pd.isna(code):
        return ""
    return parse_code_from_excel_cell(code)


def _build_name_code_map() -> dict[str, str]:
    mapping: dict[str, str] = {}

    def add(name: str, code: str) -> None:
        name = str(name).strip()
        code = _norm_code(code)
        if name and code and name not in mapping:
            mapping[name] = code

    try:
        from fine_screen import TRACK_STOCKS

        for name, code in TRACK_STOCKS.items():
            add(name, code)
    except Exception:
        pass

    for path in (PORTFOLIO_XLSX, SIM_XLSX):
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_excel(path, sheet_name=0)
            df.columns = [str(c).strip() for c in df.columns]
            if "标的" in df.columns and "代码" in df.columns:
                for _, row in df.iterrows():
                    if path == SIM_XLSX and not _is_data_row(row):
                        continue
                    add(row.get("标的"), row.get("代码"))
        except Exception:
            pass

    if os.path.isfile(COARSE_CSV):
        try:
            df = pd.read_csv(COARSE_CSV)
            if "name" in df.columns and "code" in df.columns:
                for _, row in df.iterrows():
                    add(row["name"], row["code"])
        except Exception:
            pass

    return mapping


def resolve_stock_name(query: str, mapping: dict[str, str] | None = None) -> tuple[str, str]:
    q = query.strip()
    if not q:
        raise ValueError("标的名为空")
    mapping = mapping or _build_name_code_map()

    if q in mapping:
        return q, mapping[q]

    ql = q.lower()
    for name, code in mapping.items():
        if name.lower() == ql:
            return name, code

    partial = [name for name in mapping if q in name or name in q]
    if len(partial) == 1:
        name = partial[0]
        return name, mapping[name]
    if len(partial) > 1:
        raise ValueError(f"「{q}」匹配多个标的：{', '.join(partial[:8])}…请写全名")

    raise ValueError(f"未找到标的「{q}」的代码，请先在 持仓.xlsx / 核心标的池 中确认名称")


def _shares_for_budget(price: float, budget: float) -> int | None:
    """按预算可买股数（100 股整数倍）；不足 MIN_SHARES 则返回 None。"""
    if price <= 0:
        return None
    shares = int(budget / price // 100) * 100
    if shares <= MIN_SHARES:
        return None
    return shares


def _resolve_budget(price: float) -> float:
    """
    100 万能买到（股数 > 100）则用 100 万；否则升至 200 万、300 万…（100 万的整数倍）。
    """
    need = (MIN_SHARES // 100 + 1) * 100
    max_budget = BUDGET_PER_STOCK * MAX_BUDGET_MULTIPLIER
    budget = BUDGET_PER_STOCK
    while budget <= max_budget:
        if _shares_for_budget(price, budget) is not None:
            return budget
        budget += BUDGET_PER_STOCK
    raise ValueError(
        f"按现价 {price:.2f} 元，{max_budget / 10_000:.0f} 万预算仍无法买到 > {MIN_SHARES} 股"
        f"（至少 {need} 股）"
    )


def _calc_shares(price: float, budget: float = BUDGET_PER_STOCK) -> int:
    shares = _shares_for_budget(price, budget)
    if shares is None:
        need = (MIN_SHARES // 100 + 1) * 100
        budget_wan = budget / 10_000
        raw = int(budget / price // 100) * 100 if price > 0 else 0
        raise ValueError(
            f"{budget_wan:.0f} 万元按现价 {price:.2f} 元仅能买 {raw} 股（须 > {MIN_SHARES} 股，"
            f"至少 {need} 股）"
        )
    return shares


def _calc_metrics(cost: float, shares: int, price: float | None, open_date: date, *, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    invest = round(cost * shares, 2)
    if price is None:
        return {
            "现价": None,
            "市值": None,
            "盈亏": None,
            "盈亏比": None,
            "持仓时间(天)": (as_of - open_date).days,
        }
    mkt = round(price * shares, 2)
    pnl = round(mkt - invest, 2)
    ratio = (pnl / invest * 100) if invest else 0.0
    return {
        "现价": round(price, 4),
        "市值": mkt,
        "盈亏": pnl,
        "盈亏比": f"{ratio:+.2f}%",
        "持仓时间(天)": (as_of - open_date).days,
    }


def _is_data_row(row) -> bool:
    """有效持仓行（排除空行、合计行）。"""
    name = row.get("标的")
    if pd.isna(name) or not str(name).strip():
        return False
    if str(name).strip() == SUMMARY_LABEL:
        return False
    if pd.isna(row.get("代码")) or pd.isna(row.get("股数")):
        return False
    return True


def _portfolio_totals(df: pd.DataFrame) -> dict:
    """汇总全部持仓行：投资成本合计、市值合计、盈亏、总体盈亏比。"""
    total_cost = 0.0
    total_mkt = 0.0
    for _, row in df.iterrows():
        if not _is_data_row(row):
            continue
        cost = float(row.get("成本") or 0)
        shares = int(float(row.get("股数") or 0))
        total_cost += cost * shares
        mkt = row.get("市值")
        if pd.notna(mkt):
            total_mkt += float(mkt)
    total_cost = round(total_cost, 2)
    total_mkt = round(total_mkt, 2)
    pnl = round(total_mkt - total_cost, 2)
    ratio = (pnl / total_cost * 100) if total_cost else 0.0
    return {
        "total_cost": total_cost,
        "total_mkt": total_mkt,
        "pnl": pnl,
        "ratio": f"{ratio:+.2f}%",
    }


def _with_summary_rows(positions: pd.DataFrame) -> pd.DataFrame:
    """持仓表末尾：空一行 + 合计行（成本/市值/盈亏/总体盈亏比）。"""
    if positions.empty:
        return positions.copy()
    for col in ALL_COLS:
        if col not in positions.columns:
            positions[col] = None
    positions = positions[list(ALL_COLS)]
    totals = _portfolio_totals(positions)
    blank = {col: None for col in ALL_COLS}
    summary = blank.copy()
    summary["标的"] = SUMMARY_LABEL
    summary["成本"] = totals["total_cost"]
    summary["市值"] = totals["total_mkt"]
    summary["盈亏"] = totals["pnl"]
    summary["盈亏比"] = totals["ratio"]
    return pd.concat(
        [positions, pd.DataFrame([blank]), pd.DataFrame([summary])],
        ignore_index=True,
    )


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=list(ALL_COLS))


def _load_df() -> pd.DataFrame:
    if not os.path.isfile(SIM_XLSX):
        return _empty_df()
    df = pd.read_excel(SIM_XLSX, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]
    for col in ALL_COLS:
        if col not in df.columns:
            df[col] = None
    df = df[list(ALL_COLS)]
    if "代码" in df.columns:
        df["代码"] = df["代码"].apply(_norm_code)
    return df[df.apply(_is_data_row, axis=1)].reset_index(drop=True)


def _save_df(df: pd.DataFrame) -> None:
    positions = df[df.apply(_is_data_row, axis=1)].reset_index(drop=True) if not df.empty else _empty_df()
    out = _with_summary_rows(positions)
    write_dataframe_xlsx(out, SIM_XLSX, money_cols=SIM_MONEY_COLS, int_cols=SIM_INT_COLS)


def init_sim_xlsx() -> None:
    _save_df(_empty_df())
    print(f"已创建：{SIM_XLSX}")


def _parse_open_date(val) -> date:
    if pd.isna(val) or val is None or val == "":
        return date.today()
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()[:10]
    return datetime.strptime(s, "%Y-%m-%d").date()


def sync_sim_prices(*, sleep_s: float = 0.2) -> str:
    """刷新未卖出行的现价/市值/盈亏；已卖出 (Y) 行冻结不动。"""
    if not os.path.isfile(SIM_XLSX):
        return "模拟持仓.xlsx 不存在，请先 sim 买 或运行 init"

    df = _load_df()
    if df.empty:
        return "模拟持仓为空"

    updated = 0
    frozen = 0
    today = date.today()
    price_cache: dict[str, float | None] = {}

    for idx, row in df.iterrows():
        if _is_sold(row.get(SOLD_COL)):
            frozen += 1
            continue
        code = _norm_code(row.get("代码"))
        if not code:
            continue
        if code not in price_cache:
            price_cache[code] = fetch_spot_price(code)
            if sleep_s > 0:
                time.sleep(sleep_s)
        price = price_cache[code]
        cost = float(row.get("成本") or 0)
        shares = int(float(row.get("股数") or 0))
        open_d = _parse_open_date(row.get("建仓日期"))

        if price is None:
            existing = row.get("现价")
            if pd.notna(existing) and float(existing) > 0:
                price = float(existing)
            else:
                df.at[idx, "持仓时间(天)"] = (today - open_d).days
                continue

        metrics = _calc_metrics(cost, shares, price, open_d, as_of=today)
        # 仅更新现价及衍生字段；成本/股数/建仓日期买入后不再改动
        for k in ("现价", "市值", "盈亏", "盈亏比", "持仓时间(天)"):
            df.at[idx, k] = metrics[k]
        if price is not None:
            updated += 1

    _save_df(df)
    totals = _portfolio_totals(df)
    return (
        f"已同步模拟持仓：更新 {updated} 条，冻结 {frozen} 条（已卖出）；"
        f"合计 成本 {fmt_money(totals['total_cost'])} 元 / 市值 {fmt_money(totals['total_mkt'])} 元 "
        f"({totals['ratio']})"
    )


def sim_buy(names: list[str], budget: float | None = None) -> str:
    if not names:
        return "请指定标的，例如：sim 买 利通电子，江波龙"

    if not os.path.isfile(SIM_XLSX):
        init_sim_xlsx()

    df = _load_df()
    mapping = _build_name_code_map()
    today = date.today()
    lines: list[str] = []
    errors: list[str] = []

    active_names = {
        str(r["标的"]).strip()
        for _, r in df.iterrows()
        if not _is_sold(r.get(SOLD_COL)) and not pd.isna(r.get("标的"))
    }

    new_rows: list[dict] = []
    for raw in names:
        try:
            name, code = resolve_stock_name(raw, mapping)
        except ValueError as e:
            errors.append(str(e))
            continue

        if name in active_names:
            errors.append(f"「{name}」已在模拟持仓中（未卖出），跳过")
            continue

        price = fetch_spot_price(code)
        if price is None:
            errors.append(f"「{name}」({code}) 无法获取现价")
            continue
        time.sleep(0.2)

        try:
            budget = _resolve_budget(price)
            shares = _calc_shares(price, budget)
        except ValueError as e:
            errors.append(f"「{name}」：{e}")
            continue

        cost = round(price, 4)  # 买入成本 = 下单时刻市场价，之后不再变更
        metrics = _calc_metrics(cost, shares, price, today, as_of=today)
        invest = round(cost * shares, 2)

        row = {
            "标的": name,
            "代码": code,
            "成本": cost,
            "股数": shares,
            "持有人": SIM_HOLDER,
            SOLD_COL: "N",
            "建仓日期": today.strftime("%Y-%m-%d"),
            **metrics,
        }
        new_rows.append(row)
        active_names.add(name)
        budget_wan = budget / 10_000
        lines.append(
            f"买入 {name}({code})：{shares} 股 @ {cost:.2f}（预算 {budget_wan:.0f} 万），"
            f"投入 {fmt_money(invest)} 元，市值 {fmt_money(metrics['市值'])} 元"
        )

    if new_rows:
        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
        _save_df(df)

    parts: list[str] = []
    if lines:
        parts.append("模拟买入完成：\n" + "\n".join(f"• {ln}" for ln in lines))
    if errors:
        parts.append("以下未成交：\n" + "\n".join(f"• {e}" for e in errors))
    if not parts:
        return "未执行任何买入"
    return "\n\n".join(parts)


def sim_sell(names: list[str]) -> str:
    if not names:
        return "请指定标的，例如：sim 卖 利通电子"

    if not os.path.isfile(SIM_XLSX):
        return "模拟持仓.xlsx 不存在"

    df = _load_df()
    if df.empty:
        return "模拟持仓为空"

    sync_sim_prices()
    df = _load_df()

    lines: list[str] = []
    errors: list[str] = []
    today = date.today()

    for raw in names:
        q = raw.strip()
        if not q:
            continue
        matched_idx: list[int] = []
        for idx, row in df.iterrows():
            if _is_sold(row.get(SOLD_COL)):
                continue
            name = str(row.get("标的", "")).strip()
            if name == q or q in name or name in q:
                matched_idx.append(idx)

        if not matched_idx:
            errors.append(f"未找到未卖出的持仓「{q}」")
            continue
        if len(matched_idx) > 1:
            names_found = [str(df.at[i, "标的"]) for i in matched_idx]
            errors.append(f"「{q}」匹配多条：{', '.join(names_found)}，请写全名")
            continue

        idx = matched_idx[0]
        name = str(df.at[idx, "标的"])
        code = _norm_code(df.at[idx, "代码"])
        cost = float(df.at[idx, "成本"] or 0)
        shares = int(float(df.at[idx, "股数"] or 0))
        open_d = _parse_open_date(df.at[idx, "建仓日期"])

        price = fetch_spot_price(code)
        time.sleep(0.2)
        if price is None:
            existing = df.at[idx, "现价"]
            if pd.notna(existing) and float(existing) > 0:
                price = float(existing)
        metrics = _calc_metrics(cost, shares, price, open_d, as_of=today)
        for k in ("现价", "市值", "盈亏", "盈亏比", "持仓时间(天)"):
            df.at[idx, k] = metrics[k]
        df.at[idx, SOLD_COL] = "Y"  # 卖出后整行冻结，sync 不再更新

        pnl = metrics.get("盈亏")
        ratio = metrics.get("盈亏比")
        lines.append(
            f"卖出 {name}({code})：已冻结，"
            f"盈亏 {fmt_money(pnl) if pnl is not None else '—'} 元 ({ratio or '—'})，"
            f"持仓 {metrics['持仓时间(天)']} 天"
        )

    _save_df(df)

    parts: list[str] = []
    if lines:
        parts.append("模拟卖出完成：\n" + "\n".join(f"• {ln}" for ln in lines))
    if errors:
        parts.append("以下未处理：\n" + "\n".join(f"• {e}" for e in errors))
    if not parts:
        return "未执行任何卖出"
    return "\n\n".join(parts)


def _split_stock_names(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"[,，、\s]+", text)
    return [p.strip() for p in parts if p.strip()]


def parse_sim_command(text: str) -> tuple[str | None, list[str], str | None]:
    """
    解析 sim 买/卖 指令。
    返回 (action, names, error)。action 为 'buy' | 'sell' | None。
    """
    stripped = text.strip()
    if not stripped:
        return None, [], None

    parts = stripped.split(None, 2)
    if not parts or parts[0].lower() != "sim":
        return None, [], None

    if len(parts) < 2:
        return None, [], "请使用 sim 买 {标的…} 或 sim 卖 {标的…}"

    verb = parts[1].strip()
    rest = parts[2] if len(parts) > 2 else ""
    names = _split_stock_names(rest)

    if verb in BUY_VERBS:
        if not names:
            return "buy", [], "请指定买入标的，例如：sim 买 利通电子，江波龙"
        return "buy", names, None
    if verb in SELL_VERBS:
        if not names:
            return "sell", [], "请指定卖出标的，例如：sim 卖 利通电子"
        return "sell", names, None

    return None, [], f"未知 sim 操作「{verb}」，请用 买 或 卖"


def handle_sim_command(text: str) -> str | None:
    action, names, err = parse_sim_command(text)
    if action is None and err is None:
        return None
    if err:
        return err
    if action == "buy":
        return sim_buy(names)
    if action == "sell":
        return sim_sell(names)
    return None


def rebuild_active_positions(*, keep_open_date: bool = True) -> str:
    """
    按当前预算规则（100 万整数倍）与市价，重算所有未卖出持仓的成本/股数/现价等。
    已卖出行不动。
    """
    if not os.path.isfile(SIM_XLSX):
        return "模拟持仓.xlsx 不存在"

    df = _load_df()
    if df.empty:
        return "模拟持仓为空"

    today = date.today()
    lines: list[str] = []
    errors: list[str] = []
    rebuilt = 0
    frozen = 0

    for idx, row in df.iterrows():
        if _is_sold(row.get(SOLD_COL)):
            frozen += 1
            continue

        name = str(row.get("标的", "")).strip()
        code = _norm_code(row.get("代码"))
        if not name or not code:
            errors.append(f"第 {idx + 1} 行缺少标的或代码")
            continue

        price = fetch_spot_price(code)
        if price is None:
            errors.append(f"「{name}」({code}) 无法获取现价，跳过")
            continue
        time.sleep(0.2)

        try:
            budget = _resolve_budget(price)
            shares = _calc_shares(price, budget)
        except ValueError as e:
            errors.append(f"「{name}」：{e}")
            continue

        cost = round(price, 4)
        open_d = _parse_open_date(row.get("建仓日期")) if keep_open_date else today
        metrics = _calc_metrics(cost, shares, price, open_d, as_of=today)
        invest = round(cost * shares, 2)

        df.at[idx, "成本"] = cost
        df.at[idx, "股数"] = shares
        for k in ("现价", "市值", "盈亏", "盈亏比", "持仓时间(天)"):
            df.at[idx, k] = metrics[k]
        if not keep_open_date:
            df.at[idx, "建仓日期"] = today.strftime("%Y-%m-%d")

        rebuilt += 1
        budget_wan = budget / 10_000
        lines.append(
            f"{name}({code})：{shares} 股 @ {cost:.2f}（预算 {budget_wan:.0f} 万），"
            f"投入 {fmt_money(invest)} 元"
        )

    _save_df(df)

    totals = _portfolio_totals(df)
    parts = [f"已按 100 万预算规则重算 {rebuilt} 条持仓，冻结 {frozen} 条（已卖出）"]
    parts.append(
        f"合计 成本 {fmt_money(totals['total_cost'])} 元 / 市值 {fmt_money(totals['total_mkt'])} 元 ({totals['ratio']})"
    )
    if lines:
        parts.append("\n".join(f"• {ln}" for ln in lines))
    if errors:
        parts.append("以下未处理：\n" + "\n".join(f"• {e}" for e in errors))
    return "\n\n".join(parts)


def format_sim_summary(max_rows: int = 20) -> str:
    if not os.path.isfile(SIM_XLSX):
        return "（尚无模拟持仓.xlsx）"
    df = _load_df()
    if df.empty:
        return "模拟持仓为空"
    lines = ["# 模拟持仓", ""]
    for _, row in df.head(max_rows).iterrows():
        sold = _is_sold(row.get(SOLD_COL))
        tag = "[已卖]" if sold else "[持仓]"
        lines.append(
            f"{tag} {row['标的']} {row['股数']}股 "
            f"成本{row['成本']} 现价{row.get('现价', '—')} "
            f"盈亏{row.get('盈亏比', '—')}"
        )
    totals = _portfolio_totals(df)
    lines.extend(
        [
            "",
            f"**合计** 成本 {fmt_money(totals['total_cost'])} 元 | "
            f"市值 {fmt_money(totals['total_mkt'])} 元 | "
            f"盈亏 {fmt_money(totals['pnl'], signed=True)} 元 ({totals['ratio']})",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="模拟持仓 sim 买/卖/sync")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("init", help="创建空 模拟持仓.xlsx")
    p_buy = sub.add_parser("buy", help="模拟买入")
    p_buy.add_argument("names", nargs="+", help="标的名称")
    p_sell = sub.add_parser("sell", help="模拟卖出")
    p_sell.add_argument("names", nargs="+", help="标的名称")
    sub.add_parser("sync", help="刷新现价（跳过已卖出）")
    sub.add_parser("rebuild", help="按当前预算规则重算未卖出持仓")
    p_handle = sub.add_parser("handle", help="解析 sim 指令字符串")
    p_handle.add_argument("text", help='如 "sim 买 利通电子，江波龙"')
    sub.add_parser("show", help="打印摘要")

    args = ap.parse_args()
    if args.cmd == "init":
        init_sim_xlsx()
    elif args.cmd == "buy":
        print(sim_buy(args.names))
    elif args.cmd == "sell":
        print(sim_sell(args.names))
    elif args.cmd == "sync":
        print(sync_sim_prices())
    elif args.cmd == "rebuild":
        print(rebuild_active_positions())
    elif args.cmd == "handle":
        out = handle_sim_command(args.text)
        print(out if out else "无法解析 sim 指令")
    elif args.cmd == "show":
        print(format_sim_summary())
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
