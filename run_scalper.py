#!/usr/bin/env python3
"""Intraday signal from local candle files, or from a live venue via ccxt.

    python run_scalper.py --csv-5m out/btc_5m.csv --csv-1h out/btc_1h.csv --symbol BTC
    python run_scalper.py --exchange kraken --symbol BTC --equity 21.85

Prints the decision as JSON. Placing the order is not this script's job: it
hands the sizing to src/leveraged_risk, which refuses anything outside the
envelope, and the result goes to an executor (ccxt) or to the MoonX MCP tools.
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from src.leveraged_risk import LeverageLimits, OrderRefused, size_position
from src.scalper import ScalpConfig, generate, minimum_viable_stop


def load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    time_col = next(c for c in frame.columns if c.lower() in ("t", "time", "date", "timestamp"))
    frame[time_col] = pd.to_datetime(frame[time_col])
    return frame.set_index(time_col).sort_index()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTC")
    ap.add_argument("--csv-5m")
    ap.add_argument("--csv-1h")
    ap.add_argument("--exchange", default=None)
    ap.add_argument("--quote", default="USD")
    ap.add_argument("--equity", type=float, default=None)
    ap.add_argument("--risk", type=float, default=1.50, help="USDT risked per trade")
    ap.add_argument("--max-leverage", type=float, default=12.0)
    ap.add_argument("--fee-per-side", type=float, default=0.0006)
    ap.add_argument("--news", default="", help="comma-separated ISO times to avoid")
    args = ap.parse_args()

    cfg = ScalpConfig(fee_per_side=args.fee_per_side)

    if args.csv_5m and args.csv_1h:
        fast, slow = load(args.csv_5m), load(args.csv_1h)
    elif args.exchange:
        import ccxt
        client = getattr(ccxt, args.exchange)({"enableRateLimit": True})

        def pull(tf, limit):
            raw = client.fetch_ohlcv(f"{args.symbol}/{args.quote}", timeframe=tf, limit=limit)
            idx = pd.to_datetime([r[0] for r in raw], unit="ms")
            return pd.DataFrame(raw, columns=["t", "open", "high", "low", "close", "volume"],
                                index=idx).drop(columns="t").iloc[:-1]
        fast, slow = pull("5m", 500), pull("1h", 300)
    else:
        print(json.dumps({"error": "give --csv-5m and --csv-1h, or --exchange"}))
        return 2

    news = [pd.Timestamp(t.strip()) for t in args.news.split(",") if t.strip()]
    signal = generate(fast, slow, cfg, symbol=args.symbol, news_times=news)

    report = {
        "as_of": str(fast.index[-1]),
        "last_price": float(fast["close"].iloc[-1]),
        "minimum_viable_stop_pct": round(minimum_viable_stop(cfg) * 100, 3),
        "signal": signal.to_dict(),
    }

    if signal.action == "long" and args.equity:
        daily_vol = fast["close"].pct_change().std() * (288 ** 0.5)
        limits = LeverageLimits(risk_per_trade=args.risk / args.equity,
                                max_leverage=args.max_leverage,
                                min_stop_sigma=0.0)   # the fee budget already gates the stop
        try:
            order = size_position(args.equity, signal.entry, signal.stop, "long",
                                  daily_vol, limits)
            report["order"] = order.to_dict()
            report["order"]["risk_usdt"] = round(args.risk, 2)
        except OrderRefused as exc:
            report["order_refused"] = str(exc)

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
