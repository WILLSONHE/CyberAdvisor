"""插件化 supplement：从 registry + 启用状态组装 tick 补充数据。"""
from __future__ import annotations

import os
from typing import Any

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "supplement_registry.yaml")


def _load_yaml(path: str) -> dict:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(open(path, encoding="utf-8")) or {}
    except ImportError:
        pass
    # 无 PyYAML 时的极简解析（仅支持本 registry 扁平结构）
    metrics: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "metrics:":
            continue
        if line.endswith(":") and not line.startswith(" "):
            key = line[:-1].strip()
            if key != "metrics":
                current = key
                metrics[current] = {}
            continue
        if current and ":" in line:
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if v.lower() in ("true", "false"):
                metrics[current][k] = v.lower() == "true"
            else:
                metrics[current][k] = v.strip('"')
    return {"metrics": metrics}


def load_registry() -> dict[str, dict[str, Any]]:
    if not os.path.isfile(REGISTRY_PATH):
        return {}
    raw = _load_yaml(REGISTRY_PATH)
    metrics = raw.get("metrics") or {}
    return {str(k): dict(v) for k, v in metrics.items()}


def registry_summary_for_prompt() -> str:
    reg = load_registry()
    lines = ["| metric | 说明 | 默认 | 可禁用 |", "|--------|------|------|--------|"]
    for mid, spec in reg.items():
        lines.append(
            f"| `{mid}` | {spec.get('label', mid)} | "
            f"{'开' if spec.get('default') else '关'} | "
            f"{'否' if spec.get('always_on') else '是'} |"
        )
    return "\n".join(lines)


def build_supplement_payload(
    enabled: set[str],
    *,
    include_overnight: bool = False,
    kline_limit: int = 20,
) -> dict[str, Any]:
    """按 registry 抓取已启用指标；always_on 强制包含。"""
    from market_daily import supplement as sup

    reg = load_registry()
    active: set[str] = set(enabled)
    for mid, spec in reg.items():
        if spec.get("always_on"):
            active.add(mid)

    payload: dict[str, Any] = {"_enabled_metrics": sorted(active)}

    fetchers: dict[str, Any] = {
        "kline_60m": lambda: sup.fetch_klines_60m_multi(limit=kline_limit),
        "northbound": sup.fetch_northbound_snapshot,
        "northbound_history": lambda: sup.fetch_northbound_history(days=10),
        "overnight": sup.fetch_overnight_indices,
        "us_vix": sup.fetch_us_vix,
        "us_10y_yield": sup.fetch_us_10y_yield,
    }

    for mid in sorted(active):
        if mid == "overnight" and not include_overnight:
            continue
        spec = reg.get(mid) or {}
        fetcher_key = str(spec.get("fetcher") or mid)
        fn = fetchers.get(fetcher_key)
        if not fn:
            payload[mid] = {"error": f"no fetcher for {fetcher_key}"}
            continue
        try:
            payload[mid] = fn()
        except Exception as exc:
            payload[mid] = {"error": str(exc)}

    return payload
