"""AI 模拟盘补充指标启用状态（Agent data_requests 写入）。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from ai_sim.config import ROOT
from ai_sim.supplement_registry import load_registry

STATE_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟盘补充指标.json")
PENDING_PATH = os.path.join(ROOT, "Wiki", "数据", "待扩展指标.md")


def _defaults_enabled() -> set[str]:
    reg = load_registry()
    return {mid for mid, spec in reg.items() if spec.get("default") or spec.get("always_on")}


def load_state() -> dict[str, Any]:
    if not os.path.isfile(STATE_PATH):
        return {"enabled": sorted(_defaults_enabled()), "history": []}
    try:
        raw = json.loads(open(STATE_PATH, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {"enabled": sorted(_defaults_enabled()), "history": []}
    enabled = raw.get("enabled")
    if not isinstance(enabled, list):
        enabled = sorted(_defaults_enabled())
    reg = load_registry()
    base = set(enabled)
    for mid, spec in reg.items():
        if spec.get("always_on"):
            base.add(mid)
    return {"enabled": sorted(base), "history": raw.get("history") or []}


def enabled_metrics() -> set[str]:
    return set(load_state()["enabled"])


def save_state(state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def append_history(entry: dict[str, Any]) -> None:
    state = load_state()
    hist = state.setdefault("history", [])
    hist.append(entry)
    if len(hist) > 200:
        state["history"] = hist[-200:]
    save_state(state)
