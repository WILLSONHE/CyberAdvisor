"""单标的分析报告 · 专业名词解释（必写章节）。"""
from __future__ import annotations

from typing import Any


def _ml_cell(outlook: dict[str, Any] | None, key: str) -> str:
    if not outlook:
        return "—"
    ml = outlook.get(key) or {}
    if not ml:
        return "—"
    return f"{ml.get('price')}（{ml.get('label')} {ml.get('pct_vs_now', 0):+.2f}%）"


def format_glossary_markdown(
    b: dict[str, Any],
    *,
    outlook: dict[str, Any] | None = None,
    name: str = "",
    extra_rows: list[tuple[str, str, str]] | None = None,
) -> str:
    """生成「专业名词解释」章节 Markdown（定义 + 对本标的的含义）。"""
    stock = name or b.get("name") or b.get("code") or "本标的"
    zone = b.get("zone") or "—"
    mid = b.get("mid")
    price = b.get("price")
    vip = b.get("vipdoc") or {}

    rows: list[tuple[str, str, str]] = [
        (
            "七轨（顶/二/中/四/五/底）",
            "20 日 MA 为中轨；±1σ=二/四轨，±2σ=五轨，±3σ=顶/底轨；描述现价在通道中的相对位置。",
            f"现价 {price} 位于 **{zone}**；中轨 {mid}，四轨 {b.get('track4')}，二轨 {b.get('track2')}。",
        ),
        (
            "20日MA / 相对20MA",
            "近 20 个交易日收盘价均线；「相对20MA 高低」= 现价距中轨的百分比。",
            f"距中轨 **{b.get('pct_vs_mid', 0):+.1f}%**（{ '低于' if (b.get('pct_vs_mid') or 0) < 0 else '高于' }均线）。",
        ),
        (
            "带宽",
            "（顶轨−底轨）/ 中轨 ×100%；越大波动越宽，收敛表示波动收窄。",
            f"带宽 **{b.get('bandwidth_pct')}%**{'，通道收敛' if b.get('converging') else ''}。",
        ),
        (
            "4033 / L1 清仓线",
            "上证机械清仓纪律线；有效跌破则降仓、原则上禁止新开仓。",
            "报告期上证已破 L1 → **不宜新开仓/战略加仓**；存量仅做 T 或持有。",
        ),
        (
            "做 T 进 / 做 T 出",
            "日内或短周期低买高卖，**不增加战略仓位**；单次常用 ≤ 持仓 1/4。",
            "位于四轨附近时标的池标 🔵 适合 T 进；反弹至中轨下方可 T 出减压。",
        ),
        (
            "锚点价",
            "综合现价、中轨、轨道与 MA 斜率算出的技术倾向中心价（非预测均值）。",
            "见 §七各周期「技术锚点价」行；与「最有可能价位」不同（后者为最高概率挡位）。",
        ),
        (
            "最有可能价位",
            "1日=带内概率最高挡；3日=离**技术锚点**最近的挡；7日=通道上下段时取离**中轨**最近挡（Wiki 均值回归）。",
            f"1日 {_ml_cell(outlook, 'd1_most_likely')} | "
            f"3日 {_ml_cell(outlook, 'd3_most_likely')} | "
            f"7日 {_ml_cell(outlook, 'd7_most_likely')}。",
        ),
        (
            "倾向概率 / 概率加权漂移",
            "挡位表 % 为带内相对权重（合计 100%）；中心=现价×权重+锚点×权重，σ≈vipdoc 半带宽；七轨略加成。",
            "**不是**涨跌幅本身；看整体位移请读表下「概率加权较现价漂移」。",
        ),
        (
            "vipdoc 本地日 K",
            f"通达信 `TDX_VIPDOC` 本地 .day 文件；用于实现波动 σ 与区间加宽（近 {vip.get('lookback', 20)} 日）。",
            (
                f"σ **{vip.get('stdev_pct')}%**，平均绝对涨跌 **{vip.get('mean_abs_pct')}%**"
                if vip.get("stdev_pct") is not None
                else "本 tick 无本地文件，区间退回 mootdx/布林公式。"
            ),
        ),
        (
            "ROE / PE / PB",
            "ROE=净利/净资产；PE=市值/净利；PB=市值/净资产。",
            f"ROE { (b.get('finance') or {}).get('roe', '—') }% 与 PE 偏高并存时需核对盈利基数（见 §三）。",
        ),
    ]

    if extra_rows:
        rows.extend(extra_rows)

    lines = [
        "## 专业名词解释",
        "",
        f"> 对 **{stock}** 报告中出现的纪律/技术/数据用语：**是什么 → 对本标的意味着什么**。",
        "",
        "| 术语 | 含义 | 对" + stock + " |",
        "|------|------|------|",
    ]
    for term, meaning, interp in rows:
        lines.append(f"| **{term}** | {meaning} | {interp} |")
    lines.append("")
    return "\n".join(lines)
