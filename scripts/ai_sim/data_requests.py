"""处理 Agent data_requests：启用/禁用 registry 指标，未注册写入待扩展清单。"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

from ai_sim.config import ROOT
from ai_sim.supplement_registry import load_registry
from ai_sim.supplement_state import PENDING_PATH, append_history, load_state, save_state

_VALID_ACTIONS = frozenset({"enable", "disable", "request"})
_VALID_PRIORITY = frozenset({"high", "medium", "low"})


def _ensure_pending_file() -> None:
    if os.path.isfile(PENDING_PATH):
        return
    os.makedirs(os.path.dirname(PENDING_PATH), exist_ok=True)
    header = (
        "# 待扩展指标\n\n"
        "> Agent `data_requests` 中 **未在 supplement_registry.yaml 注册** 的指标请求。\n"
        "> 维护者审阅后可加入 registry 并实现 fetcher。\n\n"
        "---\n\n"
    )
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        f.write(header)


def _append_pending(metric: str, reason: str, priority: str, *, tick: str) -> None:
    _ensure_pending_file()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = (
        f"## {metric} · {stamp}\n\n"
        f"- **优先级**：{priority}\n"
        f"- **tick**：{tick}\n"
        f"- **原因**：{reason.strip() or '—'}\n"
        f"- **状态**：待 registry 注册\n\n"
    )
    with open(PENDING_PATH, "a", encoding="utf-8") as f:
        f.write(block)


def _normalize_requests(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        metric = str(item.get("metric") or "").strip()
        if not metric or not re.match(r"^[a-z][a-z0-9_]{0,63}$", metric):
            continue
        action = str(item.get("action") or "request").strip().lower()
        if action not in _VALID_ACTIONS:
            action = "request"
        priority = str(item.get("priority") or "medium").strip().lower()
        if priority not in _VALID_PRIORITY:
            priority = "medium"
        reason = str(item.get("reason") or "").strip()
        out.append({"metric": metric, "action": action, "reason": reason, "priority": priority})
    return out


def process_data_requests(
    raw_requests: Any,
    *,
    tick_label: str = "",
    phase: str = "",
) -> dict[str, Any]:
    """
    处理 Agent data_requests。
    返回 applied / disabled / pending / rejected 供日志写入。
    """
    reg = load_registry()
    state = load_state()
    enabled = set(state["enabled"])
    applied: list[dict[str, str]] = []
    disabled: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    rejected: list[dict[str, str]] = []

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    for req in _normalize_requests(raw_requests):
        metric = req["metric"]
        action = req["action"]
        reason = req["reason"]
        priority = req["priority"]

        if metric not in reg:
            pending.append(req)
            _append_pending(metric, reason, priority, tick=tick_label)
            append_history(
                {
                    "at": stamp,
                    "tick": tick_label,
                    "phase": phase,
                    "metric": metric,
                    "action": "request",
                    "priority": priority,
                    "reason": reason,
                    "result": "pending_registry",
                }
            )
            continue

        spec = reg[metric]
        if spec.get("always_on") and action == "disable":
            rejected.append({**req, "error": "always_on 不可禁用"})
            continue

        if action == "enable":
            if metric not in enabled:
                enabled.add(metric)
                applied.append(req)
                append_history(
                    {
                        "at": stamp,
                        "tick": tick_label,
                        "phase": phase,
                        "metric": metric,
                        "action": "enable",
                        "priority": priority,
                        "reason": reason,
                        "result": "active_next_tick",
                    }
                )
            else:
                rejected.append({**req, "error": "已启用"})
        elif action == "disable":
            if metric in enabled:
                enabled.discard(metric)
                disabled.append(req)
                append_history(
                    {
                        "at": stamp,
                        "tick": tick_label,
                        "phase": phase,
                        "metric": metric,
                        "action": "disable",
                        "priority": priority,
                        "reason": reason,
                        "result": "disabled_next_tick",
                    }
                )
            else:
                rejected.append({**req, "error": "未启用"})
        elif action == "request":
            pending.append(req)
            _append_pending(metric, reason, priority, tick=tick_label)

    for mid, spec in reg.items():
        if spec.get("always_on"):
            enabled.add(mid)

    state["enabled"] = sorted(enabled)
    save_state(state)

    return {
        "applied": applied,
        "disabled": disabled,
        "pending": pending,
        "rejected": rejected,
        "enabled_now": sorted(enabled),
    }


def format_data_extension_block(result: dict[str, Any] | None) -> list[str]:
    """模拟交易日志：自我扩展调整说明。"""
    if not result:
        return []
    applied = result.get("applied") or []
    disabled = result.get("disabled") or []
    pending = result.get("pending") or []
    rejected = result.get("rejected") or []
    if not (applied or disabled or pending or rejected):
        return []

    lines = ["### 数据扩展（Agent data_requests）", ""]
    reg = load_registry()

    if applied:
        lines.append("#### 已启用（下一 tick 起采集）")
        lines.append("")
        for r in applied:
            label = (reg.get(r["metric"]) or {}).get("label", r["metric"])
            lines.append(f"- **`{r['metric']}`**（{label}）| 优先级 {r['priority']}")
            if r.get("reason"):
                lines.append(f"  - **原因**：{r['reason']}")
        lines.append("")

    if disabled:
        lines.append("#### 已禁用（下一 tick 起停止）")
        lines.append("")
        for r in disabled:
            label = (reg.get(r["metric"]) or {}).get("label", r["metric"])
            lines.append(f"- **`{r['metric']}`**（{label}）")
            if r.get("reason"):
                lines.append(f"  - **原因**：{r['reason']}")
        lines.append("")

    if pending:
        lines.append("#### 待 registry 注册（已写入 [[待扩展指标]]）")
        lines.append("")
        for r in pending:
            lines.append(f"- **`{r['metric']}`** | 优先级 {r['priority']}")
            if r.get("reason"):
                lines.append(f"  - **原因**：{r['reason']}")
        lines.append("")

    if rejected:
        lines.append("#### 未采纳")
        lines.append("")
        for r in rejected:
            err = r.get("error", "")
            act = r.get("action", "")
            suffix = f" — {err}" if err else ""
            lines.append(f"- `{r['metric']}` ({act}){suffix}")
        lines.append("")

    enabled = result.get("enabled_now") or []
    if enabled:
        lines.append(f"> **当前启用指标**：{', '.join(f'`{m}`' for m in enabled)}")
        lines.append("")

    return lines
