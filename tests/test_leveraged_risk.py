import numpy as np
import pytest

from src.leveraged_risk import (DailyLossGuard, LeverageLimits, OrderRefused,
                                size_position, stop_distance_from_vol, validate_order)

VOL = 0.018          # BTC daily vol, recent EWMA
LIM = LeverageLimits()


def test_no_stop_loss_means_no_order():
    with pytest.raises(OrderRefused, match="no stop-loss"):
        validate_order({"entry_price": 100.0, "side": "long"}, 10_000, VOL)


def test_leverage_is_an_output_of_the_stop_not_an_input():
    stop = stop_distance_from_vol(VOL, k=2.0)          # 3.6%
    order = size_position(10_000, 100.0, 100 * (1 - stop), "long", VOL)
    # risk 1% of 10k = 100 USD; a 3.6% stop implies 2778 notional -> 0.28x
    assert order.risk_amount == pytest.approx(100.0)
    assert order.notional == pytest.approx(100.0 / stop)
    assert order.leverage == pytest.approx(order.notional / 10_000)
    assert order.leverage < LIM.max_leverage


def test_a_two_percent_stop_on_btc_is_refused_as_noise():
    with pytest.raises(OrderRefused, match="hit by noise"):
        size_position(10_000, 100.0, 98.0, "long", 0.036)   # 2% stop on 3.6% vol = 0.56 sigma


def test_tight_stop_that_implies_too_much_leverage_is_refused_with_the_arithmetic():
    limits = LeverageLimits(risk_per_trade=0.05, max_leverage=3.0, min_stop_sigma=0.5,
                            max_concurrent_risk=0.10)
    with pytest.raises(OrderRefused, match="above the 3.0x cap"):
        size_position(10_000, 100.0, 99.0, "long", VOL, limits)


def test_stop_on_the_wrong_side_is_refused():
    with pytest.raises(OrderRefused, match="below the entry"):
        size_position(10_000, 100.0, 103.0, "long", VOL)
    with pytest.raises(OrderRefused, match="above the entry"):
        size_position(10_000, 100.0, 97.0, "short", VOL)


def test_daily_loss_limit_blocks_new_risk():
    with pytest.raises(OrderRefused, match="daily loss limit"):
        size_position(10_000, 100.0, 96.0, "long", VOL, LIM, day_pnl=-500.0)


def test_concurrent_risk_cap():
    with pytest.raises(OrderRefused, match="concurrent cap"):
        size_position(10_000, 100.0, 96.0, "long", VOL, LIM, open_risk=0.03)


def test_requested_notional_cannot_exceed_the_sized_one():
    with pytest.raises(OrderRefused, match="exceeds the sized"):
        validate_order({"entry_price": 100.0, "stop_price": 96.0, "side": "long",
                        "notional": 1_000_000}, 10_000, VOL)


def test_guard_counts_remaining_stop_outs():
    guard = DailyLossGuard(equity_at_open=10_000, max_daily_loss=0.05)
    assert guard.remaining_risk_budget(0.01) == 5
    guard.record(-100.0, "trade 1")
    guard.record(-100.0, "trade 2")
    assert guard.remaining_risk_budget(0.01) == 3
    assert not guard.breached
    guard.record(-300.0, "trade 3")
    assert guard.breached
    assert guard.remaining_risk_budget(0.01) == 0


def test_short_sizing_is_symmetric():
    long_order = size_position(10_000, 100.0, 96.0, "long", VOL)
    short_order = size_position(10_000, 100.0, 104.0, "short", VOL)
    assert long_order.notional == pytest.approx(short_order.notional)
    assert long_order.risk_amount == pytest.approx(short_order.risk_amount)
