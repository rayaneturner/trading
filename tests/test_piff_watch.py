"""The loop's guards, against a fake venue.

Every branch that can lose money is exercised here: the daily stop, the one
position rule, the stale order cancellation, and the refusal to size a trade
past the risk cap. The transport is deliberately absent — this is about what
the loop decides, not how it talks.
"""
import pandas as pd
import pytest

from src.piff import PiffConfig
from src.piff_watch import WatchConfig, WatchState, step
from tests.test_piff import _piff_short_setup, _piff_armed_setup


def _payload(bars, interval):
    return {"interval": interval,
            "candles": [{"time": int(t.timestamp() * 1000), "open": r["open"],
                         "high": r["high"], "low": r["low"], "close": r["close"],
                         "volume": 1.0} for t, r in bars.iterrows()]}


class FakeClient:
    """Records what the loop asked for, answers with a scripted market."""

    def __init__(self, m1, equity=23.0, free=23.0, positions=None, orders=None):
        self.m1, self.equity, self.free = m1, equity, free
        self._positions = positions or []
        self._orders = orders or []
        self.sent, self.cancelled = [], []

    def overview(self):
        return {"forexWallet": {"equity": self.equity, "freeMargin": self.free}}

    def positions(self):
        return self._positions

    def orders(self):
        return self._orders

    def candles(self, symbol, interval, limit=500):
        if interval == "1m":
            return _payload(self.m1, "1m")
        return _payload(self.m1.resample("15min").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}
        ).dropna(), "15m")

    def open_market(self, *a):
        self.sent.append(("market",) + a)
        return {"ok": True}

    def open_limit(self, *a):
        self.sent.append(("limit",) + a)
        return {"ok": True}

    def cancel_order(self, oid):
        self.cancelled.append(oid)
        return {"ok": True}


def _cfg(**kw):
    base = dict(risk_usd=2.0, structure_rule="5min", use_htf_bias=False,
                strategy=PiffConfig(min_rr=0.1, require_htf_bias=False,
                                    session_start_hour=None, min_structure_bars=5,
                                    swing_k=1, fvg_min_points=1.0, min_bars=20,
                                    max_fee_fraction_of_r=10.0),
                max_risk_fraction=0.50)
    base.update(kw)
    return WatchConfig(**base)


def _now(bars, extra=pd.Timedelta(minutes=1)):
    """The fixtures are tz-naive; parse_candles returns UTC, so localise."""
    return (bars.index[-1] + extra).tz_localize("UTC")


# --- the loop acts ---------------------------------------------------------

def test_dry_run_describes_the_trade_without_sending_it():
    """The default. The engine is unvalidated, so acting is the second step."""
    bars = _piff_armed_setup()
    client = FakeClient(bars)
    out = step(client, _cfg(), WatchState(), now=_now(bars))
    assert out["action"] == "would_send"
    assert out["side"] == "sell"
    assert client.sent == []


def test_live_mode_sends_a_resting_order():
    bars = _piff_armed_setup()
    client = FakeClient(bars)
    out = step(client, _cfg(live=True), WatchState(), now=_now(bars))
    assert out["action"] == "sent" and out["pending"] is True
    assert len(client.sent) == 1 and client.sent[0][0] == "limit"


def test_the_trade_is_sized_to_the_risk_budget():
    bars = _piff_armed_setup()
    client = FakeClient(bars)
    out = step(client, _cfg(risk_usd=2.0), WatchState(), now=_now(bars))
    assert out["risk_usd"] == pytest.approx(2.0, abs=0.01)


# --- the loop refuses ------------------------------------------------------

def test_the_daily_stop_halts_everything():
    bars = _piff_armed_setup()
    client = FakeClient(bars, equity=20.0)
    state = WatchState(day=_now(bars).date(), day_start_equity=23.0)
    out = step(client, _cfg(live=True), state, now=_now(bars))
    assert out["action"] == "halted"
    assert state.halted_for_day
    assert client.sent == []


def test_the_halt_survives_the_equity_recovering():
    """Once the day is done it is done; a bounce does not reopen trading."""
    bars = _piff_armed_setup()
    state = WatchState(day=_now(bars).date(), day_start_equity=23.0)
    step(FakeClient(bars, equity=20.0), _cfg(), state, now=_now(bars))
    out = step(FakeClient(bars, equity=23.0), _cfg(live=True), state, now=_now(bars))
    assert out["action"] == "halted"


def test_a_new_day_clears_the_halt():
    bars = _piff_armed_setup()
    state = WatchState(day=(_now(bars) - pd.Timedelta(days=1)).date(),
                       day_start_equity=23.0, halted_for_day=True)
    out = step(FakeClient(bars), _cfg(), state, now=_now(bars))
    assert out["action"] != "halted"


def test_one_position_at_a_time():
    bars = _piff_armed_setup()
    client = FakeClient(bars, positions=[{"_id": "p1"}])
    out = step(client, _cfg(live=True), WatchState(), now=_now(bars))
    assert out["action"] == "holding"
    assert client.sent == []


def test_a_resting_order_blocks_a_second_one():
    bars = _piff_armed_setup()
    client = FakeClient(bars, orders=[{"_id": "o1"}])
    out = step(client, _cfg(live=True), WatchState(), now=_now(bars))
    assert out["action"] == "waiting_on_order"
    assert client.sent == []


def test_an_order_whose_setup_is_gone_is_cancelled():
    """Price closed through the gap: the order is a trade nobody decided on."""
    bars = _piff_short_setup()     # the gap has been traded into on this fixture
    client = FakeClient(bars, orders=[{"_id": "stale"}])
    out = step(client, _cfg(live=True), WatchState(), now=_now(bars))
    assert "stale" in client.cancelled
    assert "stale" in out["cancelled"]


def test_a_risk_above_the_cap_is_refused():
    bars = _piff_armed_setup()
    client = FakeClient(bars, equity=5.0, free=5.0)
    out = step(client, _cfg(live=True, max_risk_fraction=0.10), WatchState(),
               now=_now(bars))
    assert out["action"] == "flat"
    assert client.sent == []


def test_a_stale_feed_is_treated_as_a_closed_market():
    bars = _piff_armed_setup()
    client = FakeClient(bars)
    out = step(client, _cfg(live=True), WatchState(),
               now=_now(bars, pd.Timedelta(hours=3)))
    assert out["action"] == "skipped" and "closed" in out["why"]
    assert client.sent == []


def test_a_flat_market_reports_why():
    flat = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        index=pd.date_range("2026-03-26 14:00", periods=200, freq="1min"))
    out = step(FakeClient(flat), _cfg(), WatchState(), now=_now(flat))
    assert out["action"] == "flat" and out["why"]
