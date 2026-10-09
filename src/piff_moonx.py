"""Position sizing for PIFF on MoonX indices, calibrated on real fills.

The constants here are not read off the venue's metadata, because that metadata
is easy to misread and I misread it: a NAS100 position reports
`contractSize: 3.5, pipSize: 1, pipValue: 3.5`, and `pipValue` is the value of
one point for ONE LOT, not for the position. Taking it as the position's point
value overstates the risk of a 0.01-lot trade by a factor of 100, which turns
a 4%-of-equity trade into a 400% one and leads to exactly the wrong advice.

So the numbers below are fixed by two executed round trips instead:

    0.001 lot, +11.4 points -> +0.0399 USD   =>  0.0035 USD/point
    0.010 lot,  +0.95 points -> +0.03325 USD  =>  0.0350 USD/point

Both give 3.5 USD per point per lot. Fees came to 0.01082725 USD on a
108.2725 USD notional, i.e. 0.010% per side, charged on entry and on exit.

Minimum size was measured, not assumed: 0.001 lot filled.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .piff import PiffSignal

POINT_VALUE_PER_LOT = 3.5      # USD per index point, per lot (contractSize)
FEE_PER_SIDE = 0.0001          # fraction of notional, measured
# Measured again, lower: a 0.000001-lot order filled and settled (notional
# 0.108 USD, zero fee, auto-closed on its take profit). My earlier 0.001 floor
# was another assumption dressed as a measurement — it was simply the smallest
# size I had happened to send.
MIN_LOTS = 0.000001
LOT_STEP = 0.000001
APPLIED_LEVERAGE = 500         # the venue applies its own, ignoring a request


def point_value(lots: float) -> float:
    """USD gained or lost per index point, for this position size."""
    return lots * POINT_VALUE_PER_LOT


def lots_for_risk(risk_usd: float, stop_points: float) -> float:
    """Largest size whose stop loses no more than `risk_usd`, on the lot step.

    Rounded DOWN: rounding up would silently exceed the risk the caller set.
    """
    if stop_points <= 0 or risk_usd <= 0:
        return 0.0
    raw = risk_usd / (stop_points * POINT_VALUE_PER_LOT)
    return math.floor(raw / LOT_STEP) * LOT_STEP


@dataclass
class TradePlan:
    lots: float
    risk_usd: float
    risk_fraction: float        # of equity
    reward_usd: float
    notional: float
    margin: float
    fees_usd: float             # round trip
    fees_in_r: float
    liquidation_points: float   # adverse points equity absorbs
    stop_reachable: bool        # is the stop closer than liquidation
    refusals: list

    @property
    def ok(self) -> bool:
        return not self.refusals


def plan_trade(signal: PiffSignal, equity: float, lots: float | None = None,
               risk_fraction: float | None = None,
               max_risk_fraction: float = 0.10) -> TradePlan:
    """Size a PIFF signal and state every reason it should not be sent.

    Either `lots` is given, or `risk_fraction` sizes it. The liquidation check
    is the one that matters on a small balance: a stop further away than the
    equity can absorb is never reached, so the position would be closed by the
    venue at a loss the plan never accounted for.
    """
    if signal.action == "flat":
        return TradePlan(0, 0, 0, 0, 0, 0, 0, 0, 0, False, ["the signal is flat"])

    if lots is None:
        if risk_fraction is None:
            raise ValueError("pass either lots or risk_fraction")
        lots = lots_for_risk(equity * risk_fraction, signal.stop_points)

    refusals = []
    if lots < MIN_LOTS:
        refusals.append(
            f"{lots:.4f} lots is below the {MIN_LOTS} minimum — a {signal.stop_points:.1f} "
            f"point stop cannot be risked that small; the floor is "
            f"{MIN_LOTS * POINT_VALUE_PER_LOT * signal.stop_points:.3f} USD")

    pv = point_value(lots)
    risk = pv * signal.stop_points
    reward = pv * abs(signal.target - signal.entry)
    notional = lots * POINT_VALUE_PER_LOT * signal.entry
    fees = 2 * FEE_PER_SIDE * notional
    liq = equity / pv if pv > 0 else 0.0

    frac = risk / equity if equity > 0 else float("inf")
    if frac > max_risk_fraction:
        refusals.append(f"risks {frac:.1%} of equity, above the {max_risk_fraction:.0%} cap")
    if signal.stop_points >= liq:
        refusals.append(
            f"the {signal.stop_points:.1f} point stop sits beyond the {liq:.1f} points "
            f"this equity absorbs: liquidation would come first")
    if notional / APPLIED_LEVERAGE > equity:
        refusals.append("not enough free margin")

    return TradePlan(lots=round(lots, 4), risk_usd=risk, risk_fraction=frac,
                     reward_usd=reward, notional=notional,
                     margin=notional / APPLIED_LEVERAGE, fees_usd=fees,
                     fees_in_r=fees / risk if risk > 0 else 0.0,
                     liquidation_points=liq,
                     stop_reachable=signal.stop_points < liq, refusals=refusals)
