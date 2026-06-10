"""AI 自主模拟盘配置。"""
from __future__ import annotations

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TOTAL_CASH = 5_000_000.0
SIM_HOLDER = "AI"
SIM_XLSX = os.path.join(ROOT, "模拟持仓.xlsx")
DAILY_REPORT = os.path.join(ROOT, "Wiki", "数据", "市场状态日报.md")
TRACK_DIR = os.path.join(ROOT, "Wiki", "内容源", "标的追踪")
TICK_ROOT = os.path.join(ROOT, "Raw", "每15分钟市场数据")
JOURNAL_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟交易日志.md")

MAX_POSITIONS = 5
MAX_WEIGHT = 0.25  # 单标的最大占总资金比例
MIN_TRADE_YUAN = 50_000.0

# 默认中性；仓位/止损/止盈/是否成交由 Agent 读 Wiki 后写入 override
EQUITY_TARGET_NORMAL = 0.75
BUY_MIN_GAP = 0.05
MAX_BUYS_PER_TICK = 1
REBALANCE_MIN_HOLD_DAYS = 1
PRICE_SANITY_BAND = 0.15

# 短线：持仓超过 N 日且盈利可减仓；长线标签仅日志
SHORT_HOLD_DAYS = 5
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 12.0

# 交易时段 tick（本地时间 HH:MM）
# 09:15 早盘前 | 11:45 午休复盘 | 15:15 收盘后 | 中间为盘中 15 分钟（共 21 个 tick）
SESSION_TICKS: tuple[tuple[str, ...], ...] = (
    ("09:15",),
    ("09:30", "09:45", "10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30"),
    ("11:45",),
    ("13:00", "13:15", "13:30", "13:45", "14:00", "14:15", "14:30", "14:45", "15:00"),
    ("15:15",),
)

STRATEGY_MD = os.path.join(ROOT, "Wiki", "数据", "AI模拟盘策略.md")
