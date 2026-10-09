import numpy as np
import pandas as pd

from src import backtest
from src.config import StrategyConfig
from src.execution import ExecutionLimits, plan_orders


def prices_frame(n=900, drift=0.002, vol=0.04, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2019-01-01", periods=n, freq="D")
    data = {}
    for i, name in enumerate(("A", "B")):
        data[name] = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.DataFrame(data, index=idx)


CFG = StrategyConfig(assets=("A", "B"), ema_fast=5, ema_slow=10, sma_long=20, mom_lookback=10,
                     vol_halflife=5)


def test_costs_only_reduce_returns():
    prices = prices_frame()
    free = backtest.run(prices, StrategyConfig(**{**CFG.to_dict(), "cost_per_side": 0.0}))
    paid = backtest.run(prices, StrategyConfig(**{**CFG.to_dict(), "cost_per_side": 0.005}))
    assert paid["stats"]["cagr"] < free["stats"]["cagr"]


def test_flat_market_produces_no_position_and_no_loss():
    idx = pd.date_range("2020-01-01", periods=600, freq="D")
    prices = pd.DataFrame({"A": np.full(600, 100.0), "B": np.full(600, 50.0)}, index=idx)
    res = backtest.run(prices, CFG)
    assert res["weights"].to_numpy().max() == 0.0
    assert abs(res["equity"].iloc[-1] - 1.0) < 1e-12


def test_downtrend_keeps_us_flat_and_preserves_capital():
    n = 700
    idx = pd.date_range("2020-01-01", periods=n, freq="D")
    path = 100 * np.exp(np.cumsum(np.full(n, -0.004)))
    prices = pd.DataFrame({"A": path, "B": path * 0.5}, index=idx)
    res = backtest.run(prices, CFG)
    assert res["equity"].iloc[-1] > 0.9          # we did not ride it down
    assert res["stats"]["max_dd"] > -0.25


def test_execution_lag_shifts_exposure():
    prices = prices_frame()
    fast = backtest.run(prices, StrategyConfig(**{**CFG.to_dict(), "exec_lag_days": 1}))
    slow = backtest.run(prices, StrategyConfig(**{**CFG.to_dict(), "exec_lag_days": 5}))
    assert not np.allclose(fast["returns"].to_numpy(), slow["returns"].to_numpy())


def test_plan_orders_respects_band_and_cash():
    target = pd.Series({"A": 0.5, "B": 0.0})
    limits = ExecutionLimits(no_trade_band=0.05, max_order_notional=1e9)
    orders, diag = plan_orders(target, {"A": 0.0, "B": 1.0}, {"A": 100.0, "B": 100.0},
                               cash=900.0, limits=limits)
    by_symbol = {o.symbol: o for o in orders}
    assert by_symbol["B"].side == "sell"                      # full exit happens
    assert by_symbol["A"].side == "buy"
    assert diag["equity"] == 1000.0
    assert sum(o.notional for o in orders if o.side == "buy") <= 900.0 + 1e-9


def test_plan_orders_skips_tiny_drift():
    target = pd.Series({"A": 0.51})
    limits = ExecutionLimits(no_trade_band=0.05)
    orders, _ = plan_orders(target, {"A": 5.0}, {"A": 100.0}, cash=500.0, limits=limits)
    assert orders == []


def test_turnover_cap_drops_buys_but_keeps_sells():
    target = pd.Series({"A": 0.6, "B": 0.0})
    limits = ExecutionLimits(no_trade_band=0.01, max_turnover_fraction=0.2,
                             max_order_notional=1e9)
    orders, diag = plan_orders(target, {"A": 0.0, "B": 5.0}, {"A": 100.0, "B": 100.0},
                               cash=500.0, limits=limits)
    assert [o.side for o in orders] == ["sell"]
    assert diag["warning"] is not None


class _FakeExchange:
    """Paginating venue stub: 720 daily candles per page, honours `since`."""

    def __init__(self, n_days=2000, start="2020-04-10"):
        self.start = pd.Timestamp(start)
        self.n_days = n_days
        self.calls = 0

    def fetch_ohlcv(self, symbol, timeframe="1d", since=None, limit=720):
        self.calls += 1
        base = int(self.start.timestamp() * 1000)
        day = 86_400_000
        all_bars = [[base + i * day, 1, 1, 1, 100.0 + i, 0] for i in range(self.n_days)]
        bars = [b for b in all_bars if since is None or b[0] >= since]
        return bars[:limit]


def test_paginated_history_walks_back_and_dedupes(monkeypatch):
    import sys, types
    from src import datafeed

    fake = _FakeExchange()
    module = types.SimpleNamespace(kraken=lambda *a, **k: fake)
    monkeypatch.setitem(sys.modules, "ccxt", module)

    frame = datafeed.fetch_ccxt_history(("BTC",), exchange="kraken", since="2020-04-10")
    assert frame.index.is_monotonic_increasing
    assert not frame.index.has_duplicates
    assert len(frame) == fake.n_days - 1          # today's unfinished candle dropped
    assert fake.calls >= 3                        # 2000 days at 720 per page
