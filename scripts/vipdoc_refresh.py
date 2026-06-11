#!/usr/bin/env python3
"""
vipdoc 日 K 就绪后刷新布林/σ/1·3·7 追踪快照（Cursor 指令 `vipdoc`）。

典型时机：daily.bat（15:00）之后、通达信 vipdoc 写入当日 .day（约 15:45+）再跑；
随后再 `sug 全员 午盘` 或 `agent sug 全员 午盘`。
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


def _today() -> date:
    return date.today()


def _collect_codes() -> list[str]:
    from outlook_universe import iter_universe

    codes: set[str] = {"000001"}
    for universe in ("portfolio", "track"):
        for e in iter_universe(universe):
            c = str(e.code or "").zfill(6)
            if len(c) == 6 and c.isdigit():
                codes.add(c)
    return sorted(codes)


def _latest_bar_date(code: str) -> date | None:
    from tdx_vipdoc import read_daily_bars

    df = read_daily_bars(code, limit=5)
    if df is None or df.empty:
        return None
    last = str(df.iloc[-1]["datetime"])[:10]
    try:
        return date.fromisoformat(last)
    except ValueError:
        return None


def check_vipdoc_freshness(codes: list[str], *, expect: date | None = None) -> dict:
    from tdx_vipdoc import vipdoc_root

    expect = expect or _today()
    root = vipdoc_root()
    ok: list[str] = []
    stale: list[tuple[str, date | None]] = []
    missing: list[str] = []

    for code in codes:
        d = _latest_bar_date(code)
        if d is None:
            missing.append(code)
        elif d >= expect:
            ok.append(code)
        else:
            stale.append((code, d))

    return {
        "root": root,
        "expect": expect.isoformat(),
        "ok_count": len(ok),
        "stale": stale,
        "missing": missing,
        "total": len(codes),
    }


def run_batches(*, session: str = "午盘", dry_run: bool = False) -> list[str]:
    from outlook_tracker import run_batch

    steps = [
        ("track", ""),
        ("portfolio", session),
    ]
    outputs: list[str] = []
    for universe, sess in steps:
        label = f"batch --universe {universe}" + (f" --session {sess}" if sess else "")
        print(f"\n[{label}]")
        if dry_run:
            print("  (dry-run skip)")
            continue
        result = run_batch(universe, session=sess)
        path = result.get("review_file") or result.get("path") or ""
        if path:
            outputs.append(path)
            print(f"  -> {path}")
    return outputs


def run_sync(*, dry_run: bool = False) -> None:
    print("\n[sim_portfolio.py sync]")
    if dry_run:
        print("  (dry-run skip)")
        return
    from sim_portfolio import sync_sim_prices

    sync_sim_prices()


def main() -> int:
    parser = argparse.ArgumentParser(description="vipdoc 就绪后刷新 outlook 批追踪（Cursor: vipdoc）")
    parser.add_argument("--session", default="午盘", help="portfolio 批追踪盘次（默认 午盘）")
    parser.add_argument("--expect-date", default="", help="期望最新 K 线日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--skip-sync", action="store_true", help="跳过 sim_portfolio sync")
    parser.add_argument("--dry-run", action="store_true", help="只检查 freshness，不写文件")
    args = parser.parse_args()

    expect = date.fromisoformat(args.expect_date) if args.expect_date else _today()
    codes = _collect_codes()
    print(f"vipdoc refresh | {datetime.now():%Y-%m-%d %H:%M} | 标的 {len(codes)} 只 | 期望 K 线 ≥ {expect}")

    stat = check_vipdoc_freshness(codes, expect=expect)
    root = stat["root"]
    if not os.path.isdir(root):
        print(f"[FAIL] vipdoc 根目录不存在: {root}（.env 设 TDX_VIPDOC）")
        return 1
    print(f"  根目录: {root}")
    print(f"  已含当日 K 线: {stat['ok_count']}/{stat['total']}")

    if stat["missing"]:
        print(f"  [WARN] 无本地 .day ({len(stat['missing'])}): {', '.join(stat['missing'][:8])}"
              + (" …" if len(stat["missing"]) > 8 else ""))
    if stat["stale"]:
        sample = ", ".join(f"{c}({d})" for c, d in stat["stale"][:6])
        print(f"  [WARN] K 线早于 {expect} ({len(stat['stale'])}): {sample}"
              + (" …" if len(stat["stale"]) > 6 else ""))
        print("  提示: 确认通达信/招商已收盘下载；通常 15:45 后 .day 才写入当日 bar")

    if stat["ok_count"] == 0 and not args.dry_run:
        print("[FAIL] 无任何标的含期望日期 K 线，已中止 batch（加 --dry-run 仅检查）")
        return 2

    outputs = run_batches(session=args.session, dry_run=args.dry_run)
    if not args.skip_sync:
        run_sync(dry_run=args.dry_run)

    print("\n[Done]")
    if outputs:
        print("  复盘/快照:")
        for p in outputs:
            print(f"    {p}")
    print("  下一步: Cursor `sug 全员 午盘` 或飞书 `agent sug 全员 午盘`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
