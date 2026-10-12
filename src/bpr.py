"""The Balanced Price Range, measured.

A BPR is the overlap between a bullish and a bearish fair value gap formed
close together. The claim attached to it is that the overlap, having been
delivered in both directions, is where price reacts when it comes back. The
most recent of the two gaps is said to set the bias.

This module turns that claim into a mechanical rule so it can be scored:

  1. A fair value gap is confirmed on bar i -- bullish when low[i] >
     high[i-2], bearish when high[i] < low[i-2].
  2. A new gap is paired with the most recent opposite gap within
     `max_gap_age` bars whose overlap is wider than `min_ovl_atr` ATRs. The
     zone is that overlap; the new gap gives the side.
  3. Entry on the retest, at the close of the bar that triggers it. Stop on
     the far edge of the zone plus a buffer, target at a fixed R multiple or
     the last opposite pivot.

Nothing here reads a bar before it has closed. A bar that touches both the
stop and the target counts as a loss, because the tape cannot say which came
first.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BprConfig:
    # pairing
    max_gap_age: int = 20        # bars allowed between the two gaps
    min_ovl_atr: float = 0.05    # overlap floor, in ATR14
    one_use: bool = True         # a gap feeds at most one zone
    entry_delay: int = 1         # bars between zone creation and first trigger

    # entry
    trigger: str = "ce"          # "touch" | "ce" | "through" | "reject"
    max_wait: int = 40           # bars a zone stays armed
    side: str = "both"           # "both" | "long" | "short"
    ema_filter: int = 0          # 0 = off, else trade only with the EMA

    # exit
    stop_mode: str = "zone"      # "zone" = far edge + buffer, "atr"
    stop_buf_atr: float = 0.25
    stop_atr: float = 1.5
    target: str = "rr"           # "rr" | "structure"
    rr: float = 2.0
    piv_len: int = 10
    min_rr: float = 1.0
    min_stop_atr: float = 0.0    # refuse a stop tighter than this, in ATR14
    max_hold: int = 100

    fee_per_side: float = 0.0    # fraction of notional, 0.0004 = 4 bps
    invert: bool = False         # trade against the zone, as a control


@dataclass
class BprTrade:
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
    zone_width_atr: float = 0.0


def _atr(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    prev = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def _ema(df: pd.DataFrame, n: int) -> np.ndarray:
    return df["close"].ewm(span=n, adjust=False).mean().to_numpy()


def find_zones(df: pd.DataFrame, cfg: BprConfig) -> list:
    """Every BPR the data contains, as (bar, top, bot, bullish)."""
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    atr = _atr(df)
    gaps: list = []          # [bar, top, bot, bull, used]
    zones: list = []
    for i in range(2, len(df)):
        bull = l[i] > h[i - 2]
        bear = h[i] < l[i - 2]
        if not (bull or bear):
            continue
        top = l[i] if bull else l[i - 2]
        bot = h[i - 2] if bull else h[i]
        while gaps and i - gaps[0][0] > cfg.max_gap_age:
            gaps.pop(0)
        for g in reversed(gaps):
            if g[3] == bull or (cfg.one_use and g[4]):
                continue
            ot, ob = min(top, g[1]), max(bot, g[2])
            if ot - ob <= cfg.min_ovl_atr * atr[i]:
                continue
            g[4] = True
            zones.append((i, ot, ob, bull))
            break
        gaps.append([i, top, bot, bull, False])
    return zones


def backtest(df: pd.DataFrame, cfg: BprConfig) -> list:
    """Walk the bars once, one position at a time."""
    o = df["open"].to_numpy()
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    idx = df.index
    atr = _atr(df)
    ema = _ema(df, cfg.ema_filter) if cfg.ema_filter else None
    k = cfg.piv_len

    zones = find_zones(df, cfg)
    by_bar: dict = {}
    for z in zones:
        by_bar.setdefault(z[0], []).append(z)

    live: list = []          # [bar, top, bot, bull, touched]
    trades: list = []
    pos = None               # dict while a position is open
    last_ph = last_pl = np.nan

    for i in range(len(df)):
        # pivots confirmed k bars after the fact
        p = i - k
        if p - k >= 0:
            if h[p] == h[p - k:p + k + 1].max():
                last_ph = h[p]
            if l[p] == l[p - k:p + k + 1].min():
                last_pl = l[p]

        # resolve an open position before looking for a new one
        if pos is not None:
            long = pos["side"] == "long"
            hit_stop = l[i] <= pos["stop"] if long else h[i] >= pos["stop"]
            hit_tgt = h[i] >= pos["target"] if long else l[i] <= pos["target"]
            out = px = None
            if hit_stop:                      # ambiguous bars go to the stop
                out, px = "loss", pos["stop"]
            elif hit_tgt:
                out, px = "win", pos["target"]
            elif i - pos["bar"] >= cfg.max_hold:
                out, px = "timeout", c[i]
            if out is not None:
                risk = abs(pos["entry"] - pos["stop"])
                r = (px - pos["entry"]) / risk * (1 if long else -1)
                fees = cfg.fee_per_side * (pos["entry"] + abs(px)) / risk
                trades.append(BprTrade(
                    entered=idx[pos["bar"]], exited=idx[i], entry=pos["entry"],
                    stop=pos["stop"], target=pos["target"], outcome=out,
                    r_gross=float(r), r_net=float(r - fees), fees_in_r=float(fees),
                    stop_pct=float(risk / pos["entry"]), rr=pos["rr"],
                    side=pos["side"], zone_width_atr=pos["width"]))
                pos = None

        live = [z for z in live if i - z[0] <= cfg.max_wait]

        if pos is None:
            for z in live:
                if i - z[0] < cfg.entry_delay:
                    continue
                bull = z[3] if not cfg.invert else not z[3]
                if cfg.side == "long" and not bull:
                    continue
                if cfg.side == "short" and bull:
                    continue
                if ema is not None and (c[i] < ema[i] if bull else c[i] > ema[i]):
                    continue
                top, bot = z[1], z[2]
                ce = (top + bot) / 2
                in_zone = l[i] <= top and h[i] >= bot
                if in_zone:
                    z[4] = True
                if cfg.trigger == "touch":
                    trig = in_zone
                elif cfg.trigger == "ce":
                    trig = (l[i] <= ce and h[i] >= bot) if z[3] else (h[i] >= ce and l[i] <= top)
                elif cfg.trigger == "through":
                    trig = l[i] <= bot if z[3] else h[i] >= top
                else:
                    trig = z[4] and (c[i] > top if z[3] else c[i] < bot)
                if not trig:
                    continue

                entry = c[i]
                if cfg.stop_mode == "atr":
                    stop = entry - cfg.stop_atr * atr[i] if bull else entry + cfg.stop_atr * atr[i]
                else:
                    stop = bot - cfg.stop_buf_atr * atr[i] if bull else top + cfg.stop_buf_atr * atr[i]
                # a stop on the wrong side of the entry is not a trade: the bar
                # that triggered the retest closed past the zone.
                if (stop >= entry) if bull else (stop <= entry):
                    continue
                risk = abs(entry - stop)
                if risk <= 0 or risk < cfg.min_stop_atr * atr[i]:
                    continue
                if cfg.target == "rr":
                    tgt = entry + cfg.rr * risk if bull else entry - cfg.rr * risk
                else:
                    tgt = last_ph if bull else last_pl
                    if not np.isfinite(tgt) or (tgt <= entry if bull else tgt >= entry):
                        tgt = entry + cfg.rr * risk if bull else entry - cfg.rr * risk
                got_rr = abs(tgt - entry) / risk
                if got_rr < cfg.min_rr:
                    continue
                pos = {"bar": i, "side": "long" if bull else "short", "entry": entry,
                       "stop": stop, "target": tgt, "rr": float(got_rr),
                       "width": float((top - bot) / atr[i]) if atr[i] > 0 else 0.0}
                live.remove(z)
                break

        for z in by_bar.get(i, ()):
            live.append([z[0], z[1], z[2], z[3], False])

    return trades


def summarise(trades: list, label: str = "") -> dict:
    """Same shape as ict_sweep.summarise, so results sit side by side."""
    if not trades:
        print(f"{label:42s} aucun trade")
        return {}
    R = np.array([t.r_net for t in trades])
    wins = sum(1 for t in trades if t.outcome == "win")
    resolved = sum(1 for t in trades if t.outcome in ("win", "loss"))
    hit = wins / resolved if resolved else float("nan")
    rr = float(np.mean([t.rr for t in trades]))
    t_stat = R.mean() / (R.std(ddof=1) / np.sqrt(len(R))) if R.std(ddof=1) > 0 else np.nan
    be = 1 / (1 + rr)
    print(f"{label:42s} n={len(R):5d}  wr={hit*100:5.2f}% "
          f"(seuil {be*100:5.2f}%, {len(R)-resolved:3d} timeouts)  R:R={rr:4.2f}  "
          f"E={R.mean():+.4f}R  t={t_stat:+5.2f}")
    return {"n": len(R), "wr": hit, "resolved": resolved, "rr": rr,
            "expectancy": float(R.mean()), "t": float(t_stat), "breakeven": be}
