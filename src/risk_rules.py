"""Daily-loss kill switch, and the sizing identity behind "risk 1% per trade".

Both exist because a trader asked for them in the vocabulary of leveraged
discretionary trading. They are implemented here so the question "what would
that rule have done" has a number instead of an opinion.

Modelling limit, stated up front: with daily closes, a kill switch can only be
evaluated close-to-close. A real -5% stop fires intraday, at a worse price than
the close, and often on a day that closes better than it traded. So the measured
impact below is the *optimistic* case for the kill switch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT, StrategyConfig
from .metrics import stats
from .strategy import apply_rebalance_schedule, target_weights


def run_with_daily_stop(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT,
                        max_daily_loss: float = 0.05,
                        resume: str = "next_rebalance") -> dict:
    """Flatten the book for the rest of the cooldown after a daily loss breach.

    resume: "next_rebalance" (flat until the next scheduled rebalance day) or an
    integer-like number of calendar days as a string, e.g. "5".
    """
    prices = prices.sort_index()
    asset_rets = prices.pct_change().fillna(0.0)
    scheduled = apply_rebalance_schedule(target_weights(prices, cfg), cfg)
    desired = scheduled.shift(cfg.exec_lag_days).fillna(0.0)

    index = prices.index
    cols = prices.columns
    held = np.zeros(len(cols))
    flat_until = None

    applied, rets, triggers = [], [], []
    for i, date in enumerate(index):
        gross_ret = float(held @ asset_rets.iloc[i].to_numpy())
        rets.append(gross_ret)

        breached = gross_ret < -max_daily_loss
        if breached:
            triggers.append({"date": date, "day_return": gross_ret})
            if resume == "next_rebalance":
                flat_until = "rebalance"
            else:
                flat_until = date + pd.Timedelta(days=int(resume))

        if flat_until == "rebalance":
            is_rebal = cfg.rebalance_weekday is None or date.weekday() == cfg.rebalance_weekday
            # The breach day itself cannot also be the resume day.
            target = desired.iloc[i].to_numpy() if (is_rebal and not breached) else np.zeros(len(cols))
            if is_rebal and not breached:
                flat_until = None
        elif flat_until is not None:
            target = np.zeros(len(cols)) if date <= flat_until else desired.iloc[i].to_numpy()
            if date > flat_until:
                flat_until = None
        else:
            target = desired.iloc[i].to_numpy()

        applied.append(target.copy())
        held = target

    applied = pd.DataFrame(applied, index=index, columns=cols)
    turnover = applied.diff().abs().sum(axis=1).fillna(applied.iloc[0].abs().sum())
    net = pd.Series(rets, index=index) - turnover * cfg.cost_per_side
    out = {"returns": net, "equity": (1.0 + net).cumprod(), "weights": applied,
           "turnover": turnover, "triggers": triggers,
           "stats": stats(net, turnover)}
    out["stats"]["time_in_market"] = float((applied.sum(axis=1) > 0.01).mean())
    out["stats"]["stop_triggers"] = len(triggers)
    return out


def per_asset_daily_risk(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.DataFrame:
    """What the current weights actually risk, in the "% of capital" vocabulary.

    A position of weight w in an asset with daily vol s risks w*s of capital on a
    one-sigma day. Inverse-vol sizing holds that product roughly constant, which
    is exactly what a fixed "risk 1% per trade" rule is trying to achieve — with
    the difference that it adapts when volatility changes instead of relying on a
    stop distance chosen by hand.
    """
    from .strategy import realised_vol
    weights = apply_rebalance_schedule(target_weights(prices, cfg), cfg).iloc[-1]
    daily_vol = realised_vol(prices, cfg).iloc[-1] / np.sqrt(365.0)
    frame = pd.DataFrame({
        "weight": weights,
        "daily_vol_pct": daily_vol * 100,
        "one_sigma_risk_pct_of_capital": weights * daily_vol * 100,
    })
    return frame
