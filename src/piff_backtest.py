"""Replay the PIFF rule over M1 history and measure what it did.

The engine's unit tests prove it applies the rule. They say nothing about
whether the rule pays, and no backtest existed, so every number quoted about
this strategy so far came from the author's own FX Replay log rather than from
anything reproducible. This closes that gap: give it M1 bars and it returns the
trade list and the statistics, or it returns nothing and says so.

Four modelling choices decide the answer, and each one is set the pessimistic
way, because a backtest that flatters a rule is worse than none:

  * **Only closed bars reach the engine.** The slice handed to `generate` ends
    at the previous bar, never the forming one. Reading a live bar's close is
    how a structure break repaints -- measured on the real feed, the M5 bar
    stamped 14:30 showed a close of 30,863.3 at 14:30 and 30,851.8 at 14:32,
    on either side of the threshold.
  * **A bar that touches both the stop and the target is a loss.** M1 bars
    carry no tick sequence, so the order inside them is unknowable. Resolving
    the ambiguity the other way turns losses into 4R winners and would be the
    single largest lie this file could tell.
  * **The lookback is capped at the venue's own limit.** MoonX serves at most
    500 bars with no start date, so a decision made here on more history than
    that is a decision the live loop could never reproduce.
  * **Fees are charged on both sides**, at the venue's measured rate, against
    the notional at the fill -- not netted out of the R multiple afterwards.

What it does NOT model: slippage, the spread, weekend gaps, and the chance
that a resting limit order at the gap edge goes unfilled while price trades
through it. All four make the real result worse than this one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .piff import PiffConfig, generate
from .piff_live import resample


@dataclass
class Trade:
    direction: str
    signalled_at: pd.Timestamp
    filled_at: pd.Timestamp | None
    entry: float
    stop: float
    target: float
    stop_points: float
    planned_rr: float
    fee_r: float
    outcome: str = ""          # "target" | "stop" | "unfilled" | "open"
    r: float = 0.0             # realised, net of both fees
    closed_at: pd.Timestamp | None = None

    def to_dict(self) -> dict:
        return {k: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
                for k, v in self.__dict__.items()}


@dataclass
class BacktestConfig:
    structure_rule: str = "5min"
    pending: bool = True         # resting orders: the mode that needs no watcher
    lookback: int = 500          # the venue's own candle cap
    max_wait_bars: int = 60      # M1 bars a resting order stays live before it expires
    max_hold_bars: int = 480     # M1 bars a filled trade may stay open
    warmup: int | None = None    # bars before the first decision; defaults to lookback
    strategy: PiffConfig = field(default_factory=PiffConfig)


def _slice_htf(htf: pd.DataFrame | None, upto: pd.Timestamp) -> pd.DataFrame | None:
    """The M15 bars that had closed by `upto`.

    A bar is addressed by its opening stamp, so the bar containing `upto` is
    still forming and is dropped: its wick is not yet a level the market has
    printed.
    """
    if htf is None or not len(htf):
        return None
    step = htf.index[1] - htf.index[0] if len(htf) > 1 else pd.Timedelta(minutes=15)
    return htf.loc[htf.index + step <= upto]


def _resolve(bars: pd.DataFrame, start: int, trade: Trade,
             cfg: BacktestConfig) -> Trade:
    """Walk forward from `start` until the order fills and the trade closes."""
    high = bars["high"].to_numpy()
    low = bars["low"].to_numpy()
    idx = bars.index
    long = trade.direction == "long"

    i = start
    fill = None
    limit = min(start + cfg.max_wait_bars, len(bars) - 1)
    while i <= limit:
        # A resting order fills when price trades to it. The stop order of the
        # confirming-bar break and the limit order at the gap edge sit on
        # opposite sides of price, so the test is directional either way.
        touched = (low[i] <= trade.entry <= high[i])
        if touched:
            fill = i
            break
        # Price can run past the stop without ever filling the order; that is
        # the order expiring, not a loss. The stop sits on the far side of the
        # entry from price, so the sides are the same way round as they are
        # after the fill -- writing them the other way round made every short
        # expire on its first bar, because any bar's low sits under a stop
        # that is above price.
        if (low[i] <= trade.stop) if long else (high[i] >= trade.stop):
            trade.outcome = "unfilled"
            trade.closed_at = idx[i]
            return trade
        i += 1
    if fill is None:
        trade.outcome = "unfilled"
        trade.closed_at = idx[min(limit, len(bars) - 1)]
        return trade

    trade.filled_at = idx[fill]
    held = min(fill + cfg.max_hold_bars, len(bars) - 1)
    for j in range(fill, held + 1):
        hit_stop = (low[j] <= trade.stop) if long else (high[j] >= trade.stop)
        hit_target = (high[j] >= trade.target) if long else (low[j] <= trade.target)
        # Both inside one M1 bar: the sequence is unknowable, so it is a loss.
        if hit_stop:
            trade.outcome, trade.r = "stop", -1.0 - trade.fee_r
            trade.closed_at = idx[j]
            return trade
        if hit_target:
            trade.outcome, trade.r = "target", trade.planned_rr - trade.fee_r
            trade.closed_at = idx[j]
            return trade
    trade.outcome = "open"
    trade.closed_at = idx[held]
    return trade


def replay(m1: pd.DataFrame, m15: pd.DataFrame | None = None,
           cfg: BacktestConfig = BacktestConfig()) -> dict:
    """Every trade the rule would have taken, and the statistics of them.

    `m1` is the entry frame. `m15` is the frame the target is read on; when it
    is None it is resampled from `m1`, which only reaches as far back as `m1`
    does. One position at a time, as the live loop enforces.
    """
    warmup = cfg.warmup if cfg.warmup is not None else cfg.lookback
    warmup = max(warmup, cfg.strategy.min_bars + 1)
    trades: list[Trade] = []

    i = warmup
    while i < len(m1):
        window = m1.iloc[max(0, i - cfg.lookback):i]   # closed bars only
        structure = resample(window, cfg.structure_rule)
        if len(structure) < cfg.strategy.min_structure_bars:
            i += 1
            continue
        target_bars = (_slice_htf(m15, window.index[-1]) if m15 is not None
                       else resample(window, "15min"))

        sig = generate(window, structure, None, cfg.strategy,
                       pending=cfg.pending, target_bars=target_bars)
        if sig.action == "flat":
            i += 1
            continue

        trade = Trade(direction=sig.action, signalled_at=window.index[-1],
                      filled_at=None, entry=sig.entry, stop=sig.stop,
                      target=sig.target, stop_points=sig.stop_points,
                      planned_rr=sig.rr, fee_r=sig.fee_fraction_of_r)
        trade = _resolve(m1, i, trade, cfg)
        trades.append(trade)
        # Resume after the trade resolved: one position at a time, and a signal
        # re-read on the next bar is the same trade counted twice.
        closed = m1.index.get_indexer([trade.closed_at])[0]
        i = max(i + 1, closed + 1)

    return {"trades": trades, "stats": stats(trades)}


def stats(trades: list[Trade]) -> dict:
    """What the replay measured, with the uncertainty on it.

    The win rate is a proportion from a finite sample, so it carries a standard
    error of sqrt(p(1-p)/n); quoting it without one invites reading noise as
    edge. The break-even rate is the author's identity,
    (1 + fees/stop_distance) / (1 + R:R), evaluated at the mean R:R and mean fee
    load actually taken -- the number the measured rate has to beat.
    """
    filled = [t for t in trades if t.outcome in ("target", "stop")]
    n = len(filled)
    out = {"signals": len(trades), "filled": n,
           "unfilled": sum(t.outcome == "unfilled" for t in trades),
           "still_open": sum(t.outcome == "open" for t in trades)}
    if not n:
        out.update(win_rate=None, win_rate_stderr=None, mean_rr=None,
                   mean_fee_r=None, breakeven_rate=None, expectancy_r=None,
                   total_r=None, edge_sigma=None)
        return out

    wins = sum(t.outcome == "target" for t in filled)
    p = wins / n
    rr = float(np.mean([t.planned_rr for t in filled]))
    fee = float(np.mean([t.fee_r for t in filled]))
    be = (1 + fee) / (1 + rr)
    rs = np.array([t.r for t in filled], dtype=float)
    se = float(np.sqrt(p * (1 - p) / n)) if 0 < p < 1 else 0.0
    out.update(
        win_rate=p, win_rate_stderr=se, mean_rr=rr, mean_fee_r=fee,
        breakeven_rate=be, expectancy_r=float(rs.mean()), total_r=float(rs.sum()),
        # How many standard errors the measured rate sits above break-even.
        # Below about 2 the sample cannot tell an edge from noise.
        edge_sigma=float((p - be) / se) if se > 0 else None)
    return out
