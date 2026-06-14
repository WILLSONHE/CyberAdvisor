"""缠论结论 → 可操作中文指引（报告 / 看板 / sug 共用）。"""
from __future__ import annotations

from typing import Any


def _fmt_price(v: Any) -> str:
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v) if v is not None else "—"


def _trend_phrase(summary: dict[str, Any]) -> str:
    t = summary.get("trend_day") or summary.get("structure") or "—"
    if t == "上涨":
        return "近段走势仍标注为**上涨**（高低点整体抬高）"
    if t == "下跌":
        return "近段走势为**下跌**"
    if "盘整" in str(t):
        return "近段处于**盘整/中枢震荡**"
    return f"走势类型：**{t}**"


def build_chan_guidance(
    summary: dict[str, Any],
    *,
    has_position: bool | None = None,
) -> str:
    """生成一句完整操作指引；has_position 未知时合并无仓/有仓要点。"""
    if not summary.get("ok"):
        return f"缠论数据不可用：{summary.get('error', '请检查 K 线源')}。"

    bp = str(summary.get("buy_point") or "无明确买卖点")
    prot = _fmt_price(summary.get("protect_price"))
    zd = _fmt_price(summary.get("ZD"))
    zg = _fmt_price(summary.get("ZG"))
    trend = _trend_phrase(summary)
    action = str(summary.get("action") or "wait")

    if has_position is None:
        a = _guidance_body(bp, trend, prot, zd, zg, action, has_position=True)
        b = _guidance_body(bp, trend, prot, zd, zg, action, has_position=False)
        if a == b:
            return a
        return f"**有仓**：{a} **无仓**：{b}"

    return _guidance_body(bp, trend, prot, zd, zg, action, has_position=has_position)


def _guidance_body(
    bp: str,
    trend: str,
    prot: str,
    zd: str,
    zg: str,
    action: str,
    *,
    has_position: bool,
) -> str:
    pos = "已有持仓" if has_position else "当前无持仓"

    if bp.startswith("一买"):
        if has_position:
            return (
                f"{trend}，出现**{bp}**（下跌末端动能衰竭）。{pos}：以持有/观察为主，保护位 **{prot}**；"
                f"有效跌破则反弹假设失效，应减仓；未破保护前不宜恐慌清仓，亦勿追高加仓。"
            )
        return (
            f"{trend}，出现**{bp}**。{pos}：可纳入观察池，保护位 **{prot}**（约中枢下沿 ZD≈{zd}）；"
            f"须等指数无「一卖」且门禁允许后再**小仓试探**，止损参考保护位，非确认反转勿重仓。"
        )

    if bp.startswith("二买"):
        if has_position:
            return (
                f"{trend}，**{bp}**（上涨/盘整中的**回调**未破结构）。{pos}：趋势延续假设下以**持有**为主，"
                f"保护位 **{prot}**；回调结束可小幅加仓，跌破保护则按**趋势破坏**处理、减仓。"
            )
        return (
            f"{trend}，**{bp}**（**回调**至支撑区）。{pos}：门禁通过时可**分批建仓**，保护位 **{prot}**；"
            f"止损设于保护位下方，目标先看 ZG≈{zg} 一带，不追已远离回调低点的价位。"
        )

    if bp.startswith("三买"):
        if has_position:
            return (
                f"{trend}，**{bp}**（离开中枢后**回抽** ZG≈{zg} 未破）。{pos}：强势结构，以**持有/顺势**为主，"
                f"保护位 **{prot}**（回抽低点）；跌破 ZG 则三买叙事失效，应减仓。"
            )
        return (
            f"{trend}，**{bp}**（**回抽**确认离开中枢）。{pos}：可积极关注，保护位 **{prot}**；"
            f"回抽不破 ZG 且门禁允许时考虑建仓，跌破保护位则放弃本次介入。"
        )

    if bp.startswith("一卖"):
        if has_position:
            return (
                f"{trend}，**{bp}**（上涨**顶背驰**）。{pos}：优先**减仓或做 T 出**，保护位 **{prot}**；"
                f"不宜加仓；若指数同步一卖，全员新开仓门禁关闭。"
            )
        return (
            f"{trend}，**{bp}**。**{pos}**：**不开新多**；等待回调或结构重新走好后，再寻找二买/三买候选。"
            f"保护位 **{prot}** 供观察，非入场价。"
        )

    if bp.startswith("观望/空"):
        # 用户特别关心的组合：上涨 + 观望/空
        if has_position:
            return (
                f"{trend}，但现价已落至中枢下方，处于**{bp}**阶段（收盘低于 ZD≈{zd}）。{pos}：**不应开新仓/加仓**；"
                f"保护位 **{prot}**——有效跌破则多头结构失效，宜**减仓或至少停止加仓**；"
                f"若仅短期回落而趋势标签仍为上涨，等待站回 ZD 上方或出现新买点后再评估。"
            )
        return (
            f"{trend}，但已进入**{bp}**阶段（价在中枢下沿 ZD≈{zd} 之下）。{pos}：**不应开新多**；"
            f"保护位 **{prot}** 为结构参考；站回 ZD 上方或出现一/二买候选且门禁通过前，保持观望。"
            f"（「空」=不做多，非融券做空。）"
        )

    if bp == "无明确买卖点":
        if has_position:
            return (
                f"{trend}，**{bp}**（中枢 ZD≈{zd}~ZG≈{zg} 内震荡）。{pos}：**持有观望**，保护位 **{prot}**；"
                f"无新信号前不加仓；破保护减仓，突破 ZG 且放量再考虑加仓。"
            )
        return (
            f"{trend}，**{bp}**。{pos}：**不介入**，等待三类买点候选或方向明朗；"
            f"区间 ZD≈{zd}~ZG≈{zg}，保护位 **{prot}** 供监控。"
        )

    # fallback by action
    act_map = {
        "buy": "门禁允许时可考虑建仓",
        "hold_add": "持有，可小幅加仓",
        "hold": "持有观望",
        "wait": "不介入、不开新仓",
        "sell": "倾向减仓或清仓",
    }
    hint = act_map.get(action, "按 Wiki 纪律与门禁操作")
    return f"{trend}，标记 **{bp}**。{pos}：{hint}；保护位 **{prot}**。"
