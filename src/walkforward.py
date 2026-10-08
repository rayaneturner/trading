"""Robustness checks. The point is not to find the best parameters, it is to
find out whether the result depends on finding them.

Three tests:
  * `grid`          - full parameter sweep; report the distribution of Sharpe,
                      not the maximum. A strategy whose median grid Sharpe is
                      good is a strategy; one where only the peak is good is a
                      curve fit.
  * `split`         - fit-free in/out split. The rule has no fitted parameters,
                      so OOS here means "a period the parameters were never
                      eyeballed on".
  * `sensitivity`   - perturb costs and execution lag. If a 1-day slower fill
                      or 2x fees kills it, it was never tradeable.
"""
from __future__ import annotations

import itertools

import pandas as pd

from . import backtest
from .config import StrategyConfig


def grid(prices: pd.DataFrame, base: StrategyConfig, space: dict) -> pd.DataFrame:
    keys = list(space)
    rows = []
    for combo in itertools.product(*(space[k] for k in keys)):
        params = dict(zip(keys, combo))
        cfg = StrategyConfig(**{**base.to_dict(), **params, "assets": tuple(prices.columns)})
        res = backtest.run(prices, cfg)
        rows.append({**params, **{k: res["stats"][k] for k in
                                  ("cagr", "vol", "sharpe", "max_dd", "calmar", "turnover_per_year")}})
    return pd.DataFrame(rows)


def split(prices: pd.DataFrame, cfg: StrategyConfig, cut: str) -> pd.DataFrame:
    out = {}
    for label, sl in (("in_sample", slice(None, cut)), ("out_of_sample", slice(cut, None))):
        sub = prices.loc[sl]
        cfg_sub = StrategyConfig(**{**cfg.to_dict(), "assets": tuple(sub.columns)})
        out[label] = backtest.run(sub, cfg_sub)["stats"]
        out[f"hodl_{label}"] = backtest.buy_and_hold(sub, None, cfg_sub)["stats"]
    return pd.DataFrame(out).T


def sensitivity(prices: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    scenarios = {
        "base": {},
        "cost_2x": {"cost_per_side": cfg.cost_per_side * 2},
        "cost_4x": {"cost_per_side": cfg.cost_per_side * 4},
        "lag_2d": {"exec_lag_days": 2},
        "lag_3d": {"exec_lag_days": 3},
        "daily_rebal": {"rebalance_weekday": None},
        "no_band": {"no_trade_band": 0.0},
    }
    rows = {}
    for name, override in scenarios.items():
        c = StrategyConfig(**{**cfg.to_dict(), **override, "assets": tuple(prices.columns)})
        rows[name] = backtest.run(prices, c)["stats"]
    return pd.DataFrame(rows).T
