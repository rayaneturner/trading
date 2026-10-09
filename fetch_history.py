#!/usr/bin/env python3
"""Rebuild data/prices_daily.csv from a live exchange. Run this from a machine
with exchange access; public endpoints, no API key needed.

    python fetch_history.py --exchange kraken --assets BTC,ETH,SOL --since 2017-01-01
    python run_backtest.py && python run_validation.py    # re-validate with SOL in

Kraken's daily history is short for some pairs; if SOL comes back with fewer than
~1500 closes, try --exchange binance --quote USDT --page 1000.
"""
from __future__ import annotations

import argparse

from src import datafeed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exchange", default="kraken")
    ap.add_argument("--quote", default="USD")
    ap.add_argument("--assets", default="BTC,ETH,SOL")
    ap.add_argument("--since", default="2017-01-01")
    ap.add_argument("--page", type=int, default=720)
    ap.add_argument("--out", default=datafeed.LOCAL_CSV)
    args = ap.parse_args()

    assets = tuple(a.strip().upper() for a in args.assets.split(",") if a.strip())
    prices = datafeed.fetch_ccxt_history(assets, exchange=args.exchange, quote=args.quote,
                                         since=args.since, page=args.page)
    if prices.empty:
        print("no data returned — check the symbols exist on this venue")
        return 1

    datafeed.save_local(prices, args.out)
    print(f"wrote {args.out}")
    print(prices.notna().sum().to_string())
    print(f"range: {prices.index[0].date()} -> {prices.index[-1].date()}")
    short = [a for a in prices.columns if prices[a].notna().sum() < 1500]
    if short:
        print(f"\nshort history on {short}: the 200-day filter plus the 90-day momentum "
              "needs ~290 closes to produce a signal at all, and a validation run on "
              "fewer than ~1500 is too short to mean much. Try another venue.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
