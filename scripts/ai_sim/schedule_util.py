"""交易时段与 tick 时间判断。"""
from __future__ import annotations

from datetime import datetime, time

from ai_sim.config import SESSION_TICKS
from trading_calendar import is_trading_day


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


LUNCH_TICKS = frozenset({"11:45"})
PRE_OPEN_TICK = "09:15"
POST_CLOSE_TICK = "15:15"


def _hm_from_tick_label(label: str) -> str:
    """HHMM 或 HH:MM → HH:MM。"""
    s = label.strip().replace(":", "")
    if len(s) >= 4 and s[:4].isdigit():
        return f"{s[:2]}:{s[2:4]}"
    return label.strip()


def tick_phase_at(hm: str) -> str:
    """由 tick 时刻 HH:MM 判定阶段。"""
    if hm == PRE_OPEN_TICK:
        return "pre_open"
    if hm in LUNCH_TICKS:
        return "lunch"
    if hm == POST_CLOSE_TICK:
        return "post_close"
    return "intraday"


def tick_phase(now: datetime | None = None, *, tick_label: str = "") -> str:
    """pre_open | intraday | lunch | post_close"""
    if tick_label:
        return tick_phase_at(_hm_from_tick_label(tick_label))
    now = now or datetime.now()
    return tick_phase_at(now.strftime("%H:%M"))


def tick_phase_label(phase: str) -> str:
    return {
        "pre_open": "早盘前策略",
        "intraday": "盘中",
        "lunch": "午休复盘",
        "post_close": "收盘复盘",
    }.get(phase, phase)


def is_in_session(now: datetime | None = None) -> bool:
    """是否允许采集/Agent（含早盘前、午休、收盘后计划 tick）。"""
    now = now or datetime.now()
    if not is_trading_day(now.date()):
        return False
    if is_scheduled_tick(now):
        return True
    t = now.time()
    morning = time(9, 30) <= t <= time(11, 30)
    afternoon = time(13, 0) <= t <= time(15, 0)
    return morning or afternoon


def is_scheduled_tick(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    return is_trading_day(now.date()) and now.strftime("%H:%M") in all_tick_times()
