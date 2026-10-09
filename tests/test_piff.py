"""The PIFF sequence, asserted step by step.

Each test builds the minimum price action that should or should not trigger,
so a failure names which link of the chain broke rather than just "no signal".
"""
import numpy as np
import pandas as pd
import pytest

from src.piff import (PiffConfig, find_fvg, find_fvgs, gap_is_dead, generate,
                      is_confirming, swing_highs, swing_lows)


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
    sb1  an earlier low at 22950 — the pool the trade will target
    sb2  back to the range
    sb3  the swing high at 23060 — the liquidity the move will take
    sb4  the swing low at 22980 — the level whose break shifts structure
    sb5  a pullback that sets no new extreme
    sb6  ONE bar sweeps 23060 and closes under 22980: sweep and structure shift
         on the same bar, and the displacement leaves an M1 gap at 23030-23040
    sb7  the retrace begins
    sb8  price trades back into the gap, pokes above it, and closes inside on a
         bearish engulfing bar — the trigger
    """
    rows = [[23000, 23005, 22995, 23000]] * 20 + [
        # sb1 (5-9) an EARLIER low at 22950 — the pool the trade targets. It has
        # to exist and sit beyond the structure level, or there is nothing left
        # to aim at once the break has taken 22980.
        [23000, 23002, 22980, 22985],
        [22985, 22990, 22960, 22965],
        [22965, 22970, 22950, 22955],
        [22955, 22975, 22952, 22972],
        [22972, 22990, 22970, 22988],
        # sb2 (10-14) back to the range, no new extreme
        [22988, 23000, 22986, 22998],
        [22998, 23005, 22996, 23002],
        [23002, 23006, 22998, 23000],
        [23000, 23004, 22997, 23001],
        [23001, 23005, 22999, 23000],
        # sb3 (15-19) the swing high at 23060
        [23000, 23020, 22998, 23018],
        [23018, 23040, 23016, 23038],
        [23038, 23060, 23036, 23055],
        [23055, 23058, 23045, 23050],
        [23050, 23052, 23046, 23050],
        # sb4 (20-24) the swing low at 22980
        [23050, 23050, 23030, 23032],
        [23032, 23034, 23010, 23012],
        [23012, 23014, 22990, 22992],
        [22992, 22994, 22980, 22985],
        [22985, 22992, 22982, 22990],
        # sb5 (25-29) pullback, no new extreme either side
        [22990, 23005, 22988, 23002],
        [23002, 23015, 23000, 23012],
        [23012, 23025, 23010, 23022],
        [23022, 23030, 23018, 23026],
        [23026, 23028, 23016, 23020],
        # sb6 (30-34) sweep + shift, and the gap the displacement leaves
        [23020, 23075, 23040, 23045],
        [23045, 23050, 23030, 23035],
        [23028, 23030, 22990, 22992],   # bar i: high 23030 < low 23040 two bars back
        [22992, 22995, 22965, 22970],
        [22970, 22975, 22960, 22965],
        # sb7 (35-39) the retrace
        [22965, 22985, 22963, 22982],
        [22982, 23000, 22980, 22998],
        [22998, 23012, 22996, 23010],
        [23010, 23014, 23005, 23012],
        [23012, 23015, 23010, 23014],
        # sb8 (40-44) into the gap, fake above, engulfing close inside
        [23014, 23022, 23012, 23020],
        [23020, 23030, 23018, 23028],
        [23028, 23036, 23026, 23034],
        [23034, 23042, 23032, 23036],
        [23036, 23042, 23032, 23033.5],
    ]
    return frame(rows, start="2026-03-26 13:45")


def _structure(entry):
    return entry.resample("5min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()


def _htf15(entry):
    """The M15 frame the target is read on.

    Resampled from the same M1 bars rather than fetched, so a test says in one
    place which wick it expects the target to find.
    """
    return entry.resample("15min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()


def _cfg(**kw):
    base = dict(min_bars=20, min_structure_bars=5, swing_k=1, fvg_min_points=1.0, min_rr=0.1,
                require_htf_bias=False, session_start_hour=None)
    base.update(kw)
    return PiffConfig(**base)


def test_full_short_sequence_fires_on_the_confirming_bar():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(),
                   target_bars=_htf15(entry))

    assert sig.action == "short"
    assert sig.entry_type == "stop"          # a confirming bar printed inside the gap
    assert sig.swept_level == 23060.0        # the high that held the liquidity
    assert sig.fvg == (23030.0, 23040.0)     # the FIRST M1 gap, at the origin of the leg
    assert sig.entry == 23032.0              # the low of the confirming bar
    assert sig.stop == 23044.0               # its high, plus the 2-point buffer
    assert sig.target == 22950.0             # the pool BEYOND the 22,980 break level
    assert sig.stop_points == 12.0
    assert round(sig.rr, 2) == 6.83
    assert not sig.rejected
    # And the venue's cost is a bounded fraction of the risk, on the real fee.
    assert sig.fee_fraction_of_r < PiffConfig.max_fee_fraction_of_r


def test_limit_mode_leans_on_the_swept_level_instead():
    """Same price action, the other entry the author uses: rest at the gap edge."""
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(entry_mode="limit"),
                   target_bars=_htf15(entry))

    assert sig.action == "short" and sig.entry_type == "limit"
    assert sig.entry == 23040.0              # the far edge of the gap
    assert sig.stop == 23062.0               # beyond the swept high, not the bar
    assert sig.stop_points == 22.0           # wider stop, lower R:R — the trade-off
    assert sig.rr < 6.0


def test_htf_bias_vetoes_the_wrong_direction():
    """A rising higher timeframe forbids the short, however clean the sequence."""
    entry = _piff_short_setup()
    up = pd.DataFrame(
        {"open": 1.0, "high": 1.0, "low": 1.0,
         "close": np.linspace(22000, 23500, 60), "volume": 1.0},
        index=pd.date_range("2026-03-24", periods=60, freq="1h"))
    cfg = _cfg(require_htf_bias=True, htf_fast=5, htf_slow=20)
    # The bias frame is hourly and carries no wick to aim at; the target frame
    # is passed separately, which is why the two are separate inputs.
    m15 = _htf15(entry)
    assert generate(entry, _structure(entry), up, cfg, target_bars=m15).action == "flat"

    down = up.assign(close=np.linspace(23500, 22000, 60))
    assert generate(entry, _structure(entry), down, cfg,
                    target_bars=m15).action == "short"


def test_flat_market_produces_nothing():
    entry = flat_bars(200)
    cfg = PiffConfig(min_bars=50, min_structure_bars=5, require_htf_bias=False,
                     session_start_hour=None)
    assert generate(entry, _structure(entry), None, cfg).action == "flat"


def test_session_filter_blocks_outside_hours():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None,
                   _cfg(session_start_hour=20, session_end_hour=21))
    assert sig.action == "flat"
    assert any("session" in r for r in sig.rejected)


def test_min_rr_rejects_a_setup_that_does_not_pay_enough():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(min_rr=8.0),
                   target_bars=_htf15(entry))
    assert sig.action == "flat"
    assert any("R:R" in r for r in sig.rejected)


def test_fee_budget_rejects_a_stop_too_tight_for_the_venue():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(max_fee_fraction_of_r=0.0001),
                   target_bars=_htf15(entry))
    assert sig.action == "flat"
    assert any("fees" in r for r in sig.rejected)


def test_signal_is_deterministic():
    entry = _piff_short_setup()
    structure, m15 = _structure(entry), _htf15(entry)
    assert generate(entry, structure, None, _cfg(), target_bars=m15).to_dict() == \
           generate(entry, structure, None, _cfg(), target_bars=m15).to_dict()


def test_no_lookahead_future_bars_do_not_change_the_past_decision():
    """Append bars after the decision point; the decision at that point must hold."""
    entry = _piff_short_setup()
    now = generate(entry, _structure(entry), None, _cfg(),
                   target_bars=_htf15(entry))

    future = pd.DataFrame(
        [[23033, 23035, 22900, 22905], [22905, 22910, 22850, 22860]],
        columns=["open", "high", "low", "close"],
        index=pd.date_range(entry.index[-1] + pd.Timedelta(minutes=1),
                            periods=2, freq="1min")).assign(volume=1.0)
    extended = pd.concat([entry, future])
    cut = extended.iloc[:len(entry)]
    assert generate(cut, _structure(cut), None, _cfg(),
                    target_bars=_htf15(cut)).to_dict() == now.to_dict()


# --- resting orders -------------------------------------------------------

def _piff_armed_setup():
    """The same sequence, cut BEFORE price returns to the gap.

    Dropping the last five bars of the full fixture leaves the sweep, the shift
    and the M1 gap in place while price is still below the zone, which is
    exactly the state a resting order is for.
    """
    return _piff_short_setup().iloc[:-5]


def test_pending_mode_arms_an_order_before_price_returns():
    entry = _piff_armed_setup()
    sig = generate(entry, _structure(entry), None, _cfg(), pending=True,
                   target_bars=_htf15(entry))

    assert sig.action == "short"
    assert sig.entry_type == "limit"
    assert sig.entry == 23040.0          # rests at the far edge of the gap
    assert sig.stop == 23062.0           # behind the swept high
    assert sig.target == 22950.0
    assert "awaiting the retrace" in " ".join(sig.reasons)


def test_a_gap_already_poked_into_is_still_live():
    """The fake. The author's sequence is a first poke, then the return.

    Treating any touch as invalidation threw away the setup the rule exists to
    find, which is the retest after the fake.
    """
    bars = frame([[10, 12, 9, 11], [13, 20, 12, 19], [21, 24, 18, 23],
                  [23, 24, 17, 22],        # pokes into the 12-18 gap
                  [22, 23, 19, 22]])       # back above it
    gap = find_fvg(bars, 0, 2, "long", min_points=2.0)
    assert gap == (12.0, 18.0, 2)
    assert not gap_is_dead(bars, gap, "long")


def test_a_gap_closed_through_is_dead():
    """A bullish gap is support until a bar CLOSES below it."""
    bars = frame([[10, 12, 9, 11], [13, 20, 12, 19], [21, 24, 18, 23],
                  [23, 24, 10, 11]])       # closes under the gap's low
    gap = find_fvg(bars, 0, 2, "long", min_points=2.0)
    assert gap_is_dead(bars, gap, "long")


def test_a_dead_gap_is_skipped_for_the_next_live_one():
    """The leg leaves several gaps; the first is not always the one in play."""
    bars = frame([[10, 12, 9, 11], [13, 20, 12, 19], [21, 24, 18, 23]])
    assert len(find_fvgs(bars, 0, 2, "long", min_points=2.0)) == 1


def test_the_two_modes_disagree_by_design_on_the_same_bars():
    """Immediate mode needs a confirming bar in the zone; pending mode forbids it."""
    armed = _piff_armed_setup()
    m15 = _htf15(armed)
    assert generate(armed, _structure(armed), None, _cfg(),
                    target_bars=m15).action == "flat"
    assert generate(armed, _structure(armed), None, _cfg(), pending=True,
                    target_bars=m15).action == "short"


def test_pending_mode_is_off_when_only_stop_entries_are_allowed():
    entry = _piff_armed_setup()
    sig = generate(entry, _structure(entry), None, _cfg(entry_mode="stop"), pending=True)
    assert sig.action == "flat"


def test_the_target_sits_beyond_the_structure_level_not_on_it():
    """Otherwise the two conditions contradict: structure breaks by closing past
    the level, so a target on that level is already taken when the setup forms.
    """
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(),
                   target_bars=_htf15(entry))
    assert sig.action == "short"
    # the shift was called on the swing low at 22,980; the target must be beyond it
    assert sig.target < 22980.0
    assert sig.rr > 1.0


def test_a_break_through_the_session_extreme_is_refused_by_default():
    """The author retired the synthetic target: every target is now a level the
    market put there, or there is no trade. This is the case that costs -- the
    break takes the session's own low and no wick is left to aim at."""
    entry = _piff_short_setup()
    # Strip the earlier 22,950 leg, so nothing sits beyond the 22,980 level.
    stripped = entry.iloc[25:]
    sig = generate(stripped, _structure(stripped), None, _cfg(),
                   target_bars=_htf15(stripped))
    assert sig.action == "flat"
    assert any("no M15 wick beyond" in w for w in sig.trace.values())


def test_the_synthetic_target_can_be_restored():
    """Setting fallback_rr back to 4.0 brings the retired behaviour back, so the
    cost of the author's choice stays measurable rather than unreachable."""
    stripped = _piff_short_setup().iloc[25:]
    sig = generate(stripped, _structure(stripped), None, _cfg(fallback_rr=4.0),
                   target_bars=_htf15(stripped))
    assert sig.action == "short"
    assert round(sig.rr, 2) == 4.0
    assert any("synthetic" in r for r in sig.reasons)


def test_the_target_is_read_on_the_m15_frame_not_the_structure_frame():
    """The rule names the M15 wick of the previous move. An M15 wick deeper than
    the M5 swing standing at the same place makes the two frames disagree, and
    the number says which one the target came from.
    """
    entry = _piff_short_setup()
    m15 = _htf15(entry).copy()
    m15.loc[m15.index[1], "low"] = 22900.0

    assert generate(entry, _structure(entry), None, _cfg(),
                    target_bars=m15).target == 22900.0
    assert generate(entry, _structure(entry), None, _cfg(target_frame="structure"),
                    target_bars=m15).target == 22950.0


def test_a_target_frame_too_short_to_carry_a_fractal_refuses():
    """Two M15 bars cannot hold a k=1 swing. Silently falling back to the M5
    swing there would report a target the named rule never chose."""
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(),
                   target_bars=_htf15(entry).iloc[:2])
    assert sig.action == "flat"
    assert any("no M15 wick beyond" in w for w in sig.trace.values())


def test_a_real_pool_still_wins_over_the_synthetic_one():
    entry = _piff_short_setup()
    sig = generate(entry, _structure(entry), None, _cfg(),
                   target_bars=_htf15(entry))
    assert sig.target == 22950.0
    assert any("pool" in r and "synthetic" not in r for r in sig.reasons)


def test_a_gap_carved_after_the_structure_break_is_found():
    """The window runs from the sweep to now, not to the break.

    The displacement that follows the break usually carves the zone that gets
    retested; cutting the window at the break hid it, and the engine reported
    every gap dead while a live one sat just under price.
    """
    base = _piff_short_setup()
    # Extend the move down, leaving a fresh bearish gap well after the shift.
    extra = pd.DataFrame(
        [[23030, 23032, 23020, 23022],
         [23022, 23024, 23000, 23002],
         [22998, 22999, 22980, 22982],   # high 22,999 < low 23,020 two bars back
         [22982, 22995, 22978, 22990],
         [22990, 22996, 22985, 22988]],
        columns=["open", "high", "low", "close"],
        index=pd.date_range(base.index[-1] + pd.Timedelta(minutes=1),
                            periods=5, freq="1min")).assign(volume=1.0)
    entry = pd.concat([base, extra])
    gaps = find_fvgs(entry, 2, len(entry) - 1, "short", 1.0)
    # the late gap exists and is found by a window that reaches the present
    assert any(g[2] >= len(base) for g in gaps)
