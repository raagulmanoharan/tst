"""Projection maths, especially the decay model.

The equilibrium result is the one worth guarding: a portfolio built at rate B
against decay d settles at B/d, so a goal above that equilibrium is unreachable
at any horizon. Naive division hides this, which is exactly the mistake that
would cost two years.
"""

from __future__ import annotations

import math

import pytest

from fiftyk.economics import net_monthly_at, project, yield_capital_needed
from fiftyk.goal import Constraints, Goal

from .conftest import economics

GOAL = Goal()
CONSTRAINTS = Constraints()

#: 25 h/week x 52 weeks / 10 hours per listing = 130 listings a year.
BUILD_RATE = 130.0


def test_listings_needed_is_goal_over_earnings_per_listing():
    p = project(economics(), GOAL, CONSTRAINTS)
    assert p.listings_needed == pytest.approx(50_000 / (250 * 2))  # 100


def test_no_decay_is_linear():
    p = project(economics(), GOAL, CONSTRAINTS)
    expected = (100 / BUILD_RATE) * 12 + 1  # +1 month to first revenue
    assert p.months_to_goal == pytest.approx(expected, rel=1e-6)
    assert p.equilibrium_portfolio == math.inf
    assert p.reachable


def test_decay_follows_the_equilibrium_model_not_division():
    p = project(economics(annual_decay=0.30), GOAL, CONSTRAINTS)
    # t = -(1/d)·ln(1 - P·d/B)
    expected_years = -(1 / 0.30) * math.log(1 - (100 * 0.30 / BUILD_RATE))
    assert p.months_to_goal == pytest.approx(expected_years * 12 + 1, rel=1e-6)
    # Slower than the no-decay case, because ground is lost while building.
    assert p.months_to_goal > (100 / BUILD_RATE) * 12 + 1


def test_goal_above_equilibrium_is_unreachable_at_any_horizon():
    """The result that division would hide entirely."""
    p = project(economics(net_per_unit_inr=50.0, units_per_listing_per_month=1.0,
                          annual_decay=0.40), GOAL, CONSTRAINTS)
    assert p.listings_needed == 1000
    assert p.equilibrium_portfolio == pytest.approx(BUILD_RATE / 0.40)  # 325
    assert not p.reachable
    assert p.months_to_goal is None
    assert "never gets there" in " ".join(p.notes)


def test_maintenance_is_the_replacement_treadmill():
    """Holding a decaying portfolio steady costs hours forever."""
    p = project(economics(annual_decay=0.30), GOAL, CONSTRAINTS)
    # 100 listings x 30% = 30 replacements a year x 10h / 52 weeks
    assert p.maintenance_hours_per_week == pytest.approx(30 * 10 / 52)
    assert not p.hands_off  # 5.8 h/week exceeds the 5 h/week ceiling


def test_no_decay_means_genuinely_hands_off():
    p = project(economics(), GOAL, CONSTRAINTS)
    assert p.maintenance_hours_per_week == 0.0
    assert p.hands_off


def test_fixed_upkeep_counts_toward_the_ceiling():
    p = project(economics(fixed_upkeep_hours_per_week=6.0), GOAL, CONSTRAINTS)
    assert p.maintenance_hours_per_week == pytest.approx(6.0)
    assert not p.hands_off


def test_worthless_listing_is_unreachable_rather_than_dividing_by_zero():
    p = project(economics(net_per_unit_inr=0.0), GOAL, CONSTRAINTS)
    assert not p.reachable
    assert p.listings_needed == math.inf


def test_net_monthly_at_scales_linearly():
    assert net_monthly_at(economics(), 100) == pytest.approx(50_000)
    assert net_monthly_at(economics(), 50) == pytest.approx(25_000)


@pytest.mark.parametrize(
    "annual_yield,expected_capital",
    [(0.075, 8_000_000), (0.035, 17_142_857), (0.07, 8_571_428)],
)
def test_yield_routes_need_capital_two_orders_of_magnitude_above_the_ceiling(
    annual_yield, expected_capital
):
    """States plainly why every capital-yield route is closed at ₹1 lakh."""
    needed = yield_capital_needed(GOAL, annual_yield)
    assert needed == pytest.approx(expected_capital, rel=1e-3)
    assert needed > Constraints().capital_ceiling_inr * 50
