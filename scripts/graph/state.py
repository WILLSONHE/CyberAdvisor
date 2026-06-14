"""Graph 管线共享状态。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BudgetLedger:
    cap_usd: float = 5.0
    spent_usd: float = 0.0
    llm_calls: int = 0
    tokens_estimated: int = 0
    degraded: bool = False
    skip_debate: bool = False
    analyst_mode: str = "full"  # full | batch | skip

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    def pct_used(self) -> float:
        if self.cap_usd <= 0:
            return 100.0
        return min(100.0, self.spent_usd / self.cap_usd * 100.0)


@dataclass
class GraphState:
    analysis_id: str
    task: str  # sug | qry
    holder: str = ""
    session: str | None = None
    question: str = ""
    started_at: str = ""
    finished_at: str = ""

    holdings: list[dict[str, Any]] = field(default_factory=list)
    index_chan: dict[str, Any] = field(default_factory=dict)
    stock_chans: dict[str, dict[str, Any]] = field(default_factory=dict)
    stock_verdicts: dict[str, dict[str, Any]] = field(default_factory=dict)

    analyst_reports: dict[str, str] = field(default_factory=dict)
    quality_gate: dict[str, Any] = field(default_factory=dict)

    bull_case: str = ""
    bear_case: str = ""
    debate_rounds: list[dict[str, str]] = field(default_factory=list)

    research_manager: str = ""
    trader_proposal: str = ""
    risk_tiers: dict[str, str] = field(default_factory=dict)
    portfolio_manager: str = ""

    hard_gate: dict[str, Any] = field(default_factory=dict)
    final_markdown: str = ""

    budget: BudgetLedger = field(default_factory=BudgetLedger)
    stages_done: list[str] = field(default_factory=list)
    current_stage: str = ""
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GraphState:
        budget_raw = data.pop("budget", {}) or {}
        budget = BudgetLedger(**budget_raw) if isinstance(budget_raw, dict) else BudgetLedger()
        return cls(budget=budget, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
