"""缠论多级别 K 线 + MACD 背驰 + 买卖点启发式（报告/模拟盘第一优先级）。"""
from chan.analyze import analyze_code, analyze_index
from chan.guidance import build_chan_guidance
from chan.policy import compact_chan
from chan.report import format_chan_brief, format_chan_markdown

__all__ = [
    "analyze_code",
    "analyze_index",
    "build_chan_guidance",
    "compact_chan",
    "format_chan_brief",
    "format_chan_markdown",
]
