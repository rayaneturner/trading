#!/usr/bin/env python3
"""What a daily-loss kill switch would have done, and what the weights already risk.

    python run_risk_rules.py --thresholds 0.05,0.07,0.10
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src import backtest, datafeed
from src.config import StrategyConfig
from src.risk_rules import per_asset_daily_risk, run_with_daily_stop


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2017-01-01")
    ap.add_argument("--thresholds", default="0.05,0.07,0.10")
    args = ap.parse_args()

    prices = datafeed.clean(datafeed.load_local()).loc[args.start:]
    cfg = StrategyConfig(assets=tuple(prices.columns))
    base = backtest.run(prices, cfg)
    rets = base["returns"]
    thresholds = [float(t) for t in args.thresholds.split(",")]

    print("=== daily loss distribution of the strategy ===")
    print(f"daily vol {rets.std() * 100:.2f}%   worst day {rets.min() * 100:.1f}%")
    years = len(rets) / 365.0
    for thr in thresholds:
        n = int((rets < -thr).sum())
        print(f"  days below -{thr * 100:.0f}%: {n} ({n / len(rets) * 100:.2f}% of days, "
              f"~{n / years:.1f}/yr)")

    print("\n=== what happens AFTER a breach day, with no kill switch ===")
    breach = rets.index[rets < -thresholds[0]]
    uncond = ((1 + rets).rolling(5).apply(np.prod, raw=True) - 1).mean()
    for horizon in (1, 5, 10):
        fwd = []
        for date in breach:
            i = rets.index.get_loc(date)
            if i + horizon < len(rets):
                fwd.append(float((1 + rets.iloc[i + 1:i + 1 + horizon]).prod() - 1))
        fwd = np.array(fwd)
        print(f"  next {horizon:2d}d: mean {fwd.mean() * 100:+.2f}%  median "
              f"{np.median(fwd) * 100:+.2f}%  positive {(fwd > 0).mean() * 100:.0f}%")
    print(f"  unconditional 5d mean for comparison: {uncond * 100:+.2f}%")

    print("\n=== kill switch, measured ===")
    rows = {"no stop": base["stats"]}
    for thr in thresholds:
        for resume in ("next_rebalance", "5"):
            rows[f"stop {int(thr * 100)}% / resume {resume}"] = run_with_daily_stop(
                prices, cfg, max_daily_loss=thr, resume=resume)["stats"]
    keys = ("cagr", "vol", "sharpe", "max_dd", "calmar", "time_in_market", "stop_triggers")
    table = pd.DataFrame({k: {x: v.get(x) for x in keys} for k, v in rows.items()}).T
    print(table.astype(float).round(3).to_string())

    print("\n=== what the current weights already risk per day ===")
    print(per_asset_daily_risk(prices, cfg).round(3).to_string())
    print(f"portfolio 1-sigma (last 250d, correlation included): "
          f"{rets.tail(250).std() * 100:.2f}% of capital per day")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
