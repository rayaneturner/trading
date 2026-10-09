"""Evaluate the order-block strategy from saved candle payloads.

    python run_orderblock.py --htf h1.json --ltf m15.json --pair H1
    python run_orderblock.py --htf m30.json --ltf m5.json --pair M30 --indices

The payloads are whatever MoonX's get_candles returned, saved verbatim. Keeping
the download out of this script makes the decision a pure function of files on
disk, so the same input always gives the same signal.
"""
import argparse
import json

from src.orderblock import PAIRS, PAIRS_INDICES, generate
from src.piff_live import parse_candles, resample


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--htf", required=True, help="analysis-timeframe payload")
    ap.add_argument("--ltf", required=True, help="power-timeframe payload")
    ap.add_argument("--htf-interval", default="1h")
    ap.add_argument("--ltf-interval", default="15m")
    ap.add_argument("--pair", default="H1", choices=list(PAIRS))
    ap.add_argument("--indices", action="store_true",
                    help="use the indices fee schedule (0.010%% per side)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    table = PAIRS_INDICES if args.indices else PAIRS
    _, cfg = table[args.pair]

    htf = parse_candles(open(args.htf).read(), args.htf_interval,
                        min_bars=cfg.min_htf_bars)
    ltf = parse_candles(open(args.ltf).read(), args.ltf_interval,
                        min_bars=cfg.min_ltf_bars)
    sig = generate(htf, ltf, cfg)

    if args.json:
        print(json.dumps(sig.to_dict(), indent=2))
        return

    print(f"analyse {args.pair} ({len(htf)} barres, derniere {htf.index[-1]})")
    print(f"confirm {args.ltf_interval} ({len(ltf)} barres, derniere {ltf.index[-1]}, "
          f"close {ltf['close'].iloc[-1]:,.2f})")
    print(f"\n{sig.action.upper()}")
    if sig.action != "flat":
        print(f"  entree {sig.entry:,.2f}   SL {sig.stop:,.2f} "
              f"({sig.stop_points:,.2f} = {sig.stop_pct * 100:.4f}%)   "
              f"TP {sig.target:,.2f}")
        print(f"  R:R {sig.rr:.2f}   frais {sig.fee_fraction_of_r:.3f}R   "
              f"zone {sig.zone[0]:,.2f}-{sig.zone[1]:,.2f}   confirmation {sig.confirm}")
    for r in sig.reasons:
        print(f"  + {r}")
    for r in sig.rejected:
        print(f"  - {r}")


if __name__ == "__main__":
    main()
