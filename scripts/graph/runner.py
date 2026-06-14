#!/usr/bin/env python3
"""Graph 管线 CLI（默认 dry-run，不调用 Cursor）。"""
from __future__ import annotations

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
if os.path.join(SCRIPT_DIR, "..") not in sys.path:
    sys.path.insert(0, os.path.join(SCRIPT_DIR, ".."))

from bilibili.env import ROOT as PROJ_ROOT, apply_config_to_environ  # noqa: E402
from graph.llm import graph_pipeline_enabled  # noqa: E402
from graph.orchestrator import run_qry_pipeline, run_sug_pipeline  # noqa: E402
from graph.progress import list_recent_progress  # noqa: E402


def main() -> int:
    apply_config_to_environ()
    ap = argparse.ArgumentParser(description="CyberAdvisor Graph 编排（非 LangGraph）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sug = sub.add_parser("sug", help="持有人 sug 管线")
    sug.add_argument("holder")
    sug.add_argument("session", nargs="?", choices=("早盘", "午盘"))
    sug.add_argument("--live", action="store_true", help="实际调用 Cursor（须 GRAPH_PIPELINE_ENABLED=1）")
    sug.add_argument("--dry-run", action="store_true", default=False)
    sug.add_argument("--stdout", action="store_true")
    sug.add_argument("--json", action="store_true")

    qry = sub.add_parser("qry", help="深度 qry 管线")
    qry.add_argument("question")
    qry.add_argument("--live", action="store_true")
    qry.add_argument("--dry-run", action="store_true", default=False)
    qry.add_argument("--stdout", action="store_true")

    sub.add_parser("status", help="Graph 开关与最近进度")

    args = ap.parse_args()

    if args.cmd == "status":
        print(f"GRAPH_PIPELINE_ENABLED={graph_pipeline_enabled()}")
        for p in list_recent_progress(5):
            print(
                f"  {p.get('analysis_id')} stage={p.get('current_label')} "
                f"budget={p.get('budget', {}).get('pct')}% dry={p.get('dry_run')}"
            )
        return 0

    dry = args.dry_run or not args.live
    if args.live and not graph_pipeline_enabled():
        print(
            "GRAPH_PIPELINE_ENABLED 未开启（默认 0）。"
            "开发完成但未启用；设置 GRAPH_PIPELINE_ENABLED=1 后再 --live。",
            file=sys.stderr,
        )
        return 2

    if args.cmd == "sug":
        state = run_sug_pipeline(
            args.holder,
            session=args.session,
            dry_run=dry,
            force_live=args.live,
        )
    else:
        state = run_qry_pipeline(args.question, dry_run=dry, force_live=args.live)

    out_dir = os.path.join(PROJ_ROOT, "Wiki", "数据", "graph_runs")
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, f"{state.analysis_id}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(state.final_markdown or "")
    print(f"wrote {md_path}")
    print(
        f"analysis_id={state.analysis_id} spent=${state.budget.spent_usd:.2f} "
        f"calls={state.budget.llm_calls} dry_run={state.dry_run}"
    )

    if args.stdout:
        print("\n---\n")
        print(state.final_markdown or "")

    if getattr(args, "json", False):
        print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2)[:12000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
