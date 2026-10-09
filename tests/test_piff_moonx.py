"""Sizing, pinned to real MoonX fills.

The first test exists because the venue's `pipValue` field was misread as the
position's point value rather than the per-lot value, overstating the dollar
risk of every trade by 100x. Both executed round trips are encoded here so the
same mistake cannot pass again.
"""
import pytest

from src.piff import PiffSignal
from src.piff_moonx import (MIN_LOTS, lots_for_risk, plan_trade, point_value)


def test_point_value_matches_the_two_executed_round_trips():
    # 0.001 lot moved 11.4 points and paid 0.0399 USD.
    assert point_value(0.001) * 11.4 == pytest.approx(0.0399, abs=5e-4)
    # 0.01 lot moved 0.95 points and paid 0.03325 USD.
    assert point_value(0.01) * 0.95 == pytest.approx(0.03325, abs=5e-4)


def _short(stop_points=25.5, rr=4.0, entry=30935.0):
    return PiffSignal(action="short", entry_type="stop", entry=entry,
                      stop=entry + stop_points,
                      target=entry - rr * stop_points,
                      stop_points=stop_points, rr=rr)


def test_a_typical_piff_stop_is_a_few_percent_of_a_19_dollar_account():
    """The corrected arithmetic: 0.01 lot on a 25.5 point stop risks ~0.89 USD."""
    plan = plan_trade(_short(), equity=19.07, lots=0.01)
    assert plan.risk_usd == pytest.approx(0.893, abs=0.01)
    assert plan.risk_fraction == pytest.approx(0.0468, abs=0.002)
    assert plan.ok


def test_the_widest_logged_stop_also_fits():
    plan = plan_trade(_short(stop_points=44.8), equity=19.07, lots=0.01)
    assert plan.risk_fraction < 0.09
    assert plan.ok


def test_liquidation_is_far_beyond_any_piff_stop_at_the_minimum_size():
    plan = plan_trade(_short(), equity=19.07, lots=0.01)
    assert plan.liquidation_points > 500
    assert plan.stop_reachable


def test_a_stop_beyond_what_equity_absorbs_is_refused():
    """Oversize the position until the stop sits past the liquidation point."""
    plan = plan_trade(_short(stop_points=25.5), equity=19.07, lots=0.5)
    assert not plan.ok
    assert any("liquidation would come first" in r for r in plan.refusals)


def test_sizing_from_a_risk_fraction_rounds_down():
    """Rounding up would quietly exceed the risk the caller set."""
    lots = lots_for_risk(19.07 * 0.01, 25.5)
    assert lots == pytest.approx(0.002, abs=1e-9)
    assert point_value(lots) * 25.5 <= 19.07 * 0.01


def test_a_risk_too_small_for_the_lot_floor_is_named_as_such():
    plan = plan_trade(_short(), equity=19.07, risk_fraction=0.0001)
    assert not plan.ok
    assert any("below the" in r and "minimum" in r for r in plan.refusals)


def test_fees_in_r_do_not_depend_on_size():
    a = plan_trade(_short(), equity=1000.0, lots=0.001)
    b = plan_trade(_short(), equity=1000.0, lots=0.05)
    assert a.fees_in_r == pytest.approx(b.fees_in_r, rel=1e-9)
    assert a.fees_in_r == pytest.approx(0.243, abs=0.01)


def test_a_flat_signal_is_refused_rather_than_sized():
    assert not plan_trade(PiffSignal("flat"), equity=19.07, lots=0.01).ok
