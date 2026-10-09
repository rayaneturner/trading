"""Turn MoonX candle payloads into a PIFF decision.

Two reasons this is a module and not a few lines in a script.

First, the venue's candle endpoint is not trustworthy on its face. Asked for
500 NAS100 bars at "5m" it returned a block whose timestamps are 60 seconds
apart, with highs and lows that look like running aggregates, followed by a
block correctly spaced at 300 seconds. Feeding that to a structure rule would
invent sweeps and gaps that never happened, so every series is checked against
the spacing its own timeframe implies and the bad prefix is dropped rather than
silently used.

Second, PIFF reads three timeframes and only one of them has to come from the
venue. The structure frame is the M1 series resampled here, which makes the
M15 bars arithmetically consistent with the M1 bars the gap is found on — two
independent downloads are not.
"""
from __future__ import annotations

import json
from dataclasses import replace

import pandas as pd

from .piff import PiffConfig, PiffSignal, generate

INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600,
                    "2h": 7200, "4h": 14400, "1d": 86400}


class CandleDataError(RuntimeError):
    """The payload cannot be trusted as bars of the timeframe it claims."""


def parse_candles(payload: dict | str, expect_interval: str | None = None,
                  min_bars: int = 60) -> pd.DataFrame:
    """MoonX candles -> a UTC-indexed OHLCV frame, with the bad prefix removed.

    MoonX sends `time` in milliseconds. A bar whose gap to the next one is not
    the timeframe's own period is either a market break (weekends, the daily
    session gap) or corrupt aggregation. The two are told apart by direction:
    a gap LARGER than the period is a closed market and is kept, a gap SMALLER
    than the period means the series is not what it claims, and everything up
    to and including the last such bar is dropped.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)
    candles = payload["candles"] if "candles" in payload else payload
    if not candles:
        raise CandleDataError("empty payload")

    frame = pd.DataFrame(candles)
    frame.index = pd.to_datetime(frame.pop("time"), unit="ms", utc=True)
    frame = frame[["open", "high", "low", "close", "volume"]].astype(float)
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()

    interval = expect_interval or payload.get("interval")
    if interval in INTERVAL_SECONDS:
        period = INTERVAL_SECONDS[interval]
        deltas = frame.index.to_series().diff().dt.total_seconds()
        bad = deltas < period            # too close together: not these bars
        if bad.any():
            cut = int(bad.to_numpy().nonzero()[0].max()) + 1
            frame = frame.iloc[cut:]
    if len(frame) < min_bars:
        raise CandleDataError(
            f"only {len(frame)} usable {interval} bars after the integrity cut, "
            f"need {min_bars}")
    if not (frame["high"] >= frame["low"]).all():
        raise CandleDataError("a bar has a high below its low")
    return frame


def resample(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    return bars.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "volume": "sum"}).dropna()


def signal_from_m1(m1: pd.DataFrame, structure_rule: str = "15min",
                   htf: pd.DataFrame | None = None,
                   cfg: PiffConfig = PiffConfig()) -> PiffSignal:
    """The decision, from one M1 series plus an optional higher-timeframe frame.

    The structure frame is derived, not downloaded: the sweep and the shift then
    describe the same prices the M1 gap was found in.
    """
    structure = resample(m1, structure_rule)
    if htf is None:
        return generate(m1, structure, None, replace(cfg, require_htf_bias=False))
    return generate(m1, structure, htf, cfg)
