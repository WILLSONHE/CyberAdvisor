#!/usr/bin/env python3
"""
Wiki 轻量查询 CLI（与飞书 Bot 共用逻辑）。

用法:
  python wiki_cli.py trk 寒武纪
  python wiki_cli.py chk
  python wiki_cli.py qry 博主怎么看存储
"""
from __future__ import annotations

import argparse
import sys

from wiki import run_chk, search_wiki, track_stock


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description="Wiki trk/chk/qry")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_trk = sub.add_parser("trk", help="标的追踪")
    p_trk.add_argument("name", help="标的名称")

    sub.add_parser("chk", help="Wiki 体检")

    p_qry = sub.add_parser("qry", help="Wiki 关键词检索")
    p_qry.add_argument("question", help="问题或关键词")

    args = ap.parse_args()
    if args.cmd == "trk":
        print(track_stock(args.name))
    elif args.cmd == "chk":
        print(run_chk())
    elif args.cmd == "qry":
        print(search_wiki(args.question))
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
