"""每 tick 调用 Cursor Cloud Agent 分析行情并调整 runtime 参数。"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from ai_sim.agent_client import AgentClientError, run_analysis_prompt
from ai_sim.config import DAILY_REPORT, JOURNAL_PATH, ROOT
from ai_sim.portfolio_ops import active_positions, cash_available, total_assets
from ai_sim.runtime_params import PARAM_SCHEMA, apply_patch, defaults_for_agent, effective_all, snapshot
from ai_sim.schedule_util import tick_phase, tick_phase_label
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


def _positions_summary() -> str:
    pos = active_positions()
    if pos.empty:
        return "当前无 AI 持仓"
    lines = []
    for _, r in pos.iterrows():
        lines.append(
            f"- {r['标的']}({r['代码']}) 成本{r['成本']} 现价{r.get('现价')} "
            f"股数{r['股数']} 盈亏比{r.get('盈亏比')}"
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
            "【午休复盘 tick】复盘 9:30–11:30 上午盘面与持仓；对照 Wiki/博主判断。"
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

    return f"""你是 CyberAdvisor 项目的 AI 模拟盘风控分析师。

## 当前阶段
- **{phase_cn}**（`{phase}`）
- {phase_instructions}

## 你的职责
1. 阅读下方 **Wiki 策略上下文**（含全库索引 + 核心框架）、行情 tick、持仓、日志与市场日报
2. 给出简短中文行情分析（3–6 句）
3. **可选**调整规则引擎参数（充分分析后可 **维持不变**）
4. 禁止建议直接改 xlsx 持仓；执行仍由本地规则引擎负责

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

## 持仓
{_positions_summary()}

## 最新 tick JSON（`{tick_path}`）
```json
{tick_json}
```

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
  "notes": "给本地规则引擎的补充说明（可选）"
}}
```

规则：
- `param_changes` 为空对象 {{}} 表示本 tick 不调参
- 数值必须在 schema 边界内
- **指数纪律多层框架**（必读 `Wiki/投资方法论/指数纪律框架.md`）：
  - **L1** 4033/4130：规则引擎硬参数；上证 < 4033 时通常 `NO_BUY_BELOW_CLEAR: true` 且降低 `EQUITY_TARGET_BELOW_CLEAR`
  - **L2** 硬科技清仓：创业板/深成指趋势破位时叙事须提及
  - **L3** 回补须 **4120 站稳** 或 **60 分钟及以上明确底部** — **禁止**写「站回 4033 即可回补」
  - **L4** 4000→3950 结构；**L5** 缩量验证企稳
- `analysis` 须分层表述 L1 +（破线/调整环境下）L3–L5，不可只写 4033
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
    """调用 Cloud Agent；成功时写入 override + 日志。返回摘要 dict。"""
    _load_env_file()
    if os.environ.get("AI_SIM_AGENT", "1").strip() in ("0", "false", "no"):
        return {"skipped": True, "reason": "AI_SIM_AGENT=0", "ok": False}

    phase = phase or tick_phase()
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

    applied, warnings = ({}, [])
    if changes and not hold_params:
        applied, warnings = apply_patch(changes)

    return {
        "ok": True,
        "analysis": analysis,
        "applied": applied,
        "warnings": warnings,
        "notes": notes,
        "hold_params": hold_params,
        "phase": phase,
        "agent_meta": meta,
    }
