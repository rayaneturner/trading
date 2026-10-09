"""Run the PIFF loop against MoonX.

    export MOONX_MCP_TOKEN=...            # never on the command line
    python run_watch.py                   # dry run: decides, sends nothing
    python run_watch.py --live            # sends orders
    python run_watch.py --once            # one pass, then exit

Dry run is the default and `--live` is a deliberate choice, because the engine
applies the rule correctly but has never been shown to make money.
"""
import argparse
import json
import logging
import os
import signal
import time

from src.moonx_client import MoonXClient, MoonXError
from src.piff import PiffConfig
from src.piff_watch import WatchConfig, WatchState, step

_stop = False


def _on_signal(*_):
    global _stop
    _stop = True
    logging.getLogger("piff").info("stopping after this pass")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="actually send orders")
    ap.add_argument("--once", action="store_true", help="a single pass")
    ap.add_argument("--pair", default="NAS100")
    ap.add_argument("--risk", type=float, default=2.0, help="USD risked per trade")
    ap.add_argument("--min-rr", type=float, default=2.0)
    ap.add_argument("--structure", default="5min")
    ap.add_argument("--poll", type=int, default=60, help="seconds between passes")
    ap.add_argument("--daily-stop", type=float, default=0.05)
    ap.add_argument("--log", default="piff.log")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(args.log), logging.StreamHandler()])
    log = logging.getLogger("piff")

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    cfg = WatchConfig(
        pair=args.pair, risk_usd=args.risk, structure_rule=args.structure,
        poll_seconds=args.poll, live=args.live, daily_loss_stop=args.daily_stop,
        strategy=PiffConfig(min_rr=args.min_rr, require_htf_bias=False,
                            session_start_hour=None))
    state = WatchState()
    client = MoonXClient()

    log.info("PIFF on %s, risk %.2f USD/trade, %s, polling %ds",
             cfg.pair, cfg.risk_usd, "LIVE" if cfg.live else "DRY RUN",
             cfg.poll_seconds)
    if not cfg.live:
        log.info("dry run: decisions are logged, no order is sent")

    quiet = None
    while not _stop:
        try:
            out = step(client, cfg, state)
            # Collapse repeats: a flat market would otherwise fill the log with
            # one identical line a minute and bury the lines that matter.
            key = (out.get("action"), out.get("why"))
            if out["action"] in ("sent", "would_send") or key != quiet:
                log.info(json.dumps(out, default=str))
                quiet = key
        except MoonXError as exc:
            log.error("venue: %s", exc)
        except Exception:
            log.exception("pass failed, continuing")
        if args.once:
            break
        for _ in range(cfg.poll_seconds):
            if _stop:
                break
            time.sleep(1)
    log.info("stopped")


if __name__ == "__main__":
    main()
