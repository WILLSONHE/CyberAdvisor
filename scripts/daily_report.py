#!/usr/bin/env python3
"""
脚本3：每日市场状态日报
拉取北向资金、强势股/题材归因、概念板块排名，输出市场状态。
输出：Wiki/数据/市场状态日报.md
"""
import os
import json
import time
import urllib.request
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "Wiki", "数据")
OUTPUT = os.path.join(DATA_DIR, "市场状态日报.md")

def fetch_json(url: str, headers: dict = None, timeout: int = 15) -> dict:
    """通用JSON抓取"""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

def get_northbound_flow() -> str:
    """北向资金（简化版：从腾讯财经抓沪股通/深股通汇总）"""
    # 腾讯财经港股通资金流向
    url = "https://qt.gtimg.cn/q=ff_hsgt"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk", errors="ignore")
        return "数据已获取（腾讯财经）" if len(data) > 100 else "数据异常"
    except:
        return "接口暂不可用"

def get_hot_stocks() -> list[dict]:
    """同花顺当日强势股+题材归因（零鉴权）"""
    url = "https://emweb.securities.eastmoney.com/PC_HSF10/CoreConception/PageAjax?code=SZ300476"
    # 改用百度股市通热点
    url2 = "https://finance.pae.baidu.com/vapi/v1/hotrank?market=ab&type=day&pagenum=1&pagesize=20"
    try:
        req = urllib.request.Request(url2)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Referer", "https://gushitong.baidu.com/")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("ResultCode") in ["0", 0, 0]:
            items = data.get("Result", {}).get("list", [])[:15]
            return [{"name": item.get("stockName", ""), "code": item.get("stockCode", ""),
                     "change": item.get("changePct", ""), "reason": item.get("hotReason", "")[:30]}
                    for item in items]
    except Exception as e:
        return [{"error": str(e)}]
    return []

def get_sector_ranking() -> list[dict]:
    """概念板块排名（百度股市通）"""
    url = "https://finance.pae.baidu.com/vapi/v1/boardrank?boardtype=concept&pagenum=1&pagesize=10"
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Referer", "https://gushitong.baidu.com/")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        if data.get("ResultCode") in ["0", 0, 0]:
            items = data.get("Result", {}).get("list", [])[:10]
            return [{"name": item.get("boardName", ""), "change": item.get("changePct", ""),
                     "leader": item.get("leadStockName", "")}
                    for item in items]
    except:
        pass
    return []

def generate_report() -> str:
    """生成市场状态日报"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# 市场状态日报",
        f"\n> 更新时间：{now}\n",
        "## 北向资金",
        f"状态：{get_northbound_flow()}\n",
        "## 今日强势股 / 题材归因",
    ]
    
    hot = get_hot_stocks()
    if hot:
        lines.append("| 标的 | 代码 | 涨跌幅 | 题材 |")
        lines.append("|------|------|--------|------|")
        for h in hot[:10]:
            lines.append(f"| {h.get('name','')} | {h.get('code','')} | {h.get('change','')}% | {h.get('reason','')} |")
    else:
        lines.append("暂未获取到数据\n")
    
    lines.append("\n## 概念板块排名")
    sectors = get_sector_ranking()
    if sectors:
        lines.append("| 板块 | 涨跌幅 | 领涨股 |")
        lines.append("|------|--------|--------|")
        for s in sectors:
            lines.append(f"| {s.get('name','')} | {s.get('change','')}% | {s.get('leader','')} |")
    else:
        lines.append("暂未获取到数据\n")
    
    lines.append(f"\n## 博主框架视角\n")
    lines.append("*请结合精筛结果和标的池日报综合判断。*")
    lines.append(f"\n- [[博主决策时间线]]")
    lines.append(f"- [[标的总览]]")
    lines.append(f"- [精筛候选](精筛候选.csv)")
    
    return "\n".join(lines)

def main():
    print("[1/2] Fetching market data...")
    report = generate_report()
    print("[2/2] Writing report...")
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Written to {OUTPUT}")
    print("Done.")

if __name__ == "__main__":
    main()
