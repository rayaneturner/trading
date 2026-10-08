"""Order generation and execution.

Design rules, in order of importance:

1. The strategy decides *weights*; the executor decides *orders*. They are
   separate so the risk logic can be tested without a venue, and so the venue
   can be swapped without touching the risk logic.
2. Dry run is the default. Nothing hits a venue unless `live=True` is passed
   explicitly AND the environment variable TRADING_LIVE=1 is set. Two
   independent switches, because one is too easy to flip by accident.
3. Hard caps are enforced here, not in the strategy: per-order notional, total
   turnover per run, and a minimum trade size. A bug in the signal can ask for
   anything; the executor is what stops it from being filled.
4. Spot, long/flat only. No margin, no futures, no borrowing.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ExecutionLimits:
    min_trade_notional: float = 25.0      # skip dust; most venues reject it anyway
    max_order_notional: float = 5_000.0   # per order
    max_turnover_fraction: float = 1.00   # of equity, per run: a full rotation
                                          # (all cash -> fully invested) is 1.0,
                                          # so anything above this is a bug, not
                                          # a rebalance
    no_trade_band: float = 0.05           # of equity, per leg
    slippage_guard: float = 0.01          # reject if price moved >1% vs signal price


@dataclass
class Order:
    symbol: str
    side: str          # "buy" | "sell"
    notional: float    # USD
    amount: float      # base units
    reason: str = ""

    def to_dict(self) -> dict:
        return {"symbol": self.symbol, "side": self.side,
                "notional": round(self.notional, 2), "amount": self.amount,
                "reason": self.reason}


def plan_orders(target_weights: pd.Series, holdings: dict, prices: dict,
                cash: float, limits: ExecutionLimits) -> tuple[list[Order], dict]:
    """Translate target weights into orders.

    holdings: {"BTC": base_units, ...}; prices: {"BTC": usd_price, ...}
    cash:     USD (or stablecoin) balance.
    """
    positions = {a: holdings.get(a, 0.0) * prices[a] for a in prices}
    equity = cash + sum(positions.values())
    if equity <= 0:
        return [], {"equity": equity, "error": "no equity"}

    orders: list[Order] = []
    for asset, weight in target_weights.items():
        if asset not in prices:
            continue
        target_notional = float(weight) * equity
        delta = target_notional - positions.get(asset, 0.0)
        if abs(delta) < limits.no_trade_band * equity:
            continue
        if abs(delta) < limits.min_trade_notional:
            continue
        # A full exit is never capped away: reducing risk must always complete.
        is_exit = float(weight) == 0.0
        notional = delta if is_exit else max(min(delta, limits.max_order_notional),
                                             -limits.max_order_notional)
        orders.append(Order(
            symbol=asset,
            side="buy" if notional > 0 else "sell",
            notional=abs(notional),
            amount=abs(notional) / prices[asset],
            reason=f"target {weight:.3f} vs current {positions.get(asset, 0.0) / equity:.3f}",
        ))

    # Never spend more cash than exists.
    buys = sum(o.notional for o in orders if o.side == "buy")
    if buys > cash:
        scale = cash / buys if buys else 0.0
        for o in orders:
            if o.side == "buy":
                o.notional *= scale
                o.amount *= scale
                o.reason += f" (cash-scaled {scale:.2f})"
        orders = [o for o in orders if o.notional >= limits.min_trade_notional]

    turnover = sum(o.notional for o in orders)
    cap = limits.max_turnover_fraction * equity
    blocked = None
    if turnover > cap:
        blocked = f"turnover {turnover:.0f} exceeds cap {cap:.0f}; sells kept, buys dropped"
        orders = [o for o in orders if o.side == "sell"]

    diagnostics = {
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "current_weights": {a: round(v / equity, 4) for a, v in positions.items()},
        "target_weights": {a: round(float(w), 4) for a, w in target_weights.items()},
        "turnover": round(sum(o.notional for o in orders), 2),
        "warning": blocked,
    }
    return orders, diagnostics


class CcxtExecutor:
    """Spot executor for any ccxt venue. Market orders, one shot, no chasing."""

    def __init__(self, exchange: str = "kraken", quote: str = "USD",
                 limits: ExecutionLimits | None = None, live: bool = False):
        self.exchange_id = exchange
        self.quote = quote
        self.limits = limits or ExecutionLimits()
        self.live = bool(live) and os.environ.get("TRADING_LIVE") == "1"
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import ccxt
            key = os.environ.get(f"{self.exchange_id.upper()}_API_KEY")
            secret = os.environ.get(f"{self.exchange_id.upper()}_API_SECRET")
            self._client = getattr(ccxt, self.exchange_id)({
                "apiKey": key, "secret": secret, "enableRateLimit": True,
            })
        return self._client

    def snapshot(self, assets) -> tuple[dict, dict, float]:
        balance = self.client.fetch_balance()
        holdings = {a: float(balance.get(a, {}).get("free", 0.0) or 0.0) for a in assets}
        prices = {}
        for a in assets:
            prices[a] = float(self.client.fetch_ticker(f"{a}/{self.quote}")["last"])
        cash = float(balance.get(self.quote, {}).get("free", 0.0) or 0.0)
        return holdings, prices, cash

    def execute(self, orders: list[Order]) -> list[dict]:
        receipts = []
        for order in orders:
            payload = {"symbol": f"{order.symbol}/{self.quote}", "side": order.side,
                       "amount": order.amount, "ts": time.time()}
            if not self.live:
                receipts.append({**payload, "status": "dry_run"})
                continue
            try:
                res = self.client.create_order(payload["symbol"], "market",
                                               order.side, order.amount)
                receipts.append({**payload, "status": "sent", "id": res.get("id")})
            except Exception as exc:  # a venue rejection must not abort the rest
                receipts.append({**payload, "status": "error", "error": str(exc)})
        return receipts


def append_log(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")
