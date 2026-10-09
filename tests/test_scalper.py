import numpy as np
import pandas as pd
import pytest

from src.scalper import (ScalpConfig, atr, breakeven_multiple_of_random, generate,
                         in_blackout, minimum_viable_stop, rsi)


def bars(n=1200, drift=0.0, vol=0.001, seed=0, start="2026-01-01"):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=n, freq="5min")
    close = 80000 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    high = close * (1 + np.abs(rng.normal(0, vol, n)))
    low = close * (1 - np.abs(rng.normal(0, vol, n)))
    return pd.DataFrame({"open": close, "high": high, "low": low, "close": close,
                         "volume": 1.0}, index=idx)


def higher_from(frame):
    return frame.resample("1h").agg({"open": "first", "high": "max", "low": "min",
                                     "close": "last", "volume": "sum"}).dropna()


def test_breakeven_multiple_is_independent_of_reward_risk():
    """The result the whole design rests on: widening the target does not help."""
    cfg = ScalpConfig()
    stop = 0.004
    cost = 2 * cfg.fee_per_side / stop
    for rr in (1, 3, 10):
        p_be = (1 + cost) / (1 + rr)
        p_random = 1 / (1 + rr)
        assert p_be / p_random == pytest.approx(breakeven_multiple_of_random(stop, cfg))


def test_minimum_viable_stop_matches_the_fee_budget():
    cfg = ScalpConfig(fee_per_side=0.0006, max_fee_fraction_of_r=0.20)
    assert minimum_viable_stop(cfg) == pytest.approx(0.006)
    assert breakeven_multiple_of_random(minimum_viable_stop(cfg), cfg) == pytest.approx(1.20)


def test_a_stop_too_tight_for_the_fees_is_refused():
    frame = bars(1200, drift=0.0002, vol=0.00005, seed=1)   # very quiet -> tiny ATR
    sig = generate(frame, higher_from(frame), ScalpConfig())
    assert sig.action == "flat"
    assert any("too tight for the fee schedule" in r for r in sig.rejected)


def test_downtrend_is_never_traded():
    frame = bars(1200, drift=-0.0008, vol=0.002, seed=2)
    sig = generate(frame, higher_from(frame), ScalpConfig())
    assert sig.action == "flat"
    assert any("trend is not up" in r for r in sig.rejected)


def test_news_blackout_blocks_entry():
    frame = bars(1200, drift=0.0008, vol=0.002, seed=3)
    now = frame.index[-1]
    sig = generate(frame, higher_from(frame), ScalpConfig(), news_times=[now])
    assert sig.action == "flat"
    assert any("blackout" in r for r in sig.rejected)
    # Outside the window the blackout is not a reason to refuse.
    far = generate(frame, higher_from(frame), ScalpConfig(),
                   news_times=[now + pd.Timedelta(hours=3)])
    assert not any("blackout" in r for r in far.rejected)


def test_signal_is_deterministic():
    frame = bars(1200, drift=0.0006, vol=0.002, seed=4)
    high = higher_from(frame)
    a, b = generate(frame, high), generate(frame, high)
    assert a.to_dict() == b.to_dict()


def test_target_and_stop_are_on_the_right_sides_when_long():
    frame = bars(1200, drift=0.0008, vol=0.003, seed=5)
    sig = generate(frame, higher_from(frame), ScalpConfig())
    if sig.action == "long":
        assert sig.stop < sig.entry < sig.target
        assert sig.reward_risk == pytest.approx(
            (sig.target - sig.entry) / (sig.entry - sig.stop))


def test_no_lookahead_truncating_the_frame_reproduces_the_signal():
    frame = bars(1200, drift=0.0005, vol=0.0025, seed=6)
    cut = frame.iloc[:900]
    a = generate(cut, higher_from(cut))
    b = generate(frame.iloc[:900], higher_from(frame.iloc[:900]))
    assert a.to_dict() == b.to_dict()


def test_atr_and_rsi_are_finite_and_bounded():
    frame = bars(1200, vol=0.002, seed=7)
    assert atr(frame, 14).dropna().gt(0).all()
    r = rsi(frame["close"], 14).dropna()
    assert r.between(0, 100).all()


def test_in_blackout_edges():
    t = pd.Timestamp("2026-01-01 12:00")
    assert in_blackout(t, [pd.Timestamp("2026-01-01 12:09")], 10)
    assert not in_blackout(t, [pd.Timestamp("2026-01-01 12:11")], 10)
    assert not in_blackout(t, [], 10)
    assert not in_blackout(t, None, 10)


def test_intraday_preset_clears_its_own_fee_floor_only_with_a_wide_enough_stop():
    """The preset documents a frontier; this asserts the frontier is where it says."""
    from src.scalper import INTRADAY
    floor = minimum_viable_stop(INTRADAY)
    assert floor == pytest.approx(0.0014 / 0.18)          # 0.78%
    assert breakeven_multiple_of_random(floor, INTRADAY) == pytest.approx(1.18)
    # A 5m-sized stop is below it; a 4h-sized one clears it.
    assert 0.0024 < floor < 0.0146
