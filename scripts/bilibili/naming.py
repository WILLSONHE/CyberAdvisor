"""Raw / 未审阅 文件名生成（对齐现有命名习惯）。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

INVALID_CHARS = re.compile(r'[\\/:*?"<>|\u200b\u200c\u200d\ufeff]')

PREFIX_RULES = [
    ("午盘补发", "午盘补发："),
    ("周末补充", "周末补充："),
    ("周复盘", "周复盘："),
    ("早盘", "早盘："),
    ("午盘", "午盘："),
    ("复盘", "复盘："),
    ("日更", "日更："),
    ("参考", "参考："),
]

DATE_PATTERNS = [
    re.compile(r"(20(\d{2})-(\d{2})-(\d{2}))"),
    re.compile(r"(\d{2})-(\d{2})-(\d{2})"),
]

DOT_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})")


def _sanitize(text: str, max_len: int = 80) -> str:
    text = INVALID_CHARS.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("https://", "https：//").replace("/", "，")
    return text[:max_len].rstrip("，. ")


def parse_dot_date(title: str, ref: datetime | None = None) -> str | None:
    """从标题解析 M.D 日期 → yy-mm-dd，如 5.18（复盘）→ 26-05-18。"""
    ref = ref or datetime.now()
    m = DOT_DATE.search(title)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    year = ref.year
    try:
        candidate = datetime(year, month, day)
    except ValueError:
        return None
    if candidate > ref + timedelta(days=1):
        year -= 1
        candidate = datetime(year, month, day)
    return candidate.strftime("%y-%m-%d")


def title_to_timestamp(title: str, pub_ts: int | None = None) -> int:
    if pub_ts and pub_ts > 0:
        return pub_ts
    ds = parse_dot_date(title)
    if not ds:
        return 0
    yy, mm, dd = ds.split("-")
    return int(datetime(2000 + int(yy), int(mm), int(dd)).timestamp())


def extract_date_str(title: str, pub_ts: int | None = None) -> str:
    ds = parse_dot_date(title)
    if ds:
        return ds
    for pat in DATE_PATTERNS:
        m = pat.search(title)
        if m:
            g = m.groups()
            if len(g) == 4:
                return f"{g[1]}-{g[2]}-{g[3]}"
            if len(g) == 3:
                return f"{g[0]}-{g[1]}-{g[2]}"
    if pub_ts and pub_ts > 0:
        return datetime.fromtimestamp(pub_ts).strftime("%y-%m-%d")
    return datetime.now().strftime("%y-%m-%d")


def classify_prefix(title: str) -> str:
    if "午盘补发" in title:
        return "午盘补发："
    if "周复盘" in title:
        return "周复盘："
    if "周末补充" in title:
        return "周末补充："
    if "（午盘" in title or "(午盘" in title or title.startswith("午盘"):
        return "午盘："
    if "（复盘" in title or "(复盘" in title or "复盘" in title:
        return "复盘："
    for keyword, prefix in PREFIX_RULES:
        if keyword in title:
            return prefix
    return "动态："


def raw_filename(title: str, pub_ts: int | None = None) -> str:
    prefix = classify_prefix(title)
    date_str = extract_date_str(title, pub_ts)
    core = _sanitize(title) or "无标题"
    return f"{prefix}{date_str}：{core}.md"


def pending_video_filename(title: str, bvid: str, pub_ts: int | None = None) -> str:
    date_str = extract_date_str(title, pub_ts)
    core = _sanitize(title) or bvid
    return f"{date_str}_{bvid}_{core}.md"
