"""Order block → pullback → lower-timeframe confirmation.

Mechanised from the author's description:

    find an order block in H1, M30 or M15, wait for a pullback into it, wait for
    confirmation in a "power timeframe" (M15 for the H1, M5 for the M30, M1 or
    M3 for the M15), take the trade, put the TP at the last highest low or high
    on the timeframe analysed, and the stop beyond the candle before the
    confirmation.

The description leaves one thing undefined, and it is the thing that decides
everything: what an order block *is*. Coded here as the standard reading, with
every condition measurable:

    a bullish order block is the last DOWN candle before an impulsive up move
    that BREAKS a prior swing high.

"Impulsive" is not a feeling either. The move must cover at least
`displacement_atr` times the average range within `displacement_bars` bars, and
it must close beyond the structure it breaks. Without the break the candle is
just a down candle in a range, and there are hundreds of those.

Five guards carried over from the PIFF engine, each of which was a real defect
found while running that one live:

  1. nothing is read off a bar that has not closed
  2. a zone price has merely poked into is still live; only a CLOSE through it
     kills the zone
  3. the target is never the level whose break defined the setup, because that
     level is already taken the moment the setup is valid
  4. when no pool exists beyond the break, the target falls back to an R
     multiple rather than refusing a valid setup
  5. the search runs to the present, not to the break

And one that matters more here than it did there: the round-trip fee as a
fraction of the risk. That fraction is cost/stop_distance and is independent of
the reward:risk ratio, so on a venue charging 0.07% per side a stop narrow
enough to be "scalping" can cost more than 1R before the trade starts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .piff import is_confirming, swing_highs, swing_lows


@dataclass(frozen=True)
class OBConfig:
    # --- what counts as an order block ---
    swing_k: int = 1                  # fractal half-width for structure swings
    displacement_bars: int = 3        # bars the impulsive move may take
    displacement_atr: float = 1.5     # and how many average ranges it must cover
    atr_window: int = 14
    zone: str = "range"               # "range" (low..high) or "body" (open..close)
    ob_max_age: int = 30              # HTF bars an unmitigated block stays valid

    # --- the pullback and the trigger ---
    require_untouched: bool = False   # True = only the first return to the zone
    confirm_lookback: int = 3         # LTF bars inside the zone that may confirm

    # --- stop and target ---
    stop_buffer_frac: float = 0.15    # of the confirming bar's range
    min_rr: float = 3.0
    fallback_rr: float = 3.0          # when no pool lies beyond the break

    # --- the venue ---
    fee_per_side: float = 0.0007      # MoonX crypto futures at high leverage
    max_fee_fraction_of_r: float = 0.50

    min_htf_bars: int = 60
    min_ltf_bars: int = 30


@dataclass
class OBSignal:
    action: str = "flat"
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    stop_points: float = 0.0
    stop_pct: float = 0.0
    rr: float = 0.0
    fee_fraction_of_r: float = 0.0
    zone: tuple = ()
    confirm: str = ""
    reasons: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    trace: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"action": self.action, "entry": round(self.entry, 2),
                "stop": round(self.stop, 2), "target": round(self.target, 2),
                "stop_points": round(self.stop_points, 2),
                "stop_pct": round(self.stop_pct * 100, 4),
                "rr": round(self.rr, 2),
                "fee_fraction_of_r": round(self.fee_fraction_of_r, 3),
                "zone": [round(x, 2) for x in self.zone], "confirm": self.confirm,
                "reasons": self.reasons, "rejected": self.rejected,
                "trace": self.trace}


def average_range(bars: pd.DataFrame, window: int) -> float:
    rng = (bars["high"] - bars["low"]).tail(window)
    return float(rng.mean()) if len(rng) else 0.0


def find_order_blocks(bars: pd.DataFrame, direction: str,
                      cfg: OBConfig = OBConfig()) -> list:
    """Every order block in `direction`, newest first.

    A bullish block is the last down candle before an impulsive up move that
    closes beyond a prior swing high. The break is what separates a block from
    an ordinary candle: without it there is no evidence anyone defended the
    level, and the zone is arbitrary.
    """
    o, h, l, c = (bars[k].to_numpy() for k in ("open", "high", "low", "close"))
    hi, lo = swing_highs(bars, cfg.swing_k), swing_lows(bars, cfg.swing_k)
    atr = average_range(bars, cfg.atr_window)
    if atr <= 0:
        return []

    out = []
    last = len(bars) - 1
    for i in range(1, last):
        opposite = (c[i] < o[i]) if direction == "long" else (c[i] > o[i])
        if not opposite:
            continue
        end = min(i + cfg.displacement_bars, last)
        if end <= i:
            continue
        # the impulsive leg out of the candle
        if direction == "long":
            move = h[i + 1:end + 1].max() - l[i]
            broke = [p for p in hi if p < i and c[i + 1:end + 1].max() > h[p]]
        else:
            move = h[i] - l[i + 1:end + 1].min()
            broke = [p for p in lo if p < i and c[i + 1:end + 1].min() < l[p]]
        if move < cfg.displacement_atr * atr or not broke:
            continue

        zone = ((min(o[i], c[i]), max(o[i], c[i])) if cfg.zone == "body"
                else (l[i], h[i]))
        out.append({"idx": i, "zone": zone, "broke": broke[-1],
                    "broke_level": (h[broke[-1]] if direction == "long"
                                    else l[broke[-1]]),
                    "move_in_atr": move / atr})
    return list(reversed(out))


def zone_is_dead(bars: pd.DataFrame, idx: int, zone: tuple,
                 direction: str) -> bool:
    """Has price CLOSED through the block, against the trade?

    Poking into it is the pullback the setup waits for. Only a close beyond the
    far edge says the level was not defended after all.
    """
    z_low, z_high = zone
    after = bars["close"].to_numpy()[idx + 1:]
    if not len(after):
        return False
    return bool((after < z_low).any() if direction == "long"
                else (after > z_high).any())


def generate(htf: pd.DataFrame, ltf: pd.DataFrame,
             cfg: OBConfig = OBConfig()) -> OBSignal:
    """One decision from two timeframes.

    `htf` carries the order block and the target; `ltf` is the power timeframe
    where the confirmation and the stop are read. Both must already exclude any
    bar that has not closed.
    """
    depth: dict = {}
    trace: dict = {}

    def note(d: str, stage: int, why: str) -> None:
        if depth.get(d, -1) < stage:
            depth[d], trace[d] = stage, why

    if len(htf) < cfg.min_htf_bars:
        return OBSignal(rejected=[f"only {len(htf)} HTF bars, need {cfg.min_htf_bars}"])
    if len(ltf) < cfg.min_ltf_bars:
        return OBSignal(rejected=[f"only {len(ltf)} LTF bars, need {cfg.min_ltf_bars}"])

    h_last = len(htf) - 1
    price = float(ltf["close"].iloc[-1])
    l_open, l_high, l_low, l_close = (ltf[k].to_numpy()
                                      for k in ("open", "high", "low", "close"))
    l_last = len(ltf) - 1

    best = None
    for direction in ("long", "short"):
        blocks = find_order_blocks(htf, direction, cfg)
        if not blocks:
            note(direction, 0, "no order block: no impulsive move broke structure")
            continue

        for ob in blocks:
            z_low, z_high = ob["zone"]
            age = h_last - ob["idx"]
            if age > cfg.ob_max_age:
                note(direction, 1, f"the block is {age} HTF bars old, limit {cfg.ob_max_age}")
                continue
            if zone_is_dead(htf, ob["idx"], ob["zone"], direction):
                note(direction, 2, f"price closed through the {z_low:,.1f}-{z_high:,.1f} block")
                continue

            # --- the pullback: price has to be in the zone now ---
            in_zone = z_low <= price <= z_high
            if not in_zone:
                note(direction, 3, (f"price {price:,.1f} is outside the "
                                    f"{z_low:,.1f}-{z_high:,.1f} block"))
                continue
            if cfg.require_untouched:
                mid = ltf.index.get_indexer([htf.index[ob["idx"]]], method="bfill")[0]
                prior = ((l_low[mid:l_last] <= z_high) & (l_high[mid:l_last] >= z_low))
                if prior.any():
                    note(direction, 3, "the block was already revisited")
                    continue

            # --- the confirmation, on the power timeframe ---
            confirm, c_idx = None, None
            for j in range(l_last, max(l_last - cfg.confirm_lookback, 0), -1):
                if l_low[j] <= z_high and l_high[j] >= z_low:
                    confirm = is_confirming(ltf, j, direction)
                    if confirm:
                        c_idx = j
                        break
            if not confirm:
                note(direction, 4, (f"in the block but no confirming bar in the last "
                                    f"{cfg.confirm_lookback} LTF bars"))
                continue

            # --- entry, and the stop beyond the candle BEFORE the confirmation ---
            entry = float(l_close[c_idx])
            prev = max(c_idx - 1, 0)
            pad = cfg.stop_buffer_frac * max(l_high[c_idx] - l_low[c_idx], 1e-9)
            if direction == "long":
                stop = float(min(l_low[prev], l_low[c_idx], z_low) - pad)
            else:
                stop = float(max(l_high[prev], l_high[c_idx], z_high) + pad)
            stop_points = abs(entry - stop)
            if stop_points <= 0:
                note(direction, 5, "entry and stop coincide")
                continue

            # --- target: the pool BEYOND the level the break defined ---
            pools = swing_highs(htf, cfg.swing_k) if direction == "long" else swing_lows(htf, cfg.swing_k)
            hh, ll = htf["high"].to_numpy(), htf["low"].to_numpy()
            beyond = [p for p in pools
                      if ((hh[p] > ob["broke_level"]) if direction == "long"
                          else (ll[p] < ob["broke_level"]))]
            if beyond:
                target = float(hh[beyond[-1]] if direction == "long" else ll[beyond[-1]])
                kind = "pool"
            else:
                target = float(entry + cfg.fallback_rr * stop_points if direction == "long"
                               else entry - cfg.fallback_rr * stop_points)
                kind = "synthetic"
            if (target <= entry) if direction == "long" else (target >= entry):
                note(direction, 6, f"the target at {target:,.1f} sits the wrong side of the entry")
                continue

            rr = abs(target - entry) / stop_points
            fee_fraction = (2 * cfg.fee_per_side * entry) / stop_points
            cand = OBSignal(
                action=direction, entry=entry, stop=stop, target=target,
                stop_points=stop_points, stop_pct=stop_points / entry, rr=rr,
                fee_fraction_of_r=fee_fraction, zone=ob["zone"], confirm=confirm,
                trace=trace,
                reasons=[f"{direction} order block {z_low:,.1f}-{z_high:,.1f}, "
                         f"{ob['move_in_atr']:.1f} ATR of displacement",
                         f"broke structure at {ob['broke_level']:,.1f}",
                         f"price pulled back into it, {confirm} on the power timeframe",
                         f"target is a {kind}"])
            if rr < cfg.min_rr:
                cand.rejected.append(f"R:R {rr:.2f} below the {cfg.min_rr} minimum")
            if fee_fraction > cfg.max_fee_fraction_of_r:
                cand.rejected.append(
                    f"a {cand.stop_pct * 100:.4f}% stop carries {fee_fraction:.2f}R of fees, "
                    f"above the {cfg.max_fee_fraction_of_r:.2f}R limit")
            if cand.rejected:
                cand.action = "flat"
                best = best or cand
                continue
            if best is None or best.action == "flat" or cand.rr > best.rr:
                best = cand
            break

    if best is None:
        return OBSignal(trace=trace, rejected=[
            "; ".join(f"{d}: {w}" for d, w in trace.items()) or "no order block setup"])
    return best


# --- the author's three pairs, with the venue's cost built in --------------
#
# The pairing is his: M15 confirms the H1, M5 confirms the M30, M1 or M3
# confirms the M15. What is NOT his, and is not a preference, is the fee budget
# attached to each. The stop is set by one confirmation-timeframe candle, so the
# pair fixes the stop width, and the stop width alone fixes what the venue
# costs in R. Measured on BTC (out/btc_5m.csv, out/btc_1h.csv):
#
#   confirmation TF   median range   stop (+30%)   fees at 0.07%/side   BE @3:1
#   M15                   0.198%        0.257%          0.54 R            38.6%
#   M5                    0.106%        0.138%          1.01 R            50.3%
#   M3                    0.070%        0.091%          1.54 R            63.5%
#
# So the three pairs are not three flavours of the same strategy. The first is
# tradeable at a plausible win rate, the second needs better than a coin flip
# just to break even, and the third needs 63.5% — which no scalping strategy
# sustains. The budgets below encode that: SWING_H1 allows a wide fee share
# because its stop earns it, SCALP_M15 is deliberately set where it will refuse
# nearly everything, and it is left in so the refusal is visible rather than
# the setup being silently taken.

PAIRS = {
    # analysis timeframe -> (confirmation timeframe, config)
    "H1": ("15min", OBConfig(min_rr=3.0, max_fee_fraction_of_r=0.60,
                             ob_max_age=30, min_htf_bars=60, min_ltf_bars=40)),
    "M30": ("5min", OBConfig(min_rr=3.0, max_fee_fraction_of_r=0.35,
                             ob_max_age=40, min_htf_bars=80, min_ltf_bars=60)),
    "M15": ("3min", OBConfig(min_rr=4.0, max_fee_fraction_of_r=0.25,
                             ob_max_age=60, min_htf_bars=100, min_ltf_bars=60)),
}

# Indices cost 0.010% per side instead of 0.070%, a factor of seven, so the
# same stop widths carry 0.08R to 0.22R rather than 0.54R to 1.54R. The pairs
# that are hopeless on crypto futures are comfortable here.
PAIRS_INDICES = {
    name: (ltf, OBConfig(**{**cfg.__dict__, "fee_per_side": 0.0001,
                            "max_fee_fraction_of_r": 0.40}))
    for name, (ltf, cfg) in PAIRS.items()
}
