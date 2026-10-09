import numpy as np
import pandas as pd

from src import backtest
from src.config import StrategyConfig
from src.risk_rules import per_asset_daily_risk, run_with_daily_stop

CFG = StrategyConfig(assets=("A",), ema_fast=5, ema_slow=10, sma_long=20,
                     mom_lookback=10, vol_halflife=5)


def smooth_uptrend(n=500):
    idx = pd.date_range("2020-01-06", periods=n, freq="D")
    return pd.DataFrame({"A": 100 * np.exp(np.cumsum(np.full(n, 0.002)))}, index=idx)


def test_stop_is_inert_when_no_day_breaches_it():
    prices = smooth_uptrend()
    base = backtest.run(prices, CFG)
    stopped = run_with_daily_stop(prices, CFG, max_daily_loss=0.05)
    assert stopped["stats"]["stop_triggers"] == 0
    np.testing.assert_allclose(stopped["returns"].to_numpy(),
                               base["returns"].to_numpy(), atol=1e-12)


def test_stop_flattens_after_a_breach_and_stays_flat_until_resume():
    prices = smooth_uptrend(400)
    # One violent down day deep in the uptrend, while fully invested.
    prices.iloc[300:] = prices.iloc[300:] * 0.80
    res = run_with_daily_stop(prices, CFG, max_daily_loss=0.05, resume="5")
    assert res["stats"]["stop_triggers"] >= 1
    breach = res["triggers"][0]["date"]
    after = res["weights"].loc[breach:].head(5)
    assert after.sum(axis=1).max() == 0.0


def test_one_sigma_risk_is_weight_times_daily_vol():
    prices = smooth_uptrend()
    frame = per_asset_daily_risk(prices, CFG)
    expected = frame["weight"] * frame["daily_vol_pct"]
    np.testing.assert_allclose(frame["one_sigma_risk_pct_of_capital"].to_numpy(),
                               expected.to_numpy(), rtol=1e-9)
