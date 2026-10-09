"""The order block sequence, asserted step by step.

The author's description left one thing undefined — what an order block is —
and that definition decides every signal, so it is pinned here first.
"""
import numpy as np
import pandas as pd
import pytest

from src.orderblock import (OBConfig, OBSignal, average_range, find_order_blocks,
                            generate, zone_is_dead)


def frame(rows, start="2026-10-09 08:00", freq="1h"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                        index=idx).assign(volume=1.0)


# --- what an order block is ------------------------------------------------

def _bullish_ob_frame():
    """A down candle, then an impulsive leg that closes beyond a prior high."""
    rows = [[100, 102, 98, 101]] * 6
    rows += [[101, 108, 100, 107]]      # the swing high at 108
    rows += [[107, 107, 101, 102]]
    rows += [[102, 103, 97, 98]]        # <- the order block: last down candle
    rows += [[98, 112, 98, 111]]        # impulsive up, closes beyond 108
    rows += [[111, 113, 108, 110]]
    return frame(rows)


def test_a_bullish_block_is_the_last_down_candle_before_a_break():
    bars = _bullish_ob_frame()
    obs = find_order_blocks(bars, "long", OBConfig(displacement_atr=1.0, atr_window=6))
    assert obs, "the sequence should produce a block"
    assert obs[0]["idx"] == 8               # the down candle at index 8
    assert obs[0]["zone"] == (97.0, 103.0)  # its full range
    assert obs[0]["broke_level"] == 108.0


def test_a_down_candle_with_no_structure_break_is_not_a_block():
    """Without the break there is no evidence the level was defended."""
    rows = [[100, 102, 98, 101]] * 6
    rows += [[101, 108, 100, 107]]
    rows += [[107, 107, 101, 102]]
    rows += [[102, 103, 97, 98]]
    rows += [[98, 104, 98, 103]]       # up move, but never closes beyond 108
    rows += [[103, 105, 100, 104]]
    bars = frame(rows)
    assert find_order_blocks(bars, "long", OBConfig(displacement_atr=1.0,
                                                   atr_window=6)) == []


def test_a_move_too_small_to_be_impulsive_is_not_a_block():
    bars = _bullish_ob_frame()
    strict = OBConfig(displacement_atr=10.0, atr_window=6)
    assert find_order_blocks(bars, "long", strict) == []


def test_the_body_zone_is_narrower_than_the_range_zone():
    bars = _bullish_ob_frame()
    rng = find_order_blocks(bars, "long", OBConfig(displacement_atr=1.0, atr_window=6,
                                                   zone="range"))[0]["zone"]
    body = find_order_blocks(bars, "long", OBConfig(displacement_atr=1.0, atr_window=6,
                                                    zone="body"))[0]["zone"]
    assert body == (98.0, 102.0) and rng == (97.0, 103.0)
    assert body[1] - body[0] < rng[1] - rng[0]


# --- what kills a zone -----------------------------------------------------

def test_a_poke_into_the_zone_leaves_it_alive():
    """The poke IS the pullback the setup waits for."""
    bars = _bullish_ob_frame()
    extra = frame([[110, 111, 99, 109]],      # wicks into 97-103, closes above
                  start="2026-10-09 19:00")
    bars = pd.concat([bars, extra])
    assert not zone_is_dead(bars, 8, (97.0, 103.0), "long")


def test_a_close_through_the_zone_kills_it():
    bars = _bullish_ob_frame()
    extra = frame([[110, 111, 95, 96]], start="2026-10-09 19:00")
    bars = pd.concat([bars, extra])
    assert zone_is_dead(bars, 8, (97.0, 103.0), "long")


# --- the whole sequence ----------------------------------------------------

def _setup():
    """HTF block, pullback into it, confirming engulfing bar on the LTF."""
    htf = _bullish_ob_frame()
    # price drifts up, leaves a higher pool, then returns into the 97-103 block
    htf = pd.concat([htf, frame(
        [[110, 125, 109, 124],       # the pool the trade targets
         [124, 126, 118, 119],
         [119, 120, 104, 105],
         [105, 106, 99, 101]],       # back at the block
        start="2026-10-09 19:00")])
    ltf = frame(
        [[104, 105, 102, 103]] * 8
        + [[102, 103, 99, 99.5],     # down into the zone
           [99.4, 103, 99.2, 102.8]],  # engulfing: the confirmation
        start="2026-10-09 22:00", freq="15min")
    return htf, ltf


def _cfg(**kw):
    base = dict(displacement_atr=1.0, atr_window=6, min_htf_bars=10,
                min_ltf_bars=5, min_rr=1.0, max_fee_fraction_of_r=10.0,
                fee_per_side=0.0007)
    base.update(kw)
    return OBConfig(**base)


def test_the_full_sequence_fires():
    htf, ltf = _setup()
    sig = generate(htf, ltf, _cfg())
    assert sig.action == "long", sig.trace
    assert sig.confirm == "engulfing"
    assert sig.zone == (97.0, 103.0)
    assert sig.entry == pytest.approx(102.8)
    assert sig.stop < 99.0                 # beyond the bar before the confirmation
    assert sig.target == 126.0             # the most recent pool beyond the 108 break
    assert sig.rr > 1.0
    assert not sig.rejected


def test_the_stop_sits_beyond_the_candle_before_the_confirmation():
    htf, ltf = _setup()
    sig = generate(htf, ltf, _cfg())
    # the pre-confirmation bar's low is 99.0; the stop must clear it
    assert sig.stop < 99.0
    assert sig.stop_points == pytest.approx(abs(sig.entry - sig.stop))


def test_no_confirmation_means_no_trade():
    htf, ltf = _setup()
    quiet = ltf.copy()
    quiet.iloc[-1] = [102.8, 103.0, 102.6, 102.7, 1.0]   # no engulfing, no pin
    sig = generate(htf, quiet, _cfg())
    assert sig.action == "flat"
    assert any("no confirming bar" in w for w in sig.trace.values())


def test_price_outside_the_block_means_no_trade():
    htf, ltf = _setup()
    away = ltf.copy()
    away.iloc[-1] = [120, 121, 119, 120.5, 1.0]
    sig = generate(htf, away, _cfg())
    assert sig.action == "flat"


def test_a_stop_too_tight_for_the_venue_is_refused_with_the_number():
    """The scalping trap: fees are cost/stop and ignore the R:R entirely."""
    htf, ltf = _setup()
    sig = generate(htf, ltf, _cfg(max_fee_fraction_of_r=0.01))
    assert sig.action == "flat"
    assert any("of fees" in r for r in sig.rejected)
    assert sig.fee_fraction_of_r > 0.01


def test_an_rr_below_the_minimum_is_refused():
    htf, ltf = _setup()
    sig = generate(htf, ltf, _cfg(min_rr=99.0))
    assert sig.action == "flat"
    assert any("R:R" in r for r in sig.rejected)


def test_a_flat_market_produces_nothing_and_says_why():
    flat = frame([[100, 101, 99, 100]] * 80)
    ltf = frame([[100, 101, 99, 100]] * 40, freq="15min")
    sig = generate(flat, ltf, _cfg())
    assert sig.action == "flat"
    assert sig.rejected and sig.rejected[0]


def test_the_decision_is_deterministic():
    htf, ltf = _setup()
    assert generate(htf, ltf, _cfg()).to_dict() == generate(htf, ltf, _cfg()).to_dict()


def test_future_bars_do_not_change_the_past_decision():
    htf, ltf = _setup()
    now = generate(htf, ltf, _cfg())
    future = frame([[103, 130, 102, 129], [129, 131, 125, 126]],
                   start="2026-10-10 06:00", freq="15min")
    assert generate(htf, pd.concat([ltf, future]).iloc[:len(ltf)], _cfg()).to_dict() \
           == now.to_dict()
