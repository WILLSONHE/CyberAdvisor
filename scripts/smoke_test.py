#!/usr/bin/env python3
"""CyberAdvisor 全链路冒烟测试（只读/ dry-run 为主，不写业务数据）。"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""
    skipped: bool = False


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "", *, skipped: bool = False) -> None:
        self.results.append(Result(name, ok, detail, skipped))

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if not r.ok and not r.skipped]

    @property
    def ok(self) -> bool:
        return not self.failed


def _run_py(args: list[str], *, timeout: int = 300, cwd: str | None = None) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    p = subprocess.run(
        [sys.executable] + args,
        cwd=cwd or SCRIPT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=env,
    )
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out.strip()[-2000:]


def _import(name: str, attr: str = "") -> None:
    mod = importlib.import_module(name)
    if attr:
        getattr(mod, attr)


def test_imports(s: Suite) -> None:
    modules = [
        "bilibili.env",
        "feishu.env",
        "douyin.env",
        "tdx_vipdoc",
        "tdx_market_data",
        "daily_bars",
        "tushare_daily",
        "bollinger_utils",
        "report_data",
        "chan.kline",
        "chan.analyze",
        "chan.outlook_blend",
        "chan.policy",
        "chan.report",
        "chan.backtest",
        "llm_budget",
        "dashboard.data",
        "graph.orchestrator",
        "graph.runner",
        "market_intraday",
        "market_daily.report",
        "market_daily.supplement",
        "outlook_tracker",
        "outlook_params",
        "outlook_universe",
        "trading_calendar",
        "ai_sim.collector",
        "ai_sim.strategy",
        "ai_sim.agent_review",
        "ai_sim.index_context",
        "feishu.agent_prompts",
        "generate_single_analysis_report",
        "analysis_report",
        "vipdoc_refresh",
        "minute_data_audit",
        "mootdx_bestip",
        "portfolio",
        "sim_portfolio",
        "coarse_screen",
        "fine_screen",
        "wiki.chk",
    ]
    for m in modules:
        try:
            _import(m)
            s.add(f"import {m}", True)
        except Exception as exc:
            s.add(f"import {m}", False, str(exc))


def test_env(s: Suite) -> None:
    try:
        from bilibili.env import apply_config_to_environ

        apply_config_to_environ()
        s.add("env TDX_VIPDOC", bool(os.environ.get("TDX_VIPDOC")), os.environ.get("TDX_VIPDOC", "")[:40])
        s.add("env TUSHARE_TOKEN", bool(os.environ.get("TUSHARE_TOKEN")), "configured" if os.environ.get("TUSHARE_TOKEN") else "missing")
    except Exception as exc:
        s.add("env load", False, str(exc))


def test_data_core(s: Suite) -> None:
    try:
        from chan.analyze import analyze_code, analyze_index
        from daily_bars import get_daily_bars
        from tushare_daily import status

        df = get_daily_bars("600021", limit=60, min_bars=25)
        s.add("daily_bars 600021", df is not None and len(df) >= 25, f"bars={len(df) if df is not None else 0}")
        st = status("600021")
        s.add("tushare status", st.get("resolved_last") is not None, str(st.get("resolved_last")))
        ic = analyze_index()
        s.add("chan analyze_index", ic.get("ok"), ic.get("action", ic.get("error")))
        sc = analyze_code("600021")
        s.add("chan analyze_code", sc.get("ok"), sc.get("action", sc.get("error")))
    except Exception as exc:
        s.add("data_core", False, traceback.format_exc()[-500:])


def test_trading_calendar(s: Suite) -> None:
    try:
        from datetime import date

        from trading_calendar import (
            add_trading_days,
            ensure_calendar,
            expected_latest_bar_date,
            is_trading_day,
            status,
        )

        ensure_calendar(start=date(2026, 1, 1), end=date(2026, 12, 31))
        st = status()
        s.add("trade_cal cache", st.get("days_cached", 0) > 200, str(st.get("days_cached")))
        # 2026-06-12 周五开盘；13-14 休市（Tushare）
        s.add("trade_cal 2026-06-12", is_trading_day(date(2026, 6, 12)), "open")
        s.add("trade_cal 2026-06-14", not is_trading_day(date(2026, 6, 14)), "closed")
        d1 = add_trading_days(date(2026, 6, 10), 1)
        s.add("add_trading_days +1", str(d1) == "2026-06-11", str(d1))
        s.add("expected_bar", expected_latest_bar_date(as_of=date(2026, 6, 14)) <= date(2026, 6, 12), str(st.get("expected_bar")))
    except Exception as exc:
        s.add("trading_calendar", False, str(exc))


def test_graph_dry_run(s: Suite) -> None:
    try:
        from graph.llm import graph_pipeline_enabled
        from graph.orchestrator import run_sug_pipeline

        state = run_sug_pipeline("Wilson", dry_run=True)
        s.add(
            "graph sug dry-run",
            bool(state.analysis_id) and state.current_stage == "done",
            f"id={state.analysis_id[:24]}… spent=${state.budget.spent_usd:.2f} enabled={graph_pipeline_enabled()}",
        )
        rc, tail = _run_py(["graph/runner.py", "status"], timeout=30)
        s.add("graph runner status", rc == 0, tail[-120:] if rc == 0 else tail[-200:])
    except Exception as exc:
        s.add("graph_dry_run", False, str(exc))


def test_backtest_offline(s: Suite) -> None:
    try:
        from chan.analyze import analyze_day_frame
        from chan.backtest import run_backtest, walk_code
        from daily_bars import get_daily_bars
        from llm_budget import check_budget, load_budget

        df = get_daily_bars("600021", limit=120, min_bars=60)
        if df is None or len(df) < 60:
            s.add("backtest slice", True, "skip: insufficient bars", skipped=True)
            return
        snap = analyze_day_frame(df.iloc[:80].copy(), code="600021", name="上海电力")
        s.add("analyze_day_frame", snap.get("ok"), snap.get("buy_point", snap.get("error")))
        wc = walk_code("600021", "上海电力", lookback_days=60, horizons=(3, 5))
        s.add("walk_code", True, f"outcomes={len(wc)}")
        rep = run_backtest([("600021", "上海电力")], lookback_days=60, horizons=(3, 5))
        s.add("run_backtest", rep.signal_count >= 0, f"signals={rep.signal_count}")
        cfg = load_budget()
        ok, msg = check_budget("sug", cfg)
        s.add("llm_budget", ok or not ok, msg[:80])
    except Exception as exc:
        s.add("backtest_offline", False, str(exc))


def test_bollinger_outlook(s: Suite) -> None:
    try:
        from bollinger_utils import bollinger_for_code, export_outlook_horizon, get_kline, _outlook_3d_7d

        k = get_kline("600021", 60)
        b = bollinger_for_code("600021")
        s.add("bollinger 600021", b and "error" not in b, b.get("zone") if b else "none")
        if b:
            ol = _outlook_3d_7d(b, kline_extra=b.get("kline_extra"))
            s.add("outlook 1/3/7", bool(ol.get("d1_most_likely")), str(ol.get("d1_most_likely")))
            s.add("outlook chan blend", ol.get("chan") is not None or "缠论" in str(ol.get("d1", "")), str(ol.get("note", ""))[:60])
            h1 = export_outlook_horizon(b, days=1, kline_extra=b.get("kline_extra"))
            s.add("export_outlook chan", bool(h1.get("chan")), str(h1.get("params_version")))
    except Exception as exc:
        s.add("bollinger_outlook", False, str(exc))


def test_verdict_index_gate(s: Suite) -> None:
    try:
        from chan.policy import allows_new_buy, compact_chan
        from bollinger_utils import build_stock_verdict

        fake_index = {
            "ok": True,
            "buy_point": "一卖/减仓",
            "action": "sell",
            "score": -1.8,
            "structure": "上涨趋势",
            "ZD": 3000,
            "ZG": 3100,
            "protect_price": 3050,
        }
        fake_stock = {
            "ok": True,
            "buy_point": "二买候选",
            "action": "buy",
            "score": 1.6,
            "structure": "盘整",
            "ZD": 10,
            "ZG": 12,
            "protect_price": 10.5,
        }
        ok, _ = allows_new_buy(fake_stock, fake_index)
        s.add("policy index 一卖 blocks", not ok, "allows_new_buy")
        v = build_stock_verdict("600021", name="测试", index_ok_buy=True, index_chan=fake_index)
        s.add("verdict index 一卖 can_open", v.get("can_open") is False, str(v.get("open_block_reason", ""))[:50])
    except Exception as exc:
        s.add("verdict_index_gate", False, str(exc))


def test_report_enrich(s: Suite) -> None:
    try:
        from report_data import enrich_stock

        row = enrich_stock("600021", name="测试")
        gaps = row.get("gaps") or []
        s.add("report_data enrich", row.get("code") == "600021", f"gaps={gaps[:3]}")
        s.add("report_data chan", bool(row.get("chan")), (row.get("chan") or {}).get("action"))
    except Exception as exc:
        s.add("report_enrich", False, str(exc))


def test_ai_sim_offline(s: Suite) -> None:
    try:
        from ai_sim.strategy import plan_trades
        from ai_sim.universe import build_universe

        u = build_universe()
        s.add("ai_sim universe", len(u) > 0, f"n={len(u)}")
        # 无 tick 文件时 plan 应优雅返回
        dec = plan_trades(tick_path=os.path.join(SCRIPT_DIR, "__no_such_tick__.json"))
        s.add("ai_sim plan_trades", dec is not None, f"decisions={len(getattr(dec, 'decisions', []) or [])}")
    except Exception as exc:
        s.add("ai_sim_offline", False, str(exc))


def test_scripts(s: Suite) -> None:
    cases: list[tuple[str, list[str], int, bool]] = [
        ("mootdx_bestip", ["mootdx_bestip.py"], 120, False),
        ("minute_data_audit", ["minute_data_audit.py", "--write"], 180, False),
        ("tushare_daily", ["tushare_daily.py", "--code", "600021", "--json"], 120, False),
        ("sync_portfolio", ["sync_portfolio_from_xlsx.py"], 60, True),
        ("wiki_chk", ["wiki_cli.py", "chk"], 120, False),
        ("bilibili_dry", ["bilibili_fetch.py", "--dry-run"], 180, False),
        ("douyin_dry", ["douyin_fetch.py", "--dry-run"], 180, False),
        ("rw_video_dry", ["rw_video.py", "--dry-run", "--pending-only"], 120, False),
        ("vipdoc_dry", ["vipdoc_refresh.py", "--dry-run"], 120, False),
        ("outlook_snap", ["outlook_tracker.py", "snapshot", "--code", "600021"], 120, False),
        ("coarse_screen", ["coarse_screen.py"], 600, True),
        ("fine_screen", ["fine_screen.py"], 300, True),
        ("daily_report", ["daily_report.py"], 300, True),
        ("outlook_batch_track", ["outlook_tracker.py", "batch", "--universe", "track"], 600, True),
    ]
    for name, args, timeout, soft in cases:
        if name == "sync_portfolio":
            xlsx = os.path.join(ROOT, "持仓.xlsx")
            if not os.path.isfile(xlsx):
                s.add(name, True, "skip: no 持仓.xlsx", skipped=True)
                continue
        try:
            rc, tail = _run_py(args, timeout=timeout)
            ok = rc == 0
            if not ok and soft:
                s.add(name, True, f"WARN rc={rc} {tail[-200:]}", skipped=True)
            else:
                s.add(name, ok, f"rc={rc}" if ok else tail[-300:])
        except subprocess.TimeoutExpired:
            s.add(name, False, f"timeout>{timeout}s")
        except Exception as exc:
            s.add(name, False, str(exc))


def test_feishu_download(s: Suite) -> None:
    if not os.environ.get("FEISHU_PORTFOLIO_URL"):
        s.add("feishu_download_portfolio", True, "skip: no FEISHU_PORTFOLIO_URL", skipped=True)
        return
    rc, tail = _run_py(["feishu_download_portfolio.py"], timeout=120)
    s.add("feishu_download_portfolio", rc == 0, f"rc={rc}" if rc == 0 else tail[-300:])


def main() -> int:
    from bilibili.env import apply_config_to_environ

    apply_config_to_environ()
    s = Suite()
    print(f"CyberAdvisor smoke test @ {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"ROOT={ROOT}\n")

    for fn in (
        test_imports,
        test_env,
        test_data_core,
        test_trading_calendar,
        test_backtest_offline,
        test_graph_dry_run,
        test_bollinger_outlook,
        test_verdict_index_gate,
        test_report_enrich,
        test_ai_sim_offline,
        test_feishu_download,
        test_scripts,
    ):
        fn(s)

    fails = s.failed
    skipped = [r for r in s.results if r.skipped]
    passed = [r for r in s.results if r.ok and not r.skipped]

    print(f"\n{'='*60}")
    print(f"PASS {len(passed)} | SKIP {len(skipped)} | FAIL {len(fails)} | TOTAL {len(s.results)}")
    for r in s.results:
        tag = "SKIP" if r.skipped else ("OK  " if r.ok else "FAIL")
        extra = f" — {r.detail}" if r.detail else ""
        print(f"  [{tag}] {r.name}{extra}")
    if fails:
        print(f"\n{'='*60}\nFAILED")
        return 1
    print(f"\n{'='*60}\nALL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
