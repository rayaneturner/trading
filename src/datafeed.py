"""Price data loading.

Two sources:
  * `load_local` / `fetch_coinmetrics` -> daily USD closes, used for research.
  * `fetch_ccxt`                       -> live exchange data, used in production.

The research source (Coin Metrics community data) is free and survivorship-bias
free for BTC/ETH, but it publishes *no price series for SOL* (market cap only),
and it lags the live market by weeks. Never trade off it.
"""
from __future__ import annotations

import csv
import io
import os

import pandas as pd

CM_URL = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/{}.csv"
CM_SLUG = {"BTC": "btc", "ETH": "eth", "SOL": "sol"}
PRICE_COLS = ("PriceUSD", "ReferenceRateUSD", "ReferenceRate")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
LOCAL_CSV = os.path.join(DATA_DIR, "prices_daily.csv")


def fetch_coinmetrics(assets=("BTC", "ETH", "SOL")) -> pd.DataFrame:
    """Daily USD closes from the Coin Metrics community dataset."""
    import requests

    series = {}
    for asset in assets:
        slug = CM_SLUG.get(asset, asset.lower())
        resp = requests.get(CM_URL.format(slug), timeout=300)
        resp.raise_for_status()
        rows = {}
        for row in csv.DictReader(io.StringIO(resp.text)):
            price = next((row[c] for c in PRICE_COLS if row.get(c)), None)
            if price:
                rows[row["time"][:10]] = float(price)
        if rows:
            series[asset] = pd.Series(rows)
    frame = pd.DataFrame(series)
    frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


def save_local(prices: pd.DataFrame, path: str = LOCAL_CSV) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = prices.copy()
    out.index.name = "date"
    out.to_csv(path)


def load_local(path: str = LOCAL_CSV) -> pd.DataFrame:
    prices = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    return prices.astype(float)


def fetch_ccxt(assets=("BTC", "ETH", "SOL"), exchange="kraken", quote="USD",
               timeframe="1d", limit=1500) -> pd.DataFrame:
    """Daily closes from a live exchange via ccxt. Public endpoints, no API key.

    The last candle is the *current, unfinished* day: drop it before computing
    signals, or the signal will repaint intraday.
    """
    import ccxt

    client = getattr(ccxt, exchange)({"enableRateLimit": True})
    series = {}
    for asset in assets:
        ohlcv = client.fetch_ohlcv(f"{asset}/{quote}", timeframe=timeframe, limit=limit)
        idx = pd.to_datetime([bar[0] for bar in ohlcv], unit="ms", utc=True).tz_localize(None)
        series[asset] = pd.Series([bar[4] for bar in ohlcv], index=idx.normalize())
    frame = pd.DataFrame(series).sort_index()
    return frame


def fetch_ccxt_history(assets=("BTC", "ETH", "SOL"), exchange="kraken", quote="USD",
                       timeframe="1d", since="2017-01-01", page=720) -> pd.DataFrame:
    """Full daily history from a live exchange, paginated.

    `fetch_ccxt` takes one page and is enough for signals; this walks back to
    `since` and is what you run once to build the research CSV. Venues cap a page
    at a few hundred to a few thousand candles (Kraken 720, Binance 1000), so the
    page size is a parameter rather than a constant.

    The final row is today's unfinished candle and is dropped: leaving it in makes
    the last signal repaint intraday.
    """
    import ccxt

    client = getattr(ccxt, exchange)({"enableRateLimit": True})
    start_ms = int(pd.Timestamp(since).timestamp() * 1000)
    day_ms = 86_400_000

    series = {}
    for asset in assets:
        symbol = f"{asset}/{quote}"
        bars, cursor = [], start_ms
        while True:
            batch = client.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=page)
            if not batch:
                break
            # A venue that ignores `since` returns the same window forever.
            fresh = [b for b in batch if b[0] >= cursor]
            if not fresh:
                break
            bars.extend(fresh)
            next_cursor = fresh[-1][0] + day_ms
            if next_cursor <= cursor or fresh[-1][0] >= pd.Timestamp.now("UTC").value // 10**6:
                break
            cursor = next_cursor

        if not bars:
            continue
        dedup = {bar[0]: bar[4] for bar in bars}
        idx = pd.to_datetime(sorted(dedup), unit="ms", utc=True).tz_localize(None).normalize()
        series[asset] = pd.Series([dedup[k] for k in sorted(dedup)], index=idx)

    frame = pd.DataFrame(series).sort_index()
    return frame.iloc[:-1] if len(frame) else frame


def clean(prices: pd.DataFrame, min_history: int = 260) -> pd.DataFrame:
    """Forward-fill single-day gaps, drop assets with too little history.

    Repeated identical closes at the tail of a vendor file are stale publishing,
    not a flat market: they are left in place (they only mute the signal) but
    `stale_tail` reports them so the caller can refuse to trade.
    """
    out = prices.sort_index().ffill(limit=2)
    keep = [c for c in out.columns if out[c].notna().sum() >= min_history]
    return out[keep]


def stale_tail(prices: pd.DataFrame) -> dict:
    """Number of trailing days with an unchanged close, per asset."""
    result = {}
    for col in prices.columns:
        s = prices[col].dropna()
        n = 0
        for i in range(len(s) - 1, 0, -1):
            if s.iloc[i] == s.iloc[i - 1]:
                n += 1
            else:
                break
        result[col] = n
    return result
