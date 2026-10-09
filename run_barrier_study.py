#!/usr/bin/env python3
"""Measure a fixed SL/TP setup, e.g. the "SL 2%, TP 1:3, 20x" shown by venues.

    python run_barrier_study.py --sl 0.02 --tp 0.06
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src import datafeed
from src.barrier_study import barrier_study, breakeven_win_rate
from src.config import StrategyConfig
from src.strategy import trend_score


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--sl", type=float, default=0.02)
    ap.add_argument("--tp", type=float, default=0.06)
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    prices = datafeed.clean(datafeed.load_local()).loc[args.start:]
    cfg = StrategyConfig(assets=tuple(prices.columns))
    scores = trend_score(prices, cfg)

    be = breakeven_win_rate(args.tp, args.sl)
    print(f"SL {args.sl*100:.1f}%  TP {args.tp*100:.1f}%  (1:{args.tp/args.sl:.0f})")
    print(f"break-even win rate = random-walk hit rate = {be:.1f}%\n")

    rows = {}
    for asset in prices.columns:
        closes = prices[asset].dropna()
        daily_vol = closes.pct_change().std()
        print(f"{asset}: daily vol {daily_vol*100:.2f}%  ->  a {args.sl*100:.0f}% stop sits at "
              f"{args.sl/daily_vol:.2f} sigma")
        filt = (scores[asset].reindex(closes.index).fillna(0) == 1.0).to_numpy()
        rows[f"{asset} all entries"] = barrier_study(
            closes, tp=args.tp, sl=args.sl, seeds=args.seeds).to_dict()
        rows[f"{asset} trend filter"] = barrier_study(
            closes, tp=args.tp, sl=args.sl, entry_filter=filt, seeds=args.seeds).to_dict()

    print()
    print(pd.DataFrame(rows).T.to_string())
    print("\nnet_R is per trade, after taker fees and perp funding. Compare it to "
          "stderr_R: an expectancy smaller than ~2x its standard error is not an edge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
