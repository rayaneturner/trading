#!/usr/bin/env python3
"""Measure the PIFF rule over M1 history from a CSV.

    python run_piff_backtest.py --m1 data/nas100_m1.csv

The CSV needs a timestamp column and open/high/low/close; volume is optional.
Pass --m15 to read the target frame from its own file instead of resampling it
from the M1 series, which is what the live loop does and reaches further back.

The numbers it prints are a measurement of this data, not a forecast. Read the
standard error and the break-even rate before reading the win rate.
"""
from __future__ import annotations

import argparse
import json

import pandas as pd

from src.piff import PiffConfig
from src.piff_backtest import BacktestConfig, replay


def load(path: str, tz: str | None) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    stamp = next((cols[k] for k in ("time", "timestamp", "date", "datetime", "open time")
                  if k in cols), None)
    if stamp is None:
        raise SystemExit(f"{path}: no timestamp column found among {list(df.columns)}")
    idx = pd.to_datetime(df[stamp], utc=False, errors="coerce",
                         unit="ms" if pd.api.types.is_numeric_dtype(df[stamp]) else None)
    if idx.isna().any():
        raise SystemExit(f"{path}: {int(idx.isna().sum())} timestamps did not parse")
    out = pd.DataFrame({k: pd.to_numeric(df[cols[k]], errors="coerce")
                        for k in ("open", "high", "low", "close") if k in cols})
    missing = {"open", "high", "low", "close"} - set(out.columns)
    if missing:
        raise SystemExit(f"{path}: missing {sorted(missing)}")
    out["volume"] = pd.to_numeric(df[cols["volume"]], errors="coerce") if "volume" in cols else 1.0
    out.index = idx
    out = out[~out.index.duplicated(keep="last")].sort_index().dropna(
        subset=["open", "high", "low", "close"])
    if tz:
        out.index = (out.index.tz_localize(tz).tz_convert("UTC").tz_localize(None)
                     if out.index.tz is None else out.index.tz_convert("UTC").tz_localize(None))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m1", required=True, help="CSV of M1 bars")
    ap.add_argument("--m15", default=None, help="CSV of M15 bars for the target frame")
    ap.add_argument("--tz", default=None, help="timezone the CSV stamps are in, e.g. America/New_York")
    ap.add_argument("--structure", default="5min")
    ap.add_argument("--mode", default="pending", choices=["pending", "immediate"])
    ap.add_argument("--min-rr", type=float, default=3.0)
    ap.add_argument("--fallback-rr", type=float, default=0.0,
                    help="4.0 restores the synthetic target the author retired")
    ap.add_argument("--target-frame", default="htf", choices=["htf", "structure"])
    ap.add_argument("--lookback", type=int, default=500)
    ap.add_argument("--trades-out", default=None, help="write the trade list as JSON")
    args = ap.parse_args()

    m1 = load(args.m1, args.tz)
    m15 = load(args.m15, args.tz) if args.m15 else None
    print(f"M1: {len(m1)} bars, {m1.index[0]} -> {m1.index[-1]}")
    if m15 is not None:
        print(f"M15: {len(m15)} bars, {m15.index[0]} -> {m15.index[-1]}")

    cfg = BacktestConfig(
        structure_rule=args.structure, pending=args.mode == "pending",
        lookback=args.lookback,
        strategy=PiffConfig(min_rr=args.min_rr, fallback_rr=args.fallback_rr,
                            target_frame=args.target_frame, require_htf_bias=False))
    out = replay(m1, m15, cfg)
    s = out["stats"]

    print("\n=== what the replay took ===")
    print(f"signals {s['signals']}   filled {s['filled']}   "
          f"unfilled {s['unfilled']}   still open {s['still_open']}")
    if not s["filled"]:
        print("\nNo trade filled. The rule refused this data, which is a result.")
        return

    print("\n=== measured ===")
    print(f"win rate        {s['win_rate']:.2%}  ± {s['win_rate_stderr']:.2%} (1 s.e.)")
    print(f"break-even rate {s['breakeven_rate']:.2%}  at mean R:R {s['mean_rr']:.2f} "
          f"and {s['mean_fee_r']:.3f}R of fees")
    print(f"expectancy      {s['expectancy_r']:+.3f} R per filled trade")
    print(f"total           {s['total_r']:+.1f} R over {s['filled']} trades")
    if s["edge_sigma"] is not None:
        print(f"distance from break-even: {s['edge_sigma']:+.2f} standard errors")
        if abs(s["edge_sigma"]) < 2:
            print("  -> under 2 s.e. this sample cannot separate an edge from noise")

    if args.trades_out:
        with open(args.trades_out, "w") as fh:
            json.dump([t.to_dict() for t in out["trades"]], fh, indent=2)
        print(f"\nwrote {args.trades_out}")


if __name__ == "__main__":
    main()
