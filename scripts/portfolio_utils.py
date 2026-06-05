"""持仓持有人解析与按人过滤（sync / 飞书 Bot / fine_screen 共用）。"""
from __future__ import annotations

import importlib
import os
import re
import sys
import time
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PORTFOLIO_MD = os.path.join(ROOT, "portfolio.md")
POOL_MD = os.path.join(ROOT, "Wiki", "数据", "博主标的池日报.md")
SUG_VAULT = os.path.join(ROOT, "SugVault")

HOLDER_SECTION = re.compile(r"^##\s+持有人：(.+)\s*$", re.MULTILINE)
SUG_SESSIONS = frozenset({"早盘", "午盘"})
SUG_ALL_ALIASES = frozenset({"全员", "全部", "all"})
# YYYY-MM-DD[_HHMM]_Holder_sug.md 或 YYYY-MM-DD[_HHMM]_Holder_sug 早盘.md
SUG_FILE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})(?:_(\d{4}))?_(.+?)_sug(?: (早盘|午盘))?\.md$",
    re.IGNORECASE,
)

FORMAT_HINT = "请校对格式{cmd} {{持有人}}，以精确搜索"


def format_hint(cmd: str) -> str:
    return FORMAT_HINT.format(cmd=cmd)


def _import_portfolio():
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
    return importlib.import_module("portfolio")


def load_holder_names() -> list[str]:
    try:
        mod = _import_portfolio()
        holders = getattr(mod, "HOLDERS", None)
        if holders:
            return list(holders)
    except Exception:
        pass
    return _holders_from_md()


def _holders_from_md() -> list[str]:
    if not os.path.isfile(PORTFOLIO_MD):
        return []
    with open(PORTFOLIO_MD, encoding="utf-8") as f:
        text = f.read()
    return [m.group(1).strip() for m in HOLDER_SECTION.finditer(text)]


def resolve_holder(query: str, names: list[str] | None = None) -> str | None:
    """按持有人名精确匹配（不区分大小写），返回 xlsx 中的 canonical 名称。"""
    q = query.strip()
    if not q:
        return None
    names = names if names is not None else load_holder_names()
    for name in names:
        if name.lower() == q.lower():
            return name
    return None


def parse_holder_arg(text: str, verbs: tuple[str, ...]) -> tuple[str | None, str | None] | None:
    """
    解析「动词 + 持有人」指令。
    返回 None 表示不是该组动词；否则 (canonical_holder, error_msg)。
    """
    stripped = text.strip()
    if not stripped:
        return None
    parts = stripped.split(None, 1)
    verb = parts[0]
    if verb.lower() not in {v.lower() for v in verbs}:
        return None
    if len(parts) < 2 or not parts[1].strip():
        return None, format_hint(verb)
    names = load_holder_names()
    if not names:
        return None, "尚无持仓数据，请先运行 daily.bat 同步 持仓.xlsx"
    canonical = resolve_holder(parts[1].strip(), names)
    if not canonical:
        return None, f"未找到持有人「{parts[1].strip()}」。可选：{', '.join(names)}"
    return canonical, None


def parse_sug_command(text: str) -> tuple[str | None, str | None, str | None] | None:
    """
    解析 sug / 交易策略 / 开仓 指令。
    返回 None 表示非 sug 组；否则 (holder_or___ALL__, session, error_msg)。
    session 为「早盘」或「午盘」，未指定则为 None。
    """
    stripped = text.strip()
    if not stripped:
        return None
    parts = stripped.split()
    verb = parts[0]
    if verb.lower() not in {"sug", "交易策略", "开仓", "买什么", "持仓分析"}:
        return None
    if len(parts) < 2:
        return None, None, format_hint("sug")

    names = load_holder_names()
    if not names:
        return None, None, "尚无持仓数据，请先运行 daily.bat 同步 持仓.xlsx"

    rest_parts = parts[1:]
    session: str | None = None
    if rest_parts[-1] in SUG_SESSIONS:
        session = rest_parts[-1]
        rest_parts = rest_parts[:-1]
    if not rest_parts:
        return None, None, format_hint("sug")

    target = " ".join(rest_parts)
    if target.lower() in {a.lower() for a in SUG_ALL_ALIASES}:
        return "__ALL__", session, None

    canonical = resolve_holder(target, names)
    if not canonical:
        return None, None, f"未找到持有人「{target}」。可选：{', '.join(names)}"
    return canonical, session, None


def sug_archive_basename(
    holder: str,
    session: str | None = None,
    *,
    date: str | None = None,
    hhmm: str | None = None,
) -> str:
    """生成 SugVault 归档文件名（不含目录）。"""
    from datetime import datetime

    d = date or datetime.now().strftime("%Y-%m-%d")
    prefix = f"{d}_{hhmm}_" if hhmm else f"{d}_"
    if session and session in SUG_SESSIONS:
        return f"{prefix}{holder}_sug {session}.md"
    return f"{prefix}{holder}_sug.md"


def latest_sug_path(holder: str, session: str | None = None) -> str | None:
    import glob

    hl = holder.lower()
    matched: list[str] = []
    for path in glob.glob(os.path.join(SUG_VAULT, "*.md")):
        base = os.path.basename(path)
        m = SUG_FILE.match(base)
        if not m or m.group(3).lower() != hl:
            continue
        file_session = m.group(4)  # 早盘/午盘 or None
        if session:
            if file_session == session:
                matched.append(path)
        elif file_session is None:
            matched.append(path)
    if not matched:
        return None
    return sorted(matched, reverse=True)[0]
    """从 markdown 提取 ## 持有人：XXX 章节（至下一同级章节或 EOF）。"""
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+持有人：(.+)\s*$", line)
        if not m:
            continue
        if m.group(1).strip().lower() == holder.lower():
            start = i
            continue
        if start is not None:
            return "\n".join(lines[start:i]).strip()
    if start is not None:
        return "\n".join(lines[start:]).strip()
    return None


def filter_portfolio_md(holder: str) -> str:
    if not os.path.isfile(PORTFOLIO_MD):
        return f"（文件不存在：{PORTFOLIO_MD}）"
    with open(PORTFOLIO_MD, encoding="utf-8") as f:
        text = f.read()
    section = extract_holder_section(text, holder)
    if section:
        return section
    return f"未找到持有人「{holder}」的持仓章节。"


def filter_pool_md(holder: str) -> str:
    if not os.path.isfile(POOL_MD):
        return f"（文件不存在：{POOL_MD}）"
    with open(POOL_MD, encoding="utf-8") as f:
        text = f.read()
    first_holder = HOLDER_SECTION.search(text)
    if not first_holder:
        return text
    header = text[: first_holder.start()].rstrip()
    section = extract_holder_section(text, holder)
    if not section:
        return f"{header}\n\n（该持有人无持仓做T章节：{holder}）"
    return f"{header}\n\n{section}"


def extract_holder_section(text: str, holder: str) -> str | None:
    mod = _import_portfolio()
    hl = holder.lower()
    return [h for h in mod.HOLDINGS if h.get("holder", "").lower() == hl]


def pad_a_share_code(code: str) -> str:
    s = str(code).strip().replace(".0", "")
    if s.isdigit() and len(s) < 6:
        return s.zfill(6)
    return s


def fetch_spot_price(code: str) -> float | None:
    """从腾讯行情接口获取 A 股现价（元）。"""
    code = pad_a_share_code(code)
    if not code:
        return None
    prefixed = f"sh{code}" if code.startswith(("6", "9")) else f"sz{code}"
    url = f"https://qt.gtimg.cn/q={prefixed}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk", errors="ignore")
        vals = data.split('"')[1].split("~") if '"' in data else []
        if len(vals) < 4:
            return None
        price = float(vals[3] or 0)
        return price if price > 0 else None
    except Exception:
        return None


def enrich_holdings_with_prices(holdings: list[dict], *, sleep_s: float = 0.2) -> list[dict]:
    """为持仓补充 price、market_value（股数×现价）。"""
    enriched: list[dict] = []
    seen: dict[str, float | None] = {}
    for h in holdings:
        row = dict(h)
        code = row["code"]
        if code not in seen:
            seen[code] = fetch_spot_price(code)
            if sleep_s > 0:
                time.sleep(sleep_s)
        price = seen[code]
        row["price"] = price
        row["market_value"] = round(price * row["shares"], 2) if price is not None else None
        enriched.append(row)
    return enriched
