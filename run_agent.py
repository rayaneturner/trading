#!/usr/bin/env python3
"""One agent decision on today's data, bounded by the risk envelope.

    python run_agent.py --exchange kraken --assets BTC,ETH,SOL          # decide, print JSON
    python run_agent.py --csv data/prices_daily.csv --offline           # no API call, rule only
    TRADING_LIVE=1 python run_agent.py --exchange kraken --trade --live  # decide and trade

The envelope is applied after the model answers: the agent can cut risk to zero
but can never exceed the deterministic rule's weight by more than --max-tilt-up,
and can never hold an asset the rule says is in a downtrend.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

from src import datafeed
from src.agent import MODEL, RiskEnvelope, StubAgent, apply_envelope, build_snapshot, decide
from src.config import StrategyConfig
from src.execution import CcxtExecutor, ExecutionLimits, append_log, plan_orders
from src.strategy import live_weights


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="kraken")
    ap.add_argument("--quote", default="USD")
    ap.add_argument("--assets", default="BTC,ETH,SOL")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--max-tilt-up", type=float, default=0.10)
    ap.add_argument("--offline", action="store_true", help="skip the API, follow the rule exactly")
    ap.add_argument("--trade", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-order", type=float, default=5000.0)
    ap.add_argument("--log", default="out/agent.jsonl")
    args = ap.parse_args()

    assets = tuple(a.strip().upper() for a in args.assets.split(",") if a.strip())
    cfg = StrategyConfig(assets=assets)

    if args.csv:
        prices = datafeed.load_local(args.csv)
    else:
        prices = datafeed.fetch_ccxt(assets, exchange=args.exchange, quote=args.quote).iloc[:-1]
    prices = datafeed.clean(prices, min_history=cfg.sma_long + cfg.mom_lookback)
    if prices.empty:
        print(json.dumps({"error": "no asset has enough history"}), file=sys.stderr)
        return 2
    cfg = StrategyConfig(assets=tuple(prices.columns))

    stale = {a: n for a, n in datafeed.stale_tail(prices).items() if n >= 2}
    rule = live_weights(prices, cfg)
    env = RiskEnvelope(max_tilt_up=args.max_tilt_up,
                       max_weight_per_asset=cfg.max_weight_per_asset,
                       max_gross=cfg.max_gross)
    snapshot = build_snapshot(prices, cfg)

    if args.offline:
        decision = StubAgent().decide(snapshot, env=env)
    else:
        decision = decide(snapshot, env=env, model=args.model, effort=args.effort)

    final = apply_envelope(rule, decision, env)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "as_of_close": snapshot["as_of_close"],
        "source": args.csv or f"ccxt:{args.exchange}",
        "rule_weights": {k: round(float(v), 4) for k, v in rule.items()},
        "agent_decision": decision.to_dict(),
        "final_weights": {k: round(float(v), 4) for k, v in final.items()},
        "cash_weight": round(1.0 - float(final.sum()), 4),
        "envelope": {"max_tilt_up": env.max_tilt_up, "allow_new_longs": env.allow_new_longs,
                     "max_weight_per_asset": env.max_weight_per_asset, "max_gross": env.max_gross},
        "snapshot": snapshot,
        "stale_feeds": stale,
    }

    if stale:
        report["action"] = "aborted: stale feed"
        print(json.dumps(report, indent=2))
        append_log(args.log, report)
        return 1

    if args.trade:
        limits = ExecutionLimits(max_order_notional=args.max_order,
                                 no_trade_band=cfg.no_trade_band)
        ex = CcxtExecutor(args.exchange, args.quote, limits, live=args.live)
        holdings, spot, cash = ex.snapshot(prices.columns)
        orders, diag = plan_orders(final, holdings, spot, cash, limits)
        report["diagnostics"] = diag
        report["orders"] = [o.to_dict() for o in orders]
        report["receipts"] = ex.execute(orders)
        report["action"] = "traded" if ex.live else "planned"
    else:
        report["action"] = "signal_only"

    print(json.dumps(report, indent=2))
    append_log(args.log, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
