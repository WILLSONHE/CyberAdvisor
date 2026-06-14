#!/usr/bin/env python3
"""审计 vipdoc 本地 1/5 分钟覆盖（持仓+追踪+指数）。"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tdx_market_data import read_minute_bars

OUTPUT_JSON = SCRIPT_DIR.parent / "Wiki" / "数据" / "minute_data_audit.json"
OUTPUT_MD = SCRIPT_DIR.parent / "Wiki" / "数据" / "minute_data_audit.md"

# 与 [[缠论-数据接入]] 一致
EXPECT = {"1m": "2026-05-18", "5m": "2026-03-23"}
MIN_BARS = {"1m": 200, "5m": 40}


def _collect_codes() -> list[str]:
    from outlook_universe import iter_universe

    codes = {"000001", "399001", "000300"}
    for u in ("portfolio", "track", "queried"):
        for e in iter_universe(u):
            c = str(e.code).zfill(6)
            if len(c) == 6 and c.isdigit():
                codes.add(c)
    return sorted(codes)


def audit_code(code: str) -> dict:
    row: dict = {"code": code}
    for klt, label in ((1, "1m"), (5, "5m")):
        df = read_minute_bars(code, klt=klt, limit=999999)
        key = label
        if df is None or df.empty:
            row[key] = {"ok": False, "bars": 0, "issues": ["无本地文件"]}
            continue
        days = sorted(set(str(t)[:10] for t in df["time"]))
        cnt = df.assign(day=df["time"].astype(str).str[:10]).groupby("day").size()
        thin = [str(d) for d, n in cnt.items() if n < MIN_BARS[label]]
        issues: list[str] = []
        if days[0] > EXPECT[label]:
            issues.append(f"起始 {days[0]} 晚于期望 {EXPECT[label]}")
        if thin:
            issues.append(f"稀疏日 {thin[:5]}")
        row[key] = {
            "ok": len(issues) == 0,
            "bars": len(df),
            "start": days[0],
            "end": days[-1],
            "days": len(days),
            "issues": issues,
        }
    return row


def build_report(*, expect: dict[str, str] | None = None) -> tuple[list[dict], str]:
    expect = expect or EXPECT
    codes = _collect_codes()
    rows = [audit_code(c) for c in codes]
    missing_1m = [r["code"] for r in rows if not r.get("1m", {}).get("bars")]
    missing_5m = [r["code"] for r in rows if not r.get("5m", {}).get("bars")]
    bad_1m = [r["code"] for r in rows if r.get("1m", {}).get("issues")]
    bad_5m = [r["code"] for r in rows if r.get("5m", {}).get("issues")]

    lines = [
        "# 分钟 K 线审计",
        "",
        f"> 日期：{date.today()} | 标的 {len(codes)} 只 | 期望 1m≥{expect['1m']} · 5m≥{expect['5m']}",
        "",
        "## 摘要",
        "",
        f"- **1m 缺失**：{len(missing_1m)} {missing_1m[:8]}",
        f"- **5m 缺失**：{len(missing_5m)} {missing_5m[:8]}",
        f"- **1m 起始/稀疏问题**：{len(bad_1m)}",
        f"- **5m 起始/稀疏问题**：{len(bad_5m)}",
        "",
    ]
    if not missing_1m and not missing_5m and not bad_1m and not bad_5m:
        lines.append("✅ **全宇宙覆盖正常**（与当前下载区间一致）。")
    else:
        lines.append("⚠️ 见下表 `issues`。")
    lines.extend(["", "## 明细", "", "| 代码 | 1m 根数 | 1m 区间 | 5m 根数 | 5m 区间 | 问题 |", "|------|---------|---------|---------|---------|------|"])
    for r in rows:
        m1, m5 = r.get("1m", {}), r.get("5m", {})
        iss = "; ".join((m1.get("issues") or []) + (m5.get("issues") or [])) or "—"
        lines.append(
            f"| {r['code']} | {m1.get('bars', 0)} | {m1.get('start', '—')}~{m1.get('end', '—')} | "
            f"{m5.get('bars', 0)} | {m5.get('start', '—')}~{m5.get('end', '—')} | {iss} |"
        )
    lines.append("")
    return rows, "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="审计 vipdoc 1/5 分钟覆盖")
    ap.add_argument("--write", action="store_true", help="写入 Wiki/数据/minute_data_audit.*")
    args = ap.parse_args()
    rows, md = build_report()
    print(md)
    if args.write:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps({"date": str(date.today()), "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
        OUTPUT_MD.write_text(md, encoding="utf-8")
        print(f"Written {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
