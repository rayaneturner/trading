"""Signal construction.

First principles, stated so they can be attacked:

1. Crypto majors have no cash-flow anchor, so nothing pulls price back to a
   fair value. What they do have is flow-driven, reflexive trends (leverage,
   liquidation cascades, ETF and treasury flows) and extremely strong
   volatility clustering. So the exploitable structure is *persistence*, not
   valuation.
2. Therefore: do not forecast direction. Participate while the trend is up,
   sit in cash while it is not, and size by inverse volatility so that a
   doubling of vol does not double the risk taken.
3. Every parameter is a cost. The signal uses three slow, uncorrelated trend
   votes averaged together instead of one "best" lookback, because the average
   of several mediocre horizons is far more stable out of sample than the
   single horizon that happened to win in-sample.
4. Long/flat only. Shorting crypto majors fights the unconditional positive
   drift and pays borrow/funding; it is a different, harder business.

The output is a target-weight matrix in [0, max_weight], one row per day. It is
a pure function of past prices: no look-ahead, no refitting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT, StrategyConfig


def trend_score(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.DataFrame:
    """Fraction of trend votes that are positive, in {0, 1/3, 2/3, 1}."""
    ema_fast = prices.ewm(span=cfg.ema_fast, min_periods=cfg.ema_fast).mean()
    ema_slow = prices.ewm(span=cfg.ema_slow, min_periods=cfg.ema_slow).mean()
    sma_long = prices.rolling(cfg.sma_long, min_periods=cfg.sma_long).mean()

    vote_cross = (ema_fast > ema_slow).astype(float).where(ema_slow.notna())
    vote_regime = (prices > sma_long).astype(float).where(sma_long.notna())
    past = prices.shift(cfg.mom_lookback)
    vote_mom = (prices > past).astype(float).where(past.notna())

    return (vote_cross + vote_regime + vote_mom) / 3.0


def realised_vol(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.DataFrame:
    """Annualised EWMA volatility of daily log returns, floored."""
    rets = np.log(prices).diff()
    vol = rets.ewm(halflife=cfg.vol_halflife, min_periods=cfg.vol_halflife).std() * np.sqrt(365.0)
    return vol.clip(lower=cfg.vol_floor)


def target_weights(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.DataFrame:
    """Target portfolio weights per asset, decided on each day's close.

    weight = trend_score * (target_vol / realised_vol), capped per asset, then
    scaled down if the gross exposure would exceed `max_gross`.
    """
    score = trend_score(prices, cfg)
    vol = realised_vol(prices, cfg)

    raw = score * (cfg.target_vol / vol)
    raw = raw.clip(upper=cfg.max_weight_per_asset).fillna(0.0)

    gross = raw.sum(axis=1)
    scale = (cfg.max_gross / gross).clip(upper=1.0).replace([np.inf, -np.inf], 1.0).fillna(1.0)
    weights = raw.mul(scale, axis=0)

    # An asset with no usable history is simply not traded.
    weights = weights.where(prices.notna(), 0.0)
    return weights


def apply_rebalance_schedule(weights: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.DataFrame:
    """Hold the last traded weights except on rebalance days, and only move a
    leg when it drifts more than `no_trade_band`.

    This is where most of the turnover (and therefore most of the cost) is
    killed. It is applied to the *target*, so the backtest and the live
    executor share one definition of "what we should be holding today".
    """
    held = np.zeros(weights.shape[1])
    out = np.empty(weights.shape)
    index = weights.index
    values = weights.to_numpy(dtype=float)

    for i in range(len(index)):
        is_rebal = cfg.rebalance_weekday is None or index[i].weekday() == cfg.rebalance_weekday
        if is_rebal:
            desired = values[i]
            move = np.abs(desired - held) > cfg.no_trade_band
            # Always honour a full exit: going to zero is risk reduction, and
            # a band must never trap us in a position the signal has dropped.
            move |= (desired == 0.0) & (held > 0.0)
            held = np.where(move, desired, held)
        out[i] = held

    return pd.DataFrame(out, index=index, columns=weights.columns)


def live_weights(prices: pd.DataFrame, cfg: StrategyConfig = DEFAULT) -> pd.Series:
    """The weights to be holding after today's close. Last row of the pipeline."""
    scheduled = apply_rebalance_schedule(target_weights(prices, cfg), cfg)
    return scheduled.iloc[-1]
