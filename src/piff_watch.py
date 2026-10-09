"""The PIFF loop: evaluate, size, act, and refuse.

Split from the transport on purpose. `step` takes a client object and returns
what it did, so every branch — the daily stop, the one-position rule, the stale
pending order, the refusal to trade — is exercised against a fake client in the
test suite. Only the HTTP in moonx_client is untested, and it fails loudly.

DRY RUN IS THE DEFAULT. The engine has never been backtested: 101 tests show it
applies the rule, not that the rule makes money, and five separate defects were
found in it on its first live afternoon — two of which made every correct setup
unprofitable by construction. Running it for a while in dry run, comparing its
signals against a human read, is how the next one gets found before it costs
anything. `live=True` is a deliberate second step.

The guards are not decoration. An automated loop with no daily stop and no
position cap is how an account reaches zero while nobody is reading the log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from .piff import PiffConfig, generate
from .piff_live import CandleDataError, parse_candles, resample
from .piff_moonx import lots_for_risk, plan_trade

log = logging.getLogger("piff")


@dataclass(frozen=True)
class WatchConfig:
    pair: str = "NAS100"
    risk_usd: float = 2.0          # absolute, as the author sets it
    structure_rule: str = "5min"
    htf_interval: str = "15m"
    poll_seconds: int = 60
    live: bool = False             # dry run until explicitly turned off
    max_open: int = 1              # one position at a time
    max_pending: int = 1           # one resting order at a time
    daily_loss_stop: float = 0.05  # halt for the day after losing this fraction
    max_risk_fraction: float = 0.10
    use_htf_bias: bool = False     # the EMA bias lags badly on M15; off by default
    allow_pending: bool = True     # arm resting orders, not just immediate entries
    strategy: PiffConfig = field(default_factory=lambda: PiffConfig(
        min_rr=2.0, require_htf_bias=False, session_start_hour=None))


@dataclass
class WatchState:
    day: object = None
    day_start_equity: float = 0.0
    halted_for_day: bool = False
    trades_today: int = 0


def _roll_day(state: WatchState, now: pd.Timestamp, equity: float) -> None:
    day = now.date()
    if state.day != day:
        state.day, state.day_start_equity = day, equity
        state.halted_for_day, state.trades_today = False, 0


def step(client, cfg: WatchConfig, state: WatchState,
         now: pd.Timestamp | None = None) -> dict:
    """One pass. Returns what happened; never raises on a refusal."""
    now = now or pd.Timestamp.now(tz="UTC")
    overview = client.overview()
    equity = float(overview["forexWallet"]["equity"])
    free = float(overview["forexWallet"]["freeMargin"])
    _roll_day(state, now, equity)

    drawdown = ((state.day_start_equity - equity) / state.day_start_equity
                if state.day_start_equity else 0.0)
    if drawdown >= cfg.daily_loss_stop:
        state.halted_for_day = True
    if state.halted_for_day:
        return {"action": "halted",
                "why": f"down {drawdown:.2%} today, stop is {cfg.daily_loss_stop:.0%}"}

    positions, orders = client.positions(), client.orders()

    try:
        # The history requirement lives in the strategy config, not here: two
        # places deciding how many bars are enough is one place too many.
        m1 = parse_candles(client.candles(cfg.pair, "1m", 500), "1m",
                           min_bars=cfg.strategy.min_bars)
        # Two different jobs, two different depths. The EMA bias needs enough
        # history for the slow span to mean anything; the target only needs
        # enough bars for a k-fractal to exist. Demanding 50 either way made
        # the loop skip every pass on a short series it could have read.
        m15 = parse_candles(client.candles(cfg.pair, cfg.htf_interval, 500),
                            cfg.htf_interval,
                            min_bars=50 if cfg.use_htf_bias
                            else 2 * cfg.strategy.swing_k + 1)
        htf = m15 if cfg.use_htf_bias else None
    except CandleDataError as exc:
        return {"action": "skipped", "why": f"candle data unusable: {exc}"}

    # A feed that has stopped moving is a closed market, not an opportunity.
    if (now - m1.index[-1]) > pd.Timedelta(minutes=10):
        return {"action": "skipped",
                "why": f"last bar is {m1.index[-1]}, market looks closed"}

    structure = resample(m1, cfg.structure_rule)

    # Cancel a resting order whose setup no longer exists. An untended order is
    # a trade nobody decided on: the sweep it was placed for can expire, or
    # price can close through the gap, while the order sleeps at the venue.
    cancelled = []
    if orders and generate(m1, structure, htf, cfg.strategy, target_bars=m15,
                           pending=True).action == "flat":
        for o in orders:
            oid = o.get("_id") or o.get("id")
            if cfg.live:
                client.cancel_order(oid)
            cancelled.append(oid)

    if len(positions) >= cfg.max_open:
        return {"action": "holding", "positions": len(positions),
                "cancelled": cancelled}
    if len(orders) - len(cancelled) >= cfg.max_pending:
        return {"action": "waiting_on_order", "cancelled": cancelled}

    # Immediate entry first: it carries the tighter stop and the confirmed bar.
    last = None
    for pending in (False, True) if cfg.allow_pending else (False,):
        sig = generate(m1, structure, htf, cfg.strategy, pending=pending,
                       target_bars=m15)
        last = sig
        if sig.action == "flat":
            continue
        lots = lots_for_risk(cfg.risk_usd, sig.stop_points)
        plan = plan_trade(sig, free, lots=lots,
                          max_risk_fraction=cfg.max_risk_fraction)
        if not plan.ok:
            log.warning("refused %s: %s", sig.action, "; ".join(plan.refusals))
            continue

        side = "buy" if sig.action == "long" else "sell"
        out = {"action": "would_send" if not cfg.live else "sent",
               "pending": pending, "side": side, "lots": plan.lots,
               "entry": sig.entry, "stop": sig.stop, "target": sig.target,
               "rr": round(sig.rr, 2), "risk_usd": round(plan.risk_usd, 2),
               "fees_in_r": round(plan.fees_in_r, 3), "reasons": sig.reasons,
               "cancelled": cancelled}
        if cfg.live:
            out["venue"] = (
                client.open_limit(cfg.pair, side, plan.lots, sig.entry,
                                  sig.stop, sig.target) if pending else
                client.open_market(cfg.pair, side, plan.lots, sig.stop, sig.target))
            state.trades_today += 1
        return out

    return {"action": "flat", "cancelled": cancelled,
            "why": "; ".join(f"{d}: {w}" for d, w in (last.trace or {}).items())
                   if last else ""}
