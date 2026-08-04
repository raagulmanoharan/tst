"""Elimination gates.

The failure this project exists to prevent is a tool that recommends things the
operator cannot act on. Each gate has a test, and each blocker must carry the
arithmetic that produced it.
"""

from __future__ import annotations

from fiftyk.feasibility import MEDIAN_OUTPERFORMANCE_LIMIT, Verdict, assess, rank
from fiftyk.goal import Constraints, DemandMechanism, Exclusion, Goal
from fiftyk.models import Assumption
from fiftyk.provenance import SampleBasis

from .conftest import economics, opportunity

GOAL = Goal()
CONSTRAINTS = Constraints()


def test_a_clean_opportunity_is_viable():
    a = assess(opportunity(), GOAL, CONSTRAINTS)
    assert a.verdict is Verdict.VIABLE
    assert not a.blockers


def test_outbound_sales_is_blocked_by_the_no_chasing_rule():
    a = assess(
        opportunity(mechanism=DemandMechanism.OUTBOUND_SALES), GOAL, CONSTRAINTS
    )
    assert a.verdict is Verdict.BLOCKED
    assert any(b.gate == "demand_mechanism" for b in a.blockers)


def test_personal_audience_is_blocked():
    a = assess(
        opportunity(mechanism=DemandMechanism.PERSONAL_AUDIENCE), GOAL, CONSTRAINTS
    )
    assert a.verdict is Verdict.BLOCKED


def test_marketplace_search_is_allowed():
    assert CONSTRAINTS.allows(DemandMechanism.MARKETPLACE_SEARCH)
    assert CONSTRAINTS.allows(DemandMechanism.APP_STORE_SEARCH)
    assert not CONSTRAINTS.allows(DemandMechanism.OUTBOUND_SALES)


def test_capital_block_shows_the_shortfall():
    a = assess(opportunity(capital_required_inr=1_500_000.0), GOAL, CONSTRAINTS)
    blocker = next(b for b in a.blockers if b.gate == "capital")
    assert "1,500,000" in blocker.arithmetic
    assert "15.0x over" in blocker.arithmetic


def test_zero_median_is_a_hard_block_not_a_missing_value():
    """A documented zero is the strongest evidence available, not an absence."""
    a = assess(opportunity(median_seller_net_monthly_inr=0.0), GOAL, CONSTRAINTS)
    assert a.verdict is Verdict.BLOCKED
    assert any(b.gate == "median_outcome" for b in a.blockers)


def test_goal_far_above_the_median_is_a_lottery_ticket():
    a = assess(opportunity(median_seller_net_monthly_inr=6_000.0), GOAL, CONSTRAINTS)
    blocker = next(b for b in a.blockers if b.gate == "median_outcome")
    assert "8x the median" in blocker.arithmetic


def test_goal_within_reach_of_the_median_passes():
    a = assess(
        opportunity(median_seller_net_monthly_inr=GOAL.net_monthly_inr / (MEDIAN_OUTPERFORMANCE_LIMIT - 1)),
        GOAL,
        CONSTRAINTS,
    )
    assert not any(b.gate == "median_outcome" for b in a.blockers)


def test_disproven_fatal_assumption_blocks_outright():
    opp = opportunity()
    opp.assumptions.append(
        Assumption(
            claim="an Indian creator can be paid at all",
            why_it_matters="hard stop",
            fatal_if_false=True,
            resolved=False,
        )
    )
    a = assess(opp, GOAL, CONSTRAINTS)
    assert a.verdict is Verdict.BLOCKED
    assert any(b.gate == "disproven_assumption" for b in a.blockers)


def test_unreachable_portfolio_is_blocked_with_the_equilibrium_shown():
    a = assess(
        opportunity(net_per_unit_inr=50.0, units_per_listing_per_month=1.0, annual_decay=0.40),
        GOAL,
        CONSTRAINTS,
    )
    blocker = next(b for b in a.blockers if b.gate == "reachability")
    assert "settles at" in blocker.arithmetic


def test_treadmill_fails_the_passivity_gate():
    a = assess(opportunity(annual_decay=0.30), GOAL, CONSTRAINTS)
    blocker = next(b for b in a.blockers if b.gate == "passivity")
    assert "forever" in blocker.arithmetic


def test_missing_evidence_separates_research_from_your_own_estimate():
    """Two different problems needing two different actions."""
    a = assess(
        opportunity(units_per_listing_per_month=None, build_hours_per_listing=None),
        GOAL,
        CONSTRAINTS,
    )
    assert a.verdict is Verdict.NEEDS_EVIDENCE
    gates = {w.gate for w in a.warnings}
    assert "needs_research" in gates
    assert "needs_your_estimate" in gates


def test_mean_basis_is_flagged_as_overstating():
    opp = opportunity()
    opp.economics.median_seller_net_monthly_inr = opp.economics.median_seller_net_monthly_inr.model_copy(
        update={"basis": SampleBasis.MEAN}
    )
    a = assess(opp, GOAL, CONSTRAINTS)
    assert any("overstates" in w.reason for w in a.warnings)


def test_top_decile_evidence_downgrades_to_marginal():
    a = assess(
        opportunity(units_per_listing_per_month=2.0), GOAL, CONSTRAINTS
    )
    assert a.verdict is Verdict.VIABLE
    opp = opportunity()
    opp.economics.units_per_listing_per_month = opp.economics.units_per_listing_per_month.model_copy(
        update={"basis": SampleBasis.TOP_DECILE}
    )
    downgraded = assess(opp, GOAL, CONSTRAINTS)
    assert downgraded.verdict is Verdict.MARGINAL
    assert any(w.gate == "evidence_quality" for w in downgraded.warnings)


def test_ranking_prefers_the_cheaper_attention_price():
    cheap = assess(opportunity(key="cheap", build_hours_per_listing=5.0), GOAL, CONSTRAINTS)
    dear = assess(opportunity(key="dear", build_hours_per_listing=20.0), GOAL, CONSTRAINTS)
    ordered = rank([dear, cheap])
    assert [a.opportunity_key for a in ordered] == ["cheap", "dear"]


def test_relaxing_the_exclusion_unblocks_outbound():
    opp = opportunity(mechanism=DemandMechanism.OUTBOUND_SALES)
    assert assess(opp, GOAL, CONSTRAINTS).verdict is Verdict.BLOCKED

    relaxed = Constraints(exclusions=CONSTRAINTS.exclusions - {Exclusion.CHASING_DEMAND})
    assert assess(opp, GOAL, relaxed).verdict is not Verdict.BLOCKED
