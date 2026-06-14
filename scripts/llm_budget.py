"""LLM / sug 预算配置（Cursor、Streamlit、LangGraph 共用）。"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUDGET_PATH = os.path.join(ROOT, "Wiki", "数据", "llm_budget.json")

DEFAULT: dict[str, Any] = {
    "per_sug_usd_cap": 5.0,
    "per_qry_usd_cap": 2.0,
    "warn_at_pct": 80,
    "providers": {
        "cursor_cloud": {"enabled": True, "priority": 1, "note": "飞书 agent sug / Cloud Agent"},
        "deepseek": {"enabled": False, "priority": 2, "model": "deepseek-chat"},
        "openai": {"enabled": False, "priority": 3, "model": "gpt-4o-mini"},
        "ollama": {"enabled": False, "priority": 4, "model": "qwen2.5:14b", "base_url": "http://127.0.0.1:11434"},
    },
    "multi_agent_mode": "orchestrator_stub",
    "multi_agent_roles": [
        "chan_local",
        "market",
        "fundamentals",
        "news",
        "policy",
        "hot_money",
        "lockup",
        "sentiment",
        "bull",
        "bear",
        "research_manager",
        "trader",
        "risk_tiers",
        "portfolio_manager",
    ],
    "graph": {
        "enabled": False,
        "max_debate_rounds": 1,
        "analyst_batch_mode": "batch",
        "skip_on_budget_pct": 80,
        "per_call_usd_est": 0.85,
    },
    "estimated_tokens_per_role": 8000,
    "notes": "单次 sug 默认 USD 上限 $5；可在 Streamlit 侧边栏或编辑本 JSON 调节。",
}


def _ensure_env() -> None:
    try:
        from bilibili.env import apply_config_to_environ

        apply_config_to_environ()
    except Exception:
        pass


def load_budget() -> dict[str, Any]:
    _ensure_env()
    cfg = deepcopy(DEFAULT)
    if os.path.isfile(BUDGET_PATH):
        try:
            with open(BUDGET_PATH, encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                cfg.update({k: v for k, v in raw.items() if k != "providers"})
                if isinstance(raw.get("providers"), dict):
                    for name, prov in raw["providers"].items():
                        cfg["providers"].setdefault(name, {})
                        if isinstance(prov, dict):
                            cfg["providers"][name].update(prov)
        except (OSError, json.JSONDecodeError):
            pass
    cap = os.environ.get("LLM_BUDGET_USD")
    if cap:
        try:
            cfg["per_sug_usd_cap"] = float(cap)
        except ValueError:
            pass
    return cfg


def save_budget(cfg: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(BUDGET_PATH), exist_ok=True)
    with open(BUDGET_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def enabled_providers(cfg: dict[str, Any] | None = None) -> list[str]:
    cfg = cfg or load_budget()
    items = []
    for name, prov in (cfg.get("providers") or {}).items():
        if prov.get("enabled"):
            items.append((int(prov.get("priority", 99)), name))
    return [n for _, n in sorted(items)]


def estimate_sug_cost_usd(cfg: dict[str, Any] | None = None, *, roles: int | None = None) -> dict[str, Any]:
    """粗算单次 sug 成本（用于预算预警，非精确账单）。"""
    cfg = cfg or load_budget()
    roles = roles or len(cfg.get("multi_agent_roles") or [])
    tok_per = int(cfg.get("estimated_tokens_per_role") or 8000)
    total_tok = roles * tok_per
    # 混合单价：输入 $1/M，输出 $3/M 粗估
    usd = total_tok * 2.0 / 1_000_000
    cap = float(cfg.get("per_sug_usd_cap") or 5.0)
    return {
        "roles": roles,
        "estimated_tokens": total_tok,
        "estimated_usd": round(usd, 3),
        "cap_usd": cap,
        "within_cap": usd <= cap,
        "providers": enabled_providers(cfg),
        "mode": cfg.get("multi_agent_mode"),
    }


def check_budget(task: str = "sug", cfg: dict[str, Any] | None = None) -> tuple[bool, str]:
    cfg = cfg or load_budget()
    est = estimate_sug_cost_usd(cfg)
    cap_key = "per_sug_usd_cap" if task == "sug" else "per_qry_usd_cap"
    cap = float(cfg.get(cap_key) or 5.0)
    if est["estimated_usd"] > cap:
        return False, f"预估 ${est['estimated_usd']:.2f} 超过 {task} 上限 ${cap:.2f}"
    return True, f"预估 ${est['estimated_usd']:.2f} / 上限 ${cap:.2f}"
