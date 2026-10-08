#!/usr/bin/env python3
"""Robustness suite: parameter grid, in/out-of-sample split, cost sensitivity."""
from __future__ import annotations

import argparse

import pandas as pd

from src import datafeed, walkforward
from src.config import StrategyConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--cut", default="2022-01-01")
    args = ap.parse_args()

    prices = datafeed.clean(datafeed.load_local()).loc[args.start:]
    cfg = StrategyConfig(assets=tuple(prices.columns))
    pd.set_option("display.width", 220, "display.max_columns", 60, "display.max_rows", 400)

    print("=== in / out of sample split at", args.cut, "===")
    print(walkforward.split(prices, cfg, args.cut).round(3).to_string())

    print("\n=== sensitivity to costs, fill delay and rebalance frequency ===")
    print(walkforward.sensitivity(prices, cfg).round(3).to_string())

    space = {
        "ema_fast": [10, 20, 30],
        "ema_slow": [50, 60, 100],
        "sma_long": [150, 200, 250],
        "mom_lookback": [60, 90, 120],
        "target_vol": [0.25, 0.35, 0.50],
    }
    table = walkforward.grid(prices, cfg, space)
    print(f"\n=== parameter grid: {len(table)} combinations ===")
    print(table[["cagr", "vol", "sharpe", "max_dd", "calmar"]].describe().round(3).to_string())
    print("\nworst 5 by Sharpe:")
    print(table.nsmallest(5, "sharpe").round(3).to_string(index=False))
    print("\nbest 5 by Sharpe:")
    print(table.nlargest(5, "sharpe").round(3).to_string(index=False))
    print("\nmedian Sharpe by target_vol:")
    print(table.groupby("target_vol")["sharpe"].median().round(3).to_string())


if __name__ == "__main__":
    main()
