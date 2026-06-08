"""市场历史摘要 JSON（近 N 日指数收盘/成交额/北向）— daily + tick 收盘后追加。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "Wiki" / "数据" / "市场历史摘要.json"
MAX_DAYS = 30

TRACK_INDEX_CODES = ("000001", "399001", "399006")


def _load() -> dict[str, Any]:
    if not HISTORY_PATH.is_file():
        return {"version": 1, "updated": "", "daily": []}
    try:
        raw = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("daily"), list):
            return raw
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "updated": "", "daily": []}


def _save(data: dict[str, Any]) -> None:
    data["updated"] = datetime.now().isoformat(timespec="seconds")
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_daily_snapshot(
    *,
    date: str,
    indices: dict[str, dict[str, Any]],
    northbound: dict[str, Any] | None = None,
    source: str = "daily_report",
) -> None:
    """按日期 upsert 一条日快照。"""
    data = _load()
    daily: list[dict] = data["daily"]
    row = {
        "date": date,
        "indices": indices,
        "northbound": northbound or {},
        "source": source,
    }
    daily = [d for d in daily if d.get("date") != date]
    daily.append(row)
    daily.sort(key=lambda x: x.get("date", ""))
    data["daily"] = daily[-MAX_DAYS:]
    _save(data)


def load_daily_history(*, days: int = MAX_DAYS) -> list[dict[str, Any]]:
    data = _load()
    daily = data.get("daily") or []
    return daily[-days:]


def history_path() -> str:
    return str(HISTORY_PATH)
