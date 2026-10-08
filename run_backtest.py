#!/usr/bin/env python3
"""Backtest the strategy against buy-and-hold benchmarks on the research data."""
from __future__ import annotations

import argparse

import pandas as pd

from src import backtest, datafeed
from src.config import StrategyConfig
from src.metrics import summary_table


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--cost", type=float, default=None, help="cost per side, e.g. 0.0015")
    ap.add_argument("--target-vol", type=float, default=None)
    ap.add_argument("--csv", default=datafeed.LOCAL_CSV)
    args = ap.parse_args()

    overrides = {}
    if args.cost is not None:
        overrides["cost_per_side"] = args.cost
    if args.target_vol is not None:
        overrides["target_vol"] = args.target_vol
    cfg = StrategyConfig(**overrides)

    prices = datafeed.clean(datafeed.load_local(args.csv)).loc[args.start:args.end]
    cfg = StrategyConfig(**{**overrides, "assets": tuple(prices.columns)})
    print(f"universe: {list(prices.columns)}  {prices.index[0].date()} -> {prices.index[-1].date()}")

    strat = backtest.run(prices, cfg)
    ew = backtest.buy_and_hold(prices, None, cfg)
    btc = backtest.buy_and_hold(prices[["BTC"]], None, cfg)

    results = {"strategy": strat["stats"], "hodl_equal_weight": ew["stats"], "hodl_btc": btc["stats"]}
    pd.set_option("display.width", 200, "display.max_columns", 50)
    print("\n=== performance (net of costs, % where relevant) ===")
    print(summary_table(results).to_string())

    print("\n=== calendar-year net returns (%) ===")
    years = pd.DataFrame({
        "strategy": backtest.by_year(strat["returns"]),
        "hodl_ew": backtest.by_year(ew["returns"]),
        "hodl_btc": backtest.by_year(btc["returns"]),
    }) * 100
    years.index = years.index.year
    print(years.round(1).to_string())

    print("\n=== current target weights (last row of the research data) ===")
    print(strat["weights"].iloc[-1].round(3).to_string())


if __name__ == "__main__":
    main()
