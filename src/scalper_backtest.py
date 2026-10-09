"""Walk-forward test of the scalper rule itself, on the longest series available.

The 5-minute history needed to measure the engine at its own timeframe is not
reachable from here. What can be measured is the *rule*: higher-timeframe trend
filter, pullback to the entry EMA that is then reclaimed, RSI band, ATR stop,
fixed reward:risk, time stop. That rule is scale-invariant — nothing in it
refers to a bar duration — so running it on daily bars with a weekly trend
filter answers the question that matters: does this entry logic have positive
expectancy at all, once costs are charged?

Two honest limits, both of which make this a proxy rather than the measurement:
  * The long series has closes only, so highs and lows are synthesised with a
    Brownian bridge pinned to the real closes and scaled to realised volatility.
    ATR and the "the low touched the EMA" test therefore use plausible, not
    actual, intraday extremes.
  * Expectancy measured on daily bars does not transfer to 1h bars by itself.
    It bounds the rule, not the horizon.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .scalper import ScalpConfig, generate


def synthetic_ohlc(closes: pd.Series, steps: int = 24, seed: int = 0) -> pd.DataFrame:
    """OHLC bars whose closes are real and whose extremes come from a bridge."""
    rng = np.random.default_rng(seed)
    logp = np.log(closes.to_numpy())
    sigma = np.diff(logp).std()
    rows = []
    for i in range(1, len(logp)):
        a, b = logp[i - 1], logp[i]
        t = np.arange(1, steps + 1) / steps
        walk = rng.standard_normal(steps).cumsum() / np.sqrt(steps)
        path = np.exp(a + t * (b - a) + sigma * (walk - t * walk[-1]))
        rows.append((float(np.exp(a)), float(path.max()), float(path.min()), float(np.exp(b))))
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                         index=closes.index[1:])
    frame["volume"] = 1.0
    return frame


def _resolve(bars: pd.DataFrame, start: int, entry: float, stop: float, target: float,
             max_bars: int, steps: int, rng) -> tuple[float, int]:
    """First barrier touched on a bridge path through the following bars."""
    sigma = np.log(bars["close"]).diff().std()
    for offset in range(1, max_bars + 1):
        i = start + offset
        if i >= len(bars):
            break
        a, b = np.log(bars["close"].iloc[i - 1]), np.log(bars["close"].iloc[i])
        t = np.arange(1, steps + 1) / steps
        walk = rng.standard_normal(steps).cumsum() / np.sqrt(steps)
        path = np.exp(a + t * (b - a) + sigma * (walk - t * walk[-1]))
        if (path <= stop).any() and (path >= target).any():
            # Both inside one bar: assume the adverse one filled first.
            return -1.0, offset
        if (path <= stop).any():
            return -1.0, offset
        if (path >= target).any():
            return (target - entry) / (entry - stop), offset
    last = bars["close"].iloc[min(start + max_bars, len(bars) - 1)]
    return (last - entry) / (entry - stop), max_bars


def run(closes: pd.Series, cfg: ScalpConfig, trend_rule: str = "W",
        seeds: int = 4, steps: int = 24) -> dict:
    pnl, dur, n_signals = [], [], 0
    for seed in range(seeds):
        rng = np.random.default_rng(1000 + seed)
        bars = synthetic_ohlc(closes, steps=steps, seed=seed)
        higher = bars.resample(trend_rule).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        ).dropna()
        for i in range(cfg.min_bars, len(bars) - 1):
            window = bars.iloc[: i + 1]
            hi = higher.loc[: window.index[-1]]
            if len(hi) < cfg.trend_slow:
                continue
            signal = generate(window, hi, cfg)
            if signal.action != "long":
                continue
            n_signals += 1
            r, bars_held = _resolve(bars, i, signal.entry, signal.stop, signal.target,
                                    cfg.time_stop_bars, steps, rng)
            cost = (2 * cfg.fee_per_side) / signal.stop_distance
            pnl.append(r - cost)
            dur.append(bars_held)

    if not pnl:
        return {"signals": 0}
    pnl = np.array(pnl)
    dur = np.array(dur)
    per_seed = len(pnl) / seeds
    n_eff = max(per_seed / max(dur.mean(), 1.0), 1.0)
    return {
        "signals": int(per_seed),
        "win_rate": float((pnl > 0).mean() * 100),
        "net_R": float(pnl.mean()),
        "stderr_R": float(pnl.std() / np.sqrt(n_eff)),
        "avg_bars_held": float(dur.mean()),
        "signal_rate_pct": float(per_seed / (len(closes) - cfg.min_bars) * 100),
    }
