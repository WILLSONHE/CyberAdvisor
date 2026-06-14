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


def _default_expect_bar() -> date:
    from trading_calendar import expected_latest_bar_date

    return expected_latest_bar_date()


def _collect_codes() -> list[str]:
    from outlook_universe import iter_universe

    codes: set[str] = {"000001"}
    for universe in ("portfolio", "track", "queried"):
        for e in iter_universe(universe):
            c = str(e.code or "").zfill(6)
            if len(c) == 6 and c.isdigit():
                codes.add(c)
    return sorted(codes)


def _latest_bar_date(code: str) -> date | None:
    try:
        from tdx_market_data import latest_bar_date as _merged_latest

        return _merged_latest(code)
    except Exception:
        pass
    return None


def check_vipdoc_freshness(
    codes: list[str], *, expect: date | None = None, allow_lag_days: int = 0
) -> dict:
    from datetime import timedelta

    from tdx_vipdoc import vipdoc_root

    expect = expect or _default_expect_bar()
    root = vipdoc_root()
    ok: list[str] = []
    stale: list[tuple[str, date | None]] = []
    missing: list[str] = []
    min_ok = expect - timedelta(days=max(0, allow_lag_days))

    for code in codes:
        d = _latest_bar_date(code)
        if d is None:
            missing.append(code)
        elif d >= expect:
            ok.append(code)
        elif allow_lag_days and d >= min_ok:
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


def run_batches(*, session: str = "午盘", dry_run: bool = False, report_date: date | None = None) -> list[str]:
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
        result = run_batch(universe, session=sess, report_date=report_date)
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
    parser.add_argument("--allow-lag", type=int, default=0, help="允许 K 线落后期望日 N 个自然日仍跑 batch（如 6/12 期望但只有 6/11）")
    parser.add_argument(
        "--rerecord-from",
        default="",
        help="vipdoc 数据日 YYYY-MM-DD：先重做 track+portfolio 预测再 batch",
    )
    parser.add_argument(
        "--report-date",
        default="",
        help="复盘 markdown 文件名日期 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只检查 freshness，不写文件")
    args = parser.parse_args()

    from mootdx_bestip import run_bestip

    run_bestip()

    expect = date.fromisoformat(args.expect_date) if args.expect_date else _default_expect_bar()
    codes = _collect_codes()
    print(f"vipdoc refresh | {datetime.now():%Y-%m-%d %H:%M} | 标的 {len(codes)} 只 | 期望 K 线 ≥ {expect}")

    stat = check_vipdoc_freshness(codes, expect=expect, allow_lag_days=max(0, args.allow_lag))
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
        lag_note = f"（allow-lag={args.allow_lag} 已计入 ok）" if args.allow_lag else ""
        print(f"  [WARN] K 线早于 {expect} ({len(stat['stale'])}): {sample}"
              + (" …" if len(stat["stale"]) > 6 else "")
              + lag_note)
        if not args.allow_lag:
            print("  提示: 确认通达信/招商已收盘下载；通常 15:45 后 .day 才写入当日 bar；或加 --allow-lag 1")

    if stat["ok_count"] == 0 and not args.dry_run:
        print("[FAIL] 无任何标的含期望日期 K 线，已中止 batch（加 --dry-run 仅检查）")
        return 2

    try:
        from tdx_market_data import coverage_vs_vipdoc, minute_data_status

        cov = coverage_vs_vipdoc(["000001", "399001", "000300"])
        for row in cov:
            if row.get("merged_last") and row.get("vipdoc_last") and row["merged_last"] > row["vipdoc_last"]:
                print(f"  [ds 扩展] {row['code']}: vipdoc {row['vipdoc_last']} → 合并 {row['merged_last']}")
        mins = minute_data_status(["000001", "000300", "600021"])
        print(f"  本地分钟K抽样: {mins.get('samples')}")
        try:
            from market_intraday import recent_index_patterns

            intra = recent_index_patterns("000001", klt=5, days=3)
            hint = intra.get("next_session_hint") or {}
            if hint.get("summary"):
                print(f"  大盘形态: {hint['summary']}")
        except Exception as e2:
            print(f"  [WARN] 日内形态跳过: {e2}")
    except Exception as e:
        print(f"  [WARN] 扩展行情检查跳过: {e}")

    if args.rerecord_from and not args.dry_run:
        from outlook_tracker import rerecord_pool_outlooks

        tf = date.fromisoformat(args.rerecord_from)
        reg = date.fromisoformat(args.report_date) if args.report_date else _today()
        print(f"\n[rerecord-pools] track_from={tf} 登记日={reg} → 重做 track+portfolio 1/3/7 预测")
        rr = rerecord_pool_outlooks(
            tf,
            registration_date=reg,
            purge_dates=(tf, reg, _today()),
            portfolio_session=args.session,
        )
        print(
            f"  删除 {rr['removed']} 条旧记录 | track {len(rr['added'].get('track', []))} | "
            f"portfolio {len(rr['added'].get('portfolio', []))}"
        )

    report_date = date.fromisoformat(args.report_date) if args.report_date else None
    outputs = run_batches(session=args.session, dry_run=args.dry_run, report_date=report_date)
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
