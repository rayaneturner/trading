"""Produce one PIFF decision from saved MoonX candle payloads.

    python run_piff.py --m1 m1.json --htf h15.json [--structure 15min] [--json]

The payloads are whatever MoonX's get_candles returned, saved verbatim. Keeping
the download out of this script is deliberate: the decision is then a pure
function of a file on disk, so the same input always gives the same signal and
a disputed trade can be replayed exactly.
"""
import argparse
import json

from src.piff import PiffConfig
from src.piff_live import parse_candles, signal_from_m1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--m1", required=True, help="M1 candle payload (the FVG timeframe)")
    ap.add_argument("--htf", help="higher-timeframe payload for the bias")
    ap.add_argument("--htf-interval", default="15m")
    ap.add_argument("--structure", default="5min", help="pandas rule for the structure frame")
    ap.add_argument("--entry-mode", default="both", choices=["limit", "stop", "both"])
    ap.add_argument("--min-rr", type=float, default=3.0)
    ap.add_argument("--no-session", action="store_true", help="ignore the session window")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    m1 = parse_candles(open(args.m1).read(), "1m", min_bars=120)
    htf = parse_candles(open(args.htf).read(), args.htf_interval, min_bars=60) if args.htf else None

    cfg = PiffConfig(entry_mode=args.entry_mode, min_rr=args.min_rr,
                     require_htf_bias=htf is not None,
                     session_start_hour=None if args.no_session else 13)
    sig = signal_from_m1(m1, args.structure, htf, cfg)

    if args.json:
        print(json.dumps(sig.to_dict(), indent=2))
        return

    print(f"M1   {m1.index[0]} -> {m1.index[-1]}  ({len(m1)} bars, last close {m1['close'].iloc[-1]:,.2f})")
    if htf is not None:
        print(f"HTF  {htf.index[0]} -> {htf.index[-1]}  ({len(htf)} bars)")
    print(f"\n{sig.action.upper()}")
    if sig.action != "flat":
        print(f"  {sig.entry_type} entry {sig.entry:,.2f}   stop {sig.stop:,.2f} "
              f"({sig.stop_points:,.1f} pts)   target {sig.target:,.2f}")
        print(f"  R:R {sig.rr:.2f}   fees {sig.fee_fraction_of_r:.3f}R   "
              f"FVG {sig.fvg[0]:,.2f}-{sig.fvg[1]:,.2f}")
    for r in sig.reasons:
        print(f"  + {r}")
    for r in sig.rejected:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
