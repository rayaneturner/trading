"""The venue's candle payloads, and what has to be checked before trusting them.

These are not hypothetical cases. Asked for 500 NAS100 bars at "5m" and "15m",
MoonX returned a leading block whose timestamps are 60 seconds apart with
running-aggregate highs and lows, followed by a correctly spaced block. The
same rule read on those bars would invent sweeps and gaps, so the prefix has to
be found and dropped rather than used.
"""
import json

import pandas as pd
import pytest

from src.piff_live import CandleDataError, parse_candles, resample, signal_from_m1


def payload(times_ms, interval="5m", price=30000.0):
    return {"symbol": "NAS100", "interval": interval,
            "candles": [{"time": t, "open": price, "high": price + 5,
                         "low": price - 5, "close": price, "volume": 0}
                        for t in times_ms]}


def test_timestamps_become_a_utc_index():
    bars = parse_candles(payload([1791521640000 + 300000 * i for i in range(80)]),
                         min_bars=80)
    assert str(bars.index.tz) == "UTC"
    assert bars.index[0] == pd.Timestamp("2026-10-09 04:54:00", tz="UTC")
    assert list(bars.columns) == ["open", "high", "low", "close", "volume"]


def test_a_prefix_spaced_tighter_than_the_timeframe_is_dropped():
    """The real defect: 20 bars 60s apart, then 80 correctly spaced at 300s."""
    bad = [1791486180000 + 60000 * i for i in range(20)]
    good = [1791496800000 + 300000 * i for i in range(80)]
    bars = parse_candles(payload(bad + good), min_bars=80)
    assert len(bars) == 80
    assert bars.index[0] == pd.Timestamp(1791496800000, unit="ms", tz="UTC")


def test_a_gap_wider_than_the_timeframe_is_kept():
    """A market break is not corruption: the weekend has to survive the check."""
    friday = [1791486000000 + 300000 * i for i in range(60)]
    monday = [1791486000000 + 300000 * 60 + 86400000 * 2 + 300000 * i for i in range(60)]
    bars = parse_candles(payload(friday + monday), min_bars=120)
    assert len(bars) == 120


def test_too_few_usable_bars_is_an_error_not_a_short_frame():
    with pytest.raises(CandleDataError, match="usable"):
        parse_candles(payload([1791486180000 + 60000 * i for i in range(30)]), min_bars=20)


def test_a_high_below_its_low_is_refused():
    bad = payload([1791486000000 + 300000 * i for i in range(80)])
    bad["candles"][40]["high"] = bad["candles"][40]["low"] - 1
    with pytest.raises(CandleDataError, match="high below its low"):
        parse_candles(bad, min_bars=80)


def test_a_json_string_is_accepted():
    raw = json.dumps(payload([1791486000000 + 300000 * i for i in range(80)]))
    assert len(parse_candles(raw, min_bars=80)) == 80


def test_duplicate_timestamps_keep_the_last_quote():
    times = [1791486000000 + 300000 * i for i in range(80)]
    doubled = payload(times)
    doubled["candles"].append(dict(doubled["candles"][40], close=31234.0))
    bars = parse_candles(doubled, min_bars=80)
    assert len(bars) == 80
    assert bars["close"].iloc[40] == 31234.0


def test_the_structure_frame_is_derived_from_the_entry_frame():
    """M15 bars must be arithmetically consistent with the M1 bars under them."""
    times = [1791486000000 + 60000 * i for i in range(150)]
    m1 = parse_candles(payload(times, interval="1m"), min_bars=150)
    m15 = resample(m1, "15min")
    assert len(m15) == 10
    assert m15["high"].iloc[0] == m1["high"].iloc[:15].max()
    assert m15["low"].iloc[0] == m1["low"].iloc[:15].min()
    assert m15["close"].iloc[0] == m1["close"].iloc[14]


def test_a_flat_series_produces_a_flat_decision_with_a_stated_reason():
    times = [1791486000000 + 60000 * i for i in range(600)]
    m1 = parse_candles(payload(times, interval="1m"), min_bars=600)
    sig = signal_from_m1(m1, "15min")
    assert sig.action == "flat"
    assert sig.rejected and sig.rejected[0]
