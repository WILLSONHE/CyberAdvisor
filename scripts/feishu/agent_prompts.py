"""飞书 Bot → Cloud Agent 的 prompt 组装（只读项目 Wiki/持仓，不写库）。"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bilibili.env import ROOT
from portfolio_utils import filter_pool_md, filter_portfolio_md

TRADE_TEMPLATE = os.path.join(ROOT, "trade_template.md")
MARKET_DAILY = os.path.join(ROOT, "Wiki", "数据", "市场状态日报.md")
POOL_DAILY = os.path.join(ROOT, "Wiki", "数据", "标的池日报.md")
ANALYSIS_SPEC = os.path.join(ROOT, "ANALYSIS_REPORT_SPEC.md")


def _read(path: str, *, max_chars: int = 12000) -> str:
    if not os.path.isfile(path):
        return f"（缺失：{os.path.relpath(path, ROOT)}）"
    text = open(path, encoding="utf-8").read()
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n…（截断）…\n\n" + text[-half:]


def _wiki_context(*, max_chars: int = 14000) -> str:
    from ai_sim.wiki_context import build_wiki_context

    return build_wiki_context(max_chars=max_chars)


def _local_paths_note() -> str:
    from tdx_vipdoc import vipdoc_root

    root = vipdoc_root()
    ok = os.path.isdir(root)
    return (
        f"vipdoc 根目录 `{root}`（含 `ds/lday` 扩展日线、`ds/minline` 1 分钟；T0002 为客户端缓存 `{os.environ.get('TDX_T0002', r'C:\\new_tdx64\\T0002')}`）。"
        + " Cloud Agent 在云端运行、**不能**直接读你电脑上的文件夹；"
        "下方「本机只读数据」由 Bot 在本机抓取后嵌入 prompt。"
        " `CURSOR_CLOUD_REPO`（GitHub）可选，仅作 Wiki 补充，**不能**替代 vipdoc。"
    )


def _sim_portfolio_block() -> str:
    from sim_portfolio import SIM_XLSX, format_sim_summary

    if not os.path.isfile(SIM_XLSX):
        return f"（`{SIM_XLSX}` 不存在）"
    return format_sim_summary(max_rows=30)


def _compact_stock_block(code: str, name: str) -> str:
    """持仓标的轻量快照：缠论（第一）+ 七轨 + vipdoc + outlook。"""
    from bollinger_utils import bollinger_for_code, export_outlook_horizon
    from chan.analyze import analyze_code
    from chan.report import format_chan_markdown
    from outlook_params import load_params
    from report_data import fetch_vipdoc_stats

    code = str(code).zfill(6)
    ch = analyze_code(code, name=name, has_position=True)
    chan_s = format_chan_markdown(ch).strip() if ch.get("ok") else f"缠论：{ch.get('error', '—')}"

    b = bollinger_for_code(code)
    if not b or b.get("error"):
        return f"**{name}**（{code}）\n{chan_s}\n布林不可用 — {b.get('error') if b else '无'}"

    params = load_params()
    ke = b.get("kline_extra") or {}
    ol_parts: list[str] = []
    for days in (1, 3, 7):
        h = export_outlook_horizon(b, days=days, kline_extra=ke, params=params)
        ml = h.get("most_likely") or {}
        ol_parts.append(f"{days}日 {ml.get('price', '—')}（{ml.get('label', '')}）")

    vip = fetch_vipdoc_stats(code)
    if vip.get("stdev_pct") is not None:
        vip_s = f"vipdoc σ {vip['stdev_pct']}%（近{vip.get('lookback', 20)}日）"
    else:
        vip_s = str(vip.get("error") or "无 vipdoc 本地日 K")

    return (
        f"**{name}**（{code}）现价 **{b.get('price')}**\n"
        f"{chan_s}\n"
        f"  七轨 **{b.get('zone')}** | {vip_s}\n"
        f"  最有可能价：{' | '.join(ol_parts)}"
    )


def _holdings_local_data(holder: str, *, max_stocks: int = 15) -> str:
    from portfolio_utils import holdings_for_holder, pad_a_share_code

    rows = holdings_for_holder(holder)
    if not rows:
        return "（该持有人无 A 股持仓行）"
    blocks: list[str] = []
    for h in rows[:max_stocks]:
        name = str(h.get("name") or "").strip()
        code = pad_a_share_code(h.get("code", ""))
        if not code or len(code) != 6 or not code.isdigit():
            blocks.append(f"- **{name}**（{code or '—'}）：非 6 位 A 股，跳过 vipdoc/布林")
            continue
        blocks.append(_compact_stock_block(code, name))
    if len(rows) > max_stocks:
        blocks.append(f"… 另有 {len(rows) - max_stocks} 只未展开")
    return "\n\n".join(blocks)


def build_sug_prompt(holder: str, *, session: str | None = None) -> str:
    import os

    session_note = ""
    if session == "早盘":
        session_note = "本次为 **早盘回顾**（上午收盘后），禁止写「收盘前必盯」等前瞻表述。"
    elif session == "午盘":
        session_note = "本次为 **午盘回顾**（全天收盘后），须写实际收盘点位及相对 4033/4130 纪律。"

    skip_vipdoc = (os.environ.get("SKIP_VIPDOC_TODAY") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    vipdoc_note = ""
    if skip_vipdoc:
        vipdoc_note = (
            "8. **今日跳过 vipdoc 批刷新**（通达信 new_tdx64 当日 .day 未就绪）："
            "§七 七轨/σ/1·3·7 仅引用下方快照与 market 日报；"
            "若快照标注 vipdoc 不可用，写「数据缺口」勿编造当日 K。"
        )

    return f"""你是 CyberAdvisor 交易策略助手。根据下方 **只读上下文** 为持有人 **{holder}** 生成完整 sug 报告。

## 硬性约束
1. **仅输出 Markdown 正文**（从 `## 今日一句话` 起），不要修改任何仓库文件、不要执行 git、不要写 SugVault。
2. 严格遵循 `trade_template.md` 结构与金额格式（千位逗号 + 两位小数）。
3. 表述须可核查，标注 Wiki/日更/研报来源；**§零 缠论须先于布林/outlook**。
4. {session_note or "未指定盘次：按当前最新日更与大盘状态撰写。"}
5. 金额单位用「元」；不推荐科创板（688xxx）新开仓。
6. §七 1/3/7 日须引用下方「持仓标的本机快照」中的 **最有可能价** 与 vipdoc σ；**须含「大盘与指数预测」短表**（上证/深成指/创业板/科创50/沪深300 + 板块代表股，1/3/7 日最有可能价）；AI 模拟盘章节参考「模拟持仓」。
7. §八 只写复盘结论；**禁止**写「未在本环境执行」「outlook_tracker 未运行」等元信息（登记由本机归档脚本完成）。
{vipdoc_note}

## 数据来源
{_local_paths_note()}

## trade_template.md
{_read(TRADE_TEMPLATE, max_chars=8000)}

## Wiki 策略上下文
{_wiki_context()}

## 持有人持仓（portfolio.md 章节）
{filter_portfolio_md(holder)}

## 持仓标的本机快照（缠论第一 + vipdoc + 七轨 + 1/3/7 最有可能价）
{_holdings_local_data(holder)}

## 模拟持仓（AI 自主盘 · 本机 xlsx）
{_sim_portfolio_block()}

## 标的池 + 做 T（标的池日报 该持有人章节）
{filter_pool_md(holder)}

## 市场状态日报
{_read(MARKET_DAILY, max_chars=6000)}

## 标的池日报（全文摘要）
{_read(POOL_DAILY, max_chars=4000)}

请直接输出完整 sug Markdown；§八 只写复盘结论，**禁止**写「未在本环境执行 outlook_tracker」等元信息。
"""


def build_qry_prompt(question: str) -> str:
    return f"""你是 CyberAdvisor 财经 Wiki 助手。基于下方 **只读 Wiki 上下文** 深度回答用户问题。

## 硬性约束
1. **仅输出 Markdown 回答**，不要修改仓库、不要创建文件。
2. 综合多页 Wiki（方法论、日更、市场分析、标的追踪、其他材料索引）；矛盾处注明日期与来源。
3. 无法从上下文确定时明确说「Wiki 未覆盖」，勿编造点位或持仓。
4. 结构：结论摘要 → 依据（[[双链页面名]]）→ 操作建议（若有）→ 风险/时效说明。

## 用户问题
{question.strip()}

## Wiki 策略上下文
{_wiki_context(max_chars=16000)}

请用中文回答，适当使用 [[页面名]] 双链。
"""


def guess_stock_in_text(text: str) -> tuple[str, str]:
    """从自由文本猜测 A 股代码与名称（只读本地映射）。"""
    from outlook_universe import EXTRA_NAME_CODES, resolve_name_to_code

    m = re.search(r"\b(\d{6})\b", text)
    if m:
        code = m.group(1)
        return code, code

    for pat in (
        r"([\u4e00-\u9fff]{2,10})的(?:分析|研究)报告",
        r"(?:分析|研究)报告[：:\s]*([\u4e00-\u9fff]{2,10})",
        r"(?:关于|针对)([\u4e00-\u9fff]{2,10})",
    ):
        hit = re.search(pat, text)
        if hit:
            name = hit.group(1).strip()
            code = resolve_name_to_code(name)
            if code:
                return code, name

    name_map: dict[str, str] = {}
    try:
        from fine_screen import TRACK_STOCKS
        from outlook_universe import _coarse_name_map

        name_map.update(TRACK_STOCKS)
        name_map.update(EXTRA_NAME_CODES)
        name_map.update(_coarse_name_map())
    except Exception:
        pass

    for name in sorted(name_map, key=len, reverse=True):
        if len(name) >= 2 and name in text:
            code = resolve_name_to_code(name) or name_map.get(name, "")
            if code:
                return str(code).zfill(6), name
    return "", ""


def _stock_context_block(code: str, name: str) -> str:
    """Bot 本机只读抓取：布林、outlook、补充数据、追踪摘要。"""
    from bollinger_utils import bollinger_for_code, build_stock_verdict, export_outlook_horizon
    from outlook_params import load_params
    from report_data import enrich_stock, format_enrichment_markdown, format_gaps_markdown
    from wiki import track_stock

    code = str(code).zfill(6)
    b = bollinger_for_code(code)
    if not b or b.get("error"):
        return f"（{name} {code} 布林数据不可用：{b.get('error') if b else '无'}）"

    params = load_params()
    ke = b.get("kline_extra") or {}
    outlook_parts: list[str] = []
    for days in (1, 3, 7):
        h = export_outlook_horizon(b, days=days, kline_extra=ke, params=params)
        outlook_parts.append(f"#### {days}日\n```json\n{json.dumps(h, ensure_ascii=False, indent=2)}\n```")

    try:
        enr = enrich_stock(code, name=name)
        enrich_md = format_enrichment_markdown(enr)
        gaps_md = format_gaps_markdown(enr.get("gaps") or [])
    except Exception as exc:
        enrich_md = f"（补充数据抓取失败：{exc}）"
        gaps_md = ""

    verdict = build_stock_verdict(code, name=name, has_position=False, index_ok_buy=True)
    trk = track_stock(name or code)
    if len(trk) > 6000:
        trk = trk[:3000] + "\n…（截断）\n" + trk[-2500:]

    return f"""### 标的快照 {name}（{code}）
- 现价 **{b.get('price')}** | 七轨 **{b.get('zone')}**

{verdict.get('markdown', '')}

{chr(10).join(outlook_parts)}

{enrich_md}

{gaps_md}

### Wiki 追踪摘要
{trk}
"""


def build_freeform_prompt(user_request: str) -> str:
    code, name = guess_stock_in_text(user_request)
    spec_excerpt = _read(ANALYSIS_SPEC, max_chars=5000)
    stock_block = _stock_context_block(code, name) if code else "（未能从请求中识别具体 A 股代码；请基于 Wiki 与常识作答，勿编造精确现价。）"

    if code and ("报告" in user_request or "分析" in user_request):
        task_type = "单标的深度分析报告"
        structure = """
须含章节：**专业名词解释**、基本面/同业对比（2–4 只竞对）、七轨布林与操作、**§七 1/3/7 日**（含 most_likely 与概率表）、风险与 Wiki 链接。
遵循 ANALYSIS_REPORT_SPEC；飞书生成，未登记 outlook_tracker。
"""
    else:
        task_type = "自由分析任务"
        structure = "结构清晰、可核查；涉及点位/标的时标注依据与时效。"

    return f"""你是 CyberAdvisor 分析助手。完成用户的 **{task_type}**。

## 硬性约束
1. **仅输出 Markdown 正文**，不要修改仓库、不要写 SugVault/Wiki。
2. {structure.strip()}
3. 金额用「元」且千位逗号；不推荐科创板（688xxx）新开仓。

## 用户请求
{user_request.strip()}

## ANALYSIS_REPORT_SPEC（摘要）
{spec_excerpt}

## 本机只读数据（Bot 运行电脑抓取，优先采用）
{stock_block}

## Wiki 策略上下文
{_wiki_context(max_chars=12000)}

## 市场状态日报
{_read(MARKET_DAILY, max_chars=4000)}

请直接输出完整 Markdown 报告。
"""


def output_basename(kind: str, label: str, *, session: str | None = None) -> str:
    today = date.today().isoformat()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:40]
    sess = f"_{session}" if session else ""
    return f"{today}_{kind}_{safe}{sess}.md"
