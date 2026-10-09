"""H4 range break, lower-timeframe rejection, fixed 2:1.

The author's rule:

    fix the high and the low of an H4 candle, drop to M5, and as soon as price
    breaks a low, wait for a confirmation — a rejection or an engulfing candle —
    then buy, stop under the rejecting candle, take profit at twice the stop.

Simple enough to state in one line, and that is its virtue: there is almost
nothing to overfit. The target is not a level the market put anywhere, it is
twice the stop, which makes the whole thing a pure bet on the rejection meaning
something.

That also makes the arithmetic brutal and exact. Under a random walk the chance
of touching +2R before -1R is 1/(1+2) = 33.3%, so the rule has to beat 33.3%
just to be no worse than a coin. With costs it has to beat

    (1 + fees_in_R) / (1 + 2)

and fees_in_R is the round-trip cost divided by the stop distance — which, with
a stop set by one M5 candle, is around 1.0R on crypto futures. That puts the
break-even near 67%. The lower the reward:risk, the more the fees bite: at 2:1
they are divided by 3, at 4:1 by 5.

None of that is an opinion about the rule. It is what the rule costs before it
is right about anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class H4Config:
    rr: float = 2.0                  # take profit at this multiple of the stop
    stop_buffer_frac: float = 0.15   # of the rejecting candle's range
    break_lookback: int = 24         # LTF bars after the break to wait for a trigger
    require_close_below: bool = False # True: the break needs a CLOSE under the low
    confirm: str = "both"            # "reject" | "engulf" | "both"
    max_hold_bars: int = 288         # abandon a trade that neither wins nor loses
    fee_per_side: float = 0.0007     # crypto futures at high leverage
    max_fee_fraction_of_r: float = 1.0   # 1.0 = no filter; the backtest reports it
    pin_wick_frac: float = 0.55      # a rejection: this much of the range is lower wick
    pin_close_frac: float = 0.55     # and the close sits in this top fraction
    # An engulfing bar has to engulf a BODY. Against a doji — a previous bar
    # whose open and close coincide — every up bar qualified, which silently
    # counted ordinary bars as confirmations and diluted the engulfing signal
    # in the backtest. Both bodies now have to be real.
    engulf_min_body_frac: float = 0.50   # of the confirming bar's own range
    engulf_prev_body_frac: float = 0.10  # of the previous bar's range


def confirms_long(bars: pd.DataFrame, i: int, cfg: H4Config) -> str | None:
    """A rejection or a bullish engulfing bar, as the author describes them."""
    o, h, l, c = (float(bars[k].iloc[i]) for k in ("open", "high", "low", "close"))
    po, pc = float(bars["open"].iloc[i - 1]), float(bars["close"].iloc[i - 1])
    rng = h - l
    if rng <= 0:
        return None
    # The rejection is tested FIRST. A bar can satisfy both definitions, and the
    # backtest shows the rejection carries the signal while the engulfing adds
    # nothing, so a bar that is both should be labelled by what matters.
    if cfg.confirm in ("reject", "both"):
        lower_wick = min(o, c) - l
        if lower_wick >= cfg.pin_wick_frac * rng and c >= l + cfg.pin_close_frac * rng:
            return "rejection"
    if cfg.confirm in ("engulf", "both"):
        ph, pl = float(bars["high"].iloc[i - 1]), float(bars["low"].iloc[i - 1])
        prev_rng, prev_body = ph - pl, abs(pc - po)
        real_prev = prev_rng > 0 and prev_body >= cfg.engulf_prev_body_frac * prev_rng
        real_body = abs(c - o) >= cfg.engulf_min_body_frac * rng
        if (c > o and real_prev and real_body
                and c >= max(po, pc) and o <= min(po, pc)):
            return "engulfing"
    return None


@dataclass
class Trade:
    entered: object = None
    exited: object = None
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    exit_price: float = 0.0
    outcome: str = ""        # "win" | "loss" | "timeout"
    r_gross: float = 0.0     # in units of the stop distance
    r_net: float = 0.0       # after the round-trip fee
    fees_in_r: float = 0.0
    stop_pct: float = 0.0
    confirm: str = ""
    h4_low: float = 0.0


def backtest(htf: pd.DataFrame, ltf: pd.DataFrame,
             cfg: H4Config = H4Config()) -> list:
    """Walk the lower timeframe once, in order, and record every trade.

    Rules of the simulation, all conservative:

      - an H4 candle's level is only usable AFTER that candle has closed
      - the break must happen while the level is the most recent one
      - when a bar touches both the stop and the target, the STOP is taken;
        intrabar order is unknowable and assuming otherwise flatters the result
      - one position at a time, and the entry costs the fee on both sides
    """
    h_high, h_low = htf["high"].to_numpy(), htf["low"].to_numpy()
    l_open, l_high, l_low, l_close = (ltf[k].to_numpy()
                                      for k in ("open", "high", "low", "close"))
    # The latest CLOSED H4 candle at each LTF bar. Indexing with ffill on the
    # H4 open stamps picks the candle still FORMING, whose low is the minimum of
    # the LTF bars inside it — including the current one. The break condition
    # l_low[i] < level is then false by construction and the rule never fires.
    # A candle stamped 08:00 is only usable from 12:00.
    h_step = (htf.index[1] - htf.index[0] if len(htf) > 1
              else pd.Timedelta(hours=4))
    h_close_times = htf.index + h_step
    h_idx = np.searchsorted(h_close_times, ltf.index, side="right") - 1

    trades: list = []
    i, n = 1, len(ltf)
    while i < n:
        k = h_idx[i]
        if k < 0:        # no H4 candle has closed yet
            i += 1
            continue
        level = h_low[k]                       # the H4 low being broken
        broke = l_low[i] < level
        if cfg.require_close_below:
            broke = broke and l_close[i] < level
        if not broke:
            i += 1
            continue

        # a break: look forward for the confirming bar
        hit = None
        for j in range(i + 1, min(i + cfg.break_lookback, n)):
            why = confirms_long(ltf, j, cfg)
            if why:
                hit = (j, why)
                break
        if hit is None:
            i += 1
            continue
        j, why = hit

        entry = float(l_close[j])
        pad = cfg.stop_buffer_frac * max(l_high[j] - l_low[j], 1e-12)
        stop = float(l_low[j] - pad)
        risk = entry - stop
        if risk <= 0:
            i = j + 1
            continue
        target = entry + cfg.rr * risk
        fee_r = (2 * cfg.fee_per_side * entry) / risk

        tr = Trade(entered=ltf.index[j], entry=entry, stop=stop, target=target,
                   fees_in_r=fee_r, stop_pct=risk / entry, confirm=why,
                   h4_low=float(level))
        # resolve it bar by bar, stop first on an ambiguous bar
        end = min(j + 1 + cfg.max_hold_bars, n)
        for m in range(j + 1, end):
            if l_low[m] <= stop:
                tr.exited, tr.exit_price = ltf.index[m], stop
                tr.outcome, tr.r_gross = "loss", -1.0
                break
            if l_high[m] >= target:
                tr.exited, tr.exit_price = ltf.index[m], target
                tr.outcome, tr.r_gross = "win", cfg.rr
                break
        else:
            m = end - 1
            tr.exited, tr.exit_price = ltf.index[m], float(l_close[m])
            tr.outcome = "timeout"
            tr.r_gross = (tr.exit_price - entry) / risk
        tr.r_net = tr.r_gross - fee_r
        trades.append(tr)
        i = m + 1                              # no overlapping positions
    return trades


def summarise(trades: list, cfg: H4Config = H4Config()) -> dict:
    """What the trades add up to, and what the rule would have needed."""
    if not trades:
        return {"trades": 0}
    r_net = np.array([t.r_net for t in trades])
    r_gross = np.array([t.r_gross for t in trades])
    wins = sum(1 for t in trades if t.outcome == "win")
    losses = sum(1 for t in trades if t.outcome == "loss")
    outs = sum(1 for t in trades if t.outcome == "timeout")
    fees = float(np.mean([t.fees_in_r for t in trades]))
    wr = wins / len(trades)
    se = float(np.sqrt(wr * (1 - wr) / len(trades))) if len(trades) else 0.0
    return {
        "trades": len(trades), "wins": wins, "losses": losses, "timeouts": outs,
        "win_rate": wr, "win_rate_se": se,
        "breakeven_random": 1.0 / (1.0 + cfg.rr),
        "breakeven_with_fees": (1.0 + fees) / (1.0 + cfg.rr),
        "expectancy_gross_r": float(r_gross.mean()),
        "expectancy_net_r": float(r_net.mean()),
        "total_net_r": float(r_net.sum()),
        "std_net_r": float(r_net.std(ddof=1)) if len(r_net) > 1 else 0.0,
        "t_stat": (float(r_net.mean() / (r_net.std(ddof=1) / np.sqrt(len(r_net))))
                   if len(r_net) > 1 and r_net.std(ddof=1) > 0 else 0.0),
        "mean_fees_in_r": fees,
        "median_stop_pct": float(np.median([t.stop_pct for t in trades])),
    }
