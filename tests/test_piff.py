"""The PIFF sequence, asserted step by step.

Each test builds the minimum price action that should or should not trigger,
so a failure names which link of the chain broke rather than just "no signal".
"""
import numpy as np
import pandas as pd
import pytest

from src.piff import (PiffConfig, find_fvg, generate, is_confirming, swing_highs,
                      swing_lows)


def frame(rows, start="2026-03-26 14:00", freq="1min"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1.0)


def flat_bars(n, price=23000.0, start="2026-03-26 14:00", freq="1min"):
    return frame([[price, price + 1, price - 1, price] for _ in range(n)], start, freq)


# --- building blocks -------------------------------------------------------

def test_swing_detection_finds_the_strict_extreme():
    bars = frame([[0, 5, 0, 1], [0, 7, 1, 2], [0, 9, 2, 3], [0, 6, 1, 2], [0, 4, 0, 1]])
    assert 2 in swing_highs(bars, 2)
    lows = frame([[0, 9, 5, 6], [0, 8, 3, 4], [0, 7, 1, 2], [0, 8, 4, 5], [0, 9, 6, 7]])
    assert 2 in swing_lows(lows, 2)


def test_swing_requires_a_unique_extreme():
    """A double top is not a swing: two bars share the high."""
    bars = frame([[0, 5, 0, 1], [0, 9, 1, 2], [0, 9, 2, 3], [0, 6, 1, 2], [0, 4, 0, 1]])
    assert len(swing_highs(bars, 2)) == 0


def test_bullish_fvg_is_a_gap_between_bar_one_and_bar_three():
    bars = frame([[10, 12, 9, 11], [13, 20, 12, 19], [21, 24, 18, 23]])
    gap = find_fvg(bars, 0, 2, "long", min_points=2.0)
    assert gap is not None and gap[0] == 12 and gap[1] == 18


def test_no_fvg_when_the_bars_overlap():
    bars = frame([[10, 15, 9, 11], [12, 16, 11, 14], [13, 18, 12, 17]])
    assert find_fvg(bars, 0, 2, "long", min_points=2.0) is None


def test_tiny_gaps_are_filtered_out():
    bars = frame([[10, 12, 9, 11], [13, 20, 12, 19], [21, 24, 12.5, 23]])
    assert find_fvg(bars, 0, 2, "long", min_points=2.0) is None


def test_confirming_candles():
    eng = frame([[10, 11, 9, 9.5], [9.4, 12, 9.3, 11.8]])
    assert is_confirming(eng, 1, "long") == "engulfing"
    pin = frame([[10, 11, 9, 10], [10, 10.2, 7, 9.9]])
    assert is_confirming(pin, 1, "long") == "pin"
    assert is_confirming(eng, 1, "short") is None


# --- the whole sequence ----------------------------------------------------

def _piff_short_setup():
    """The full PIFF sequence, bar by bar, on M1 (5 bars per structure bar).

    sb0  flat
    sb1  the swing high at 23060 — the liquidity the move will take
    sb2  the swing low at 22980 — the opposing structure, and the eventual target
    sb3  a pullback that sets no new extreme
    sb4  ONE bar sweeps 23060 and closes under 22980: sweep and structure shift
         on the same bar, and the displacement leaves an M1 gap at 23030-23040
    sb5  the retrace begins
    sb6  price trades back into the gap, pokes above it, and closes inside on a
         bearish engulfing bar — the trigger
    """
    rows = [[23000, 23005, 22995, 23000]] * 5 + [
        # sb1 (5-9) the swing high at 23060
        [23000, 23020, 22998, 23018],
        [23018, 23040, 23016, 23038],
        [23038, 23060, 23036, 23055],
        [23055, 23058, 23045, 23050],
        [23050, 23052, 23046, 23050],
        # sb2 (10-14) the swing low at 22980
        [23050, 23050, 23030, 23032],
        [23032, 23034, 23010, 23012],
        [23012, 23014, 22990, 22992],
        [22992, 22994, 22980, 22985],
        [22985, 22992, 22982, 22990],
        # sb3 (15-19) pullback, no new extreme either side
        [22990, 23005, 22988, 23002],
        [23002, 23015, 23000, 23012],
        [23012, 23025, 23010, 23022],
        [23022, 23030, 23018, 23026],
        [23026, 23028, 23016, 23020],
        # sb4 (20-24) sweep + shift, and the gap the displacement leaves
        [23020, 23075, 23040, 23045],
        [23045, 23050, 23030, 23035],
        [23028, 23030, 22990, 22992],   # bar i: high 23030 < low 23040 two bars back
        [22992, 22995, 22965, 22970],
        [22970, 22975, 22960, 22965],
        # sb5 (25-29) the retrace
        [22965, 22985, 22963, 22982],
        [22982, 23000, 22980, 22998],
        [22998, 23012, 22996, 23010],
        [23010, 23014, 23005, 23012],
        [23012, 23015, 23010, 23014],
        # sb6 (30-34) into the gap, fake above, engulfing close inside
        [23014, 23022, 23012, 23020],
        [23020, 23030, 23018, 23028],
        [23028, 23036, 23026, 23034],
        [23034, 23042, 23032, 23036],
        [23036, 23042, 23032, 23033.5],
    ]
    return frame(rows)


def _structure(entry):
    return entry.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()


def _cfg(**kw):
    base = dict(min_bars=20, swing_k=1, fvg_min_points=1.0, min_rr=0.1,
                require_htf_bias=False, session_start_hour=None)
    base.update(kw)
    return PiffConfig(**base)


def test_full_short_sequence_fires_on_the_confirming_bar():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg())

    assert sig.action == "short"
    assert sig.entry_type == "stop"          # a confirming bar printed inside the gap
    assert sig.swept_level == 23060.0        # the high that held the liquidity
    assert sig.fvg == (23030.0, 23040.0)     # the FIRST M1 gap, at the origin of the leg
    assert sig.entry == 23032.0              # the low of the confirming bar
    assert sig.stop == 23044.0               # its high, plus the 2-point buffer
    assert sig.target == 22980.0             # the swing low the previous leg left
    assert sig.stop_points == 12.0
    assert round(sig.rr, 2) == 4.33          # the author's own 4:1 profile
    assert not sig.rejected
    # And the venue's cost is a bounded fraction of the risk, on the real fee.
    assert sig.fee_fraction_of_r < PiffConfig.max_fee_fraction_of_r


def test_limit_mode_leans_on_the_swept_level_instead():
    """Same price action, the other entry the author uses: rest at the gap edge."""
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(entry_mode="limit"))

    assert sig.action == "short" and sig.entry_type == "limit"
    assert sig.entry == 23040.0              # the far edge of the gap
    assert sig.stop == 23062.0               # beyond the swept high, not the bar
    assert sig.stop_points == 22.0           # wider stop, lower R:R — the trade-off
    assert sig.rr < 4.0


def test_htf_bias_vetoes_the_wrong_direction():
    """A rising higher timeframe forbids the short, however clean the sequence."""
    entry = _piff_short_setup()
    up = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0,
         "close": np.linspace(22000, 23500, 60), "volume": 1.0},
        index=pd.date_range("2026-03-24", periods=60, freq="1h"))
    cfg = _cfg(require_htf_bias=True, htf_fast=5, htf_slow=20)
    assert generate(entry, _structure(entry), up, cfg).action == "flat"

    down = up.assign(close=np.linspace(23500, 22000, 60))
    assert generate(entry, _structure(entry), down, cfg).action == "short"


def test_flat_market_produces_nothing():
    entry = flat_bars(200)
    cfg = PiffConfig(min_bars=50, require_htf_bias=False, session_start_hour=None)
    assert generate(entry, _structure(entry), None, cfg).action == "flat"


def test_session_filter_blocks_outside_hours():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None,
                   _cfg(session_start_hour=20, session_end_hour=21))
    assert sig.action == "flat"
    assert any("session" in r for r in sig.rejected)


def test_min_rr_rejects_a_setup_that_does_not_pay_enough():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(min_rr=6.0))
    assert sig.action == "flat"
    assert any("R:R" in r for r in sig.rejected)


def test_fee_budget_rejects_a_stop_too_tight_for_the_venue():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(max_fee_fraction_of_r=0.0001))
    assert sig.action == "flat"
    assert any("fees" in r for r in sig.rejected)


def test_signal_is_deterministic():
    entry = _piff_short_setup()
    structure = _structure(entry)
    assert generate(entry, structure, None, _cfg()).to_dict() == \
           generate(entry, structure, None, _cfg()).to_dict()


def test_no_lookahead_future_bars_do_not_change_the_past_decision():
    """Append bars after the decision point; the decision at that point must hold."""
    entry = _piff_short_setup()
    now = generate(entry, _structure(entry), None, _cfg())

    future = pd.DataFrame(
        [[23033, 23035, 22900, 22905], [22905, 22910, 22850, 22860]],
        columns=["open", "high", "low", "close"],
        index=pd.date_range(entry.index[-1] + pd.Timedelta(minutes=1),
                            periods=2, freq="1min")).assign(volume=1.0)
    extended = pd.concat([entry, future])
    cut = extended.iloc[:len(entry)]
    assert generate(cut, _structure(cut), None, _cfg()).to_dict() == now.to_dict()
