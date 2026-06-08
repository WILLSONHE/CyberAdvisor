"""模拟盘/Agent 补充行情：60 分钟 K 线、北向/南向、隔夜外盘、北向历史序列。"""
from __future__ import annotations

import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from market_daily.fetch import HEADERS, IndexQuote, _float, fetch_gtimg_batch, parse_index_line

EM_HIS = "https://push2his.eastmoney.com"
EM_PUSH = "https://push2.eastmoney.com"

# secid → 名称（东方财富）
KLINE_INDEX: dict[str, str] = {
    "1.000001": "上证指数",
    "0.399001": "深证成指",
    "0.399006": "创业板指",
}

OVERNIGHT_GTIMG: list[tuple[str, str]] = [
    ("usIXIC", "纳斯达克"),
    ("usSOXX", "费城半导体ETF"),
    ("usDJI", "道琼斯"),
    ("hkHSCEI", "恒生国企指数"),
]


def _session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    retry = Retry(total=3, connect=3, read=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def _parse_kline_bar(line: str) -> dict[str, Any] | None:
    parts = line.split(",")
    if len(parts) < 6:
        return None
    return {
        "time": parts[0],
        "open": _float(parts[1]),
        "close": _float(parts[2]),
        "high": _float(parts[3]),
        "low": _float(parts[4]),
        "volume": int(_float(parts[5])),
        "amount": _float(parts[6]) if len(parts) > 6 else 0.0,
    }


def fetch_index_kline_60m(*, secid: str, limit: int = 20) -> list[dict[str, Any]]:
    """东方财富 60 分钟 K 线（最近 limit 根）。"""
    session = _session()
    params = {
        "secid": secid,
        "klt": "60",
        "fqt": "1",
        "lmt": limit,
        "end": "20500101",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
    }
    for host in (EM_HIS, EM_PUSH):
        try:
            r = session.get(f"{host}/api/qt/stock/kline/get", params=params, timeout=20)
            r.raise_for_status()
            klines = (r.json().get("data") or {}).get("klines") or []
            out = [_parse_kline_bar(x) for x in klines]
            return [b for b in out if b]
        except Exception:
            continue
    return []


def fetch_klines_60m_multi(*, limit: int = 20) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for secid, name in KLINE_INDEX.items():
        bars = fetch_index_kline_60m(secid=secid, limit=limit)
        code = secid.split(".")[-1]
        out[code] = {"name": name, "secid": secid, "bars": bars}
        time.sleep(0.15)
    return out


def _parse_kamt_channel(raw: dict | None, *, is_north: bool = True) -> dict[str, Any]:
    if not raw:
        return {}
    net_wan = _float(str(raw.get("dayNetAmtIn", 0)))
    threshold = _float(str(raw.get("dayAmtThreshold", 0)))
    # 东方财富在非交易时段或字段含义为额度时，dayNetAmtIn 可能等于 threshold
    if threshold and abs(net_wan - threshold) < 1:
        net_wan = 0.0
    if abs(net_wan) >= 100_000:
        net_wan = 0.0
    return {
        "net_yi": round(net_wan / 10000.0, 2),
        "net_wan": net_wan,
        "date": raw.get("date2") or raw.get("date") or "",
        "status": raw.get("status"),
    }


def _northbound_from_rtmin(session: requests.Session) -> dict[str, float] | None:
    """盘中分钟序列：s2n 字段 1/3 为沪股通/深股通净流入（万元）。"""
    try:
        r = session.get(
            f"{EM_PUSH}/api/qt/kamt.rtmin/get",
            params={"fields1": "f1,f2,f3,f4", "fields2": "f51,f52,f53,f54,f55,f56"},
            timeout=15,
        )
        r.raise_for_status()
        s2n = (r.json().get("data") or {}).get("s2n") or []
    except Exception:
        return None
    for line in reversed(s2n):
        parts = line.split(",")
        if len(parts) < 4:
            continue
        try:
            hgt = float(parts[1]) if parts[1] not in ("-", "") else 0.0
            sgt = float(parts[3]) if parts[3] not in ("-", "") else 0.0
        except ValueError:
            continue
        if hgt == 0 and sgt == 0:
            continue
        return {"hgt_wan": hgt, "sgt_wan": sgt, "north_wan": hgt + sgt}
    return None


def fetch_northbound_snapshot() -> dict[str, Any]:
    """北向/南向当日快照（万元 → 亿元）。"""
    session = _session()
    try:
        r = session.get(
            f"{EM_PUSH}/api/qt/kamt/get",
            params={"fields1": "f1,f2,f3,f4", "fields2": "f51,f52,f53,f54,f55,f56"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json().get("data") or {}
    except Exception:
        return {}

    hgt = _parse_kamt_channel(data.get("hk2sh"), is_north=True)
    sgt = _parse_kamt_channel(data.get("hk2sz"), is_north=True)
    sh2hk = _parse_kamt_channel(data.get("sh2hk"), is_north=False)
    sz2hk = _parse_kamt_channel(data.get("sz2hk"), is_north=False)

    rt = _northbound_from_rtmin(session)
    if rt:
        hgt = {**hgt, "net_wan": rt["hgt_wan"], "net_yi": round(rt["hgt_wan"] / 10000.0, 2)}
        sgt = {**sgt, "net_wan": rt["sgt_wan"], "net_yi": round(rt["sgt_wan"] / 10000.0, 2)}
        north_yi = round(rt["north_wan"] / 10000.0, 2)
    else:
        north_yi = round((hgt.get("net_wan", 0) + sgt.get("net_wan", 0)) / 10000.0, 2)

    south_yi = round((sh2hk.get("net_wan", 0) + sz2hk.get("net_wan", 0)) / 10000.0, 2)
    return {
        "north_net_yi": north_yi,
        "south_net_yi": south_yi,
        "hgt": hgt,
        "sgt": sgt,
        "sh2hk": sh2hk,
        "sz2hk": sz2hk,
    }


def fetch_northbound_history(*, days: int = 10) -> list[dict[str, Any]]:
    """近 N 日北向通道日序列（push2his kamt.kline，字段为通道余额/额度）。"""
    session = _session()
    try:
        r = session.get(
            f"{EM_HIS}/api/qt/kamt.kline/get",
            params={
                "klt": 101,
                "lmt": days,
                "fields1": "f1",
                "fields2": "f51,f52,f53,f54,f55,f56",
            },
            timeout=20,
        )
        r.raise_for_status()
        raw = r.json().get("data") or {}
    except Exception:
        return []

    rows: dict[str, dict] = {}
    for channel, lines in raw.items():
        if not isinstance(lines, list):
            continue
        for line in lines:
            parts = line.split(",")
            if len(parts) < 4:
                continue
            date = parts[0]
            row = rows.setdefault(date, {"date": date})
            row[channel] = {
                "field2": _float(parts[1]),
                "quota_wan": _float(parts[2]),
                "field4": _float(parts[3]),
            }
    return [rows[k] for k in sorted(rows.keys())][-days:]


def fetch_overnight_indices() -> list[dict[str, Any]]:
    """隔夜外盘：纳指、半导体 ETF、道指、恒生国企（A50 期货不可用时的代理）。"""
    symbols = [s for s, _ in OVERNIGHT_GTIMG]
    try:
        lines = fetch_gtimg_batch(symbols)
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for sym, label in OVERNIGHT_GTIMG:
        line = lines.get(sym)
        if not line or "pv_none_match" in line:
            continue
        q = parse_index_line(line, sym)
        if not q:
            vals = line.split('"')[1].split("~") if '"' in line else []
            if len(vals) < 33:
                continue
            out.append(
                {
                    "symbol": sym,
                    "name": label,
                    "close": _float(vals[3]),
                    "prev_close": _float(vals[4]),
                    "change_pct": _float(vals[32]),
                    "update_time": vals[30] if len(vals) > 30 else "",
                }
            )
            continue
        out.append(
            {
                "symbol": sym,
                "name": label,
                "close": q.close,
                "prev_close": q.prev_close,
                "change_pct": q.change_pct,
                "update_time": q.update_time,
            }
        )
    return out


def indices_to_snapshot(indices: list[IndexQuote]) -> dict[str, dict[str, Any]]:
    sym_to_code = {
        "sh000001": "000001",
        "sz399001": "399001",
        "sz399006": "399006",
    }
    snap: dict[str, dict[str, Any]] = {}
    for q in indices:
        code = sym_to_code.get(q.symbol) or (q.code.zfill(6) if q.code else "")
        if code not in ("000001", "399001", "399006"):
            continue
        snap[code] = {
            "name": q.name,
            "close": q.close,
            "open": q.open,
            "high": q.high,
            "low": q.low,
            "change_pct": q.change_pct,
            "turnover_yi": q.turnover_yi,
        }
    return snap


def build_supplement(*, include_overnight: bool = False, kline_limit: int = 20) -> dict[str, Any]:
    """组装 tick / Agent 用补充数据包。"""
    payload: dict[str, Any] = {
        "kline_60m": fetch_klines_60m_multi(limit=kline_limit),
        "northbound": fetch_northbound_snapshot(),
        "northbound_history": fetch_northbound_history(days=10),
    }
    if include_overnight:
        payload["overnight"] = fetch_overnight_indices()
    return payload
