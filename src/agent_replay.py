"""Forward paper-trading harness for the LLM layer.

Read this before trusting any number this file produces.

`claude-opus-5-5` has a training cutoff. Replaying any date before that cutoff
asks a model that already knows what happened next to pretend it does not. The
result is not a backtest; it is an upper bound produced by leakage, and it will
always look excellent. This module therefore refuses to score a replay that ends
before `TRAINING_CUTOFF` unless you pass `allow_contaminated=True`, in which case
every output is labelled `contaminated`.

The only honest measurement is forward: run the agent on dates after the cutoff,
one decision per rebalance, and compare it to the rule it is tilting — net of its
own token cost. The comparison that matters is not "did the agent make money"
but "did the agent beat the rule by more than it cost to ask it".
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from . import backtest
from .agent import AgentDecision, RiskEnvelope, StubAgent, apply_envelope, build_snapshot
from .config import DEFAULT, StrategyConfig
from .strategy import apply_rebalance_schedule, target_weights

# Knowledge cutoff of the model making the decisions. Update it when you change
# model; getting this wrong is how a leaked backtest gets mistaken for an edge.
TRAINING_CUTOFF = pd.Timestamp("2026-05-01")


@dataclass
class ReplayResult:
    weights: pd.DataFrame
    decisions: list = field(default_factory=list)
    total_cost_usd: float = 0.0
    contaminated: bool = False
    stats: dict = field(default_factory=dict)
    rule_stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"contaminated": self.contaminated,
                "total_cost_usd": round(self.total_cost_usd, 4),
                "decisions": len(self.decisions),
                "agent": self.stats, "rule": self.rule_stats}


def replay(prices: pd.DataFrame, decider, cfg: StrategyConfig = DEFAULT,
           env: RiskEnvelope | None = None, start: str | None = None,
           allow_contaminated: bool = False, min_history: int = 300) -> ReplayResult:
    prices = prices.sort_index()
    env = env or RiskEnvelope()

    first = pd.Timestamp(start) if start else prices.index[min_history]
    dates = [d for d in prices.index if d >= first]
    if not dates:
        raise ValueError("no dates to replay")

    contaminated = pd.Timestamp(dates[-1]) <= TRAINING_CUTOFF
    if contaminated and not allow_contaminated:
        raise ValueError(
            f"replay ends {dates[-1].date()}, at or before the model's training cutoff "
            f"{TRAINING_CUTOFF.date()}: the agent already knows these prices. "
            "Pass allow_contaminated=True only to inspect behaviour, never to measure it."
        )

    rule_path = apply_rebalance_schedule(target_weights(prices, cfg), cfg)

    # Before the replay window the portfolio is assumed to hold the rule's weights:
    # switching the agent on does not start you from cash, and seeding from zero
    # would flatter or penalise the agent purely through a start-of-window artefact.
    rows = {d: rule_path.loc[d] for d in prices.index if d < first}
    decisions, cost = [], 0.0
    prior = [d for d in prices.index if d < first]
    held = rule_path.loc[prior[-1]].copy() if prior else pd.Series(0.0, index=prices.columns)
    for date in dates:
        is_rebal = cfg.rebalance_weekday is None or date.weekday() == cfg.rebalance_weekday
        if is_rebal:
            window = prices.loc[:date]
            snapshot = build_snapshot(window, cfg)
            decision = decider.decide(snapshot, env=env)
            held = apply_envelope(rule_path.loc[date], decision, env)
            cost += decision.cost_usd
            decisions.append({"date": str(date.date()), **decision.to_dict()})
        rows[date] = held.copy()

    full = pd.DataFrame(rows).T.reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    # Decisions are made on each date's close; they are held from the next day. The
    # shift runs over the full index so both paths are lagged identically.
    effective = full.shift(cfg.exec_lag_days).fillna(0.0)

    sub = prices.loc[dates[0]:]
    agent_run = backtest.run_from_weights(sub, effective.loc[sub.index], cfg)
    rule_run = backtest.run_from_weights(
        sub, rule_path.shift(cfg.exec_lag_days).fillna(0.0).loc[sub.index], cfg)

    return ReplayResult(weights=full.loc[dates[0]:], decisions=decisions, total_cost_usd=cost,
                        contaminated=contaminated, stats=agent_run["stats"],
                        rule_stats=rule_run["stats"])
