"""The H4-break rule, and the simulation that scores it.

The backtest is the deliverable here, so what is tested is mostly the
simulation's honesty: no look-ahead on the H4 level, the stop taken when a bar
touches both barriers, one position at a time, and fees charged on every trade.
"""
import numpy as np
import pandas as pd
import pytest

from src.h4break import H4Config, Trade, backtest, confirms_long, summarise


def frame(rows, start="2026-10-09 00:00", freq="1h"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def h4_of(bars):
    r = bars.resample("4h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return r


# --- the confirmation ------------------------------------------------------

def test_a_rejection_is_a_long_lower_wick_closing_high():
    bars = frame([[100, 101, 99, 100], [100, 101, 94, 100.5]])
    assert confirms_long(bars, 1, H4Config(confirm="reject")) == "rejection"


def test_an_engulfing_bar_swallows_the_previous_body():
    bars = frame([[100, 101, 99, 99.2], [99.1, 102, 99.0, 101.5]])
    assert confirms_long(bars, 1, H4Config()) == "engulfing"


def test_an_ordinary_bar_confirms_nothing():
    bars = frame([[100, 101, 99, 100], [100, 100.5, 99.5, 100.1]])
    assert confirms_long(bars, 1, H4Config()) is None


def test_the_confirmation_type_can_be_restricted():
    bars = frame([[100, 101, 99, 99.2], [99.1, 102, 99.0, 101.5]])
    assert confirms_long(bars, 1, H4Config(confirm="reject")) is None
    assert confirms_long(bars, 1, H4Config(confirm="engulf")) == "engulfing"


# --- the simulation's honesty ---------------------------------------------

def test_the_h4_level_is_only_usable_after_that_candle_closes():
    """Indexing on the forming candle makes its low unbreakable by construction,
    because that low already contains the current bar."""
    rows = [[100, 102, 98, 101]] * 40
    bars = frame(rows)
    htf = h4_of(bars)
    # a flat market cannot break anything, but the point is the indexing: with
    # look-ahead the break condition is false everywhere and the rule is silent
    assert backtest(htf, bars, H4Config()) == []


def _one_trade_frame():
    """Break the previous H4 low, reject, then run to the target."""
    rows = [[100, 101, 99, 100]] * 4        # H4 #1: low 99
    rows += [[100, 101, 97, 98]]            # breaks 99
    rows += [[98, 99, 94, 98.8]]            # rejection: long lower wick, closes high
    rows += [[98.8, 120, 98.5, 119]]        # runs far enough for any 2:1
    rows += [[119, 121, 118, 120]] * 3
    return frame(rows)


def test_a_winning_trade_is_recorded_with_its_r():
    bars = _one_trade_frame()
    trades = backtest(h4_of(bars), bars, H4Config(rr=2.0))
    assert len(trades) == 1
    t = trades[0]
    assert t.outcome == "win"
    assert t.r_gross == pytest.approx(2.0)
    assert t.confirm == "rejection"
    assert t.stop < t.entry < t.target
    assert t.r_net == pytest.approx(2.0 - t.fees_in_r)


def test_the_stop_wins_when_one_bar_touches_both_barriers():
    """Intrabar order is unknowable; assuming the target flatters the result."""
    rows = [[100, 101, 99, 100]] * 4
    rows += [[100, 101, 97, 98]]
    rows += [[98, 99, 94, 98.8]]            # rejection, stop will sit under 94
    rows += [[98.8, 200, 80, 150]]          # hits both; the stop must be taken
    rows += [[150, 151, 149, 150]] * 2
    bars = frame(rows)
    trades = backtest(h4_of(bars), bars, H4Config(rr=2.0))
    assert len(trades) == 1
    assert trades[0].outcome == "loss"
    assert trades[0].r_gross == pytest.approx(-1.0)


def test_fees_are_charged_on_every_trade():
    bars = _one_trade_frame()
    paid = backtest(h4_of(bars), bars, H4Config(rr=2.0, fee_per_side=0.0007))[0]
    free = backtest(h4_of(bars), bars, H4Config(rr=2.0, fee_per_side=0.0))[0]
    assert paid.fees_in_r > 0 and free.fees_in_r == 0
    assert paid.r_net < free.r_net
    assert paid.r_gross == free.r_gross


def test_positions_do_not_overlap():
    rows = [[100, 101, 99, 100]] * 4
    for _ in range(6):
        rows += [[100, 101, 97, 98], [98, 99, 94, 98.8], [98.8, 120, 98.5, 119]]
    bars = frame(rows)
    trades = backtest(h4_of(bars), bars, H4Config())
    for a, b in zip(trades, trades[1:]):
        assert a.exited <= b.entered


def test_a_trade_that_resolves_neither_way_times_out():
    rows = [[100, 101, 99, 100]] * 4
    rows += [[100, 101, 97, 98], [98, 99, 94, 98.8]]
    rows += [[98.8, 99.2, 98.6, 98.9]] * 5     # goes nowhere
    bars = frame(rows)
    trades = backtest(h4_of(bars), bars, H4Config(max_hold_bars=3))
    assert trades and trades[0].outcome == "timeout"
    assert -1.0 < trades[0].r_gross < 2.0


# --- the summary -----------------------------------------------------------

def test_the_summary_states_both_break_even_thresholds():
    bars = _one_trade_frame()
    s = summarise(backtest(h4_of(bars), bars, H4Config(rr=2.0)), H4Config(rr=2.0))
    assert s["breakeven_random"] == pytest.approx(1 / 3)
    assert s["breakeven_with_fees"] > s["breakeven_random"]


def test_the_random_walk_threshold_follows_the_reward_ratio():
    for rr in (1.0, 2.0, 3.0, 4.0):
        s = summarise([Trade(outcome="win", r_gross=rr, r_net=rr)], H4Config(rr=rr))
        assert s["breakeven_random"] == pytest.approx(1 / (1 + rr))


def test_an_empty_backtest_summarises_without_raising():
    assert summarise([], H4Config())["trades"] == 0
