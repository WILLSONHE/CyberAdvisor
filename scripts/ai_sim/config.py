"""AI 自主模拟盘配置。"""
from __future__ import annotations

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TOTAL_CASH = 5_000_000.0
SIM_HOLDER = "AI"
SIM_XLSX = os.path.join(ROOT, "模拟持仓.xlsx")
DAILY_REPORT = os.path.join(ROOT, "Wiki", "数据", "市场状态日报.md")
TRACK_DIR = os.path.join(ROOT, "Wiki", "博主", "标的追踪")
TICK_ROOT = os.path.join(ROOT, "Raw", "每15分钟市场数据")
JOURNAL_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟交易日志.md")

LINE_CLEAR = 4033
LINE_FULL = 4130

MAX_POSITIONS = 5
MAX_WEIGHT = 0.25  # 单标的最大占总资金比例
MIN_TRADE_YUAN = 50_000.0

# 4033 软约束：破线目标股票仓位占比；线上正常目标
EQUITY_TARGET_BELOW_CLEAR = 0.35
EQUITY_TARGET_NORMAL = 0.75

# 交易节奏：每 15 分钟采集；仅在有明确信号时成交
BUY_MIN_GAP = 0.05  # 仓位低于目标至少 5% 才考虑买入
NO_BUY_BELOW_CLEAR = True  # 上证 < 4033 不开新仓
MAX_BUYS_PER_TICK = 1  # 单次 tick 最多新开 1 笔
REBALANCE_MIN_HOLD_DAYS = 1  # 建仓当日不因「超配」强制卖出
PRICE_SANITY_BAND = 0.15  # 卖出价偏离成本超过 15% 时改用 tick/成本价

# 短线：持仓超过 N 日且盈利可减仓；长线标签仅日志
SHORT_HOLD_DAYS = 5
STOP_LOSS_PCT = -5.0
TAKE_PROFIT_PCT = 12.0

# 交易时段 tick（本地时间 HH:MM）
SESSION_TICKS: tuple[tuple[str, ...], ...] = (
    ("09:30", "09:45", "10:00", "10:15", "10:30", "10:45", "11:00", "11:15", "11:30"),
    ("13:00", "13:15", "13:30", "13:45", "14:00", "14:15", "14:30", "14:45", "15:00"),
)
