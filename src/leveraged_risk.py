"""Position sizing and order validation for a leveraged account.

The ordering that matters, and that most prompts get backwards.

A venue's example reads "5% margin, 20x leverage, stop 2%": margin and leverage
are chosen first, and the stop is pasted on afterwards. That makes the stop
cosmetic — the real risk was already fixed by the leverage.

The correct order has three steps and only one free choice:

    1. stop distance  <- volatility of the asset (not a round number)
    2. notional       <- risk_per_trade / stop_distance
    3. leverage       <- notional / margin     (an OUTPUT, never an input)

Leverage is what falls out of the first two. Asking for 20x first and then
finding a stop that fits it is sizing the risk to the leverage instead of the
other way round.

Why the stop must come from volatility: on BTC's ~3.6% daily volatility a 2%
stop sits at 0.56 sigma, so it is hit by noise rather than by the trade being
wrong. Measured in src/barrier_study.py: checking that stop intraday rather than
at the close drops the win rate of a 1:3 setup from 38% to 26-28%, against a
25% break-even.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class LeverageLimits:
    risk_per_trade: float = 0.01       # fraction of equity risked if the stop is hit
    max_daily_loss: float = 0.05       # stop opening new risk for the day beyond this
    max_leverage: float = 3.0          # hard cap on the leverage the sizing may imply
    min_stop_sigma: float = 1.5        # a stop closer than this to the noise is refused
    max_stop_sigma: float = 6.0        # a stop this wide means the size is meaningless
    max_concurrent_risk: float = 0.03  # total risk across all open positions


@dataclass
class SizedOrder:
    symbol: str
    side: str
    stop_distance: float      # fraction, e.g. 0.027 for 2.7%
    notional: float           # USD
    margin: float             # USD
    leverage: float
    risk_amount: float        # USD lost if the stop fills exactly
    stop_price: float
    entry_price: float
    stop_sigma: float

    def to_dict(self) -> dict:
        return {"symbol": self.symbol, "side": self.side,
                "entry_price": round(self.entry_price, 2),
                "stop_price": round(self.stop_price, 2),
                "stop_distance_pct": round(self.stop_distance * 100, 2),
                "stop_in_daily_sigma": round(self.stop_sigma, 2),
                "notional": round(self.notional, 2), "margin": round(self.margin, 2),
                "leverage": round(self.leverage, 2),
                "risk_amount": round(self.risk_amount, 2)}


class OrderRefused(Exception):
    """Raised instead of returning a size. A refusal is a result, not an error."""


def stop_distance_from_vol(daily_vol: float, k: float = 2.0) -> float:
    """Stop at k daily standard deviations. k below ~1.5 is inside the noise."""
    if daily_vol <= 0:
        raise OrderRefused("daily volatility must be positive")
    return k * daily_vol


def size_position(equity: float, entry_price: float, stop_price: float, side: str,
                  daily_vol: float, limits: LeverageLimits = LeverageLimits(),
                  open_risk: float = 0.0, day_pnl: float = 0.0) -> SizedOrder:
    """Size from the stop, then report the leverage that implies.

    Refuses, rather than clamping silently, whenever a limit is breached: a
    silently shrunk order is an order the caller did not ask for.
    """
    if equity <= 0:
        raise OrderRefused("no equity")
    if side not in ("long", "short"):
        raise OrderRefused(f"side must be long or short, got {side!r}")
    if entry_price <= 0 or stop_price <= 0:
        raise OrderRefused("prices must be positive")

    if side == "long" and stop_price >= entry_price:
        raise OrderRefused("a long's stop must sit below the entry")
    if side == "short" and stop_price <= entry_price:
        raise OrderRefused("a short's stop must sit above the entry")

    stop_distance = abs(entry_price - stop_price) / entry_price
    stop_sigma = stop_distance / daily_vol if daily_vol > 0 else np.inf

    if day_pnl <= -limits.max_daily_loss * equity:
        raise OrderRefused(
            f"daily loss limit reached ({day_pnl / equity * 100:.1f}% of equity, "
            f"limit {limits.max_daily_loss * 100:.0f}%): no new risk today")
    if stop_sigma < limits.min_stop_sigma:
        raise OrderRefused(
            f"stop is {stop_sigma:.2f} daily sigma away, below the {limits.min_stop_sigma} "
            "minimum: it would be hit by noise, not by the trade being wrong")
    if stop_sigma > limits.max_stop_sigma:
        raise OrderRefused(
            f"stop is {stop_sigma:.2f} daily sigma away, above the {limits.max_stop_sigma} "
            "maximum: the position would be too small to matter")
    if open_risk + limits.risk_per_trade > limits.max_concurrent_risk:
        raise OrderRefused(
            f"open risk {open_risk * 100:.1f}% plus this trade exceeds the "
            f"{limits.max_concurrent_risk * 100:.0f}% concurrent cap")

    risk_amount = limits.risk_per_trade * equity
    notional = risk_amount / stop_distance
    leverage = notional / equity

    if leverage > limits.max_leverage:
        max_notional = limits.max_leverage * equity
        raise OrderRefused(
            f"a {limits.risk_per_trade * 100:.1f}% risk with a {stop_distance * 100:.2f}% "
            f"stop implies {leverage:.1f}x leverage, above the {limits.max_leverage:.1f}x cap. "
            f"Either widen the stop or accept a smaller risk: at the cap the notional is "
            f"{max_notional:,.0f} and the risk becomes "
            f"{max_notional * stop_distance / equity * 100:.2f}% of equity")

    return SizedOrder(symbol="", side=side, stop_distance=stop_distance, notional=notional,
                      margin=notional / max(leverage, 1e-9) if leverage else notional,
                      leverage=leverage, risk_amount=risk_amount, stop_price=stop_price,
                      entry_price=entry_price, stop_sigma=stop_sigma)


def validate_order(order: dict, equity: float, daily_vol: float,
                   limits: LeverageLimits = LeverageLimits(),
                   open_risk: float = 0.0, day_pnl: float = 0.0) -> SizedOrder:
    """Gate every order an agent proposes. No stop-loss means no order."""
    if order.get("stop_price") in (None, 0):
        raise OrderRefused("no stop-loss: refused. Every order carries a stop.")
    sized = size_position(equity, float(order["entry_price"]), float(order["stop_price"]),
                          order.get("side", "long"), daily_vol, limits, open_risk, day_pnl)
    sized.symbol = order.get("symbol", "")
    requested = order.get("notional")
    if requested is not None and float(requested) > sized.notional * 1.0001:
        raise OrderRefused(
            f"requested notional {float(requested):,.0f} exceeds the sized "
            f"{sized.notional:,.0f} implied by a {limits.risk_per_trade * 100:.1f}% risk")
    return sized


@dataclass
class DailyLossGuard:
    """Tracks the day's realised P&L and blocks new risk past the limit.

    Deliberately does not close open positions when it trips: measured on this
    strategy, flattening after a bad day makes the drawdown worse, because the
    days following a sharp loss returned above average (see src/risk_rules.py).
    It stops *adding* risk, which is the part that compounds a bad day.
    """
    equity_at_open: float
    max_daily_loss: float = 0.05
    realised: float = 0.0
    trades: list = field(default_factory=list)

    def record(self, pnl: float, label: str = "") -> None:
        self.realised += pnl
        self.trades.append({"pnl": pnl, "label": label})

    @property
    def loss_fraction(self) -> float:
        return self.realised / self.equity_at_open if self.equity_at_open else 0.0

    @property
    def breached(self) -> bool:
        return self.loss_fraction <= -self.max_daily_loss

    def remaining_risk_budget(self, risk_per_trade: float) -> int:
        """How many more full stop-outs fit before the daily limit."""
        if self.equity_at_open <= 0:
            return 0
        head_room = self.max_daily_loss + self.loss_fraction
        return max(int(head_room / risk_per_trade), 0)
