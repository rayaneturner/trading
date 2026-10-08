#!/usr/bin/env python3
"""Compute today's target weights from live exchange data and (optionally) trade.

Typical use, from cron, once a day after 00:10 UTC:

    # signal only, printed as JSON
    python run_live.py --exchange kraken

    # generate orders against the real balance, but send nothing
    python run_live.py --exchange kraken --trade

    # actually send orders (needs TRADING_LIVE=1 as well)
    TRADING_LIVE=1 python run_live.py --exchange kraken --trade --live

Pre-trade checks that will refuse to produce a signal:
  * fewer than `sma_long` closes of history for an asset -> that asset is skipped
  * the feed's last close repeats the previous one -> stale feed, abort
  * the newest close is older than 48h -> abort
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import pandas as pd

from src import datafeed
from src.config import StrategyConfig
from src.execution import CcxtExecutor, ExecutionLimits, append_log, plan_orders
from src.strategy import live_weights, realised_vol, trend_score


def preflight(prices: pd.DataFrame, cfg: StrategyConfig) -> list[str]:
    problems = []
    stale = datafeed.stale_tail(prices)
    for asset, n in stale.items():
        if n >= 2:
            problems.append(f"{asset}: {n} identical trailing closes (stale feed)")
    age = (pd.Timestamp.now("UTC").tz_localize(None).normalize() - prices.index[-1]).days
    if age > 2:
        problems.append(f"newest close is {age} days old")
    for asset in prices.columns:
        if prices[asset].notna().sum() < cfg.sma_long + cfg.mom_lookback:
            problems.append(f"{asset}: only {int(prices[asset].notna().sum())} closes, "
                            f"need {cfg.sma_long + cfg.mom_lookback}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="kraken")
    ap.add_argument("--quote", default="USD")
    ap.add_argument("--assets", default="BTC,ETH,SOL")
    ap.add_argument("--target-vol", type=float, default=None)
    ap.add_argument("--trade", action="store_true", help="plan orders against real balances")
    ap.add_argument("--live", action="store_true", help="send orders (also needs TRADING_LIVE=1)")
    ap.add_argument("--max-order", type=float, default=5000.0)
    ap.add_argument("--log", default="out/live.jsonl")
    ap.add_argument("--csv", default=None, help="use a local CSV instead of the exchange")
    args = ap.parse_args()

    assets = tuple(a.strip().upper() for a in args.assets.split(",") if a.strip())
    overrides = {"assets": assets}
    if args.target_vol is not None:
        overrides["target_vol"] = args.target_vol
    cfg = StrategyConfig(**overrides)

    if args.csv:
        prices = datafeed.load_local(args.csv)
    else:
        prices = datafeed.fetch_ccxt(assets, exchange=args.exchange, quote=args.quote)
        # The last row is today's unfinished candle: it would repaint.
        prices = prices.iloc[:-1]
    prices = datafeed.clean(prices, min_history=cfg.sma_long + cfg.mom_lookback)
    if prices.empty:
        print(json.dumps({"error": "no asset has enough history"}), file=sys.stderr)
        return 2

    cfg = StrategyConfig(**{**overrides, "assets": tuple(prices.columns)})
    problems = preflight(prices, cfg)

    weights = live_weights(prices, cfg)
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "as_of_close": str(prices.index[-1].date()),
        "source": args.csv or f"ccxt:{args.exchange}",
        "target_weights": {k: round(float(v), 4) for k, v in weights.items()},
        "cash_weight": round(1.0 - float(weights.sum()), 4),
        "trend_score": {k: round(float(v), 3) for k, v in trend_score(prices, cfg).iloc[-1].items()},
        "annualised_vol": {k: round(float(v), 3) for k, v in realised_vol(prices, cfg).iloc[-1].items()},
        "config": cfg.to_dict(),
        "preflight_problems": problems,
    }

    if problems:
        report["action"] = "aborted"
        print(json.dumps(report, indent=2))
        append_log(args.log, report)
        return 1

    if args.trade:
        limits = ExecutionLimits(max_order_notional=args.max_order,
                                 no_trade_band=cfg.no_trade_band)
        ex = CcxtExecutor(args.exchange, args.quote, limits, live=args.live)
        holdings, spot, cash = ex.snapshot(prices.columns)
        orders, diag = plan_orders(weights, holdings, spot, cash, limits)
        report["diagnostics"] = diag
        report["orders"] = [o.to_dict() for o in orders]
        report["receipts"] = ex.execute(orders)
        report["mode"] = "live" if ex.live else "dry_run"
        report["action"] = "traded" if ex.live else "planned"
    else:
        report["action"] = "signal_only"

    print(json.dumps(report, indent=2))
    append_log(args.log, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
