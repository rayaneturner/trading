import numpy as np
import pandas as pd

from src.barrier_study import barrier_study, breakeven_win_rate, brownian_bridge_path


def test_breakeven_matches_the_random_walk_hit_rate():
    assert breakeven_win_rate(0.06, 0.02) == 25.0
    assert breakeven_win_rate(0.02, 0.02) == 50.0


def test_bridge_is_pinned_to_the_real_closes():
    idx = pd.date_range("2020-01-01", periods=50, freq="D")
    rng = np.random.default_rng(0)
    closes = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.03, 50))), index=idx)
    path = brownian_bridge_path(closes, steps=24, seed=0)
    np.testing.assert_allclose(path[24::24], closes.to_numpy()[1:], rtol=1e-9)


def test_intraday_checking_is_never_kinder_than_close_only():
    """The whole point: a path that touches the stop cannot show a better win
    rate than one evaluated only at closes."""
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    rng = np.random.default_rng(1)
    closes = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.03, 400))), index=idx)
    fine = barrier_study(closes, tp=0.06, sl=0.02, seeds=2, steps=24)
    coarse = barrier_study(closes, tp=0.06, sl=0.02, seeds=2, steps=1)
    assert fine.win_rate <= coarse.win_rate


def test_costs_are_charged_in_R_units():
    idx = pd.date_range("2020-01-01", periods=300, freq="D")
    closes = pd.Series(np.linspace(100, 160, 300), index=idx)
    free = barrier_study(closes, seeds=1, fee_per_side=0.0, funding_per_day=0.0)
    paid = barrier_study(closes, seeds=1, fee_per_side=0.001, funding_per_day=0.0)
    assert paid.gross_R == free.gross_R
    assert paid.net_R < free.net_R
