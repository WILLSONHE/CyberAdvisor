"""每 tick 调用 Cursor Cloud Agent 分析行情并调整 runtime 参数。"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from ai_sim.agent_client import AgentClientError, run_analysis_prompt
from ai_sim.config import DAILY_REPORT, JOURNAL_PATH
from ai_sim.data_requests import process_data_requests
from ai_sim.index_context import format_full_market_context
from ai_sim.portfolio_ops import active_positions, cash_available, total_assets
from ai_sim.runtime_params import PARAM_SCHEMA, apply_patch, defaults_for_agent, effective_all, snapshot
from ai_sim.schedule_util import tick_phase, tick_phase_label
from ai_sim.supplement_registry import registry_summary_for_prompt
from ai_sim.supplement_state import enabled_metrics, load_state
from ai_sim.wiki_context import build_wiki_context
from sim_portfolio import _portfolio_totals


def _load_env_file() -> None:
    from bilibili.env import apply_config_to_environ

    apply_config_to_environ()


def _read_tail(path: str, max_chars: int = 4000) -> str:
    if not os.path.isfile(path):
        return "（文件不存在）"
    text = open(path, encoding="utf-8").read()
    return text[-max_chars:] if len(text) > max_chars else text


def _read_json(path: str, max_chars: int = 12000) -> str:
    if not os.path.isfile(path):
        return "{}"
    text = open(path, encoding="utf-8").read()
    if len(text) > max_chars:
        data = json.loads(text)
        slim = {
            "timestamp": data.get("timestamp"),
            "tick": data.get("tick"),
            "indices": data.get("indices", [])[:8],
            "stocks": data.get("stocks", [])[:30],
            "_truncated": True,
        }
        return json.dumps(slim, ensure_ascii=False, indent=2)
    return text


def _positions_summary(tick_path: str = "") -> str:
    pos = active_positions()
    if pos.empty:
        return "当前无 AI 持仓"
    quotes: dict[str, dict] = {}
    if tick_path and os.path.isfile(tick_path):
        try:
            data = json.loads(open(tick_path, encoding="utf-8").read())
            from sim_portfolio import _norm_code

            for s in data.get("stocks", []):
                quotes[_norm_code(s.get("code", ""))] = s
        except Exception:
            pass
    lines = []
    for _, r in pos.iterrows():
        code = str(r.get("代码", "")).zfill(6)
        q = quotes.get(code, {})
        extra = ""
        vip = q.get("vipdoc") or {}
        if vip.get("stdev_pct") is not None:
            extra += f" | vipdoc σ {vip['stdev_pct']}%"
        ol = q.get("outlook_1d") or {}
        if ol.get("price"):
            extra += f" | 1日最有可能价 {ol['price']}（{ol.get('label', '')}）"
        if q.get("boll_zone"):
            extra += f" | 布林 {q['boll_zone']}"
        chan = q.get("chan") or {}
        if chan.get("buy_point"):
            extra += f" | 缠论 {chan.get('structure')} {chan.get('buy_point')} 动作={chan.get('action')}"
        lines.append(
            f"- {r['标的']}({code}) 成本{r['成本']} 现价{r.get('现价')} "
            f"股数{r['股数']} 盈亏比{r.get('盈亏比')}{extra}"
        )
    totals = _portfolio_totals(pos)
    lines.append(f"组合市值 {totals['total_mkt']:.2f} 元")
    return "\n".join(lines)


def build_prompt(tick_path: str, *, phase: str | None = None) -> str:
    phase = phase or tick_phase()
    phase_cn = tick_phase_label(phase)
    wiki_ctx = build_wiki_context(max_chars=16000)
    tick_json = _read_json(tick_path)
    journal_tail = _read_tail(JOURNAL_PATH, 3500)
    daily_tail = _read_tail(DAILY_REPORT, 3500)
    current = effective_all()
    defaults = defaults_for_agent()
    overrides = snapshot()
    schema_lines = []
    for k, spec in PARAM_SCHEMA.items():
        bounds = []
        if "min" in spec:
            bounds.append(f"min={spec['min']}")
        if "max" in spec:
            bounds.append(f"max={spec['max']}")
        schema_lines.append(f"- `{k}` ({spec['type'].__name__}, {', '.join(bounds) or 'bool'})")

    phase_instructions = {
        "pre_open": (
            "【早盘前策略 tick】阅读 Wiki 策略文件、宏观/选股框架、昨日市场日报。"
            "给出今日风险与仓位意图；**可选**调参；若无需改变请 hold_params=true。"
        ),
        "lunch": (
            "【午休复盘 tick】复盘 9:30–11:30 上午盘面与持仓；对照 Wiki 判断。"
            "为下午 session 定调；**可选**调参；允许维持不变。"
        ),
        "post_close": (
            "【收盘复盘 tick】复盘全天；对照市场状态日报与 Wiki；"
            "为次日 09:15 早盘前准备；**可选**调参。"
        ),
        "intraday": (
            "【盘中 tick】多数情况不调参；仅环境明显变化时改 1–3 个参数。"
        ),
    }.get(phase, "【盘中 tick】")

    market_ctx_txt = format_full_market_context(tick_path, days=10)
    registry_txt = registry_summary_for_prompt()
    enabled_txt = ", ".join(f"`{m}`" for m in load_state()["enabled"])

    from ai_sim.config import SIM_XLSX
    from tdx_vipdoc import vipdoc_root

    vip_root = vipdoc_root()
    local_paths = (
        f"- 模拟持仓 xlsx：`{SIM_XLSX}`（{'存在' if os.path.isfile(SIM_XLSX) else '缺失'}）\n"
        f"- vipdoc 日 K：`{vip_root}`（{'本机可读' if os.path.isdir(vip_root) else '未找到，设 TDX_VIPDOC'}）\n"
        f"- 最新 tick：`{tick_path}`\n"
        "- Cloud Agent **不能**直连本机文件夹；vipdoc/outlook/布林由 **本机 collector** 写入 tick JSON。"
    )

    return f"""你是 CyberAdvisor 项目的 AI 模拟盘风控分析师。

## 当前阶段
- **{phase_cn}**（`{phase}`）
- {phase_instructions}

## 你的职责
1. 阅读下方 **Wiki 策略上下文**（含缠论必读）、行情 tick（**`index_chan` + 每只 `chan`**）、持仓、日志与市场日报
2. 给出简短中文行情分析（3–6 句）；**先缠论结构，再指数纪律/布林**
3. **可选**调整规则引擎参数（充分分析后可 **维持不变**）
4. **可选**通过 `data_requests` **启用/禁用**已注册补充指标（不可自定义 HTTP URL）
5. **`buy_permission`**：须缠论无指数一卖/标的破保护位，且 Wiki 允许；`reason` 引用 `chan.buy_point`
6. 禁止建议直接改 xlsx 持仓；规则引擎 **缠论门禁优先于** Agent allow

## 补充指标 registry（仅 enable/disable/request）
{registry_txt}

**当前已启用**：{enabled_txt or '（默认）'}

- `enable` / `disable`：metric 须在 registry 中；**下一 tick 起生效**
- `request`：registry 无此 metric 时写入 `Wiki/数据/待扩展指标.md`
- **禁止**请求任意 HTTP 端点；未注册指标只能 `request` 登记

## Wiki 策略上下文
{wiki_ctx}

## 可调参数 schema（只能改这些键）
{chr(10).join(schema_lines)}

## 当前生效参数
```json
{json.dumps(current, ensure_ascii=False, indent=2)}
```

## config 默认值（供对比）
```json
{json.dumps(defaults, ensure_ascii=False, indent=2)}
```

## 已有 Agent override
```json
{json.dumps(overrides, ensure_ascii=False, indent=2)}
```

## 账户
- 现金：{cash_available():,.2f} 元
- 总资产：{total_assets():,.2f} 元

## 本机数据来源
{local_paths}

## 持仓
{_positions_summary(tick_path)}

## 最新 tick JSON（`{tick_path}`）

每只股票含 **chan**（缠论结构第一优先级）、**vipdoc**（本地日 K 波动 σ）、**outlook_1d/3d/7d**（最有可能价位）、**布林七轨**（`boll_zone` 等）。**买卖决策须以缠论结构为先**，布林/outlook 仅辅助；分析时写入 `buy_permission.reason`。

```json
{tick_json}
```

## 中长期市场上下文（判修复/上涨 — 必读）
{market_ctx_txt}

## 交易日志尾部
{journal_tail}

## 市场状态日报尾部
{daily_tail}

## 输出格式（必须严格 JSON，不要 markdown 围栏外的文字）
```json
{{
  "analysis": "行情分析…",
  "param_changes": {{}},
  "hold_params": true,
  "buy_permission": {{
    "allowed": false,
    "reason": "是否允许规则引擎本 tick 开新仓（须综合 Wiki 指数纪律 L1–L5、仓位管理、最新日更）",
    "confidence": "low|medium|high"
  }},
  "rebound_buy": {{
    "signal": false,
    "reason": "（兼容字段）同 buy_permission；修复/回补场景",
    "confidence": "low|medium|high"
  }},
  "data_requests": [
    {{"metric": "us_vix", "action": "enable", "reason": "判修复需 VIX 确认", "priority": "high"}}
  ],
  "notes": "给本地规则引擎的补充说明（可选）"
}}
```

`data_requests` 规则：
- 无需求时 **空数组 `[]`**
- `action`：`enable` | `disable` | `request`（未注册）
- `priority`：`high` | `medium` | `low`（high 且已注册 enable → 下一 tick 采集）
- 仅当分析 **确实缺少数据** 且 **影响决策** 时才提出；勿每 tick 滥填

规则：
- `param_changes` 为空对象 {{}} 表示本 tick 不调参
- 数值必须在 schema 边界内；**勿再使用** `NO_BUY_BELOW_CLEAR` / `EQUITY_TARGET_BELOW_CLEAR`（已废弃）
- **开新仓唯一门禁**：`buy_permission.allowed`（须读 Wiki 后显式 true/false）
- **若你认为 Wiki 指数纪律（含 L1 4033/4130）支持或禁止建仓**，在 `buy_permission.reason` 写清依据，并配合 `EQUITY_TARGET_NORMAL`、`MAX_BUYS_PER_TICK` 等参数
- **允许**在 Wiki 仍有效时因破 4033 而 `allowed=false` 或降 `EQUITY_TARGET_NORMAL`——这是你的判断，不是脚本硬编码
- **`rebound_buy.signal`**：与 `buy_permission.allowed` 等价（兼容）
- 综合 L1–L5、北向、60 分钟 K、缩量、最新日更；勿无依据滥开/滥关
- **L3** 4120/60 分钟底：回补硬科技叙事须引用
- `analysis` 须分层表述 L1 +（调整环境下）L3–L5
- 不要输出除 JSON 以外的内容
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"(\{.*\})", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise ValueError("Agent 回复中未找到 JSON")


def _format_token_usage_line(agent: dict[str, Any] | None) -> str:
    if not agent:
        return ""
    if agent.get("skipped"):
        return "- **Token 消耗**：—（Agent 跳过）"
    if not agent.get("ok", True):
        return "- **Token 消耗**：—（Agent 未成功）"
    meta = agent.get("agent_meta") or {}
    usage = meta.get("usage") or agent.get("usage")
    total = meta.get("token_total") if meta.get("token_total") is not None else agent.get("token_total")
    if total is None and isinstance(usage, dict):
        keys = ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens")
        if any(usage.get(k) is not None for k in keys):
            total = sum(int(usage.get(k) or 0) for k in keys)
    if total is None:
        return "- **Token 消耗**：—（API 未返回）"
    est = meta.get("usage_estimated") or (isinstance(usage, dict) and usage.get("estimated"))
    suffix = "（估算）" if est else ""
    parts = [f"**{int(total):,}**{suffix}"]
    if isinstance(usage, dict):
        inp, out = usage.get("inputTokens"), usage.get("outputTokens")
        if inp is not None or out is not None:
            parts.append(f"输入 {int(inp or 0):,} · 输出 {int(out or 0):,}")
        cr, cw = int(usage.get("cacheReadTokens") or 0), int(usage.get("cacheWriteTokens") or 0)
        if cr or cw:
            parts.append(f"缓存读 {cr:,} · 写 {cw:,}")
    return "- **Token 消耗**：" + " | ".join(parts)


def _format_agent_block(agent: dict[str, Any] | None) -> list[str]:
    if not agent:
        return []
    meta = agent.get("agent_meta") or {}
    lines = ["### Agent 分析", ""]
    if meta.get("url"):
        lines.append(f"- **Cloud Agent**：{meta['url']}")
    if meta.get("run_id"):
        lines.append(f"- **Run**：`{meta['run_id']}`")
    if meta.get("duration_ms") is not None:
        lines.append(f"- **耗时**：{meta['duration_ms']} ms")
    if meta.get("status"):
        lines.append(f"- **状态**：{meta['status']}")
    token_line = _format_token_usage_line(agent)
    if token_line:
        lines.append(token_line)
    lines.append("")

    if agent.get("skipped"):
        lines.append(f"*Agent 跳过：{agent.get('reason', '—')}*")
        lines.append("")
        return lines

    if not agent.get("ok", True):
        lines.append(f"**Agent 调用/解析失败**：{agent.get('error', '—')}")
        raw = (meta.get("result") or "").strip()
        if raw:
            lines.extend(["", "原始回复（截断）：", "", "```", raw[:1500], "```"])
        lines.append("")
        return lines

    analysis = (agent.get("analysis") or "").strip()
    if analysis:
        lines.append("#### 行情分析")
        lines.append("")
        for para in analysis.replace("\r\n", "\n").split("\n"):
            p = para.strip()
            if p:
                lines.append(p)
        lines.append("")

    applied = agent.get("applied") or {}
    if applied:
        lines.append("#### 参数调整")
        lines.append("")
        for k, v in applied.items():
            lines.append(f"- `{k}` → **{v}**")
        lines.append("")
    elif agent.get("hold_params") or not applied:
        lines.append("*本 tick Agent 未调整参数（维持当前规则引擎配置）*")
        lines.append("")

    rebound = agent.get("buy_permission") or agent.get("rebound_buy") or agent.get("dip_buy") or {}
    if rebound:
        sig = rebound.get("allowed") if "allowed" in rebound else rebound.get("signal")
        reason = (rebound.get("reason") or "").strip()
        conf = (rebound.get("confidence") or "").strip()
        if sig is not None:
            lines.append("#### 开新仓许可（Wiki→Agent）")
            lines.append("")
            lines.append(f"- **buy_permission**：{'允许' if sig else '禁止'}")
            if conf:
                lines.append(f"- **置信度**：{conf}")
            if reason:
                lines.append(f"- **理由**：{reason}")
            lines.append("")

    notes = (agent.get("notes") or "").strip()
    if notes:
        lines.append("#### 备注")
        lines.append("")
        lines.append(f"> {notes}")
        lines.append("")

    warnings = agent.get("warnings") or []
    if warnings:
        lines.append("#### 警告")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    return lines


def review_tick(tick_path: str, *, phase: str | None = None) -> dict[str, Any]:
    """调用 Cloud Agent；成功时写入 override + 数据扩展 + 日志。返回摘要 dict。"""
    _load_env_file()
    if os.environ.get("AI_SIM_AGENT", "1").strip() in ("0", "false", "no"):
        return {"skipped": True, "reason": "AI_SIM_AGENT=0", "ok": False}

    phase = phase or tick_phase()
    tick_label = os.path.basename(tick_path).replace(".json", "")
    prompt = build_prompt(tick_path, phase=phase)
    try:
        meta = run_analysis_prompt(prompt)
    except AgentClientError as e:
        return {
            "ok": False,
            "error": str(e),
            "analysis": "",
            "applied": {},
            "warnings": [],
            "notes": "",
            "agent_meta": {},
        }

    try:
        parsed = _extract_json(meta.get("result") or "")
    except (ValueError, json.JSONDecodeError) as e:
        meta["result"] = meta.get("result") or ""
        return {
            "ok": False,
            "error": str(e),
            "analysis": "",
            "applied": {},
            "warnings": [],
            "notes": "",
            "agent_meta": meta,
        }

    analysis = str(parsed.get("analysis") or "").strip()
    notes = str(parsed.get("notes") or "").strip()
    hold_params = bool(parsed.get("hold_params"))
    changes = parsed.get("param_changes") or {}
    if not isinstance(changes, dict):
        changes = {}
    rebound_raw = parsed.get("rebound_buy") or parsed.get("dip_buy") or {}
    buy_perm_raw = parsed.get("buy_permission") if isinstance(parsed.get("buy_permission"), dict) else {}
    if buy_perm_raw:
        buy_permission = {
            "allowed": bool(buy_perm_raw.get("allowed")),
            "reason": str(buy_perm_raw.get("reason") or "").strip(),
            "confidence": str(buy_perm_raw.get("confidence") or "").strip(),
        }
    else:
        buy_permission = {
            "allowed": bool(rebound_raw.get("signal")) if isinstance(rebound_raw, dict) else False,
            "reason": str(rebound_raw.get("reason") or "").strip() if isinstance(rebound_raw, dict) else "",
            "confidence": str(rebound_raw.get("confidence") or "").strip() if isinstance(rebound_raw, dict) else "",
        }
    rebound_buy = {
        "signal": buy_permission["allowed"],
        "reason": buy_permission["reason"],
        "confidence": buy_permission["confidence"],
    }

    applied, warnings = ({}, [])
    if changes and not hold_params:
        applied, warnings = apply_patch(changes)

    data_ext = process_data_requests(
        parsed.get("data_requests"),
        tick_label=tick_label,
        phase=phase,
    )

    return {
        "ok": True,
        "analysis": analysis,
        "applied": applied,
        "warnings": warnings,
        "notes": notes,
        "hold_params": hold_params,
        "rebound_buy": rebound_buy,
        "dip_buy": rebound_buy,
        "buy_permission": buy_permission,
        "data_requests": data_ext,
        "phase": phase,
        "agent_meta": meta,
        "usage": meta.get("usage"),
        "token_total": meta.get("token_total"),
        "usage_estimated": meta.get("usage_estimated"),
    }
