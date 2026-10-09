"""Intraday signal engine: the fastest horizon the fee schedule allows.

Why this is not a 1-5 minute scalper, stated once so the code is not mistaken
for one. MoonX charges 0.060% per side at 10-24x, on notional. For a barrier
strategy, that cost expressed in R is fee_round_trip / stop_distance, and the
win rate needed to break even is exactly (1 + cost_in_R) times the random-walk
hit rate — a result that holds for EVERY reward:risk ratio, so widening the
target does not help at all. The only lever is the stop width:

    stop 0.21% (2 sigma of a 5m bar) -> 0.57R of fees -> need 1.57x random
    stop 0.60% (6 sigma)             -> 0.20R         -> need 1.20x random

A systematic edge of 1.2x random is demanding but real; 1.57x is not something
anyone sustains paying retail fees. A 0.60% stop on 0.106% 5m volatility takes
~32 bars to resolve, i.e. 2-3 hours. That is the floor, and it is set by the fee
schedule rather than by preference.

The engine is deterministic: same candles in, same signal out. It computes
signals only — placing the order is the executor's job (src/execution.py for a
ccxt venue, or the MCP tools for MoonX), and sizing is leveraged_risk's.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScalpConfig:
    # --- horizon, derived from the fee schedule rather than chosen ---
    fee_per_side: float = 0.0006       # MoonX 10-24x, on notional
    max_fee_fraction_of_r: float = 0.20  # fees may not exceed 20% of the stop
    stop_atr_mult: float = 1.5
    atr_period: int = 14

    # --- entry ---
    trend_fast: int = 20               # on the higher timeframe
    trend_slow: int = 50
    pullback_lookback: int = 6         # bars to look back for the pullback low
    rsi_period: int = 14
    rsi_floor: float = 35.0            # below this the pullback is a breakdown
    rsi_ceiling: float = 70.0          # above this we are chasing

    # --- exit ---
    reward_risk: float = 3.0
    time_stop_bars: int = 36           # 3 hours on 5m bars
    bars_per_hour: int = 12

    # --- filters ---
    min_bars: int = 120
    blackout_minutes: int = 10         # around a scheduled news time


@dataclass
class Signal:
    action: str                     # "long" | "flat"
    symbol: str = ""
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    stop_distance: float = 0.0      # fraction of price
    reward_risk: float = 0.0
    fee_fraction_of_r: float = 0.0
    time_stop_bars: int = 0
    reasons: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"action": self.action, "symbol": self.symbol,
                "entry": round(self.entry, 2), "stop": round(self.stop, 2),
                "target": round(self.target, 2),
                "stop_distance_pct": round(self.stop_distance * 100, 3),
                "reward_risk": round(self.reward_risk, 2),
                "fee_fraction_of_r": round(self.fee_fraction_of_r, 3),
                "time_stop_bars": self.time_stop_bars,
                "reasons": self.reasons, "rejected": self.rejected}


def atr(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = candles["high"], candles["low"], candles["close"]
    prev = close.shift(1)
    true_range = pd.concat([high - low, (high - prev).abs(), (low - prev).abs()],
                           axis=1).max(axis=1)
    return true_range.ewm(alpha=1.0 / period, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / period, min_periods=period).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / period, min_periods=period).mean()
    rs = gain / loss.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def in_blackout(timestamp: pd.Timestamp, news_times, minutes: int = 10) -> bool:
    """True inside +/- `minutes` of any scheduled news release."""
    window = pd.Timedelta(minutes=minutes)
    return any(abs(timestamp - pd.Timestamp(t)) <= window for t in (news_times or []))


def generate(candles: pd.DataFrame, higher: pd.DataFrame, cfg: ScalpConfig = ScalpConfig(),
             symbol: str = "", news_times=None) -> Signal:
    """One long/flat decision from the last closed bar.

    `candles` is the entry timeframe (5m), `higher` the trend timeframe (1h).
    Long only: shorting crypto majors fights the unconditional drift and pays
    funding, and nothing in this engine is calibrated for it.

    The rule: trade with the higher-timeframe trend, enter on a pullback that
    holds, never on a breakdown and never on an extension.
    """
    rejected = []
    if len(candles) < cfg.min_bars or len(higher) < cfg.trend_slow:
        return Signal("flat", symbol, rejected=["not enough history"])

    last = candles.iloc[-1]
    now = candles.index[-1]

    if in_blackout(now, news_times, cfg.blackout_minutes):
        rejected.append(f"news blackout +/-{cfg.blackout_minutes}min")

    hclose = higher["close"]
    ema_fast = hclose.ewm(span=cfg.trend_fast).mean().iloc[-1]
    ema_slow = hclose.ewm(span=cfg.trend_slow).mean().iloc[-1]
    trend_up = ema_fast > ema_slow
    if not trend_up:
        rejected.append("higher timeframe trend is not up")

    close = candles["close"]
    ema_entry = close.ewm(span=cfg.trend_fast).mean()
    recent_low = candles["low"].iloc[-cfg.pullback_lookback:-1].min()
    touched = recent_low <= ema_entry.iloc[-1]
    reclaimed = last["close"] > ema_entry.iloc[-1]
    if not touched:
        rejected.append("no pullback to the entry EMA in the lookback")
    if not reclaimed:
        rejected.append("price has not reclaimed the entry EMA")

    momentum = rsi(close, cfg.rsi_period).iloc[-1]
    if momentum < cfg.rsi_floor:
        rejected.append(f"RSI {momentum:.0f} below {cfg.rsi_floor:.0f}: breakdown, not pullback")
    if momentum > cfg.rsi_ceiling:
        rejected.append(f"RSI {momentum:.0f} above {cfg.rsi_ceiling:.0f}: chasing an extension")

    entry = float(last["close"])
    stop_abs = float(atr(candles, cfg.atr_period).iloc[-1]) * cfg.stop_atr_mult
    if not np.isfinite(stop_abs) or stop_abs <= 0:
        return Signal("flat", symbol, rejected=rejected + ["ATR unavailable"])

    stop_distance = stop_abs / entry
    fee_fraction = (2 * cfg.fee_per_side) / stop_distance
    if fee_fraction > cfg.max_fee_fraction_of_r:
        rejected.append(
            f"stop {stop_distance * 100:.2f}% is too tight for the fee schedule: "
            f"fees would be {fee_fraction:.2f}R, above the {cfg.max_fee_fraction_of_r:.2f}R limit "
            f"(needs a stop of at least "
            f"{2 * cfg.fee_per_side / cfg.max_fee_fraction_of_r * 100:.2f}%)")

    signal = Signal(
        action="flat" if rejected else "long",
        symbol=symbol, entry=entry,
        stop=entry - stop_abs,
        target=entry + stop_abs * cfg.reward_risk,
        stop_distance=stop_distance,
        reward_risk=cfg.reward_risk,
        fee_fraction_of_r=fee_fraction,
        time_stop_bars=cfg.time_stop_bars,
        rejected=rejected,
    )
    if not rejected:
        signal.reasons = [
            f"1h trend up (EMA{cfg.trend_fast} {ema_fast:,.0f} > EMA{cfg.trend_slow} {ema_slow:,.0f})",
            "pullback to the 5m EMA then reclaimed",
            f"RSI {momentum:.0f} inside [{cfg.rsi_floor:.0f}, {cfg.rsi_ceiling:.0f}]",
            f"stop {stop_distance * 100:.2f}% carries only {fee_fraction:.2f}R of fees",
        ]
    return signal


def minimum_viable_stop(cfg: ScalpConfig = ScalpConfig()) -> float:
    """The tightest stop whose fees stay inside the budget. The horizon floor."""
    return 2 * cfg.fee_per_side / cfg.max_fee_fraction_of_r


def breakeven_multiple_of_random(stop_distance: float, cfg: ScalpConfig = ScalpConfig()) -> float:
    """How much better than a coin flip the entries must be, at this stop.

    Independent of the reward:risk ratio — that is the whole point.
    """
    return 1.0 + (2 * cfg.fee_per_side) / stop_distance
