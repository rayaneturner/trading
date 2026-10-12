"""The zone geometry and the exit accounting. Everything else is data."""
import numpy as np
import pandas as pd

from src.bpr import BprConfig, backtest, find_zones


def frame(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="h", tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)


def drift(n, start=100.0, step=0.0):
    return [[start + i * step] * 4 for i in range(n)]


def test_a_bullish_gap_needs_the_low_above_the_high_two_bars_back():
    # bar 2's low sits above bar 0's high -> bullish gap [100, 102]
    rows = [[99, 100, 98, 99], [101, 105, 100, 104], [103, 106, 102, 105]]
    z = find_zones(frame(rows), BprConfig(min_ovl_atr=0.0))
    assert z == []          # one gap alone is not a balanced range


def test_two_opposite_overlapping_gaps_make_a_zone():
    rows = [
        [100, 101, 99, 100],      # 0
        [100, 101, 94, 95],       # 1  down leg
        [95, 97, 93, 96],         # 2  bearish gap: high 97 < low 99 -> [97, 99]
        [96, 99, 95, 98],         # 3
        [99, 101, 98, 100],       # 4  bullish gap: low 98 > high 97 -> [97, 98]
    ]
    z = find_zones(frame(rows), BprConfig(min_ovl_atr=0.0))
    assert len(z) == 1
    bar, top, bot, bull = z[0]
    assert bool(bull)                        # the newer gap is bullish
    assert (top, bot) == (98.0, 97.0)        # the overlap, not either gap


def test_an_overlap_thinner_than_the_floor_is_not_a_zone():
    rows = [
        [100, 101, 99, 100],
        [100, 101, 94, 95],
        [95, 97, 93, 96],
        [96, 99, 95, 98],
        [99, 101, 98, 100],
    ]
    assert find_zones(frame(rows), BprConfig(min_ovl_atr=10.0)) == []


def test_a_bar_that_hits_both_barriers_is_scored_as_a_loss():
    # one zone, then a bar that spans stop and target at once
    rows = [
        [100, 101, 99, 100],
        [100, 101, 94, 95],
        [95, 97, 93, 96],
        [96, 99, 95, 98],
        [99, 101, 98, 100],
        [100, 120, 80, 100],      # engulfs everything
        [100, 120, 80, 100],
    ]
    tr = backtest(frame(rows), BprConfig(min_ovl_atr=0.0, trigger="touch", entry_delay=0))
    assert tr and tr[0].outcome == "loss"
    assert tr[0].r_gross == -1.0


def test_fees_are_charged_in_units_of_risk():
    rows = [
        [100, 101, 99, 100],
        [100, 101, 94, 95],
        [95, 97, 93, 96],
        [96, 99, 95, 98],
        [99, 101, 98, 100],
        [100, 120, 80, 100],
        [100, 120, 80, 100],
    ]
    free = backtest(frame(rows), BprConfig(min_ovl_atr=0.0, trigger="touch", entry_delay=0))
    paid = backtest(frame(rows), BprConfig(min_ovl_atr=0.0, trigger="touch", entry_delay=0,
                                           fee_per_side=0.001))
    assert paid[0].fees_in_r > 0
    assert np.isclose(paid[0].r_net, free[0].r_gross - paid[0].fees_in_r)


def test_no_trade_is_opened_on_the_bar_that_creates_the_zone():
    rows = [
        [100, 101, 99, 100],
        [100, 101, 94, 95],
        [95, 97, 93, 96],
        [96, 99, 95, 98],
        [99, 101, 97, 100],       # this bar both creates the zone and touches it
        [100, 101, 99, 100],
    ]
    tr = backtest(frame(rows), BprConfig(min_ovl_atr=0.0, trigger="touch", entry_delay=1))
    assert all(t.entered > frame(rows).index[4] for t in tr)
