"""Does a fixed stop / take-profit setup have an edge? Measured, not argued.

This exists because a venue's marketing (and most trading content) presents
"SL 2%, TP 1:3, 20x" as if the reward:risk ratio were itself the edge. It is not.
Under a driftless random walk the probability of touching +3R before -1R is
exactly 1/(1+3) = 25%, which makes a 1:3 setup break even *before* costs. The
entire edge has to come from entry timing, so timing is what this measures.

Two modelling choices decide the answer, and getting either wrong flatters the
result by a wide margin:

  * **Where the stop is checked.** Checking only at the daily close understates
    stop-outs enormously: on a 3.6% daily vol, a 2% stop sits at 0.56 sigma and
    the intraday path crosses it on most days. Close-only checking turns a 26%
    win rate into 38%. This module reconstructs an intraday path as a Brownian
    bridge pinned to the real daily closes, with intraday noise scaled to the
    realised daily vol, and checks barriers along it.
  * **Overlapping trades.** Entering every day while holding for several days
    produces correlated trades. The naive standard error over-states precision,
    so the reported error is also adjusted for the average holding period.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BarrierResult:
    trades: int
    win_rate: float
    gross_R: float
    net_R: float
    avg_hold_days: float
    stderr_R: float

    def to_dict(self) -> dict:
        return {"trades": self.trades, "win_rate": round(self.win_rate, 1),
                "gross_R": round(self.gross_R, 3), "net_R": round(self.net_R, 3),
                "avg_hold_days": round(self.avg_hold_days, 2),
                "stderr_R": round(self.stderr_R, 3)}


def brownian_bridge_path(closes: pd.Series, steps: int = 24, seed: int = 0) -> np.ndarray:
    """Intraday path pinned to the real closes. Not real intraday data: an
    honest stand-in that restores the order of magnitude of the intraday range."""
    rng = np.random.default_rng(seed)
    logp = np.log(closes.to_numpy())
    sigma = np.diff(logp).std()
    path = [logp[0]]
    for day in range(1, len(logp)):
        a, b = logp[day - 1], logp[day]
        t = np.arange(1, steps + 1) / steps
        walk = rng.standard_normal(steps).cumsum() / np.sqrt(steps)
        bridge = walk - t * walk[-1]
        path.extend((a + t * (b - a) + sigma * bridge).tolist())
    return np.exp(np.array(path))


def barrier_study(closes: pd.Series, tp: float = 0.06, sl: float = 0.02,
                  entry_filter: np.ndarray | None = None, steps: int = 24,
                  seeds: int = 5, max_days: int = 60,
                  fee_per_side: float = 0.0005, funding_per_day: float = 0.0003
                  ) -> BarrierResult:
    """Long at each permitted close, exit at the first barrier touched intraday.

    Costs are expressed in R: with a stop at `sl` of notional, 1R = sl of notional,
    so a fee of f on notional costs f/sl in R.
    """
    pnl_all, hold_all = [], []
    for seed in range(seeds):
        path = brownian_bridge_path(closes, steps=steps, seed=seed)
        for day in range(len(closes) - 1):
            if entry_filter is not None and not entry_filter[day]:
                continue
            entry = path[day * steps]
            segment = path[day * steps + 1: min((day + max_days) * steps, len(path))]
            if segment.size == 0:
                continue
            rel = segment / entry - 1.0
            hit_tp = int(np.argmax(rel >= tp)) if (rel >= tp).any() else None
            hit_sl = int(np.argmax(rel <= -sl)) if (rel <= -sl).any() else None
            if hit_sl is not None and (hit_tp is None or hit_sl < hit_tp):
                pnl_all.append(-1.0)
                hold_all.append((hit_sl + 1) / steps)
            elif hit_tp is not None:
                pnl_all.append(tp / sl)
                hold_all.append((hit_tp + 1) / steps)
            else:
                pnl_all.append(rel[-1] / sl)
                hold_all.append(len(segment) / steps)

    pnl = np.array(pnl_all)
    hold = np.array(hold_all)
    if pnl.size == 0:
        return BarrierResult(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    avg_hold = float(hold.mean())
    cost_R = (2 * fee_per_side) / sl + (funding_per_day * avg_hold) / sl
    per_draw = pnl.size / seeds
    # Overlapping entries: an independent observation is roughly one holding period.
    n_eff = max(per_draw / max(avg_hold, 1.0), 1.0)
    return BarrierResult(
        trades=int(per_draw),
        win_rate=float((pnl > 0).mean() * 100),
        gross_R=float(pnl.mean()),
        net_R=float(pnl.mean() - cost_R),
        avg_hold_days=avg_hold,
        stderr_R=float(pnl.std() / np.sqrt(n_eff)),
    )


def breakeven_win_rate(tp: float, sl: float) -> float:
    """Win rate a fixed R:R needs to break even, and the random-walk baseline.

    Both are the same number: a driftless walk touches +tp before -sl with
    probability sl/(tp+sl), which is exactly the break-even rate. That identity
    is why reward:risk alone is never an edge.
    """
    return sl / (tp + sl) * 100
