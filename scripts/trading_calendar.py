"""A 股交易日历：Tushare trade_cal（SSE）+ 本地缓存；无 token 时退回 Mon–Fri。"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta
from typing import Iterable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CACHE_PATH = os.path.join(ROOT, "Wiki", "数据", "trade_cal_sse.json")
_EXCHANGE = "SSE"


def _weekday_fallback(d: date) -> bool:
    return d.weekday() < 5


def _ensure_env() -> None:
    try:
        from bilibili.env import apply_config_to_environ

        apply_config_to_environ()
    except Exception:
        pass


def _load_cache() -> dict[str, dict[str, str]]:
    if not os.path.isfile(CACHE_PATH):
        return {"meta": {}, "days": {}}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"meta": {}, "days": {}}
    data.setdefault("meta", {})
    data.setdefault("days", {})
    return data


def _save_cache(data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _fetch_range(start: date, end: date) -> dict[str, int]:
    """cal_date(YYYYMMDD) -> is_open (0/1)."""
    _ensure_env()
    try:
        from tushare_daily import _get_pro
    except ImportError:
        return {}
    pro = _get_pro()
    if pro is None:
        return {}
    try:
        df = pro.trade_cal(
            exchange=_EXCHANGE,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            fields="cal_date,is_open,pretrade_date",
        )
    except Exception:
        return {}
    if df is None or df.empty:
        return {}
    out: dict[str, int] = {}
    for _, row in df.iterrows():
        cal = str(row.get("cal_date") or "")
        if len(cal) == 8:
            out[cal] = int(row.get("is_open") or 0)
    return out


def ensure_calendar(
    *,
    start: date | None = None,
    end: date | None = None,
    pad_days: int = 30,
) -> None:
    """拉取并合并 Tushare 交易日历到本地缓存。"""
    today = date.today()
    start = start or today - timedelta(days=365 + pad_days)
    end = end or today + timedelta(days=pad_days)
    fetched = _fetch_range(start, end)
    if not fetched:
        return
    cache = _load_cache()
    days: dict[str, int] = cache.setdefault("days", {})
    days.update({k: v for k, v in fetched.items()})
    cache["meta"] = {
        "exchange": _EXCHANGE,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "start": min(days.keys()) if days else "",
        "end": max(days.keys()) if days else "",
        "source": "tushare",
    }
    _save_cache(cache)


def _day_key(d: date) -> str:
    return d.strftime("%Y%m%d")


def _is_open_from_cache(d: date) -> int | None:
    days = _load_cache().get("days") or {}
    raw = days.get(_day_key(d))
    if raw is None:
        return None
    return int(raw)


def is_trading_day(d: date | None = None, *, auto_fetch: bool = True) -> bool:
    d = d or date.today()
    cached = _is_open_from_cache(d)
    if cached is not None:
        return cached == 1
    if auto_fetch:
        ensure_calendar(start=d - timedelta(days=7), end=d + timedelta(days=7))
        cached = _is_open_from_cache(d)
        if cached is not None:
            return cached == 1
    return _weekday_fallback(d)


def _step_trading_days(start: date, n: int, *, direction: int) -> date:
    if n <= 0:
        return start
    d = start
    moved = 0
    guard = 0
    while moved < n:
        d += timedelta(days=direction)
        guard += 1
        if guard > 366 * 3:
            raise RuntimeError(f"交易日历步进超限: start={start} n={n}")
        if is_trading_day(d):
            moved += 1
    return d


def add_trading_days(start: date, n: int) -> date:
    """自 start 起第 n 个交易日（不含 start）。"""
    return _step_trading_days(start, n, direction=1)


def subtract_trading_days(start: date, n: int) -> date:
    """自 start 往前第 n 个交易日。"""
    return _step_trading_days(start, n, direction=-1)


def next_trading_day(start: date | None = None) -> date:
    return add_trading_days(start or date.today(), 1)


def prev_trading_day(start: date | None = None) -> date:
    return subtract_trading_days(start or date.today(), 1)


def latest_trading_day_on_or_before(d: date) -> date:
    cur = d
    for _ in range(366):
        if is_trading_day(cur):
            return cur
        cur -= timedelta(days=1)
    return d


def filename_trading_date(d: date) -> date:
    """文件名/归档用日期：非交易日取之前最近开盘日。"""
    if is_trading_day(d):
        return d
    return latest_trading_day_on_or_before(d - timedelta(days=1))


def format_filename_date(d: date, *, short: bool = False) -> str:
    """YYYY-MM-DD 或 yy-mm-dd（文件名前缀）。"""
    if short:
        return d.strftime("%y-%m-%d")
    return d.isoformat()


def expected_latest_bar_date(*, as_of: date | None = None, now: datetime | None = None) -> date:
    """
    收盘后流水线期望的最新 A 股日 K 日期：
    - 非交易日 → 上一交易日
    - 交易日 16:00 前 → 上一交易日
    - 否则 → 当日（若当日为交易日）
    """
    d = as_of or date.today()
    now = now or datetime.now()
    if not is_trading_day(d):
        return latest_trading_day_on_or_before(d - timedelta(days=1))
    if now.date() == d and now.hour < 16:
        return prev_trading_day(d)
    return d


def registration_trading_date(*, as_of: date | None = None, now: datetime | None = None) -> date:
    """登记/归档默认交易日（等同 expected_latest_bar_date）。"""
    return expected_latest_bar_date(as_of=as_of, now=now)


def trading_days_between(start: date, end: date, *, inclusive: bool = True) -> list[date]:
    if end < start:
        start, end = end, start
    ensure_calendar(start=start, end=end)
    out: list[date] = []
    cur = start
    while cur <= end:
        if is_trading_day(cur, auto_fetch=False) or (
            is_trading_day(cur) and _is_open_from_cache(cur) is None
        ):
            if is_trading_day(cur):
                out.append(cur)
        cur += timedelta(days=1)
    if not inclusive and out:
        if out[0] == start:
            out = out[1:]
        if out and out[-1] == end:
            out = out[:-1]
    return out


def iter_open_dates(keys: Iterable[str]) -> list[date]:
    return sorted(date(int(k[:4]), int(k[4:6]), int(k[6:8])) for k in keys if len(k) == 8)


def status() -> dict:
    cache = _load_cache()
    meta = cache.get("meta") or {}
    days = cache.get("days") or {}
    today = date.today()
    return {
        "cache_path": CACHE_PATH,
        "days_cached": len(days),
        "meta": meta,
        "today": str(today),
        "today_is_trading": is_trading_day(today),
        "expected_bar": str(expected_latest_bar_date()),
        "tushare": bool(meta.get("source") == "tushare"),
    }


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="A股交易日历（Tushare SSE）")
    ap.add_argument("--refresh", action="store_true", help="拉取并更新缓存")
    ap.add_argument("--status", action="store_true", help="打印状态")
    args = ap.parse_args()
    if args.refresh or not args.status:
        ensure_calendar()
    print(json.dumps(status(), ensure_ascii=False, indent=2))
