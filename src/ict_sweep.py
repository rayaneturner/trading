"""The Liquidity Sweep Strategy, exactly as the ICT PDF specifies it.

Three steps, taken literally from the document:

  1. A valid SINGLE CANDLE liquidity sweep on the higher timeframe: one
     candle clears the previous structural low with its body or wick. The
     document adds a validity filter that nothing in this repository has
     tested yet - "the subsequent candle should neither exceed nor close
     below the sweep candle; otherwise the setup becomes invalid".
  2. Drop to the lower timeframe and wait for a CHoCH: a close through the
     most recent opposing swing, formed after the sweep.
  3. Rest a limit order on the order block or the fair value gap the CHoCH
     impulse left behind, stop beyond the block plus a buffer, target at
     the next opposite swing point.

The filter in step 1 is the part worth measuring. Everything else here
already exists in piff.py and orderblock.py and has been measured.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IctConfig:
    htf_k: int = 2               # bars either side that confirm an HTF swing
    ltf_k: int = 2
    sweep_lookback: int = 40     # HTF bars searched for the swept level
    require_validity: bool = True  # the PDF's "next candle" filter
    max_wait_choch: int = 96     # LTF bars allowed between sweep and CHoCH
    max_wait_fill: int = 96      # LTF bars a resting order stays live
    max_hold: int = 288          # LTF bars a position may stay open
    entry_zone: str = "mid"      # "ob" | "fvg" | "mid"
    stop_buffer_frac: float = 0.10   # of the zone height
    stop_mode: str = "zone"      # "zone" = under the order block (PDF)
                                 # "sweep" = under the swept liquidity itself
    target: str = "structure"    # "structure" | "rr"
    fallback_rr: float = 2.0
    min_rr: float = 1.0
    side: str = "both"
    fee_per_side: float = 0.0


@dataclass
class IctTrade:
    entered: object = None
    exited: object = None
    entry: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    outcome: str = ""
    r_gross: float = 0.0
    r_net: float = 0.0
    fees_in_r: float = 0.0
    stop_pct: float = 0.0
    rr: float = 0.0
    side: str = "long"


def swing_lows(bars: pd.DataFrame, k: int) -> np.ndarray:
    low = bars["low"].to_numpy()
    out = np.zeros(len(low), bool)
    for i in range(k, len(low) - k):
        if low[i] == low[i - k:i + k + 1].min() and low[i] < low[i - 1]:
            out[i] = True
    return out


def swing_highs(bars: pd.DataFrame, k: int) -> np.ndarray:
    high = bars["high"].to_numpy()
    out = np.zeros(len(high), bool)
    for i in range(k, len(high) - k):
        if high[i] == high[i - k:i + k + 1].max() and high[i] > high[i - 1]:
            out[i] = True
    return out


def find_sweeps(htf: pd.DataFrame, cfg: IctConfig, side: str) -> list:
    """Single-candle sweeps, each returned as (index, level, valid).

    A bullish sweep takes out a prior swing low with its wick or body and
    closes back above it, inside ONE candle. `valid` carries the PDF's
    extra filter on the candle that follows.
    """
    o, h, l, c = (htf[x].to_numpy() for x in ("open", "high", "low", "close"))
    lows, highs = swing_lows(htf, cfg.htf_k), swing_highs(htf, cfg.htf_k)
    out = []
    for i in range(cfg.htf_k + 1, len(htf) - 1):
        # Only swings already confirmed cfg.htf_k bars before i are visible.
        lo = max(0, i - cfg.sweep_lookback)
        if side == "long":
            cand = [j for j in range(lo, i - cfg.htf_k) if lows[j]]
            if not cand:
                continue
            level = l[cand[-1]]
            if not (l[i] < level and c[i] > level):
                continue
            valid = bool(l[i + 1] >= l[i] and c[i + 1] >= l[i])
        else:
            cand = [j for j in range(lo, i - cfg.htf_k) if highs[j]]
            if not cand:
                continue
            level = h[cand[-1]]
            if not (h[i] > level and c[i] < level):
                continue
            valid = bool(h[i + 1] <= h[i] and c[i + 1] <= h[i])
        out.append((i, float(level), valid))
    return out


def _zone(ltf: pd.DataFrame, impulse_start: int, brk: int, side: str):
    """The order block and the fair value gap left by the CHoCH impulse."""
    o, h, l, c = (ltf[x].to_numpy() for x in ("open", "high", "low", "close"))
    ob = None
    for j in range(brk, max(impulse_start - 1, 0), -1):
        if (c[j] < o[j]) if side == "long" else (c[j] > o[j]):
            ob = (float(l[j]), float(h[j]))
            break
    fvg = None
    for j in range(impulse_start + 1, brk + 1):
        if j - 1 < 0 or j + 1 >= len(ltf):
            continue
        if side == "long" and l[j + 1] > h[j - 1]:
            fvg = (float(h[j - 1]), float(l[j + 1]))
            break
        if side == "short" and h[j + 1] < l[j - 1]:
            fvg = (float(h[j + 1]), float(l[j - 1]))
            break
    return ob, fvg


def backtest(htf: pd.DataFrame, ltf: pd.DataFrame, cfg: IctConfig) -> list:
    """Walk the sweeps in order and resolve each on the lower timeframe."""
    step = htf.index[1] - htf.index[0] if len(htf) > 1 else pd.Timedelta("4h")
    lo, lh, ll, lc = (ltf[x].to_numpy() for x in ("open", "high", "low", "close"))
    l_hi_sw, l_lo_sw = swing_highs(ltf, cfg.ltf_k), swing_lows(ltf, cfg.ltf_k)
    h_hi_sw = swing_highs(htf, cfg.htf_k)
    h_lo_sw = swing_lows(htf, cfg.htf_k)
    htf_h, htf_l = htf["high"].to_numpy(), htf["low"].to_numpy()

    sides = ("long", "short") if cfg.side == "both" else (cfg.side,)
    trades, busy_until = [], ltf.index[0]

    for side in sides:
        for s_idx, level, valid in find_sweeps(htf, cfg, side):
            if cfg.require_validity and not valid:
                continue
            # The filter is only known once the NEXT HTF candle has closed.
            t0 = htf.index[s_idx + 1] + step
            start = int(np.searchsorted(ltf.index, t0, side="left"))
            if start >= len(ltf) - 4 or ltf.index[start] < busy_until:
                continue

            # Step 2: the first close through an opposing LTF swing.
            brk = anchor = None
            for j in range(start + cfg.ltf_k, min(start + cfg.max_wait_choch, len(ltf))):
                prior = [m for m in range(start, j - cfg.ltf_k)
                         if (l_hi_sw[m] if side == "long" else l_lo_sw[m])]
                if not prior:
                    continue
                p = prior[-1]
                hit = lc[j] > lh[p] if side == "long" else lc[j] < ll[p]
                if hit:
                    brk, anchor = j, p
                    break
            if brk is None:
                continue

            ob, fvg = _zone(ltf, anchor, brk, side)
            pick = {"ob": ob, "fvg": fvg}.get(cfg.entry_zone)
            if cfg.entry_zone == "mid":
                parts = [z for z in (ob, fvg) if z]
                pick = (min(p[0] for p in parts), max(p[1] for p in parts)) if parts else None
            if not pick:
                continue
            z_lo, z_hi = pick
            if z_hi <= z_lo:
                continue
            buf = (z_hi - z_lo) * cfg.stop_buffer_frac
            entry = (z_lo + z_hi) / 2
            if cfg.stop_mode == "sweep":
                # Beyond the liquidity the sweep candle took, not the block.
                ref = htf_l[s_idx] if side == "long" else htf_h[s_idx]
                stop = (ref - buf) if side == "long" else (ref + buf)
            else:
                stop = (z_lo - buf) if side == "long" else (z_hi + buf)
            if (stop >= entry) if side == "long" else (stop <= entry):
                continue

            # Step 3 target: the next opposite swing point.
            if cfg.target == "structure":
                if side == "long":
                    ahead = [htf_h[m] for m in range(max(0, s_idx - cfg.sweep_lookback), s_idx)
                             if h_hi_sw[m] and htf_h[m] > entry]
                    tgt = float(min(ahead)) if ahead else None
                else:
                    ahead = [htf_l[m] for m in range(max(0, s_idx - cfg.sweep_lookback), s_idx)
                             if h_lo_sw[m] and htf_l[m] < entry]
                    tgt = float(max(ahead)) if ahead else None
            else:
                tgt = None
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            if tgt is None:
                tgt = entry + cfg.fallback_rr * risk if side == "long" \
                    else entry - cfg.fallback_rr * risk
            rr = abs(tgt - entry) / risk
            if rr < cfg.min_rr:
                continue

            # Resting limit order, then the position.
            fill = None
            for j in range(brk + 1, min(brk + 1 + cfg.max_wait_fill, len(ltf))):
                if (ll[j] <= entry) if side == "long" else (lh[j] >= entry):
                    fill = j
                    break
                if (lh[j] >= tgt) if side == "long" else (ll[j] <= tgt):
                    break   # ran away without us
            if fill is None:
                continue

            out, px, k = "timeout", lc[min(fill + cfg.max_hold, len(ltf) - 1)], None
            for j in range(fill, min(fill + cfg.max_hold, len(ltf))):
                hit_stop = (ll[j] <= stop) if side == "long" else (lh[j] >= stop)
                hit_tgt = (lh[j] >= tgt) if side == "long" else (ll[j] <= tgt)
                if hit_stop:          # stop first when both land in one bar
                    out, px, k = "loss", stop, j
                    break
                if hit_tgt:
                    out, px, k = "win", tgt, j
                    break
            k = k if k is not None else min(fill + cfg.max_hold, len(ltf) - 1)

            gross = ((px - entry) if side == "long" else (entry - px)) / risk
            fee_r = 2 * cfg.fee_per_side * entry / risk
            trades.append(IctTrade(
                entered=ltf.index[fill], exited=ltf.index[k], entry=entry, stop=stop,
                target=tgt, outcome=out, r_gross=gross, r_net=gross - fee_r,
                fees_in_r=fee_r, stop_pct=risk / entry, rr=rr, side=side))
            busy_until = ltf.index[k]

    trades.sort(key=lambda t: t.entered)
    return trades


def summarise(trades: list, label: str = "") -> dict:
    if not trades:
        print(f"{label:38s} aucun trade")
        return {}
    R = np.array([t.r_net for t in trades])
    wins = sum(1 for t in trades if t.outcome == "win")
    # A timeout resolved neither barrier, so it does not belong in the
    # denominator of a hit rate compared against a break-even.
    resolved = sum(1 for t in trades if t.outcome in ("win", "loss"))
    hit = wins / resolved if resolved else float("nan")
    rr = float(np.mean([t.rr for t in trades]))
    t_stat = R.mean() / (R.std(ddof=1) / np.sqrt(len(R))) if R.std(ddof=1) > 0 else np.nan
    be = 1 / (1 + rr)
    print(f"{label:38s} n={len(R):5d}  wr={hit*100:5.2f}% "
          f"(seuil {be*100:5.2f}%, {len(R)-resolved:3d} timeouts)  R:R={rr:4.2f}  "
          f"E={R.mean():+.4f}R  t={t_stat:+5.2f}")
    return {"n": len(R), "wr": hit, "resolved": resolved, "rr": rr,
            "expectancy": float(R.mean()), "t": float(t_stat), "breakeven": be}
