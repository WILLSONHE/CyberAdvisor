"""项目统一日线入口：vipdoc → Tushare qfq → mootdx（见 tushare_daily.resolve_daily_bars）。"""
from __future__ import annotations

from datetime import date

import pandas as pd

from tushare_daily import resolve_daily_bars


def get_daily_bars(
    code: str,
    *,
    limit: int = 120,
    min_bars: int = 25,
    as_of: date | str | None = None,
) -> pd.DataFrame | None:
    as_of_d: date | None = None
    if as_of is not None:
        as_of_d = date.fromisoformat(str(as_of)[:10])
    return resolve_daily_bars(code, limit=limit, min_bars=min_bars, as_of=as_of_d)
