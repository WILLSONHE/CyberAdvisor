"""当日 tick 序列中的上证走势摘要（辅助 Agent；修复判断以中长期上下文为主）。"""
from __future__ import annotations

import json
import os
from datetime import datetime

from ai_sim.config import TICK_ROOT


def _sh_from_tick_data(data: dict) -> dict | None:
    for q in data.get("indices", []):
        if q.get("code") == "000001" or q.get("name") == "上证指数":
            close = float(q.get("close") or 0)
            if close <= 0:
                return None
            return {
                "close": close,
                "low": float(q.get("low") or close),
                "high": float(q.get("high") or close),
                "open": float(q.get("open") or close),
                "change_pct": q.get("change_pct"),
            }
    return None


def session_index_stats(tick_path: str) -> dict:
    """读取当日已采集 tick，返回上证日内高低与 tick 序列。"""
    day = datetime.now().strftime("%Y-%m-%d")
    if tick_path:
        parts = tick_path.replace("\\", "/").split("/")
        for i, p in enumerate(parts):
            if len(p) == 10 and p[4] == "-" and p[7] == "-":
                day = p
                break
    day_dir = os.path.join(TICK_ROOT, day)
    ticks: list[dict] = []
    if os.path.isdir(day_dir):
        for name in sorted(f for f in os.listdir(day_dir) if f.endswith(".json")):
            path = os.path.join(day_dir, name)
            try:
                data = json.loads(open(path, encoding="utf-8").read())
            except (OSError, json.JSONDecodeError):
                continue
            sh = _sh_from_tick_data(data)
            if not sh:
                continue
            label = name.replace(".json", "")
            ticks.append(
                {
                    "tick": label,
                    "close": sh["close"],
                    "low": sh["low"],
                    "high": sh["high"],
                }
            )
    if not ticks:
        if tick_path and os.path.isfile(tick_path):
            try:
                data = json.loads(open(tick_path, encoding="utf-8").read())
                sh = _sh_from_tick_data(data)
                if sh:
                    label = os.path.basename(tick_path).replace(".json", "")
                    ticks = [
                        {
                            "tick": label,
                            "close": sh["close"],
                            "low": sh["low"],
                            "high": sh["high"],
                        }
                    ]
            except (OSError, json.JSONDecodeError):
                pass
    if not ticks:
        return {"day": day, "ticks": [], "session_low": None, "session_high": None, "current": None}

    lows = [t["low"] for t in ticks]
    highs = [t["high"] for t in ticks]
    current = ticks[-1]["close"]
    return {
        "day": day,
        "ticks": ticks,
        "session_low": min(lows),
        "session_high": max(highs),
        "current": current,
    }


def format_session_for_prompt(stats: dict) -> str:
    if not stats.get("ticks"):
        return "（当日尚无 tick 序列）"
    lines = [
        f"- 日期：{stats['day']}",
        f"- 日内低/高/现价：{stats['session_low']:.2f} / {stats['session_high']:.2f} / {stats['current']:.2f}",
        "- 各 tick 上证：",
    ]
    for t in stats["ticks"]:
        hh, mm = t["tick"][:2], t["tick"][2:]
        lines.append(f"  - {hh}:{mm} 收 {t['close']:.2f}（低 {t['low']:.2f} 高 {t['high']:.2f}）")
    return "\n".join(lines)


def near_session_low(sh_close: float | None, stats: dict, *, tolerance_pct: float = 0.3) -> bool:
    """现价是否处于日内低点附近（默认 ±0.3%）。"""
    low = stats.get("session_low")
    if sh_close is None or low is None or low <= 0:
        return False
    return sh_close <= low * (1 + tolerance_pct / 100)
