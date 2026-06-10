#!/usr/bin/env python3
"""
脚本1：全市场粗筛（每日15:30后运行）
用腾讯财经API批量拉全市场PE/PB/市值，按 Wiki 框架硬门槛粗筛。
输出：Wiki/数据/粗筛结果.csv
"""
import time
import csv
import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "Wiki", "数据")
OUTPUT = os.path.join(DATA_DIR, "粗筛结果.csv")

BATCH_SIZE = 25
BATCH_SLEEP = 0.8
MAX_RETRIES = 4
RETRY_BACKOFF = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.qq.com/",
}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False  # 不走系统代理，避免 localhost 代理导致 SSL/503
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HEADERS)
    return session


def _prefix_code(code: str) -> str:
    from portfolio_utils import gtimg_symbol

    sym = gtimg_symbol(code)
    if sym:
        return sym
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith("8"):
        return f"bj{code}"
    return f"sz{code}"


def _parse_quote_line(line: str) -> dict | None:
    if not line.strip() or "=" not in line or '"' not in line:
        return None
    vals = line.split('"')[1].split("~")
    if len(vals) < 53:
        return None
    code = line.split("=")[0].split("_")[-1][2:]
    try:
        return {
            "code": code,
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
        }
    except (ValueError, IndexError):
        return None


def _fetch_batch(session: requests.Session, batch: list[str]) -> dict:
    prefixed = [_prefix_code(c) for c in batch]
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.content.decode("gbk", errors="ignore")
            out = {}
            for line in data.strip().split(";"):
                row = _parse_quote_line(line)
                if row:
                    out[row["code"]] = row
            return out
        except Exception as e:
            last_err = e
            wait = RETRY_BACKOFF * (attempt + 1)
            time.sleep(wait)
    raise last_err or RuntimeError("batch request failed")


def tencent_quote_batch(codes: list[str]) -> dict:
    """批量拉取腾讯财经实时行情（每批约25只，失败自动重试/降级HTTP）"""
    session = _make_session()
    results = {}
    failed_ranges = []
    total_batches = (len(codes) + BATCH_SIZE - 1) // BATCH_SIZE

    for bi, i in enumerate(range(0, len(codes), BATCH_SIZE)):
        batch = codes[i : i + BATCH_SIZE]
        try:
            results.update(_fetch_batch(session, batch))
        except Exception as e:
            print(f"  [WARN] batch {i}-{i + BATCH_SIZE} failed: {e}")
            failed_ranges.append((i, batch))
        if (bi + 1) % 20 == 0:
            print(f"  ... {bi + 1}/{total_batches} batches, {len(results)} quotes")
        time.sleep(BATCH_SLEEP)

    if failed_ranges:
        print(f"  [RETRY] {len(failed_ranges)} failed batches, splitting into smaller chunks...")
        for i, batch in failed_ranges:
            sub_size = 10
            for j in range(0, len(batch), sub_size):
                sub = batch[j : j + sub_size]
                try:
                    results.update(_fetch_batch(session, sub))
                except Exception as e:
                    print(f"  [WARN] retry {i + j}-{i + j + sub_size} still failed: {e}")
                time.sleep(1.2)

    session.close()
    return results


def generate_code_list() -> list[str]:
    """生成全A股代码列表（沪深两市）"""
    codes = []
    for i in range(600000, 606000):
        codes.append(str(i))
    for i in range(688000, 690000):
        codes.append(str(i))
    for i in range(1, 5000):
        codes.append(f"{i:06d}")
    for i in range(300000, 302000):
        codes.append(str(i))
    return codes


def coarse_filter(quotes: dict) -> list[dict]:
    """Wiki 框架粗筛"""
    passed = []
    for code, q in quotes.items():
        if q["price"] <= 0 or q["pe_ttm"] <= 0:
            continue
        if q["pb"] > 10:
            continue
        if q["mcap_yi"] < 50:
            continue
        if abs(q["change_pct"]) > 5:
            continue
        if q["pe_ttm"] > 200:
            continue
        passed.append(q)
    return passed


def main():
    print("[1/3] Generating code list...")
    codes = generate_code_list()
    print(f"  Total codes: {len(codes)}")

    print("[2/3] Fetching quotes (this will take 5-10 minutes)...")
    quotes = tencent_quote_batch(codes)
    print(f"  Got quotes for {len(quotes)} stocks")
    if len(quotes) < 3000:
        print("  [WARN] 获取数量偏少，可能被限流；可稍后重跑 coarse_screen.py")

    print("[3/3] Coarse filtering...")
    passed = coarse_filter(quotes)
    print(f"  Passed: {len(passed)} stocks")

    passed.sort(key=lambda x: x["pe_ttm"])

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["code", "name", "price", "change_pct", "pe_ttm", "pb", "mcap_yi"])
        writer.writeheader()
        for q in passed:
            writer.writerow({
                "code": q.get("code", ""),
                "name": q["name"],
                "price": q["price"],
                "change_pct": q["change_pct"],
                "pe_ttm": q["pe_ttm"],
                "pb": q["pb"],
                "mcap_yi": q["mcap_yi"],
            })
    print(f"  Written to {OUTPUT}")
    print("Done.")


if __name__ == "__main__":
    main()
