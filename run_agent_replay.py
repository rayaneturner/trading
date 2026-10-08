#!/usr/bin/env python3
"""Measure the agent against the rule it tilts, net of its own token cost.

    # behaviour inspection on historical data — CONTAMINATED, not a measurement
    python run_agent_replay.py --offline --start 2024-01-01 --allow-contaminated

    # the honest test: forward dates only, real API calls, one per rebalance
    python run_agent_replay.py --start 2026-11-01 --api

Acceptance criterion to decide before you look at the result: the agent must beat
the rule's Calmar by at least 15% over at least 26 rebalances, after its token
cost. Anything less and the extra machinery is not paying for itself — run the
deterministic rule and keep the money.
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from src import agent_replay, datafeed
from src.agent import RiskEnvelope, StubAgent
from src.agent_replay import TRAINING_CUTOFF
from src.config import StrategyConfig


class ApiDecider:
    def __init__(self, model: str, effort: str):
        self.model, self.effort = model, effort

    def decide(self, snapshot, env=None, **_):
        from src.agent import decide
        return decide(snapshot, env=env, model=self.model, effort=self.effort)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=datafeed.LOCAL_CSV)
    ap.add_argument("--start", default=None)
    ap.add_argument("--api", action="store_true", help="call the model (costs money)")
    ap.add_argument("--offline", action="store_true", help="explicit no-API run (the default)")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-tilt-up", type=float, default=0.10)
    ap.add_argument("--allow-contaminated", action="store_true")
    ap.add_argument("--out", default="out/replay.json")
    args = ap.parse_args()

    prices = datafeed.clean(datafeed.load_local(args.csv))
    cfg = StrategyConfig(assets=tuple(prices.columns))
    env = RiskEnvelope(max_tilt_up=args.max_tilt_up,
                       max_weight_per_asset=cfg.max_weight_per_asset,
                       max_gross=cfg.max_gross)
    decider = ApiDecider(args.model, args.effort) if args.api else StubAgent()

    result = agent_replay.replay(prices, decider, cfg, env, start=args.start,
                                 allow_contaminated=args.allow_contaminated)

    if result.contaminated:
        print("!! CONTAMINATED: replay ends on or before the model's training cutoff "
              f"({TRAINING_CUTOFF.date()}). These numbers measure leakage, not skill.\n")

    keys = ("cagr", "vol", "sharpe", "max_dd", "calmar", "turnover_per_year")
    table = pd.DataFrame({"agent": {k: result.stats.get(k) for k in keys},
                          "rule": {k: result.rule_stats.get(k) for k in keys}})
    print(table.round(3).to_string())
    print(f"\ndecisions: {len(result.decisions)}   token cost: ${result.total_cost_usd:.2f}")

    if result.decisions:
        tilts = pd.DataFrame([d["tilts"] for d in result.decisions])
        print("\ntilt distribution per asset:")
        print(tilts.describe().round(3).to_string())
        print(f"\nfraction of decisions that deviated from the rule: "
              f"{float((tilts.abs() > 1e-9).any(axis=1).mean()):.1%}")

    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump({**result.to_dict(), "decision_log": result.decisions}, fh, indent=2, default=str)
    print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
