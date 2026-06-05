"""市场状态日报：数据抓取（腾讯 gtimg + 东方财富）。"""
from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

EM_HOSTS = (
    "https://push2delay.eastmoney.com",
    "https://push2.eastmoney.com",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.eastmoney.com/",
}

# 主要宽基 / 指数（腾讯行情代码）
INDEX_SYMBOLS: list[tuple[str, str]] = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50"),
    ("bj899050", "北证50"),
    ("sh000300", "沪深300"),
    ("sh000016", "上证50"),
    ("sz399303", "国证2000"),
    ("sh000905", "中证500"),
    ("sz399102", "创业板综"),
]


def _make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    retry = Retry(total=3, connect=3, read=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def _prefix_code(code: str) -> str:
    import sys

    scripts = str(Path(__file__).resolve().parents[1])
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from portfolio_utils import gtimg_symbol, normalize_stock_code

    sym = gtimg_symbol(code)
    if sym:
        return sym
    code = normalize_stock_code(code)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return f"sz{code}"


def _float(s: str, default: float = 0.0) -> float:
    try:
        return float(s) if s else default
    except ValueError:
        return default


@dataclass
class IndexQuote:
    symbol: str
    name: str
    code: str
    close: float
    prev_close: float
    open: float
    high: float
    low: float
    change: float
    change_pct: float
    amplitude_pct: float
    volume: int
    turnover_yi: float  # 成交额（亿元）
    avg_price: float
    update_time: str = ""


@dataclass
class StockQuote:
    code: str
    name: str
    price: float
    prev_close: float
    open: float
    high: float
    low: float
    change: float
    change_pct: float
    amplitude_pct: float
    volume: int
    turnover_yi: float
    turnover_rate_pct: float
    pe_ttm: float
    pb: float
    mcap_yi: float
    mcap_change_yi: float  # 估算：总市值 × 涨跌幅 / (100+涨跌幅)


@dataclass
class BoardQuote:
    code: str
    name: str
    change_pct: float
    change_pts: float
    mcap_yi: float


def parse_index_line(line: str, symbol: str) -> IndexQuote | None:
    if not line.strip() or "=" not in line or '"' not in line:
        return None
    vals = line.split('"')[1].split("~")
    if len(vals) < 35:
        return None
    close = _float(vals[3])
    prev = _float(vals[4])
    open_ = _float(vals[5])
    high = _float(vals[33])
    low = _float(vals[34])
    change = _float(vals[31])
    change_pct = _float(vals[32])
    amp = (high - low) / prev * 100 if prev else 0.0
    turnover_wan = _float(vals[37]) if len(vals) > 37 else 0.0
    turnover_yi = turnover_wan / 10000.0  # 万元 → 亿元
    avg_p = _float(vals[51]) if len(vals) > 51 else 0.0
    vol = int(_float(vals[36])) if len(vals) > 36 else int(_float(vals[6]))
    return IndexQuote(
        symbol=symbol,
        name=vals[1],
        code=vals[2],
        close=close,
        prev_close=prev,
        open=open_,
        high=high,
        low=low,
        change=change,
        change_pct=change_pct,
        amplitude_pct=round(amp, 2),
        volume=vol,
        turnover_yi=round(turnover_yi, 2),
        avg_price=avg_p,
        update_time=vals[30] if len(vals) > 30 else "",
    )


def parse_stock_line(line: str) -> StockQuote | None:
    if not line.strip() or "=" not in line or '"' not in line:
        return None
    vals = line.split('"')[1].split("~")
    if len(vals) < 47:
        return None
    key = line.split("=")[0]
    code = key.split("_")[-1][2:] if "_" in key else vals[2]
    price = _float(vals[3])
    prev = _float(vals[4])
    open_ = _float(vals[5])
    high = _float(vals[33]) if len(vals) > 33 else _float(vals[41])
    low = _float(vals[34]) if len(vals) > 34 else _float(vals[42])
    change = _float(vals[31])
    change_pct = _float(vals[32])
    amp = _float(vals[43]) if len(vals) > 43 else ((high - low) / prev * 100 if prev else 0)
    vol = int(_float(vals[36])) if len(vals) > 36 else int(_float(vals[6]))
    turnover_wan = _float(vals[37]) if len(vals) > 37 else 0.0
    turnover_yi = turnover_wan / 10000.0
    tr_pct = _float(vals[38]) if len(vals) > 38 else 0.0
    pe = _float(vals[39]) if len(vals) > 39 else 0.0
    pb = _float(vals[46]) if len(vals) > 46 else 0.0
    mcap_yi = _float(vals[44]) if len(vals) > 44 else 0.0
    mcap_change = mcap_yi * change_pct / (100 + change_pct) if change_pct != -100 else 0.0
    return StockQuote(
        code=code,
        name=vals[1],
        price=price,
        prev_close=prev,
        open=open_,
        high=high,
        low=low,
        change=change,
        change_pct=change_pct,
        amplitude_pct=round(amp, 2),
        volume=vol,
        turnover_yi=round(turnover_yi, 2),
        turnover_rate_pct=tr_pct,
        pe_ttm=pe,
        pb=pb,
        mcap_yi=round(mcap_yi, 2),
        mcap_change_yi=round(mcap_change, 2),
    )


def fetch_gtimg_batch(symbols: list[str]) -> dict[str, str]:
    """返回 symbol -> raw line"""
    url = "https://qt.gtimg.cn/q=" + ",".join(symbols)
    req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
    data = urllib.request.urlopen(req, timeout=20).read().decode("gbk", errors="ignore")
    # 批量响应可能用换行而非分号分隔记录
    data = data.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "")
    out: dict[str, str] = {}
    for line in data.strip().split(";"):
        if "=" not in line:
            continue
        sym = line.split("=")[0].replace("v_", "").strip()
        out[sym] = line
    return out


def fetch_indices() -> list[IndexQuote]:
    symbols = [s for s, _ in INDEX_SYMBOLS]
    lines = fetch_gtimg_batch(symbols)
    results: list[IndexQuote] = []
    for sym, label in INDEX_SYMBOLS:
        line = lines.get(sym)
        if not line:
            continue
        q = parse_index_line(line, sym)
        if q:
            if not q.name or q.name == label:
                q.name = label
            results.append(q)
    return results


def fetch_stocks_by_codes(codes: list[str]) -> dict[str, StockQuote]:
    if not codes:
        return {}
    prefixed = [_prefix_code(c) for c in codes]
    lines = fetch_gtimg_batch(prefixed)
    out: dict[str, StockQuote] = {}
    for line in lines.values():
        q = parse_stock_line(line)
        if q:
            out[q.code] = q
    return out


def _em_clist(session: requests.Session, *, fs: str, fid: str, po: int, pz: int, fields: str) -> list[dict]:
    params = {
        "pn": 1,
        "pz": pz,
        "po": po,
        "np": 1,
        "fltt": 2,
        "invt": 2,
        "fid": fid,
        "fs": fs,
        "fields": fields,
    }
    for host in EM_HOSTS:
        try:
            r = session.get(f"{host}/api/qt/clist/get", params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
            diff = (data.get("data") or {}).get("diff") or []
            if diff:
                return diff
        except Exception:
            continue
    return []


def fetch_concept_boards(*, top_n: int = 3) -> tuple[list[BoardQuote], list[BoardQuote]]:
    """概念板块涨跌幅 TopN / BottomN"""
    session = _make_session()
    fs = "m:90+t:3"
    fields = "f12,f14,f3,f4,f20"
    gain_raw = _em_clist(session, fs=fs, fid="f3", po=1, pz=top_n, fields=fields)
    loss_raw = _em_clist(session, fs=fs, fid="f3", po=0, pz=top_n, fields=fields)

    def to_board(items: list[dict]) -> list[BoardQuote]:
        boards: list[BoardQuote] = []
        for it in items:
            boards.append(
                BoardQuote(
                    code=str(it.get("f12", "")),
                    name=str(it.get("f14", "")),
                    change_pct=_float(str(it.get("f3", 0))),
                    change_pts=_float(str(it.get("f4", 0))),
                    mcap_yi=round(_float(str(it.get("f20", 0))) / 1e8, 2),
                )
            )
        return boards

    return to_board(gain_raw), to_board(loss_raw)


def fetch_board_mcap_top_stocks(board: BoardQuote, *, top_n: int = 5) -> list[tuple[StockQuote, BoardQuote]]:
    """板块内按估算市值变化排序的 Top 标的"""
    session = _make_session()
    items = _em_clist(
        session,
        fs=f"b:{board.code}",
        fid="f20",
        po=1,
        pz=200,
        fields="f12,f14,f2,f3,f20,f4",
    )
    rows: list[tuple[float, dict]] = []
    for it in items:
        f20 = _float(str(it.get("f20", 0)))
        f3 = _float(str(it.get("f3", 0)))
        if f20 <= 0:
            continue
        delta_yi = f20 * f3 / (100 + f3) / 1e8
        rows.append((delta_yi, it))
    rows.sort(key=lambda x: x[0], reverse=True)
    out: list[tuple[StockQuote, BoardQuote]] = []
    codes = [str(it.get("f12", "")).zfill(6) for _, it in rows[:top_n]]
    gt = fetch_stocks_by_codes(codes)
    for delta_yi, it in rows[:top_n]:
        code = str(it.get("f12", "")).zfill(6)
        q = gt.get(code)
        if not q:
            price = _float(str(it.get("f2", 0)))
            f3 = _float(str(it.get("f3", 0)))
            f20_yi = _float(str(it.get("f20", 0))) / 1e8
            q = StockQuote(
                code=code,
                name=str(it.get("f14", "")),
                price=price,
                prev_close=0,
                open=0,
                high=0,
                low=0,
                change=_float(str(it.get("f4", 0))),
                change_pct=f3,
                amplitude_pct=0,
                volume=0,
                turnover_yi=0,
                turnover_rate_pct=0,
                pe_ttm=0,
                pb=0,
                mcap_yi=round(f20_yi, 2),
                mcap_change_yi=round(delta_yi, 2),
            )
        else:
            q.mcap_change_yi = round(delta_yi, 2)
        out.append((q, board))
    time.sleep(0.3)
    return out
