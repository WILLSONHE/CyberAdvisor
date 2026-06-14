"""通达信扩展行情：vipdoc/ds 日 K、minline 1 分钟 K；T0002 仅作符号映射（hq_cache）。"""
from __future__ import annotations

import os
import struct
from datetime import date
from typing import Any

import pandas as pd

from tdx_vipdoc import (
    DEFAULT_VIPDOC,
    _SH_INDEX_CODES,
    _day_path,
    _day_path_candidates,
    read_daily_bars as _read_daily_bars_single,
    vipdoc_root,
)

DEFAULT_T0002 = os.environ.get("TDX_T0002", r"C:\new_tdx64\T0002")

# ds/lday 扩展日线：A 股指数镜像（较 sh/sz lday 常多 1 个交易日）
_DS_DAILY_ALIASES: dict[str, list[str]] = {
    "000001": ["33#000001"],  # 上证指数
    "399001": ["32#399001"],  # 深证成指（若存在）
    "399006": ["32#399006"],
    "000300": ["62#000300"],  # 沪深300
    "000688": ["62#000688"],  # 科创50
    "000905": ["62#000905"],
}

# ds/minline 1 分钟（prefix#code.lc1）
_DS_MINUTE_ALIASES: dict[str, list[str]] = {
    "000300": ["62#000300"],
    "00700": ["31#00700"],
    "AAPL": ["74#AAPL"],
}


def t0002_root() -> str:
    return os.environ.get("TDX_T0002", DEFAULT_T0002)


def _ds_lday_path(alias: str, root: str | None = None) -> str | None:
    root = root or vipdoc_root()
    path = os.path.join(root, "ds", "lday", f"{alias}.day")
    return path if os.path.isfile(path) else None


def _ds_minline_path(alias: str, root: str | None = None) -> str | None:
    root = root or vipdoc_root()
    path = os.path.join(root, "ds", "minline", f"{alias}.lc1")
    return path if os.path.isfile(path) else None


def _a_share_minline_path(code: str, *, klt: int = 1, root: str | None = None) -> str | None:
    """A 股 1 分钟 .lc1 / 5 分钟 .lc5（下载后位于 sh/sz/minline 或 fzline）。"""
    code = str(code).zfill(6)
    root = root or vipdoc_root()
    sub = "sh" if code.startswith(("6", "9")) or code in _SH_INDEX_CODES else "sz"
    if klt == 5:
        for folder, ext in (("fzline", "lc5"), ("minline", "lc5")):
            p = os.path.join(root, sub, folder, f"{sub}{code}.{ext}")
            if os.path.isfile(p):
                return p
        return None
    p = os.path.join(root, sub, "minline", f"{sub}{code}.lc1")
    return p if os.path.isfile(p) else None


def _valid_close(price: float, *, code_hint: str = "") -> bool:
    if price <= 0 or price > 500_000:
        return False
    if code_hint.startswith(("000001", "399")) and not (500 <= price <= 30_000):
        return False
    return True


def _read_day_file(path: str, *, limit: int = 120, code_hint: str = "") -> pd.DataFrame | None:
    rows: list[dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if len(raw) < 32:
        return None
    # 检测 ds 扩展日线：float OHLC（<IfffffII>）
    use_float = "ds" + os.sep + "lday" in path.replace("/", os.sep)
    i = 0
    while i + 32 <= len(raw):
        b = raw[i : i + 32]
        if use_float:
            date_i, o, h, l, c, _amt, vol, _ = struct.unpack("<IfffffII", b)
            if not date_i or not _valid_close(float(c), code_hint=code_hint):
                i += 32
                continue
            rows.append(
                {
                    "datetime": f"{str(date_i)[:4]}-{str(date_i)[4:6]}-{str(date_i)[6:8]}",
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "vol": int(vol),
                    "source": path,
                }
            )
        else:
            date_i, o, h, l, c, _amt, vol, _ = struct.unpack("<IIIIIfII", b)
            if not date_i:
                i += 32
                continue
            close = c / 100.0
            if not _valid_close(close, code_hint=code_hint):
                # 回退 float 格式（个别 ds 文件误放在 sh/sz）
                date_i, o, h, l, c, _amt, vol, _ = struct.unpack("<IfffffII", b)
                if not _valid_close(float(c), code_hint=code_hint):
                    i += 32
                    continue
                rows.append(
                    {
                        "datetime": f"{str(date_i)[:4]}-{str(date_i)[4:6]}-{str(date_i)[6:8]}",
                        "open": float(o),
                        "high": float(h),
                        "low": float(l),
                        "close": float(c),
                        "vol": int(vol),
                        "source": path,
                    }
                )
            else:
                rows.append(
                    {
                        "datetime": f"{str(date_i)[:4]}-{str(date_i)[4:6]}-{str(date_i)[6:8]}",
                        "open": o / 100.0,
                        "high": h / 100.0,
                        "low": l / 100.0,
                        "close": close,
                        "vol": vol,
                        "source": path,
                    }
                )
        i += 32
    if len(rows) < 5:
        return None
    df = pd.DataFrame(rows)
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    return df


def _decode_lc1_time(raw: int) -> str:
    """通达信 lc1：uint32 拆成两个 uint16（date, minutes），同 pytdx 分钟线。"""
    date_part, minute_part = struct.unpack("<HH", struct.pack("<I", raw))
    if date_part <= 0:
        return f"slot-0-{minute_part}"
    year = date_part // 2048 + 2004
    month = (date_part % 2048) // 100
    day = (date_part % 2048) % 100
    hour, minute = minute_part // 60, minute_part % 60
    if 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59:
        return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
    return f"slot-{date_part}-{minute_part}"


def read_lc1_bars(path: str, *, limit: int = 500) -> pd.DataFrame | None:
    rows: list[dict[str, Any]] = []
    try:
        with open(path, "rb") as f:
            while True:
                b = f.read(32)
                if len(b) < 32:
                    break
                t_raw, o, h, l, c, amt, vol, _ = struct.unpack("<IfffffII", b)
                if not t_raw:
                    continue
                rows.append(
                    {
                        "time": _decode_lc1_time(t_raw),
                        "open": float(o),
                        "high": float(h),
                        "low": float(l),
                        "close": float(c),
                        "amount": float(amt),
                        "vol": int(vol),
                    }
                )
    except OSError:
        return None
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    return df


def _latest_date(df: pd.DataFrame | None) -> date | None:
    if df is None or df.empty:
        return None
    last = str(df.iloc[-1].get("datetime") or df.iloc[-1].get("time", ""))[:10]
    try:
        return date.fromisoformat(last)
    except ValueError:
        return None


def read_daily_bars(code: str, *, limit: int = 120, root: str | None = None) -> pd.DataFrame | None:
    """合并 A 股 lday + ds 扩展 lday，取最新一根 bar 更晚的来源。"""
    code = str(code).zfill(6) if code.isdigit() and len(code) <= 6 else str(code)
    root = root or vipdoc_root()
    candidates: list[pd.DataFrame] = []

    if code.isdigit() and len(code) == 6:
        if code in _SH_INDEX_CODES:
            p = os.path.join(root or vipdoc_root(), "sh", "lday", f"sh{code}.day")
            if os.path.isfile(p):
                df = _read_day_file(p, limit=limit, code_hint=code)
                if df is not None:
                    candidates.append(df)
        else:
            df = _read_daily_bars_single(code, limit=limit, root=root)
            if df is not None:
                df = df.copy()
                df["source"] = _day_path(code, root) or "vipdoc"
                candidates.append(df)
        for alias in _DS_DAILY_ALIASES.get(code, []):
            p = _ds_lday_path(alias, root)
            if p:
                ddf = _read_day_file(p, limit=limit, code_hint=code)
                if ddf is not None:
                    candidates.append(ddf)
    else:
        for alias in _DS_MINUTE_ALIASES.get(code, []):
            p = _ds_lday_path(alias.replace("#", "#") if "#" in alias else alias, root)
            if not p and "#" not in alias:
                p = _ds_lday_path(alias, root)
            if p:
                ddf = _read_day_file(p, limit=limit)
                if ddf is not None:
                    candidates.append(ddf)

    if not candidates:
        return None
    best = candidates[0]
    best_last = _latest_date(best)
    for df in candidates[1:]:
        dlast = _latest_date(df)
        if dlast and (best_last is None or dlast > best_last):
            best = df
            best_last = dlast
    return best.iloc[-limit:] if limit and len(best) > limit else best


def read_minute_bars(
    code: str,
    *,
    klt: int = 1,
    limit: int = 240,
    root: str | None = None,
) -> pd.DataFrame | None:
    """本地分钟 K：A 股 sh/sz minline|fzline，扩展 ds/minline。"""
    root = root or vipdoc_root()
    code_s = str(code).zfill(6) if str(code).isdigit() and len(str(code)) <= 6 else str(code)
    paths: list[str] = []

    if code_s.isdigit() and len(code_s) == 6:
        p = _a_share_minline_path(code_s, klt=klt, root=root)
        if p:
            paths.append(p)
        for alias in _DS_MINUTE_ALIASES.get(code_s, []):
            mp = _ds_minline_path(alias, root)
            if mp:
                paths.append(mp)
    else:
        for alias in _DS_MINUTE_ALIASES.get(code_s, []):
            mp = _ds_minline_path(alias, root)
            if mp:
                paths.append(mp)

    best: pd.DataFrame | None = None
    best_n = 0
    for path in paths:
        df = read_lc1_bars(path, limit=limit)
        if df is not None and len(df) > best_n:
            best = df
            best_n = len(df)
    return best


def latest_bar_date(code: str, *, root: str | None = None) -> date | None:
    return _latest_date(read_daily_bars(code, limit=5, root=root))


def minute_data_status(codes: list[str] | None = None) -> dict[str, Any]:
    """检查本地 1/5 分钟 K 覆盖（供 vipdoc_refresh / daily 日志）。"""
    codes = codes or ["000001", "000300", "600021"]
    root = vipdoc_root()
    rows: list[dict[str, Any]] = []
    for code in codes:
        row: dict[str, Any] = {"code": code}
        for klt in (1, 5):
            df = read_minute_bars(code, klt=klt, limit=10)
            key = "min1" if klt == 1 else "min5"
            if df is None or df.empty:
                row[key] = {"bars": 0, "last": None}
            else:
                row[key] = {"bars": len(df), "last": str(df.iloc[-1]["time"])}
        rows.append(row)
    return {"root": root, "t0002": t0002_root(), "samples": rows}


def coverage_vs_vipdoc(codes: list[str] | None = None) -> list[dict[str, Any]]:
    """对比 sh/sz lday 与合并后日 K 最新日期。"""
    codes = codes or ["000001", "399001", "000300"]
    out: list[dict[str, Any]] = []
    root = vipdoc_root()
    for code in codes:
        std = _read_daily_bars_single(code, limit=3, root=root)
        merged = read_daily_bars(code, limit=3, root=root)
        out.append(
            {
                "code": code,
                "vipdoc_last": _latest_date(std),
                "merged_last": _latest_date(merged),
                "merged_source": str(merged.iloc[-1]["source"]) if merged is not None and not merged.empty else None,
            }
        )
    return out
