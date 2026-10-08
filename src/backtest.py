"""Vectorised backtest with explicit execution lag and trading costs.

Timing convention (the single most common way backtests lie):
    * signal is computed from closes up to and including day t;
    * the resulting weights are traded at the close of day t + exec_lag_days;
    * they earn the return of day t + exec_lag_days + 1 onwards.
Costs are charged on the day the weights change, proportional to turnover.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT, StrategyConfig
from .metrics import stats
from .strategy import apply_rebalance_schedule, target_weights


def _effective_weights(prices: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    scheduled = apply_rebalance_schedule(target_weights(prices, cfg), cfg)
    return scheduled.shift(cfg.exec_lag_days).fillna(0.0)


def run(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> dict:
    return run_from_weights(prices, _effective_weights(prices, cfg), cfg)


def run_from_weights(prices: pd.DataFrame, weights: pd.DataFrame,
                     cfg: StrategyConfig = DEFAULT) -> dict:
    """Backtest an arbitrary weight path. `weights` must already be lagged, i.e. row
    t is what was actually held into day t — callers that produce weights from a
    decision made on close t must shift them before passing them in."""
    prices = prices.sort_index()
    asset_rets = prices.pct_change().fillna(0.0)
    weights = weights.reindex(prices.index).fillna(0.0)

    # Held weights earn tomorrow's return.
    held = weights.shift(1).fillna(0.0)
    gross_ret = (held * asset_rets).sum(axis=1)

    cash = (1.0 - held.sum(axis=1)).clip(lower=0.0)
    cash_ret = cash * (cfg.cash_yield / 365.0)

    turnover = weights.diff().abs().sum(axis=1).fillna(weights.iloc[0].abs().sum())
    cost = turnover * cfg.cost_per_side

    net_ret = gross_ret + cash_ret - cost
    equity = (1.0 + net_ret).cumprod()

    result = {
        "config": cfg.to_dict(),
        "weights": weights,
        "returns": net_ret,
        "gross_returns": gross_ret,
        "turnover": turnover,
        "equity": equity,
        "stats": stats(net_ret, turnover),
    }
    result["stats"]["time_in_market"] = float((held.sum(axis=1) > 0.01).mean())
    return result


def buy_and_hold(prices: pd.DataFrame, weights: dict | None = None,
                 cfg: StrategyConfig = DEFAULT) -> dict:
    """Benchmark: fixed weights, rebalanced weekly, same cost model.

    `weights=None` means equal weight across whatever is listed each day.
    """
    rets = prices.pct_change()
    if weights is None:
        available = prices.notna() & rets.notna()
        w = available.div(available.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    else:
        w = pd.DataFrame(
            {c: weights.get(c, 0.0) for c in prices.columns}, index=prices.index
        ).where(prices.notna(), 0.0)
        w = w.div(w.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    w = apply_rebalance_schedule(w, cfg)
    held = w.shift(1).fillna(0.0)
    turnover = w.diff().abs().sum(axis=1).fillna(w.iloc[0].abs().sum())
    net = (held * rets.fillna(0.0)).sum(axis=1) - turnover * cfg.cost_per_side
    out = {"returns": net, "equity": (1.0 + net).cumprod(), "stats": stats(net, turnover)}
    out["stats"]["time_in_market"] = float((held.sum(axis=1) > 0.01).mean())
    return out


def by_year(rets: pd.Series) -> pd.Series:
    return ((1.0 + rets).resample("YE").prod() - 1.0).rename("return")
