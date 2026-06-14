"""analysis_id 生成与解析。"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

_ID_RE = re.compile(
    r"^graph-(?P<date>\d{4}-\d{2}-\d{2})-(?P<holder>[^-]+)-(?P<uid>[a-f0-9]{8})$",
    re.I,
)


def new_analysis_id(*, holder: str = "na", task: str = "sug") -> str:
    from trading_calendar import filename_trading_date, format_filename_date

    d = format_filename_date(filename_trading_date(datetime.now().date()))
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "", holder)[:24] or "na"
    uid = uuid.uuid4().hex[:8]
    return f"graph-{d}-{slug}-{uid}"


def parse_analysis_id(analysis_id: str) -> dict[str, str] | None:
    m = _ID_RE.match(analysis_id.strip())
    if not m:
        return None
    return m.groupdict()
