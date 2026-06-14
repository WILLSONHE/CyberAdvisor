"""Tushare 前复权日线：vipdoc 不足或缺最新 bar 时的在线补充（2000 积分 pro_bar qfq）。"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd

# 与 chan/kline._market_for、tdx_market_data 指数口径一致
_INDEX_CODES: dict[str, str] = {
    "000001": "000001.SH",  # 上证指数
    "000016": "000016.SH",
    "000300": "000300.SH",
    "000688": "000688.SH",
    "000905": "000905.SH",
    "000852": "000852.SH",
    "399001": "399001.SZ",
    "399006": "399006.SZ",
}

_pro_api = None
_token_checked = False


def _ensure_env() -> None:
    try:
        from bilibili.env import apply_config_to_environ

        apply_config_to_environ()
    except Exception:
        pass


def token_configured() -> bool:
    _ensure_env()
    return bool((os.environ.get("TUSHARE_TOKEN") or "").strip())


def to_ts_code(code: str) -> tuple[str, str] | None:
    """返回 (ts_code, asset)，asset 为 E(股票) 或 I(指数)。"""
    raw = str(code).strip().upper()
    if "." in raw:
        base, exch = raw.split(".", 1)
        c = base.zfill(6)
        if c in _INDEX_CODES and _INDEX_CODES[c] == raw:
            return raw, "I"
        return raw, "E"
    c = raw.zfill(6) if raw.isdigit() else raw
    if c in _INDEX_CODES:
        return _INDEX_CODES[c], "I"
    if not c.isdigit() or len(c) != 6:
        return None
    if c.startswith(("6", "9")):
        return f"{c}.SH", "E"
    return f"{c}.SZ", "E"


def _get_pro():
    global _pro_api, _token_checked
    if _pro_api is not None:
        return _pro_api
    _ensure_env()
    tok = (os.environ.get("TUSHARE_TOKEN") or "").strip()
    _token_checked = True
    if not tok:
        return None
    try:
        import tushare as ts

        ts.set_token(tok)
        _pro_api = ts.pro_api()
        return _pro_api
    except Exception:
        return None


def _norm_tushare_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    if "trade_date" in out.columns:
        out["datetime"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce").dt.strftime(
            "%Y-%m-%d"
        )
    elif "datetime" not in out.columns:
        return None
    rename = {"vol": "volume"}
    out = out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            return None
        out[col] = out[col].astype(float)
    if "volume" not in out.columns:
        out["volume"] = 0.0
    else:
        out["volume"] = out["volume"].astype(float)
    out["source"] = "tushare_qfq"
    out = out.sort_values("datetime").reset_index(drop=True)
    return out[["datetime", "open", "high", "low", "close", "volume", "source"]]


def fetch_daily_bars(code: str, *, limit: int = 120) -> pd.DataFrame | None:
    """拉取前复权日线（股票 qfq；指数 asset=I）。"""
    mapped = to_ts_code(code)
    pro = _get_pro()
    if mapped is None or pro is None:
        return None
    ts_code, asset = mapped
    end = date.today()
    # 多取一些日历日，保证 limit 根交易日
    start = end - timedelta(days=max(limit * 2, 400))
    start_s = start.strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    try:
        import tushare as ts

        if asset == "I":
            df = ts.pro_bar(ts_code=ts_code, asset="I", start_date=start_s, end_date=end_s)
        else:
            df = ts.pro_bar(ts_code=ts_code, adj="qfq", start_date=start_s, end_date=end_s)
        out = _norm_tushare_df(df)
        if out is None:
            return None
        if limit and len(out) > limit:
            out = out.iloc[-limit:].reset_index(drop=True)
        return out
    except Exception:
        return None


def _bar_date(df: pd.DataFrame | None) -> date | None:
    if df is None or df.empty:
        return None
    raw = str(df.iloc[-1].get("datetime") or df.iloc[-1].get("time", ""))[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _expected_latest_bar(*, as_of: date | None = None) -> date:
    """收盘后流水线期望的最新交易日（简化：跳过周末）。"""
    d = as_of or date.today()
    now = datetime.now()
    if d.weekday() >= 5:
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        return d
    if now.hour < 16:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


def merge_daily_frames(*frames: pd.DataFrame | None) -> pd.DataFrame | None:
    """按 datetime 去重合并，同日期保留先出现的来源（vipdoc 优先）。"""
    parts: list[pd.DataFrame] = []
    for df in frames:
        if df is None or df.empty:
            continue
        d = df.copy()
        if "datetime" not in d.columns and "time" in d.columns:
            d["datetime"] = d["time"].astype(str).str[:10]
        if "datetime" not in d.columns:
            continue
        d["datetime"] = d["datetime"].astype(str).str[:10]
        if "source" not in d.columns:
            d["source"] = "unknown"
        parts.append(d)
    if not parts:
        return None
    merged = pd.concat(parts, ignore_index=True)
    merged = merged.sort_values("datetime").drop_duplicates(subset=["datetime"], keep="first")
    return merged.reset_index(drop=True)


def needs_online_patch(local: pd.DataFrame | None, *, min_bars: int, expect: date | None = None) -> bool:
    if local is None or local.empty:
        return True
    if len(local) < min_bars:
        return True
    last = _bar_date(local)
    if last is None:
        return True
    expect = expect or _expected_latest_bar()
    return last < expect


def resolve_daily_bars(
    code: str,
    *,
    limit: int = 120,
    min_bars: int = 25,
    as_of: date | None = None,
) -> pd.DataFrame | None:
    """
    统一日线：vipdoc 本地 →（不足/缺最新 bar）Tushare qfq → mootdx。
    合并时本地优先，在线源只补缺失日期。
    """
    from tdx_market_data import read_daily_bars as read_vipdoc_daily

    local = read_vipdoc_daily(code, limit=limit)
    expect = _expected_latest_bar(as_of=as_of)

    def _trim(df: pd.DataFrame | None) -> pd.DataFrame | None:
        if df is None or df.empty or as_of is None:
            return df
        out = df[df["datetime"].astype(str).str[:10] <= as_of.isoformat()]
        return out if not out.empty else None

    if local is not None and not local.empty and "source" not in local.columns:
        local = local.copy()
        local["source"] = "vipdoc_day"

    patch = needs_online_patch(local, min_bars=min_bars, expect=expect)
    tushare_df = fetch_daily_bars(code, limit=max(limit, min_bars + 5)) if patch and token_configured() else None

    mootdx_df = None
    merged = merge_daily_frames(local, tushare_df)
    if merged is None or len(merged) < min_bars or needs_online_patch(merged, min_bars=min_bars, expect=expect):
        mootdx_df = _from_mootdx_daily(code, limit=max(limit, min_bars + 5))
        merged = merge_daily_frames(local, tushare_df, mootdx_df)

    if merged is None:
        return None
    merged = _trim(merged)
    if merged is None or len(merged) < min_bars:
        return None
    if limit and len(merged) > limit:
        merged = merged.iloc[-limit:].reset_index(drop=True)
    return merged


def _from_mootdx_daily(code: str, *, limit: int) -> pd.DataFrame | None:
    try:
        from mootdx.quotes import Quotes

        c = str(code).zfill(6)
        if c.startswith(("6", "9")) or c in ("000001", "000300", "000016", "000688", "000905", "000852"):
            market = 1
        else:
            market = 0
        client = Quotes.factory(market="std")
        k = client.bars(symbol=c, market=market, category=4, offset=limit)
        if k is None or k.empty:
            return None
        out = k.copy()
        if "datetime" in out.columns:
            out["datetime"] = out["datetime"].astype(str).str[:10]
        elif "date" in out.columns:
            out["datetime"] = out["date"].astype(str).str[:10]
        out["source"] = "mootdx_day"
        if "volume" not in out.columns and "vol" in out.columns:
            out["volume"] = out["vol"].astype(float)
        return out
    except Exception:
        return None


def status(code: str = "600021") -> dict[str, Any]:
    """CLI 自检：各源最新 bar 与合并结果。"""
    from tdx_market_data import read_daily_bars as read_vipdoc_daily

    local = read_vipdoc_daily(code, limit=5)
    ts_df = fetch_daily_bars(code, limit=5) if token_configured() else None
    moo = _from_mootdx_daily(code, limit=5)
    resolved = resolve_daily_bars(code, limit=120, min_bars=25)
    return {
        "code": code,
        "token": token_configured(),
        "expect": _expected_latest_bar().isoformat(),
        "vipdoc_last": _bar_date(local).isoformat() if _bar_date(local) else None,
        "tushare_last": _bar_date(ts_df).isoformat() if _bar_date(ts_df) else None,
        "mootdx_last": _bar_date(moo).isoformat() if _bar_date(moo) else None,
        "resolved_last": _bar_date(resolved).isoformat() if _bar_date(resolved) else None,
        "resolved_source": str(resolved.iloc[-1]["source"]) if resolved is not None and not resolved.empty else None,
        "resolved_bars": len(resolved) if resolved is not None else 0,
    }


if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser(description="Tushare 日线补充自检")
    p.add_argument("--code", default="600021")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    info = status(args.code)
    print(json.dumps(info, ensure_ascii=False, indent=2) if args.json else info)
