"""交易时段与 tick 时间判断。"""
from __future__ import annotations

from datetime import date, datetime, time

from ai_sim.config import SESSION_TICKS


def all_tick_times() -> list[str]:
    out: list[str] = []
    for session in SESSION_TICKS:
        out.extend(session)
    return out


def nearest_tick_label(now: datetime | None = None) -> str:
    """当前时刻对应的 tick 标签 HHMM；非交易时段取最近已过的 tick 或当前 HHMM。"""
    now = now or datetime.now()
    hm = now.strftime("%H:%M")
    ticks = all_tick_times()
    if hm in ticks:
        return hm.replace(":", "")
    # 找当天最后一个 <= 当前时间的 tick
    past = [t for t in ticks if t <= hm]
    if past:
        return past[-1].replace(":", "")
    return hm.replace(":", "")


def is_trading_day(d: date | None = None) -> bool:
    d = d or date.today()
    return d.weekday() < 5


def is_in_session(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if not is_trading_day(now.date()):
        return False
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    return morning or afternoon


def is_scheduled_tick(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return is_trading_day(now.date()) and now.strftime("%H:%M") in all_tick_times()
