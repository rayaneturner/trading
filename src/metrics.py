"""Performance statistics. Daily returns in, dict out."""
from __future__ import annotations

import numpy as np
import pandas as pd

DAYS = 365.0


def drawdown(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def stats(rets: pd.Series, turnover: pd.Series | None = None) -> dict:
    rets = rets.dropna()
    if rets.empty:
        return {}
    equity = (1.0 + rets).cumprod()
    years = len(rets) / DAYS
    cagr = equity.iloc[-1] ** (1.0 / years) - 1.0 if years > 0 else np.nan
    vol = rets.std() * np.sqrt(DAYS)
    downside = rets[rets < 0].std() * np.sqrt(DAYS)
    max_dd = drawdown(equity).min()
    monthly = (1.0 + rets).resample("ME").prod() - 1.0
    out = {
        "start": str(rets.index[0].date()),
        "end": str(rets.index[-1].date()),
        "years": round(years, 2),
        "cagr": cagr,
        "vol": vol,
        "sharpe": cagr / vol if vol else np.nan,
        "sortino": cagr / downside if downside else np.nan,
        "max_dd": max_dd,
        "calmar": cagr / abs(max_dd) if max_dd else np.nan,
        "worst_month": monthly.min(),
        "pct_months_up": float((monthly > 0).mean()),
        "time_in_market": np.nan,
    }
    if turnover is not None:
        out["turnover_per_year"] = float(turnover.sum() / years)
    return out


def summary_table(results: dict) -> pd.DataFrame:
    frame = pd.DataFrame(results).T
    pct = ["cagr", "vol", "max_dd", "worst_month", "pct_months_up", "time_in_market"]
    for col in pct:
        if col in frame:
            frame[col] = (frame[col].astype(float) * 100).round(1)
    for col in ("sharpe", "sortino", "calmar", "turnover_per_year"):
        if col in frame:
            frame[col] = frame[col].astype(float).round(2)
    return frame
