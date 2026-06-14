"""多级别 K 线：日 K vipdoc → Tushare qfq → mootdx；分钟 vipdoc → mootdx。"""
from __future__ import annotations

from typing import Any

import pandas as pd

# mootdx category
PERIOD_MAP: dict[str, tuple[int, str, int]] = {
    "1m": (7, "mootdx", 800),
    "5m": (0, "mootdx", 800),
    "30m": (2, "mootdx", 400),
    "60m": (3, "mootdx", 400),
    "day": (4, "mootdx", 800),
}

PERIOD_LABEL = {
    "1m": "1分钟",
    "5m": "5分钟",
    "30m": "30分钟",
    "60m": "60分钟",
    "day": "日线",
}


def _norm_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None
    out = df.copy()
    if "datetime" in out.columns:
        out["time"] = out["datetime"].astype(str)
    elif "date" in out.columns:
        out["time"] = out["date"].astype(str)
    elif "time" not in out.columns:
        return None
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            return None
        out[col] = out[col].astype(float)
    if "volume" not in out.columns and "vol" in out.columns:
        out["volume"] = out["vol"].astype(float)
    elif "volume" not in out.columns:
        out["volume"] = 0.0
    return out.reset_index(drop=True)


def _market_for(code: str) -> int:
    code = str(code).zfill(6)
    if code.startswith(("6", "9")) or code in (
        "000001",
        "000300",
        "000016",
        "000688",
        "000905",
        "000852",
    ):
        return 1
    return 0


def _from_mootdx(code: str, *, category: int, limit: int) -> pd.DataFrame | None:
    try:
        from bollinger_utils import get_quotes_client

        client = get_quotes_client()
        if client is None:
            return None
        k = client.bars(symbol=str(code).zfill(6), market=_market_for(code), category=category, offset=limit)
        return _norm_df(k)
    except Exception:
        return None


def _from_local(code: str, *, period: str, limit: int) -> pd.DataFrame | None:
    try:
        if period == "day":
            from daily_bars import get_daily_bars

            df = get_daily_bars(code, limit=limit, min_bars=30)
            return _norm_df(df)
        if period in ("1m", "5m"):
            from tdx_market_data import read_minute_bars

            klt = 1 if period == "1m" else 5
            df = read_minute_bars(code, klt=klt, limit=limit)
            if df is not None and not df.empty:
                df = df.copy()
                df["source"] = f"vipdoc_{period}"
            return _norm_df(df)
    except Exception:
        pass
    return None


def get_bars(code: str, period: str = "day", *, limit: int | None = None) -> dict[str, Any]:
    """返回 {ok, period, bars, source, error}。"""
    period = period if period in PERIOD_MAP else "day"
    cat, fallback, default_limit = PERIOD_MAP[period]
    limit = limit or default_limit
    df = _from_local(code, period=period, limit=limit)
    source = str(df.iloc[-1].get("source", "vipdoc")) if df is not None and not df.empty else ""
    if period != "day" and (df is None or len(df) < 30):
        df = _from_mootdx(code, category=cat, limit=limit)
        source = "mootdx"
    if df is None or len(df) < 30:
        return {
            "ok": False,
            "period": period,
            "bars": None,
            "source": "",
            "error": f"{PERIOD_LABEL[period]} K 线不足（需≥30根）",
        }
    return {
        "ok": True,
        "period": period,
        "bars": df,
        "source": source,
        "bar_count": len(df),
        "last_time": str(df.iloc[-1]["time"]),
        "last_close": float(df.iloc[-1]["close"]),
    }
