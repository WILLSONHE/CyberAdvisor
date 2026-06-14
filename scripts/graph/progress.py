"""Graph 进度 JSON（Streamlit / 飞书可读）。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from bilibili.env import ROOT
from graph.stages import PIPELINE_STAGES, STAGE_LABELS
from graph.state import GraphState

PROGRESS_DIR = os.path.join(ROOT, "Wiki", "数据", "graph_progress")


def ensure_progress_dir() -> None:
    os.makedirs(PROGRESS_DIR, exist_ok=True)


def progress_path(analysis_id: str) -> str:
    ensure_progress_dir()
    safe = analysis_id.replace("/", "_")
    return os.path.join(PROGRESS_DIR, f"{safe}.json")


def write_progress(state: GraphState, *, note: str = "") -> str:
    path = progress_path(state.analysis_id)
    stages = []
    for sid, label in PIPELINE_STAGES:
        stages.append(
            {
                "id": sid,
                "label": label,
                "done": sid in state.stages_done,
                "current": sid == state.current_stage,
            }
        )
    payload: dict[str, Any] = {
        "analysis_id": state.analysis_id,
        "task": state.task,
        "holder": state.holder,
        "session": state.session,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "current_stage": state.current_stage,
        "current_label": STAGE_LABELS.get(state.current_stage, ""),
        "stages": stages,
        "budget": {
            "cap_usd": state.budget.cap_usd,
            "spent_usd": round(state.budget.spent_usd, 4),
            "pct": round(state.budget.pct_used(), 1),
            "llm_calls": state.budget.llm_calls,
            "degraded": state.budget.degraded,
        },
        "dry_run": state.dry_run,
        "errors": state.errors[-5:],
        "note": note,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load_progress(analysis_id: str) -> dict[str, Any] | None:
    path = progress_path(analysis_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def list_recent_progress(limit: int = 20) -> list[dict[str, Any]]:
    ensure_progress_dir()
    files = sorted(
        [f for f in os.listdir(PROGRESS_DIR) if f.endswith(".json")],
        reverse=True,
    )[:limit]
    out: list[dict[str, Any]] = []
    for name in files:
        try:
            with open(os.path.join(PROGRESS_DIR, name), encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, json.JSONDecodeError):
            continue
    return out
