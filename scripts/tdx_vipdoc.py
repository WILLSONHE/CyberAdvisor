"""读取通达信 vipdoc 本地日 K（.day），供 realized volatility 与 get_kline 兜底。"""
from __future__ import annotations

import os
import struct
from typing import Any

import pandas as pd

DEFAULT_VIPDOC = os.environ.get("TDX_VIPDOC", r"C:\new_tdx64\vipdoc")
DEFAULT_VIPDOC_QH = os.environ.get("TDX_VIPDOC_QH", r"C:\new_tdxqh\vipdoc")


def vipdoc_root() -> str:
    return os.environ.get("TDX_VIPDOC", DEFAULT_VIPDOC)


def vipdoc_root_qh() -> str:
    """期货/期权 vipdoc 根目录（当前流水线未接入，预留）。"""
    return os.environ.get("TDX_VIPDOC_QH", DEFAULT_VIPDOC_QH)


_SH_INDEX_CODES = frozenset({"000001", "000016", "000300", "000688", "000852", "000905"})


def _day_path_candidates(code: str, root: str | None = None) -> list[str]:
    """个股优先 sz/bj/sh；同名指数代码（如 sh000001）在 sz 缺失时再试 sh。"""
    code = str(code).zfill(6)
    root = root or vipdoc_root()
    tries: list[tuple[str, str]] = []
    if code.startswith(("6", "9")):
        tries = [("sh", "sh")]
    elif code.startswith(("4", "8")):
        tries = [("bj", "bj")]
    else:
        tries = [("sz", "sz")]
        if code in _SH_INDEX_CODES:
            tries.append(("sh", "sh"))
    out: list[str] = []
    for sub, prefix in tries:
        path = os.path.join(root, sub, "lday", f"{prefix}{code}.day")
        if os.path.isfile(path):
            out.append(path)
    return out


def _day_path(code: str, root: str | None = None) -> str | None:
    paths = _day_path_candidates(code, root)
    return paths[0] if paths else None


def read_daily_bars(code: str, *, limit: int = 120, root: str | None = None) -> pd.DataFrame | None:
    path = _day_path(code, root)
    if not path:
        return None
    rows: list[dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(32)
                if len(b) < 32:
                    break
                date_i, o, h, l, c, _amt, vol, _ = struct.unpack("<IIIIIfII", b)
                if not date_i:
                    continue
                ds = str(date_i)
                rows.append(
                    {
                        "datetime": f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}",
                        "open": o / 100.0,
                        "high": h / 100.0,
                        "low": l / 100.0,
                        "close": c / 100.0,
                        "vol": vol,
                    }
                )
    except OSError:
        return None
    if len(rows) < 25:
        return None
    df = pd.DataFrame(rows)
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    return df


def realized_daily_sigma_pct(code: str, *, lookback: int = 20, root: str | None = None) -> float | None:
    """近 N 日收盘涨跌幅标准差（%）。"""
    df = read_daily_bars(code, limit=lookback + 5, root=root)
    if df is None or len(df) < lookback + 1:
        return None
    closes = df["close"].astype(float)
    rets = closes.pct_change().dropna().tail(lookback) * 100.0
    if len(rets) < 5:
        return None
    return float(rets.std(ddof=0))


def daily_vol_stats(code: str, *, lookback: int = 20, root: str | None = None) -> dict[str, Any] | None:
    df = read_daily_bars(code, limit=lookback + 5, root=root)
    if df is None or len(df) < lookback + 1:
        return None
    closes = df["close"].astype(float)
    rets = closes.pct_change().dropna().tail(lookback) * 100.0
    if rets.empty:
        return None
    return {
        "lookback": len(rets),
        "stdev_pct": round(float(rets.std(ddof=0)), 2),
        "mean_abs_pct": round(float(rets.abs().mean()), 2),
        "max_abs_pct": round(float(rets.abs().max()), 2),
        "source": "vipdoc",
        "path": _day_path(code, root),
    }
