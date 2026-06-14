"""LLM 路由：按配置选择 stub / cursor。"""
from __future__ import annotations

import os

from graph.llm.cursor import CursorLLM
from graph.llm.stub import StubLLM


def graph_pipeline_enabled() -> bool:
    v = (os.environ.get("GRAPH_PIPELINE_ENABLED") or "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def resolve_llm(*, dry_run: bool = False, force_live: bool = False):
    if dry_run or not force_live:
        if not graph_pipeline_enabled():
            return StubLLM()
    if dry_run:
        return StubLLM()
    key = (os.environ.get("CURSOR_API_KEY") or "").strip()
    if not key:
        return StubLLM()
    return CursorLLM()
