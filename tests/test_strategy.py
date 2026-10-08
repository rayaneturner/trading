import numpy as np
import pandas as pd
import pytest

from src import backtest
from src.config import StrategyConfig
from src.strategy import apply_rebalance_schedule, realised_vol, target_weights, trend_score


def series(values, start="2020-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.DataFrame({"A": values}, index=idx)


CFG = StrategyConfig(assets=("A",), ema_fast=5, ema_slow=10, sma_long=20,
                     mom_lookback=10, vol_halflife=5, rebalance_weekday=None)


def test_trend_score_is_one_in_a_steady_uptrend():
    prices = series(np.linspace(100, 200, 120))
    assert trend_score(prices, CFG)["A"].iloc[-1] == pytest.approx(1.0)


def test_trend_score_is_zero_in_a_steady_downtrend():
    prices = series(np.linspace(200, 100, 120))
    assert trend_score(prices, CFG)["A"].iloc[-1] == pytest.approx(0.0)


def test_weights_never_exceed_caps():
    rng = np.random.default_rng(0)
    prices = series(100 * np.exp(np.cumsum(rng.normal(0.002, 0.04, 800))))
    w = target_weights(prices, CFG)
    assert w.max().max() <= CFG.max_weight_per_asset + 1e-12
    assert w.sum(axis=1).max() <= CFG.max_gross + 1e-12
    assert w.min().min() >= 0.0


def test_vol_is_floored():
    prices = series(np.full(200, 100.0) + np.arange(200) * 1e-9)
    assert realised_vol(prices, CFG)["A"].dropna().min() >= CFG.vol_floor - 1e-12


def test_no_lookahead_past_weights_are_immutable():
    rng = np.random.default_rng(1)
    prices = series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 500))))
    full = target_weights(prices, CFG)
    truncated = target_weights(prices.iloc[:400], CFG)
    pd.testing.assert_frame_equal(full.iloc[:400], truncated)


def test_band_blocks_small_moves_but_never_blocks_an_exit():
    idx = pd.date_range("2020-01-06", periods=4, freq="D")  # starts on a Monday
    cfg = StrategyConfig(assets=("A",), rebalance_weekday=None, no_trade_band=0.2)
    raw = pd.DataFrame({"A": [0.5, 0.55, 0.0, 0.1]}, index=idx)
    held = apply_rebalance_schedule(raw, cfg)["A"].tolist()
    assert held == [0.5, 0.5, 0.0, 0.0]


def test_weekly_schedule_only_trades_on_the_chosen_weekday():
    idx = pd.date_range("2020-01-06", periods=14, freq="D")
    cfg = StrategyConfig(assets=("A",), rebalance_weekday=0, no_trade_band=0.0)
    raw = pd.DataFrame({"A": np.linspace(0.1, 0.9, 14)}, index=idx)
    held = apply_rebalance_schedule(raw, cfg)["A"]
    assert held.nunique() == 2  # two Mondays in the window


def test_band_never_leaves_gross_above_the_cap():
    idx = pd.date_range("2020-01-06", periods=30, freq="D")
    cfg = StrategyConfig(assets=("A", "B"), rebalance_weekday=0, no_trade_band=0.05,
                         max_gross=1.0)
    raw = pd.DataFrame({"A": np.linspace(0.2, 0.9, 30),
                        "B": np.linspace(0.9, 0.2, 30)}, index=idx)
    held = apply_rebalance_schedule(raw, cfg)
    assert held.sum(axis=1).max() <= cfg.max_gross + 1e-12
