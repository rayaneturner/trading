"""The replay's own arithmetic, asserted against hand-built outcomes.

A backtest is only worth its pessimism, so the tests that matter here are the
ones that pin the pessimistic choice: the ambiguous bar, the unfilled order,
and the refusal to let a forming bar inform a decision.
"""
import pandas as pd
import pytest

from src.piff import PiffConfig
from src.piff_backtest import BacktestConfig, Trade, _resolve, replay, stats
from tests.test_piff import _htf15, _piff_short_setup


def _bars(rows, start="2026-03-26 15:00"):
    idx = pd.date_range(start, periods=len(rows), freq="1min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                        index=idx).assign(volume=1.0)


def _trade(**kw):
    base = dict(direction="short", signalled_at=pd.Timestamp("2026-03-26 15:00"),
                filled_at=None, entry=100.0, stop=110.0, target=60.0,
                stop_points=10.0, planned_rr=4.0, fee_r=0.02)
    base.update(kw)
    return Trade(**base)


# --- resolution ------------------------------------------------------------

def test_a_bar_that_touches_both_is_counted_as_a_loss():
    """M1 bars carry no tick order, so the ambiguity resolves against the trade.

    Reading it the other way turns every such bar into a 4R winner, which is
    the single largest way this file could flatter the rule.
    """
    bars = _bars([[100, 100, 100, 100],      # the fill
                  [100, 115, 55, 60]])       # stop AND target inside one bar
    t = _resolve(bars, 0, _trade(), BacktestConfig())
    assert t.outcome == "stop"
    assert t.r == pytest.approx(-1.02)


def test_the_target_pays_the_planned_multiple_net_of_fees():
    bars = _bars([[100, 100, 100, 100], [99, 99, 59, 60]])
    t = _resolve(bars, 0, _trade(), BacktestConfig())
    assert t.outcome == "target"
    assert t.r == pytest.approx(4.0 - 0.02)


def test_an_order_price_never_reaches_expires_without_a_loss():
    bars = _bars([[90, 92, 88, 90]] * 5)     # price never trades back to 100
    t = _resolve(bars, 0, _trade(), BacktestConfig(max_wait_bars=3))
    assert t.outcome == "unfilled"
    assert t.r == 0.0


def test_a_stop_reached_before_the_fill_is_an_expiry_not_a_loss():
    """The order was still resting. Charging it a loss invents a trade."""
    bars = _bars([[112, 115, 111, 113]] * 3)   # entirely beyond the 110 stop
    t = _resolve(bars, 0, _trade(), BacktestConfig())
    assert t.outcome == "unfilled" and t.r == 0.0


def test_a_short_does_not_expire_merely_because_its_stop_sits_above_price():
    """A short's stop is above the entry, which is above price. Testing the
    wrong side of it expired every short on its first bar, because any bar's
    low sits under a stop that is above price -- 115 signals, 0 fills.
    """
    bars = _bars([[95, 96, 94, 95],          # below the 100 entry, order rests
                  [96, 101, 95, 100],        # trades up to the entry: filled
                  [100, 100, 59, 60]])       # runs to the 60 target
    t = _resolve(bars, 0, _trade(), BacktestConfig())
    assert t.outcome == "target"
    assert t.filled_at == bars.index[1]


def test_a_trade_still_open_at_the_end_contributes_no_result():
    bars = _bars([[100, 100, 100, 100], [99, 101, 98, 99]])
    t = _resolve(bars, 0, _trade(), BacktestConfig(max_hold_bars=1))
    assert t.outcome == "open"
    assert t.r == 0.0


# --- statistics ------------------------------------------------------------

def test_stats_report_the_threshold_the_win_rate_has_to_beat():
    filled = ([_trade(outcome="target", r=3.98)] * 3
              + [_trade(outcome="stop", r=-1.02)] * 7)
    s = stats(filled)
    assert s["filled"] == 10
    assert s["win_rate"] == pytest.approx(0.30)
    # (1 + 0.02) / (1 + 4) = 0.204
    assert s["breakeven_rate"] == pytest.approx(0.204)
    assert s["win_rate_stderr"] == pytest.approx(0.14491, abs=1e-4)
    assert s["expectancy_r"] == pytest.approx((3 * 3.98 - 7 * 1.02) / 10)


def test_unfilled_orders_are_excluded_from_the_win_rate():
    s = stats([_trade(outcome="target", r=3.98), _trade(outcome="stop", r=-1.02),
               _trade(outcome="unfilled"), _trade(outcome="open")])
    assert s["signals"] == 4 and s["filled"] == 2
    assert s["win_rate"] == pytest.approx(0.5)
    assert s["unfilled"] == 1 and s["still_open"] == 1


def test_no_filled_trade_reports_nothing_rather_than_zero():
    """An empty sample has no win rate. Printing 0% would read as a measurement."""
    s = stats([_trade(outcome="unfilled")])
    assert s["filled"] == 0
    assert s["win_rate"] is None and s["breakeven_rate"] is None


def test_an_edge_inside_two_standard_errors_is_flagged_as_unmeasured():
    s = stats([_trade(outcome="target", r=3.98)] * 3 + [_trade(outcome="stop", r=-1.02)] * 7)
    assert abs(s["edge_sigma"]) < 2


# --- the replay end to end -------------------------------------------------

def test_the_replay_takes_the_fixture_setup_and_resolves_it():
    m1 = _piff_short_setup()
    # The fixture ends on the confirming bar, so the trade needs bars after it
    # to resolve against: price runs to the 22,950 target.
    after = pd.DataFrame(
        [[23033, 23035, 23020, 23022], [23022, 23024, 22990, 22995],
         [22995, 22996, 22940, 22945]],
        columns=["open", "high", "low", "close"],
        index=pd.date_range(m1.index[-1] + pd.Timedelta(minutes=1), periods=3,
                            freq="1min")).assign(volume=1.0)
    bars = pd.concat([m1, after])

    cfg = BacktestConfig(
        lookback=200, warmup=len(m1) - 1, max_wait_bars=5,
        strategy=PiffConfig(min_bars=20, min_structure_bars=5, swing_k=1,
                            fvg_min_points=1.0, min_rr=0.1,
                            require_htf_bias=False, session_start_hour=None))
    out = replay(bars, _htf15(bars), cfg)
    assert out["stats"]["signals"] >= 1
    assert out["trades"][0].direction == "short"
    assert out["trades"][0].target == 22950.0


def test_the_replay_refuses_a_flat_market_and_says_so_with_zeroes():
    flat = _bars([[100, 101, 99, 100]] * 300)
    cfg = BacktestConfig(lookback=200, warmup=120,
                         strategy=PiffConfig(min_bars=50, min_structure_bars=5,
                                             require_htf_bias=False,
                                             session_start_hour=None))
    out = replay(flat, None, cfg)
    assert out["stats"]["signals"] == 0
    assert out["stats"]["win_rate"] is None


def test_the_decision_never_sees_the_forming_bar():
    """The slice handed to the engine ends at the previous bar.

    A live M5 close repaints -- measured on the real feed the 14:30 bar showed
    30,863.3 at 14:30 and 30,851.8 at 14:32, on either side of the threshold --
    so a replay that reads the current bar measures a rule nobody can trade.
    """
    m1 = _piff_short_setup()
    cfg = BacktestConfig(lookback=200, warmup=len(m1) - 1, max_wait_bars=2,
                         strategy=PiffConfig(min_bars=20, min_structure_bars=5,
                                             swing_k=1, fvg_min_points=1.0,
                                             min_rr=0.1, require_htf_bias=False,
                                             session_start_hour=None))
    out = replay(m1, _htf15(m1), cfg)
    for t in out["trades"]:
        assert t.signalled_at < m1.index[-1] or t.signalled_at == m1.index[-2]
