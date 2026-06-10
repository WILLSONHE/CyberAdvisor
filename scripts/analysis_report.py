#!/usr/bin/env python3
"""生成 sug / 分析报告用的「研判总结」Markdown（调用 bollinger_utils）。"""
from __future__ import annotations

import argparse
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bollinger_utils import build_report_summary_section
from portfolio import HOLDERS, HOLDINGS


def _record_codes(codes: list[tuple[str, str]], *, holder: str, source: str) -> None:
    try:
        from outlook_tracker import record_outlooks

        code_list = [c for c, _ in codes]
        names = {c: n for c, n in codes}
        record_outlooks(code_list, names=names, holder=holder, source=source)
    except Exception as exc:
        print(f"# 预测登记跳过：{exc}", file=sys.stderr)

DAILY_REPORT = os.path.join(SCRIPT_DIR, "..", "Wiki", "数据", "市场状态日报.md")
LINE_CLEAR = 4033.0


def _parse_sh_index() -> float | None:
    if not os.path.isfile(DAILY_REPORT):
        return None
    text = open(DAILY_REPORT, encoding="utf-8").read()
    m = re.search(
        r"\|\s*上证指数\s*\|\s*000001\s*\|\s*([\d,]+\.?\d*)",
        text,
    )
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"上证收盘\s*\*\*([\d,]+\.?\d*)\*\*", text)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def holdings_for_holder(holder: str) -> list[dict[str, str]]:
    return [
        {"name": h["name"], "code": str(h["code"]).zfill(6)}
        for h in HOLDINGS
        if h.get("holder") == holder
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="生成研判总结 Markdown")
    parser.add_argument("--holder", help="持有人（Wilson / 刘岚 / 微）")
    parser.add_argument("--code", action="append", default=[], help="单标的 6 位代码（可重复）")
    parser.add_argument("--name", action="append", default=[], help="与 --code 对应的名称")
    parser.add_argument("--sh-index", type=float, default=None, help="上证点位（默认读市场状态日报）")
    parser.add_argument("--line-clear", type=float, default=LINE_CLEAR)
    args = parser.parse_args()

    sh = args.sh_index if args.sh_index is not None else _parse_sh_index()
    holdings: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []

    if args.holder:
        if args.holder not in HOLDERS:
            print(f"未知持有人 {args.holder!r}；可选：{', '.join(HOLDERS)}", file=sys.stderr)
            return 1
        holdings = holdings_for_holder(args.holder)

    for i, code in enumerate(args.code):
        code = str(code).zfill(6)
        name = args.name[i] if i < len(args.name) else code
        if args.holder:
            if any(h["code"] == code for h in holdings):
                continue
            candidates.append({"name": name, "code": code})
        else:
            candidates.append({"name": name, "code": code})

    if args.code and not args.holder:
        md = build_report_summary_section(
            holdings=[],
            candidates=candidates,
            sh_index=sh,
            line_clear=args.line_clear,
        )
        pairs = [(c["code"], c.get("name", c["code"])) for c in candidates]
        print(md)
        _record_codes(pairs, holder="", source="analysis_report")
        return 0
    elif args.holder:
        md = build_report_summary_section(
            holdings=holdings,
            candidates=candidates or None,
            sh_index=sh,
            line_clear=args.line_clear,
        )
        pairs = [(h["code"], h.get("name", h["code"])) for h in holdings]
        if candidates:
            pairs.extend((c["code"], c.get("name", c["code"])) for c in candidates)
        print(md)
        _record_codes(pairs, holder=args.holder, source="sug")
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
