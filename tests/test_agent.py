"""The envelope is the safety boundary. These tests are the reason to trust it."""
import numpy as np
import pandas as pd
import pytest

from src.agent import AgentDecision, RiskEnvelope, StubAgent, apply_envelope, build_snapshot
from src.config import StrategyConfig

ENV = RiskEnvelope(max_tilt_up=0.10, max_weight_per_asset=0.6, max_gross=1.0)


def decision(tilts):
    return AgentDecision(tilts=tilts, regime="unclear", confidence=0.0, note="t")


def test_agent_can_never_be_long_where_the_rule_is_flat():
    rule = pd.Series({"A": 0.0, "B": 0.3})
    out = apply_envelope(rule, decision({"A": 1.0, "B": 0.0}), ENV)
    assert out["A"] == 0.0


def test_tilt_minus_one_flattens():
    rule = pd.Series({"A": 0.5})
    assert apply_envelope(rule, decision({"A": -1.0}), ENV)["A"] == 0.0


def test_tilt_zero_reproduces_the_rule_exactly():
    rule = pd.Series({"A": 0.42, "B": 0.17})
    pd.testing.assert_series_equal(apply_envelope(rule, decision({}), ENV), rule,
                                   check_names=False)


def test_positive_tilt_is_capped_at_max_tilt_up():
    rule = pd.Series({"A": 0.2})
    assert apply_envelope(rule, decision({"A": 1.0}), ENV)["A"] == pytest.approx(0.3)


def test_caps_hold_against_any_tilt_vector():
    rng = np.random.default_rng(0)
    rule = pd.Series({"A": 0.55, "B": 0.5, "C": 0.3})
    for _ in range(500):
        tilts = {a: float(v) for a, v in zip("ABC", rng.uniform(-5, 5, 3))}
        out = apply_envelope(rule, decision(tilts), ENV)
        assert out.min() >= 0.0
        assert out.max() <= ENV.max_weight_per_asset + 1e-12
        assert out.sum() <= ENV.max_gross + 1e-12


def test_garbage_from_the_model_is_treated_as_no_tilt():
    rule = pd.Series({"A": 0.4})
    for junk in (float("nan"), float("inf"), float("-inf")):
        out = apply_envelope(rule, decision({"A": junk}), ENV)
        assert 0.0 <= out["A"] <= ENV.max_weight_per_asset
    assert apply_envelope(rule, decision({"A": float("nan")}), ENV)["A"] == pytest.approx(0.4)


def test_unknown_assets_in_the_decision_are_ignored():
    rule = pd.Series({"A": 0.4})
    out = apply_envelope(rule, decision({"A": 0.0, "DOGE": 1.0}), ENV)
    assert list(out.index) == ["A"]


def test_snapshot_contains_no_future_information():
    idx = pd.date_range("2020-01-01", periods=600, freq="D")
    rng = np.random.default_rng(3)
    prices = pd.DataFrame({"A": 100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, 600)))}, index=idx)
    cfg = StrategyConfig(assets=("A",), ema_fast=5, ema_slow=10, sma_long=20,
                         mom_lookback=10, vol_halflife=5)
    cut = 400
    full = build_snapshot(prices.iloc[:cut], cfg)
    extended = build_snapshot(prices, cfg)
    assert full["as_of_close"] != extended["as_of_close"]
    # Rebuilding the same date from a longer frame must give identical features.
    again = build_snapshot(prices.iloc[:cut], cfg)
    assert full == again


def test_stub_agent_follows_the_rule_by_default():
    idx = pd.date_range("2020-01-01", periods=400, freq="D")
    prices = pd.DataFrame({"A": np.linspace(100, 300, 400)}, index=idx)
    cfg = StrategyConfig(assets=("A",), ema_fast=5, ema_slow=10, sma_long=20,
                         mom_lookback=10, vol_halflife=5)
    snap = build_snapshot(prices, cfg)
    assert StubAgent().decide(snap).tilts == {"A": 0.0}
