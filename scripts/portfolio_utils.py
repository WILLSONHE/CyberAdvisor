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


def fmt_money(amount: float | int | None, *, decimals: int = 2, signed: bool = False) -> str:
    """报告用金额：千位逗号 + 固定小数（例 90,000,000.00）。"""
    if amount is None:
        return "—"
    spec = f"{{:+,.{decimals}f}}" if signed else f"{{:,.{decimals}f}}"
    return spec.format(float(amount))


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
    """返回持有人最新 sug 报告路径。未指定盘次时取时间最近的一份（含早盘/午盘）。"""
    import glob

    hl = holder.lower()
    matched: list[tuple[tuple[str, str, str], str]] = []
    for path in glob.glob(os.path.join(SUG_VAULT, "*.md")):
        base = os.path.basename(path)
        m = SUG_FILE.match(base)
        if not m or m.group(3).lower() != hl:
            continue
        file_session = m.group(4)
        if session:
            if file_session != session:
                continue
        date_part = m.group(1)
        hhmm_part = m.group(2) or "0000"
        matched.append(((date_part, hhmm_part, base), path))
    if not matched:
        return None
    matched.sort(key=lambda x: x[0], reverse=True)
    return matched[0][1]


def extract_holder_section(text: str, holder: str) -> str | None:
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


def holdings_for_holder(holder: str) -> list[dict]:
    mod = _import_portfolio()
    hl = holder.lower()
    return [h for h in mod.HOLDINGS if h.get("holder", "").lower() == hl]


def pad_a_share_code(code: str) -> str:
    """A 股 6 位代码补零（港股请用 normalize_stock_code）。"""
    return parse_code_from_excel_cell(code)


def _digits_only(code: str) -> str:
    return re.sub(r"\D", "", str(code).strip())


def parse_code_from_excel_cell(cell) -> str:
    """
    从 Excel 单元格解析证券代码，按用户填写的 A 股/港股规则归一化。

    pandas 默认把「代码」读成 float 时会吃掉前导零（000010→10.0→误判港股 00010）。
    本函数在 sync / sim 读 xlsx 时统一调用。
    """
    if cell is None:
        return ""
    try:
        import pandas as pd

        if isinstance(cell, float) and pd.isna(cell):
            return ""
    except ImportError:
        pass

    raw = str(cell).strip()
    if not raw or raw.lower() == "nan":
        return ""

    upper = raw.upper()
    if ".HK" in upper or upper.startswith("HK"):
        return normalize_stock_code(raw)

    if re.fullmatch(r"\d+\.0", raw):
        raw = raw[:-2]
    elif isinstance(cell, (int, float)) and not isinstance(cell, bool):
        n = float(cell)
        raw = str(int(n)) if n == int(n) else raw

    digits = _digits_only(raw)
    if not digits:
        return raw

    if len(digits) == 6:
        return normalize_stock_code(digits)

    if len(digits) == 5:
        return normalize_stock_code(digits)

    # 1–4 位：多为 Excel 数值型吃掉前导零的 A 股；少数为港股（700→00700）
    hk5 = digits.zfill(5)
    if hk5 in HK_TO_A_SHARE:
        return normalize_stock_code(hk5)
    if len(digits) <= 2:
        return normalize_stock_code(digits.zfill(6))
    if len(digits) == 4 and digits.zfill(6).startswith(("00", "30", "60", "68", "83", "87")):
        return normalize_stock_code(digits.zfill(6))
    return normalize_stock_code(hk5)


def format_code_for_excel(code: str) -> str:
    """写入 xlsx 时保留 A 股 6 位 / 港股 5 位文本格式。"""
    if not code:
        return ""
    norm = parse_code_from_excel_cell(code)
    market = classify_market(norm)
    if market == "hk":
        return normalize_stock_code(norm)
    if market in ("sh", "sz", "bj"):
        return normalize_stock_code(norm)
    return norm


def classify_market(code: str) -> str:
    """
    识别市场：sh / sz / bj / hk / unknown。
    - 6 位数字 → A 股/北交所
    - 1–5 位数字，或含 .HK / HK 前缀 → 港股
    """
    raw = str(code).strip().upper()
    if ".HK" in raw or raw.startswith("HK"):
        return "hk"
    digits = _digits_only(code)
    if not digits:
        return "unknown"
    if len(digits) == 6:
        if digits.startswith(("6", "9")):
            return "sh"
        if digits.startswith(("8", "4")):
            return "bj"
        return "sz"
    if len(digits) <= 5:
        return "hk"
    return "unknown"


# 常见 AH 同股同权（港股 5 位 → A 股 6 位）；无 A 股则不在此表，可用手工「A股对照」列
HK_TO_A_SHARE: dict[str, str] = {
    "00386": "600028",  # 中国石化
    "00390": "600688",  # 上海石化
    "00489": "600808",  # 鞍钢股份
    "00548": "600548",  # 深高速
    "00564": "600011",  # 华能国际
    "00588": "600332",  # 白云山
    "00670": "000338",  # 潍柴动力
    "00696": "600876",  # 凯盛新能
    "00753": "000921",  # 海信家电
    "00763": "601808",  # 中海油服
    "00857": "601857",  # 中国石油
    "00874": "600585",  # 海螺水泥
    "00914": "600585",  # 海螺水泥（H）
    "00939": "601939",  # 建设银行
    "00941": "600941",  # 中国移动
    "00998": "601998",  # 中信银行
    "01055": "600029",  # 南方航空
    "01088": "600011",  # 华能国际（H）
    "01138": "000898",  # 鞍钢股份
    "01171": "601117",  # 中国化学
    "01186": "601186",  # 中国铁建
    "01288": "601328",  # 交通银行
    "01336": "601336",  # 新华保险
    "01398": "601398",  # 工商银行
    "01658": "601658",  # 邮储银行
    "01766": "601211",  # 国泰君安
    "01787": "601788",  # 光大证券
    "01898": "601898",  # 中煤能源
    "01919": "601919",  # 中远海控
    "02007": "601800",  # 中国交建
    "02068": "601068",  # 中铝国际
    "02318": "601318",  # 中国平安
    "02333": "601633",  # 长城汽车
    "02338": "601390",  # 中国中铁
    "02359": "601238",  # 广汽集团
    "02601": "601601",  # 中国太保
    "02628": "601628",  # 中国人寿
    "02883": "601808",  # 中海油田服务
    "02899": "601899",  # 紫金矿业
    "03606": "601318",  # 中国平安（旧 H 代码，兼容）
    "03968": "600036",  # 招商银行
    "03988": "601988",  # 中国银行
    "03969": "603993",  # 洛阳钼业
    "06030": "601318",  # 中国平安（另一 H 代码段，实际 2318）
    "06181": "601881",  # 中国银河
    "06886": "601985",  # 中国核电
    "02701": "300077",  # 国民技术
}

def normalize_stock_code(code: str) -> str:
    """统一代码字符串：A 股 6 位、港股 5 位。"""
    market = classify_market(code)
    digits = _digits_only(code)
    if market == "hk":
        return digits.zfill(5)
    if market in ("sh", "sz", "bj"):
        return digits.zfill(6)
    return digits


def resolve_a_share_proxy(
    code: str,
    *,
    explicit_proxy: str | None = None,
) -> str | None:
    """
    解析用于 K 线/布林的 A 股代码。
    - A 股/北交所：返回自身 6 位代码
    - 港股等：先读 explicit_proxy（持仓.xlsx「A股对照」列），再查 HK_TO_A_SHARE
    - 无对照：None
    """
    market = classify_market(code)
    if market in ("sh", "sz", "bj"):
        return normalize_stock_code(code)
    if explicit_proxy is not None and str(explicit_proxy).strip():
        exp = str(explicit_proxy).strip()
        if classify_market(exp) in ("sh", "sz", "bj"):
            return normalize_stock_code(exp)
        return None
    if market == "hk":
        return HK_TO_A_SHARE.get(normalize_stock_code(code))
    return None


def market_label(code: str) -> str:
    m = classify_market(code)
    return {"sh": "上证", "sz": "深证", "bj": "北交所", "hk": "港股"}.get(m, "非A股")


def gtimg_symbol(code: str) -> str | None:
    """腾讯 qt.gtimg 行情前缀（A 股 sh/sz/bj，港股 hk）。"""
    market = classify_market(code)
    norm = normalize_stock_code(code)
    if market == "hk":
        return f"hk{norm}"
    if market == "sh":
        return f"sh{norm}"
    if market == "bj":
        return f"bj{norm}"
    if market == "sz":
        return f"sz{norm}"
    return None


def fetch_spot_price(code: str) -> float | None:
    """从腾讯行情接口获取现价（A 股/北交所/港股，单位：元或港元）。"""
    sym = gtimg_symbol(code)
    if not sym:
        return None
    url = f"https://qt.gtimg.cn/q={sym}"
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
