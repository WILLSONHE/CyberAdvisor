"""缠论 Markdown 输出。"""
from __future__ import annotations

from typing import Any

from chan.guidance import build_chan_guidance


def format_chan_brief(
    summary: dict[str, Any],
    *,
    has_position: bool | None = None,
    include_guidance: bool = False,
) -> str:
    if not summary.get("ok"):
        return f"缠论：{summary.get('error', '分析失败')}"
    bp = summary.get("buy_point", "—")
    act = summary.get("action", "—")
    head = (
        f"缠论 {summary.get('structure', '—')} | {bp} | 动作={act} | "
        f"保护≈{summary.get('protect_price', '—')} | 分={summary.get('score', 0):+.1f}"
    )
    if include_guidance:
        guide = summary.get("guidance") or build_chan_guidance(summary, has_position=has_position)
        return f"{head} · 指引：{guide}"
    return head


def format_chan_markdown(summary: dict[str, Any], *, has_position: bool | None = None) -> str:
    if not summary.get("ok"):
        return f"- **缠论**：{summary.get('error', '分析失败')}\n"

    src = summary.get("sources") or {}
    src_s = " / ".join(f"{k}={v}" for k, v in src.items())
    guide = build_chan_guidance(summary, has_position=has_position)
    lines = [
        f"- **缠论（第一优先级）**：{summary.get('structure')} | **{summary.get('buy_point')}**",
        f"  - **操作指引**：{guide}",
        f"  - 理由：{summary.get('buy_reason', '—')}",
        f"  - 中枢区间 ZD≈**{summary.get('ZD')}** ~ ZG≈**{summary.get('ZG')}** | 保护位≈**{summary.get('protect_price')}**",
        f"  - 建议动作：**{summary.get('action')}**（score {summary.get('score', 0):+.1f}）",
        f"  - 数据源：{src_s or '—'}",
    ]
    dd = summary.get("divergence_down") or {}
    if dd.get("divergence"):
        lines.append(
            f"  - 底背驰：价 {dd.get('price1')}→{dd.get('price2')}，MACD面积 {dd.get('area1')}→{dd.get('area2')}"
        )
    du = summary.get("divergence_up") or {}
    if du.get("divergence"):
        lines.append(
            f"  - 顶背驰：价 {du.get('price1')}→{du.get('price2')}，MACD面积 {du.get('area1')}→{du.get('area2')}"
        )
    lv = summary.get("levels") or {}
    h60 = lv.get("60m") or {}
    if h60.get("ok"):
        lines.append(
            f"  - 60min：{h60.get('trend')} | ZD/ZG {h60.get('ZD')}/{h60.get('ZG')} | hist {h60.get('macd_hist')}"
        )
    return "\n".join(lines) + "\n"


def format_chan_section_for_report(codes: list[tuple[str, str]], *, index_code: str = "000001") -> str:
    """报告用缠论专节。"""
    from chan.analyze import analyze_code, analyze_index

    lines = [
        "## 缠论结构（第一优先级）",
        "",
        "> 依据 [[缠论]] · [[缠论-背驰与买卖点]]；**优先于**布林七轨与 outlook 概率。",
        "",
    ]
    idx = analyze_index(index_code)
    lines.append("### 指数")
    lines.append("")
    lines.append(format_chan_markdown(idx, has_position=False).rstrip())
    lines.append("")
    if codes:
        lines.append("### 标的")
        lines.append("")
        for code, name in codes:
            s = analyze_code(code, name=name, has_position=True)
            lines.append(f"#### {name or code}（{code}）")
            lines.append("")
            lines.append(format_chan_markdown(s, has_position=True).rstrip())
            lines.append("")
    return "\n".join(lines)
