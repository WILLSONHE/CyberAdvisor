#!/usr/bin/env python3
"""缠论买点 walk-forward 回测（本地、0 部署；vipdoc/Tushare 日 K）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if os.path.join(SCRIPT_DIR, "..") not in sys.path:
    sys.path.insert(0, os.path.join(SCRIPT_DIR, ".."))

from chan.analyze import _is_buy_hint, analyze_day_frame  # noqa: E402
from daily_bars import get_daily_bars  # noqa: E402

BACKTEST_DIR = os.path.join(ROOT, "Wiki", "数据", "缠论回测")
DEFAULT_HORIZONS = (1, 3, 5, 10, 20)
DEFAULT_HIT_PCT = 3.0
PARAMS_VERSION = "2026-06-05-chan-wf-v1"


def _norm_day_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    if "time" not in out.columns:
        if "datetime" in out.columns:
            out["time"] = out["datetime"].astype(str).str[:10]
        elif "date" in out.columns:
            out["time"] = out["date"].astype(str).str[:10]
    out["time"] = out["time"].astype(str).str[:10]
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].astype(float)
    return out.sort_values("time").reset_index(drop=True)


def _parse_bar_date(s: str) -> date | None:
    raw = str(s)[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def load_history(code: str, *, limit: int = 800, as_of: date | None = None) -> pd.DataFrame | None:
    df = get_daily_bars(code, limit=limit, min_bars=60, as_of=as_of)
    return _norm_day_df(df)


def portfolio_codes() -> list[tuple[str, str]]:
    import portfolio

    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for h in portfolio.HOLDINGS:
        code = str(h.get("code", "")).zfill(6)
        if not code.isdigit() or len(code) != 6 or code in seen:
            continue
        seen.add(code)
        out.append((code, str(h.get("name") or code)))
    return out


@dataclass
class SignalOutcome:
    code: str
    name: str
    as_of: str
    buy_point: str
    entry: float
    protect: float
    horizon: int
    max_favorable_pct: float
    max_adverse_pct: float
    close_return_pct: float
    hit: bool
    protect_breach: bool


@dataclass
class BacktestReport:
    generated_at: str
    params_version: str
    universe: list[str]
    lookback_days: int
    hit_threshold_pct: float
    horizons: list[int]
    signal_count: int
    by_buy_point: dict[str, dict[str, Any]]
    by_horizon: dict[str, dict[str, Any]]
    oos: dict[str, Any]
    signals_sample: list[dict[str, Any]] = field(default_factory=list)


def _forward_metrics(
    df: pd.DataFrame,
    idx: int,
    *,
    entry: float,
    protect: float,
    horizon: int,
    hit_pct: float,
) -> SignalOutcome | None:
    if idx + horizon >= len(df):
        return None
    future = df.iloc[idx + 1 : idx + 1 + horizon]
    if future.empty:
        return None
    max_high = float(future["high"].max())
    min_low = float(future["low"].min())
    last_close = float(future["close"].iloc[-1])
    max_fav = (max_high / entry - 1.0) * 100.0
    max_adv = (min_low / entry - 1.0) * 100.0
    close_ret = (last_close / entry - 1.0) * 100.0
    protect_breach = min_low < protect
    hit = max_fav >= hit_pct and not protect_breach
    return SignalOutcome(
        code="",
        name="",
        as_of="",
        buy_point="",
        entry=entry,
        protect=protect,
        horizon=horizon,
        max_favorable_pct=round(max_fav, 3),
        max_adverse_pct=round(max_adv, 3),
        close_return_pct=round(close_ret, 3),
        hit=hit,
        protect_breach=protect_breach,
    )


def walk_code(
    code: str,
    name: str,
    *,
    lookback_days: int = 120,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    hit_pct: float = DEFAULT_HIT_PCT,
    min_bars: int = 60,
) -> list[SignalOutcome]:
    df = load_history(code)
    if df is None or len(df) < min_bars + max(horizons) + 5:
        return []

    last_date = _parse_bar_date(str(df.iloc[-1]["time"]))
    if not last_date:
        return []
    start_date = last_date
    # approximate calendar lookback
    from datetime import timedelta

    start_cut = last_date - timedelta(days=int(lookback_days * 1.6))

    outcomes: list[SignalOutcome] = []
    max_h = max(horizons)
    for i in range(min_bars, len(df) - max_h):
        bar_date = _parse_bar_date(str(df.iloc[i]["time"]))
        if not bar_date or bar_date < start_cut:
            continue
        slice_df = df.iloc[: i + 1].copy()
        snap = analyze_day_frame(slice_df, code=code, name=name, has_position=False, source="backtest")
        if not snap.get("ok"):
            continue
        hint = str(snap.get("buy_point") or "")
        if not _is_buy_hint(hint):
            continue
        entry = float(snap.get("last_close") or slice_df["close"].iloc[-1])
        protect = float(snap.get("protect_price") or entry * 0.95)
        as_of = str(snap.get("as_of") or bar_date.isoformat())
        for h in horizons:
            m = _forward_metrics(df, i, entry=entry, protect=protect, horizon=h, hit_pct=hit_pct)
            if m is None:
                continue
            m.code = code
            m.name = name
            m.as_of = as_of
            m.buy_point = hint
            outcomes.append(m)
    return outcomes


def _aggregate(outcomes: list[SignalOutcome]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_bp: dict[str, list[SignalOutcome]] = {}
    by_hz: dict[int, list[SignalOutcome]] = {}
    for o in outcomes:
        by_bp.setdefault(o.buy_point, []).append(o)
        by_hz.setdefault(o.horizon, []).append(o)

    def _stats(items: list[SignalOutcome]) -> dict[str, Any]:
        if not items:
            return {"n": 0}
        n = len(items)
        hits = sum(1 for x in items if x.hit)
        breaches = sum(1 for x in items if x.protect_breach)
        return {
            "n": n,
            "hit_rate_pct": round(hits / n * 100, 2),
            "protect_breach_rate_pct": round(breaches / n * 100, 2),
            "avg_max_favorable_pct": round(sum(x.max_favorable_pct for x in items) / n, 3),
            "avg_close_return_pct": round(sum(x.close_return_pct for x in items) / n, 3),
        }

    bp_summary = {k: _stats(v) for k, v in sorted(by_bp.items())}
    hz_summary = {str(k): _stats(v) for k, v in sorted(by_hz.items())}
    return bp_summary, hz_summary


def _oos_split(outcomes: list[SignalOutcome], *, ratio: float = 0.3) -> dict[str, Any]:
    if not outcomes:
        return {"n": 0}
    dates = sorted({o.as_of for o in outcomes})
    cut = max(1, int(len(dates) * (1.0 - ratio)))
    oos_from = dates[cut] if cut < len(dates) else dates[-1]
    is_set = [o for o in outcomes if o.as_of < oos_from]
    oos_set = [o for o in outcomes if o.as_of >= oos_from]
    _, is_hz = _aggregate(is_set)
    _, oos_hz = _aggregate(oos_set)
    return {
        "oos_from": oos_from,
        "in_sample_horizons": is_hz,
        "out_of_sample_horizons": oos_hz,
    }


def run_backtest(
    codes: list[tuple[str, str]],
    *,
    lookback_days: int = 120,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    hit_pct: float = DEFAULT_HIT_PCT,
) -> BacktestReport:
    all_outcomes: list[SignalOutcome] = []
    for code, name in codes:
        all_outcomes.extend(
            walk_code(code, name, lookback_days=lookback_days, horizons=horizons, hit_pct=hit_pct)
        )

    by_bp, by_hz = _aggregate(all_outcomes)
    oos = _oos_split(all_outcomes)
    sample = [
        {k: v for k, v in asdict(o).items()}
        for o in sorted(all_outcomes, key=lambda x: x.as_of, reverse=True)[:30]
    ]
    unique_signals = len({(o.code, o.as_of, o.buy_point) for o in all_outcomes})

    return BacktestReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        params_version=PARAMS_VERSION,
        universe=[c for c, _ in codes],
        lookback_days=lookback_days,
        hit_threshold_pct=hit_pct,
        horizons=list(horizons),
        signal_count=unique_signals,
        by_buy_point=by_bp,
        by_horizon=by_hz,
        oos=oos,
        signals_sample=sample,
    )


def write_report(report: BacktestReport, *, tag: str | None = None) -> tuple[str, str]:
    os.makedirs(BACKTEST_DIR, exist_ok=True)
    d = datetime.now().strftime("%Y-%m-%d")
    suffix = f"_{tag}" if tag else ""
    json_path = os.path.join(BACKTEST_DIR, f"{d}{suffix}.json")
    md_path = os.path.join(BACKTEST_DIR, f"{d}{suffix}.md")

    payload = asdict(report)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        f"# 缠论买点回测 · {d}",
        "",
        f"- 生成时间：{report.generated_at}",
        f"- 参数版本：`{report.params_version}`",
        f"- 标的数：{len(report.universe)}",
        f"- 独立信号数：{report.signal_count}",
        f"- 回看约 {report.lookback_days} 日历日",
        f"- 命中定义：{report.hit_threshold_pct}% 最大涨幅且未破保护位",
        "",
        "## 按买点类型",
        "",
        "| 买点 | n | 命中率% | 破保护% | 均最大涨幅% | 均收盘收益% |",
        "|------|---|---------|---------|-------------|-------------|",
    ]
    for bp, st in report.by_buy_point.items():
        if st.get("n", 0) == 0:
            continue
        lines.append(
            f"| {bp} | {st['n']} | {st.get('hit_rate_pct', '—')} | "
            f"{st.get('protect_breach_rate_pct', '—')} | "
            f"{st.get('avg_max_favorable_pct', '—')} | {st.get('avg_close_return_pct', '—')} |"
        )

    lines.extend(["", "## 按持有周期", "", "| 周期 | n | 命中率% | 破保护% | 均收盘收益% |", "|------|---|---------|---------|-------------|"])
    for hz, st in report.by_horizon.items():
        if st.get("n", 0) == 0:
            continue
        lines.append(
            f"| {hz}日 | {st['n']} | {st.get('hit_rate_pct', '—')} | "
            f"{st.get('protect_breach_rate_pct', '—')} | {st.get('avg_close_return_pct', '—')} |"
        )

    lines.extend(
        [
            "",
            "## IS / OOS",
            "",
            f"- OOS 起点：`{report.oos.get('oos_from', '—')}`",
            "",
            "> 本地运行：`python scripts/chan/backtest.py --universe portfolio --write`",
        ]
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return json_path, md_path


def latest_report_paths() -> tuple[str | None, str | None]:
    if not os.path.isdir(BACKTEST_DIR):
        return None, None
    jsons = sorted(
        [f for f in os.listdir(BACKTEST_DIR) if f.endswith(".json")],
        reverse=True,
    )
    if not jsons:
        return None, None
    jp = os.path.join(BACKTEST_DIR, jsons[0])
    mp = jp[:-5] + ".md"
    return jp, mp if os.path.isfile(mp) else None


def main() -> int:
    ap = argparse.ArgumentParser(description="缠论买点 walk-forward 回测")
    ap.add_argument("--universe", choices=("portfolio", "codes"), default="portfolio")
    ap.add_argument("--code", action="append", default=[], help="追加或（--universe codes 时）指定代码")
    ap.add_argument("--lookback", type=int, default=120)
    ap.add_argument("--hit-pct", type=float, default=DEFAULT_HIT_PCT)
    ap.add_argument("--horizons", default="1,3,5,10,20")
    ap.add_argument("--write", action="store_true", help="写入 Wiki/数据/缠论回测/")
    ap.add_argument("--json", action="store_true", help="stdout 打印 JSON 摘要")
    args = ap.parse_args()

    horizons = tuple(int(x.strip()) for x in args.horizons.split(",") if x.strip())
    if args.universe == "codes":
        codes = [(str(c).zfill(6), str(c).zfill(6)) for c in args.code]
    else:
        codes = portfolio_codes()
        for raw in args.code:
            c = str(raw).zfill(6)
            if c not in {x for x, _ in codes}:
                codes.append((c, c))

    if not codes:
        print("无标的", file=sys.stderr)
        return 1

    report = run_backtest(codes, lookback_days=args.lookback, horizons=horizons, hit_pct=args.hit_pct)
    print(
        f"signals={report.signal_count} codes={len(codes)} "
        f"horizons={list(horizons)} hit>={args.hit_pct}%"
    )
    for bp, st in report.by_buy_point.items():
        if st.get("n"):
            print(f"  {bp}: n={st['n']} hit={st.get('hit_rate_pct')}%")

    if args.write:
        jp, mp = write_report(report)
        print(f"wrote {jp}")
        print(f"wrote {mp}")

    if args.json:
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
