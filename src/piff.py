"""PIFF: liquidity sweep -> market structure shift -> FVG entry.

Mechanised from the author's own description and from four logged FX Replay
trades that fix the parameters the description left open.

The sequence, in the order the price has to produce it:

    1. a swing high (or low) exists and holds resting liquidity
    2. a bar sweeps it — its wick trades beyond the swing, its close comes back
       inside, so the move took stops without accepting the level
    3. a later bar closes beyond the opposing swing: structure has shifted
    4. the leg that did the shifting leaves a fair value gap behind it
    5. price retraces into that gap
    6. entry, by one of two modes the author actually uses:
         "limit" — the order rests at the gap edge and fills on the retrace;
                   the gap itself is the trigger, no confirmation is waited for
         "stop"  — a confirming bar (engulfing or pin) has to print inside the
                   gap first, and entry triggers on the break of its extreme
    7. stop beyond the structure the entry leans on, plus a buffer
    8. target at the opposing swing the previous leg left behind — the next
       pool of resting liquidity in the trade's direction

Which mode applies changes where the stop sits, which is why both are here: a
limit entry leans on the swept swing (wider), a stop entry leans on the
confirming bar (tighter). In the logged trades the limit entries carried 21.8
and 44.8 point stops, the stop entries 29.3 and 16.6.

Nothing here refers to a bar duration — the rule is scale-invariant and the
caller supplies the timeframe.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PiffConfig:
    # --- structure ---
    swing_k: int = 2                 # fractal half-width: a swing is the extreme of 2k+1 bars
    sweep_max_age: int = 40          # bars a swept swing stays relevant
    mss_max_age: int = 20            # bars between the sweep and the structure shift
    fvg_min_points: float = 2.0      # ignore imbalances too small to be a zone
    fvg_max_age: int = 60            # bars a gap stays valid before it is stale

    # --- entry ---
    entry_mode: str = "both"         # "limit" | "stop" | "both"
    fill_at: str = "far"             # which gap edge the limit rests at: "near" | "far" | "mid"
    stop_buffer_points: float = 2.0  # "one above the last candle"

    # --- higher timeframe bias ---
    require_htf_bias: bool = True
    htf_fast: int = 20
    htf_slow: int = 50

    # --- acceptance ---
    min_rr: float = 3.0
    fee_per_side: float = 0.0001     # MoonX indices, fraction of notional
    max_fee_fraction_of_r: float = 0.40

    # --- session (UTC hours, half-open) ---
    session_start_hour: int | None = 13
    session_end_hour: int | None = 21

    min_bars: int = 120


@dataclass
class PiffSignal:
    action: str                      # "long" | "short" | "flat"
    entry_type: str = ""             # "limit" | "stop"
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    stop_points: float = 0.0
    rr: float = 0.0
    fee_fraction_of_r: float = 0.0
    swept_level: float = 0.0
    fvg: tuple = ()
    reasons: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"action": self.action, "entry_type": self.entry_type,
                "entry": round(self.entry, 2), "stop": round(self.stop, 2),
                "target": round(self.target, 2),
                "stop_points": round(self.stop_points, 1), "rr": round(self.rr, 2),
                "fee_fraction_of_r": round(self.fee_fraction_of_r, 3),
                "swept_level": round(self.swept_level, 2),
                "fvg": [round(x, 2) for x in self.fvg],
                "reasons": self.reasons, "rejected": self.rejected}


def swing_highs(bars: pd.DataFrame, k: int) -> np.ndarray:
    """Indices whose high is the strict maximum of the 2k+1 window centred on them."""
    high = bars["high"].to_numpy()
    out = []
    for i in range(k, len(high) - k):
        window = high[i - k: i + k + 1]
        if high[i] == window.max() and (window == high[i]).sum() == 1:
            out.append(i)
    return np.array(out, dtype=int)


def swing_lows(bars: pd.DataFrame, k: int) -> np.ndarray:
    low = bars["low"].to_numpy()
    out = []
    for i in range(k, len(low) - k):
        window = low[i - k: i + k + 1]
        if low[i] == window.min() and (window == low[i]).sum() == 1:
            out.append(i)
    return np.array(out, dtype=int)


def find_fvg(bars: pd.DataFrame, start: int, end: int, direction: str,
             min_points: float, pick: str = "first") -> tuple | None:
    """A 3-bar imbalance inside [start, end], in `direction`.

    Bullish gap: bar i's low sits above bar i-2's high — price left a void going
    up. Bearish gap: bar i's high sits below bar i-2's low.

    `pick` decides which gap when the leg left several. "first" is the default
    because the author places the zone "toward the first wick broken", i.e. at
    the origin of the displacement rather than at its end: that gap is the one
    price has to travel back to, and it is what makes the stop sit behind the
    swept level instead of inside the move.
    """
    high, low = bars["high"].to_numpy(), bars["low"].to_numpy()
    found = None
    for i in range(max(start, 2), min(end, len(bars) - 1) + 1):
        gap = None
        if direction == "long" and low[i] - high[i - 2] >= min_points:
            gap = (float(high[i - 2]), float(low[i]), i)
        elif direction == "short" and low[i - 2] - high[i] >= min_points:
            gap = (float(high[i]), float(low[i - 2]), i)
        if gap is None:
            continue
        if pick == "first":
            return gap
        found = gap
    return found


def is_confirming(bars: pd.DataFrame, i: int, direction: str) -> str | None:
    """Engulfing or pin bar in the trade's direction. Returns which, or None."""
    o, h, l, c = (bars["open"].iloc[i], bars["high"].iloc[i],
                  bars["low"].iloc[i], bars["close"].iloc[i])
    po, pc = bars["open"].iloc[i - 1], bars["close"].iloc[i - 1]
    body = abs(c - o)
    rng = h - l
    if rng <= 0:
        return None

    # A pin is defined by where the wick and the close sit in the bar's range,
    # not by a body multiple: a rejection bar often has a near-zero body, and
    # any multiple of zero is zero.
    lower_wick = min(o, c) - l
    upper_wick = h - max(o, c)

    if direction == "long":
        if c > o and c >= max(po, pc) and o <= min(po, pc):
            return "engulfing"
        if lower_wick >= 0.6 * rng and c >= l + 0.6 * rng:
            return "pin"
    else:
        if c < o and c <= min(po, pc) and o >= max(po, pc):
            return "engulfing"
        if upper_wick >= 0.6 * rng and c <= h - 0.6 * rng:
            return "pin"
    return None


def _htf_bias(htf: pd.DataFrame, cfg: PiffConfig) -> str:
    close = htf["close"]
    fast = close.ewm(span=cfg.htf_fast).mean().iloc[-1]
    slow = close.ewm(span=cfg.htf_slow).mean().iloc[-1]
    return "long" if fast > slow else "short"


def generate(entry_bars: pd.DataFrame, structure_bars: pd.DataFrame,
             htf: pd.DataFrame | None = None, cfg: PiffConfig = PiffConfig()) -> PiffSignal:
    """One decision, from three timeframes, exactly as the author reads them.

    `structure_bars` (M10-M15) carries the sweep and the structure shift.
    `entry_bars` (M1) carries the fair value gap and the test of it.
    `htf` (M15-H1) carries the directional bias.

    Searching the gap on M1 inside the window the structure leg spans is the
    whole point: the shift says where and which way, the M1 gap says at what
    price, and the test of that gap is what triggers.
    """
    rejected = []
    if len(entry_bars) < cfg.min_bars or len(structure_bars) < cfg.min_bars // 4:
        return PiffSignal("flat", rejected=["not enough history"])

    now = entry_bars.index[-1]
    if cfg.session_start_hour is not None:
        if not (cfg.session_start_hour <= now.hour < cfg.session_end_hour):
            rejected.append(f"outside the {cfg.session_start_hour}-{cfg.session_end_hour}h UTC session")

    bias = None
    if htf is not None and len(htf) >= cfg.htf_slow:
        bias = _htf_bias(htf, cfg)

    s_hi, s_lo = swing_highs(structure_bars, cfg.swing_k), swing_lows(structure_bars, cfg.swing_k)
    s_high = structure_bars["high"].to_numpy()
    s_low = structure_bars["low"].to_numpy()
    s_close = structure_bars["close"].to_numpy()
    s_last = len(structure_bars) - 1

    e_close = entry_bars["close"].to_numpy()
    e_high = entry_bars["high"].to_numpy()
    e_low = entry_bars["low"].to_numpy()
    e_last = len(entry_bars) - 1

    best = None
    for direction in ("long", "short"):
        if cfg.require_htf_bias and bias is not None and bias != direction:
            continue

        pool = s_lo if direction == "long" else s_hi
        sweep = None
        for s in range(max(0, s_last - cfg.sweep_max_age), s_last + 1):
            prior = [p for p in pool if p < s - cfg.swing_k]
            if not prior:
                continue
            level = s_low[prior[-1]] if direction == "long" else s_high[prior[-1]]
            took = s_low[s] < level if direction == "long" else s_high[s] > level
            back = s_close[s] > level if direction == "long" else s_close[s] < level
            if took and back:
                sweep = (s, float(level))
        if sweep is None:
            continue
        s_idx, swept = sweep

        opp = s_hi if direction == "long" else s_lo
        opp_prior = [p for p in opp if p < s_idx]
        if not opp_prior:
            continue
        opp_level = s_high[opp_prior[-1]] if direction == "long" else s_low[opp_prior[-1]]
        # The shift may land on the sweep bar itself: one bar can take the high
        # and close beyond the opposing low. That is a displacement bar, not an
        # edge case, and excluding it loses the cleanest setups.
        mss = None
        for m in range(s_idx, min(s_idx + cfg.mss_max_age, s_last) + 1):
            if (s_close[m] > opp_level) if direction == "long" else (s_close[m] < opp_level):
                mss = m
                break
        if mss is None:
            continue

        # The M1 window the structure leg spans, mapped by timestamp. The end is
        # the close of the shifting bar, not its open, or the displacement that
        # carved the gap falls outside the window.
        bar_span = (structure_bars.index[1] - structure_bars.index[0]
                    if len(structure_bars) > 1 else pd.Timedelta(minutes=5))
        t0, t1 = structure_bars.index[s_idx], structure_bars.index[mss] + bar_span
        window = np.flatnonzero((entry_bars.index >= t0) & (entry_bars.index < t1))
        if window.size < 3:
            continue
        gap = find_fvg(entry_bars, int(window[0]), int(window[-1]), direction, cfg.fvg_min_points)
        if gap is None or e_last - gap[2] > cfg.fvg_max_age:
            continue
        g_low, g_high, g_idx = gap

        # The gap has to have been TESTED: price must have traded back into it
        # after it formed, not merely be near it now.
        tested = np.any((e_low[g_idx + 1:] <= g_high) & (e_high[g_idx + 1:] >= g_low))
        if not tested:
            continue
        if not (g_low <= e_close[e_last] <= g_high):
            continue

        confirm = is_confirming(entry_bars, e_last, direction)
        if cfg.entry_mode in ("stop", "both") and confirm:
            entry_type = "stop"
            entry = float(e_high[e_last] if direction == "long" else e_low[e_last])
            anchor = float(e_low[e_last] if direction == "long" else e_high[e_last])
        elif cfg.entry_mode in ("limit", "both"):
            entry_type = "limit"
            edge = {"near": g_high if direction == "long" else g_low,
                    "far": g_low if direction == "long" else g_high,
                    "mid": (g_low + g_high) / 2}[cfg.fill_at]
            entry = float(edge)
            anchor = swept
        else:
            continue

        buf = cfg.stop_buffer_points
        stop = anchor - buf if direction == "long" else anchor + buf
        stop_points = abs(entry - stop)
        if stop_points <= 0:
            continue

        pools = s_hi if direction == "long" else s_lo
        ahead = [p for p in pools if p < s_idx]
        if not ahead:
            continue
        target = float(s_high[ahead[-1]] if direction == "long" else s_low[ahead[-1]])
        if (target <= entry) if direction == "long" else (target >= entry):
            continue

        rr = abs(target - entry) / stop_points
        fee_fraction = (2 * cfg.fee_per_side * entry) / stop_points
        candidate = PiffSignal(
            action=direction, entry_type=entry_type, entry=entry, stop=stop,
            target=target, stop_points=stop_points, rr=rr,
            fee_fraction_of_r=fee_fraction, swept_level=swept, fvg=(g_low, g_high),
            reasons=[f"swept the {'low' if direction == 'long' else 'high'} at {swept:,.1f}",
                     f"structure shifted on {structure_bars.index[mss]}",
                     f"M1 gap {g_low:,.1f}-{g_high:,.1f}, tested and price inside",
                     f"entry {entry_type}" + (f" on a {confirm}" if entry_type == "stop" else "")],
        )
        if rr < cfg.min_rr:
            candidate.rejected.append(f"R:R {rr:.2f} below the {cfg.min_rr} minimum")
        if fee_fraction > cfg.max_fee_fraction_of_r:
            candidate.rejected.append(
                f"stop {stop_points:.1f} pts carries {fee_fraction:.2f}R of fees, "
                f"above the {cfg.max_fee_fraction_of_r:.2f}R limit")
        if candidate.rejected:
            candidate.action = "flat"
        if best is None or (candidate.action != "flat" and candidate.rr > best.rr):
            best = candidate

    if best is None:
        return PiffSignal("flat", rejected=rejected + ["no sweep -> shift -> tested M1 gap sequence"])
    if rejected:
        best.action = "flat"
        best.rejected = rejected + best.rejected
    return best
