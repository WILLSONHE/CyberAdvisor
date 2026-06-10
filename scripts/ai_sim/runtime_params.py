"""AI 模拟盘运行时参数：config 默认值 + Agent 可调的 override JSON。"""
from __future__ import annotations

import json
import os
from typing import Any

from ai_sim.config import ROOT

OVERRIDE_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟盘参数.override.json")

# Agent 可调参数（执行层数值边界；指数/布林门禁不在此列）
PARAM_SCHEMA: dict[str, dict[str, Any]] = {
    "STOP_LOSS_PCT": {"type": float, "min": -20.0, "max": -1.0},
    "TAKE_PROFIT_PCT": {"type": float, "min": 5.0, "max": 50.0},
    "EQUITY_TARGET_NORMAL": {"type": float, "min": 0.0, "max": 0.9},
    "BUY_MIN_GAP": {"type": float, "min": 0.02, "max": 0.2},
    "MAX_BUYS_PER_TICK": {"type": int, "min": 0, "max": 3},
    "REBALANCE_MIN_HOLD_DAYS": {"type": int, "min": 0, "max": 5},
    "MIN_TRADE_YUAN": {"type": float, "min": 30_000.0, "max": 500_000.0},
}

# 已废弃：旧版软约束键，override 中若存在则忽略
_DEPRECATED_KEYS = frozenset({"NO_BUY_BELOW_CLEAR", "EQUITY_TARGET_BELOW_CLEAR"})

_overrides: dict[str, Any] = {}


def reload() -> None:
    global _overrides
    if not os.path.isfile(OVERRIDE_PATH):
        _overrides = {}
        return
    try:
        raw = json.loads(open(OVERRIDE_PATH, encoding="utf-8").read())
        _overrides = raw if isinstance(raw, dict) else {}
    except Exception:
        _overrides = {}


def get(name: str) -> Any:
    if not _overrides and os.path.isfile(OVERRIDE_PATH):
        reload()
    if name in _overrides:
        return _overrides[name]
    from ai_sim import config

    return getattr(config, name)


def snapshot() -> dict[str, Any]:
    reload()
    out: dict[str, Any] = {}
    for key in PARAM_SCHEMA:
        val = get(key)
        if key in _overrides:
            out[key] = val
    return out


def defaults_for_agent() -> dict[str, Any]:
    from ai_sim import config

    return {k: getattr(config, k) for k in PARAM_SCHEMA}


def effective_all() -> dict[str, Any]:
    return {k: get(k) for k in PARAM_SCHEMA}


def _coerce(key: str, val: Any) -> Any:
    spec = PARAM_SCHEMA[key]
    typ = spec["type"]
    if typ is bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("1", "true", "yes", "y")
        return bool(val)
    if typ is int:
        val = int(round(float(val)))
    else:
        val = float(val)
    if "min" in spec and val < spec["min"]:
        val = spec["min"]
    if "max" in spec and val > spec["max"]:
        val = spec["max"]
    return val


def apply_patch(patch: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """校验并写入 override；返回 (applied, warnings)。"""
    reload()
    applied: dict[str, Any] = {}
    warnings: list[str] = []
    for key, val in patch.items():
        if key in _DEPRECATED_KEYS:
            warnings.append(f"已废弃参数 {key}，请用 buy_permission + EQUITY_TARGET_NORMAL（Wiki 判断含 4033 等）")
            continue
        if key not in PARAM_SCHEMA:
            warnings.append(f"忽略未授权参数 {key}")
            continue
        try:
            applied[key] = _coerce(key, val)
        except (TypeError, ValueError):
            warnings.append(f"参数 {key} 无法解析，已跳过")
    if not applied and not warnings:
        return {}, warnings
    merged = {**_overrides, **applied}
    os.makedirs(os.path.dirname(OVERRIDE_PATH), exist_ok=True)
    with open(OVERRIDE_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    reload()
    return applied, warnings


def reset_overrides() -> None:
    global _overrides
    _overrides = {}
    if os.path.isfile(OVERRIDE_PATH):
        os.remove(OVERRIDE_PATH)
