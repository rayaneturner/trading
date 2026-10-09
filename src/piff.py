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
    # Fractal half-width: a swing is the extreme of 2k+1 bars. k=1 on the
    # structure timeframe, not 2, because a swing is only confirmed k bars after
    # it prints: with k=2 on M5 a high made at 14:05 is not a swing until 14:20,
    # and the engine cannot see the level it needs to call the structure break
    # until the move is already over. k=1 sees it one bar later.
    swing_k: int = 1
    # Both lookbacks have to cover the same wall-clock span. They are counted
    # in DIFFERENT units — sweeps in structure bars, gaps in entry bars — so
    # leaving them unrelated made every gap stale before price could return to
    # it: 40 M15 bars reach back 600 minutes, 60 M1 bars only 60.
    sweep_max_age: int = 8           # structure bars a swept swing stays relevant
    mss_max_age: int = 20            # bars between the sweep and the structure shift
    fvg_min_points: float = 2.0      # ignore imbalances too small to be a zone
    fvg_max_age: int = 120           # entry bars a gap stays valid before it is stale

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
    # When the break takes the session's own extreme there is no pool left
    # beyond it to aim at, and a structural target cannot be named. The author
    # trades through that case — the logged winner targeted 294 points on a
    # 48-point stop, a level that is no swing of the session — so rather than
    # refuse the setup the target falls back to this multiple of the stop. It is
    # marked as synthetic in the reasons, because it is a choice and not a level
    # the market put there. Set to 0 to refuse instead.
    fallback_rr: float = 4.0
    fee_per_side: float = 0.0001     # MoonX indices, fraction of notional
    max_fee_fraction_of_r: float = 0.40

    # --- session (UTC hours, half-open) ---
    session_start_hour: int | None = 13
    session_end_hour: int | None = 21

    min_bars: int = 120             # entry-timeframe bars required
    min_structure_bars: int = 30    # structure-timeframe bars required


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
    # Where the chain stopped, per direction. A rule that only ever answers
    # "no setup" cannot be debugged or trusted: this says which link failed.
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"action": self.action, "entry_type": self.entry_type,
                "entry": round(self.entry, 2), "stop": round(self.stop, 2),
                "target": round(self.target, 2),
                "stop_points": round(self.stop_points, 1), "rr": round(self.rr, 2),
                "fee_fraction_of_r": round(self.fee_fraction_of_r, 3),
                "swept_level": round(self.swept_level, 2),
                "fvg": [round(x, 2) for x in self.fvg],
                "reasons": self.reasons, "rejected": self.rejected,
                "trace": self.trace}


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


def find_fvgs(bars: pd.DataFrame, start: int, end: int, direction: str,
              min_points: float) -> list:
    """Every 3-bar imbalance inside [start, end], in `direction`, oldest first.

    Bullish gap: bar i's low sits above bar i-2's high — price left a void going
    up. Bearish gap: bar i's high sits below bar i-2's low.

    All of them, because the leg usually leaves several and the first one is not
    always the one still in play. The caller decides which survives.
    """
    high, low = bars["high"].to_numpy(), bars["low"].to_numpy()
    out = []
    for i in range(max(start, 2), min(end, len(bars) - 1) + 1):
        if direction == "long" and low[i] - high[i - 2] >= min_points:
            out.append((float(high[i - 2]), float(low[i]), i))
        elif direction == "short" and low[i - 2] - high[i] >= min_points:
            out.append((float(high[i]), float(low[i - 2]), i))
    return out


def find_fvg(bars: pd.DataFrame, start: int, end: int, direction: str,
             min_points: float, pick: str = "first") -> tuple | None:
    """The first (or last) gap in the window. Kept for callers that want one."""
    gaps = find_fvgs(bars, start, end, direction, min_points)
    if not gaps:
        return None
    return gaps[0] if pick == "first" else gaps[-1]


def gap_is_dead(bars: pd.DataFrame, gap: tuple, direction: str) -> bool:
    """Has price CLOSED through the zone, against the trade?

    Entering the zone does not kill it. The author's own sequence is a first
    poke into the gap — the fake — then a return to it that confirms, so
    treating any touch as invalidation discards the setup it is meant to find.
    What kills the zone is a close beyond its far edge: a bullish gap is
    support until a bar closes below it, a bearish gap resistance until a bar
    closes above it.
    """
    g_low, g_high, g_idx = gap
    after = bars["close"].to_numpy()[g_idx + 1:]
    if not len(after):
        return False
    return bool((after < g_low).any() if direction == "long" else (after > g_high).any())


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
             htf: pd.DataFrame | None = None, cfg: PiffConfig = PiffConfig(),
             pending: bool = False) -> PiffSignal:
    """One decision, from three timeframes, exactly as the author reads them.

    `structure_bars` (M10-M15) carries the sweep and the structure shift.
    `entry_bars` (M1) carries the fair value gap and the test of it.
    `htf` (M15-H1) carries the directional bias.

    Searching the gap on M1 inside the window the structure leg spans is the
    whole point: the shift says where and which way, the M1 gap says at what
    price, and the test of that gap is what triggers.

    `pending` switches what counts as tradeable. By default the current bar has
    to be inside the gap and confirming — a decision for right now, which is
    only correct if something reads every bar. With `pending=True` the sequence
    has to be complete while price has NOT yet returned to the gap, and the
    signal describes an order to leave resting at the gap edge. It is the same
    trade, placed the way the author's logged "Limit" entries were, and it does
    not need anything watching the minute price arrives.
    """
    rejected: list = []
    # The furthest stage each direction reached, so a refusal is diagnostic.
    # Several sweeps are tried per direction and the LAST failure is usually the
    # least informative one, so the deepest is what gets kept.
    depth: dict = {}
    trace: dict = {}

    def note(direction: str, stage: int, why: str) -> None:
        # Strictly deeper only. Sweep candidates are tried newest first, so at
        # an equal stage the FIRST note is the one about the most recent sweep,
        # and that is the one worth reporting. Overwriting on equality reported
        # the oldest sweep instead, which named a structure level hundreds of
        # points away while the relevant one was a few points off.
        if depth.get(direction, -1) < stage:
            depth[direction], trace[direction] = stage, why
    if len(entry_bars) < cfg.min_bars:
        return PiffSignal("flat", rejected=[
            f"only {len(entry_bars)} entry bars, need {cfg.min_bars}"])
    if len(structure_bars) < cfg.min_structure_bars:
        return PiffSignal("flat", rejected=[
            f"only {len(structure_bars)} structure bars, need {cfg.min_structure_bars}"])

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

    bar_span = (structure_bars.index[1] - structure_bars.index[0]
                if len(structure_bars) > 1 else pd.Timedelta(minutes=5))

    best = None
    fallback = None
    for direction in ("long", "short"):
        if cfg.require_htf_bias and bias is not None and bias != direction:
            note(direction, 0, f"the higher timeframe reads {bias}")
            continue

        # Every sweep still inside the lookback is a candidate, newest first.
        # One sweep is not enough: the newest one may never produce a shift, or
        # may leave no gap, while an older one has the whole sequence behind it.
        # Taking a single candidate and giving up made the rule answer "no
        # setup" on price action that plainly contained one.
        pool = s_lo if direction == "long" else s_hi
        sweeps = []
        for s in range(max(0, s_last - cfg.sweep_max_age), s_last + 1):
            prior = [p for p in pool if p < s - cfg.swing_k]
            if not prior:
                continue
            level = s_low[prior[-1]] if direction == "long" else s_high[prior[-1]]
            took = s_low[s] < level if direction == "long" else s_high[s] > level
            back = s_close[s] > level if direction == "long" else s_close[s] < level
            if took and back:
                sweeps.append((s, float(level)))
        if not sweeps:
            note(direction, 1, "no swing was swept and reclaimed")
            continue

        for s_idx, swept in reversed(sweeps):
            opp = s_hi if direction == "long" else s_lo
            opp_prior = [p for p in opp if p < s_idx]
            if not opp_prior:
                note(direction, 2, "no opposing swing before the sweep")
                continue
            opp_level = s_high[opp_prior[-1]] if direction == "long" else s_low[opp_prior[-1]]

            # The shift may land on the sweep bar itself: one bar can take the
            # high and close beyond the opposing low. That is a displacement
            # bar, not an edge case, and excluding it loses the cleanest setups.
            mss = None
            for m in range(s_idx, min(s_idx + cfg.mss_max_age, s_last) + 1):
                if (s_close[m] > opp_level) if direction == "long" else (s_close[m] < opp_level):
                    mss = m
                    break
            if mss is None:
                note(direction, 3, (f"no close beyond {opp_level:,.1f} within "
f"{cfg.mss_max_age} bars of the sweep"))
                continue

            # The entry-timeframe window the structure leg spans, mapped by
            # timestamp. The end is the close of the shifting bar, not its open,
            # or the displacement that carved the gap falls outside the window.
            # From the sweep to NOW, not to the structure break. The gap that
            # gets retested is often carved by the displacement that FOLLOWS the
            # break, so stopping the window at the break hid it: measured live,
            # the three gaps inside 14:10-14:35 were all closed through while a
            # live 17.8-point gap at 30,836.7-30,854.5 had formed at 14:51, and
            # the engine answered "all gaps stale or closed through" with a
            # valid zone sitting 12 points under price.
            t0 = structure_bars.index[s_idx]
            window = np.flatnonzero(entry_bars.index >= t0)
            if window.size < 3:
                note(direction, 4, "structure window too short to hold a 3-bar gap")
                continue
            gaps = find_fvgs(entry_bars, int(window[0]), int(window[-1]), direction,
                             cfg.fvg_min_points)
            if not gaps:
                note(direction, 5, f"no {cfg.fvg_min_points:g}-point gap in the shifting leg")
                continue
            # Oldest first, nearest the origin of the move, which is where the
            # author places the zone. A gap price has CLOSED through is dead and
            # the next one is tried; a gap merely poked into is still live.
            gap = next((g for g in gaps
                        if e_last - g[2] <= cfg.fvg_max_age
                        and not gap_is_dead(entry_bars, g, direction)), None)
            if gap is None:
                note(direction, 6,
                     f"all {len(gaps)} gap(s) in the leg are stale or closed through")
                continue
            g_low, g_high, g_idx = gap
            if e_last - g_idx > cfg.fvg_max_age:
                note(direction, 6, (f"the gap is {e_last - g_idx} bars old, "
f"limit {cfg.fvg_max_age}"))
                continue

            touched = bool(np.any((e_low[g_idx + 1:] <= g_high)
                                  & (e_high[g_idx + 1:] >= g_low)))
            entry_type = entry = anchor = None
            if pending:
                # An order to leave resting. The gap has to be UNTOUCHED, so the
                # order has something to fill against, and price has to sit on
                # the side it would travel back from. This is the same trade the
                # author places as a limit; it just does not need anything
                # watching the minute price arrives, because the venue fills it.
                # A gap already poked into is still valid: that poke is the
                # fake the author describes, and the trade is the RETURN to the
                # zone. Only a close through it ends the setup, filtered above.
                away = ((e_close[e_last] > g_high) if direction == "long"
                        else (e_close[e_last] < g_low))
                if not away:
                    note(direction, 7, (f"price at {e_close[e_last]:,.1f} is not on the far "
                                        f"side of the {g_low:,.1f}-{g_high:,.1f} gap"))
                    continue
                if cfg.entry_mode == "stop":
                    note(direction, 9, "a resting order is a limit entry, and those are off")
                    continue
                entry_type = "limit"
                confirm = "pending retest" if touched else "pending first touch"
                retest = touched
                entry = float({"near": g_high if direction == "long" else g_low,
                               "far": g_low if direction == "long" else g_high,
                               "mid": (g_low + g_high) / 2}[cfg.fill_at])
                anchor = swept
            else:
                # Price has to be IN the gap right now — by its wick, not its
                # close. A bar that reaches into the zone and closes back out of
                # it is the rejection the setup waits for: requiring the close
                # inside would discard exactly the hammer the author enters on.
                if not (e_low[e_last] <= g_high and e_high[e_last] >= g_low):
                    note(direction, 7, (f"price is at {e_close[e_last]:,.1f}, not touching "
                                        f"the {g_low:,.1f}-{g_high:,.1f} gap"))
                    continue
                # Whether an earlier bar already reached the zone decides which
                # of the author's two entries this is, and what the stop leans on.
                retest = bool(np.any((e_low[g_idx + 1:e_last] <= g_high)
                                     & (e_high[g_idx + 1:e_last] >= g_low)))
                confirm = is_confirming(entry_bars, e_last, direction)
                if not confirm:
                    note(direction, 8, "touching the gap but the current bar does not confirm")
                    continue

            if entry_type is not None:
                pass
            elif retest and cfg.entry_mode in ("stop", "both"):
                # The usual case: a first poke, then a retest that confirms.
                # Entry triggers on the break of the confirming bar and the stop
                # leans on it — the tight stops in the log.
                entry_type = "stop"
                entry = float(e_high[e_last] if direction == "long" else e_low[e_last])
                anchor = float(e_low[e_last] if direction == "long" else e_high[e_last])
            elif cfg.entry_mode in ("limit", "both"):
                # The other case the author describes: the FIRST confirming bar
                # in the zone fills a resting order at the gap edge. Less has
                # been proven, so the stop sits behind the swept level.
                entry_type = "limit"
                entry = float({"near": g_high if direction == "long" else g_low,
                               "far": g_low if direction == "long" else g_high,
                               "mid": (g_low + g_high) / 2}[cfg.fill_at])
                anchor = swept
            else:
                note(direction, 5, ("a retest confirmed but stop entries are off, and "
"this is not the first touch"))
                continue

            buf = cfg.stop_buffer_points
            stop = anchor - buf if direction == "long" else anchor + buf
            stop_points = abs(entry - stop)
            if stop_points <= 0:
                note(direction, 10, "entry and stop coincide")
                continue

            # The target is the pool BEYOND the level that defined the structure
            # break, not that level itself. Using the same swing for both made
            # the two conditions contradict each other: structure only breaks
            # once price closes past the level, so the target was already taken
            # the moment the setup became valid. Measured live that produced an
            # entry at 30,827.95 with a target at 30,855.40 while price stood at
            # 30,853.30 — an R:R of 0.66 on a setup the author trades at 4:1.
            # The author's own words put it at "la derniere meche plus haute
            # creee par le mouvement precedent qui a casse le mouvement d'avant
            # encore": one pool further out.
            pools = s_hi if direction == "long" else s_lo
            ahead = [p for p in pools if p < s_idx
                     and ((s_high[p] > opp_level) if direction == "long"
                          else (s_low[p] < opp_level))]
            if ahead:
                target = float(s_high[ahead[-1]] if direction == "long"
                               else s_low[ahead[-1]])
                target_kind = "pool"
            elif cfg.fallback_rr > 0:
                target = float(entry + cfg.fallback_rr * stop_points if direction == "long"
                               else entry - cfg.fallback_rr * stop_points)
                target_kind = "synthetic"
            else:
                note(direction, 11, (f"no liquidity pool beyond the {opp_level:,.1f} "
                                     f"structure level to target"))
                continue
            if (target <= entry) if direction == "long" else (target >= entry):
                note(direction, 12, (f"the target at {target:,.1f} sits the wrong side "
f"of the entry"))
                continue

            rr = abs(target - entry) / stop_points
            fee_fraction = (2 * cfg.fee_per_side * entry) / stop_points
            candidate = PiffSignal(
                action=direction, entry_type=entry_type, entry=entry, stop=stop,
                target=target, stop_points=stop_points, rr=rr,
                fee_fraction_of_r=fee_fraction, swept_level=swept,
                fvg=(g_low, g_high), trace=trace,
                reasons=[f"swept the {'low' if direction == 'long' else 'high'} at {swept:,.1f}",
                         f"structure shifted on {structure_bars.index[mss]}",
                         f"gap {g_low:,.1f}-{g_high:,.1f}"
                         + (" awaiting the retrace" if pending else
                            " retested" if retest else " on first touch"),
                         f"entry {entry_type} on a {confirm}",
                         f"target is a {target_kind}"
                         + (f" {cfg.fallback_rr:g}R extension, no pool beyond "
                            f"{opp_level:,.1f}" if target_kind == "synthetic" else "")],
            )
            if rr < cfg.min_rr:
                candidate.rejected.append(f"R:R {rr:.2f} below the {cfg.min_rr} minimum")
            if fee_fraction > cfg.max_fee_fraction_of_r:
                candidate.rejected.append(
                    f"stop {stop_points:.1f} pts carries {fee_fraction:.2f}R of fees, "
                    f"above the {cfg.max_fee_fraction_of_r:.2f}R limit")
            if candidate.rejected:
                # A setup that exists but does not pay is worth reporting; it is
                # not worth preferring over one that does, so it is only a
                # fallback and the search keeps going.
                candidate.action = "flat"
                fallback = fallback or candidate
                continue
            if best is None or candidate.rr > best.rr:
                best = candidate
            break

    if best is None:
        if fallback is not None:
            return fallback
        return PiffSignal("flat", trace=trace, rejected=rejected + [
            "; ".join(f"{d}: {why}" for d, why in trace.items())
            or "no sweep -> shift -> gap sequence"])
    if rejected:
        best.action = "flat"
        best.rejected = rejected + best.rejected
    return best
