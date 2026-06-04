"""字幕整理为连贯讲稿 + 智能选轨。"""
from __future__ import annotations

import re

from .asr_fixes import looks_like_mismatch
from .rw_format import format_transcript

FINANCE_KW = re.compile(
    r"指数|A股|复盘|半导体|华为|MLCC|大盘|充电|K线|房地产|港股|"
    r"4033|4130|4200|磨底|科技|持仓|高盛|国家队|PCB|Rubin|Token|"
    r"美债|美联储|仓位|布林|主线|产业链|韬定律|再通胀|设置盘面|"
    r"抄底|牛市|急跌|周复盘|涨|跌|板块"
)


def score_subtitle(text: str, title: str = "") -> int:
    if not text or len(text.strip()) < 40:
        return -50
    if re.fullmatch(r"(音乐[♪\s]*)+", text.strip()):
        return -50
    score = len(FINANCE_KW.findall(text))
    # 标题关键词命中
    for word in re.findall(r"[\u4e00-\u9fff]{2,}", title):
        if word in text:
            score += 4
    if looks_like_mismatch(text, title):
        score -= 200
    return score


def pick_subtitle(subtitles: list[dict], title: str = "") -> tuple[str, str]:
    """返回 (语言标签, 正文) — 选财经相关度最高的轨。"""
    if not subtitles:
        return "", ""
    best: dict | None = None
    best_score = -9999
    for sub in subtitles:
        s = score_subtitle(sub.get("text", ""), title)
        # 轻微偏好人工中文字幕
        if not sub.get("ai") and sub.get("lan") in ("zh-CN", "zh-Hans"):
            s += 2
        if s > best_score:
            best_score = s
            best = sub
    if not best or best_score < 0:
        # 回退：旧逻辑
        manual = [s for s in subtitles if not s.get("ai")]
        pool = manual or subtitles
        zh = next((s for s in pool if s.get("lan") in ("zh-CN", "ai-zh", "zh-Hans")), None)
        chosen = zh or pool[0]
        return chosen.get("lan_doc") or chosen.get("lan") or "unknown", chosen.get("text", "")
    return best.get("lan_doc") or best.get("lan") or "unknown", best.get("text", "")


__all__ = ["format_transcript", "pick_subtitle", "score_subtitle"]
