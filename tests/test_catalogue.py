"""The seeded catalogue, and the no-fabrication rule.

Guards the failure mode that matters most: a plausible-looking number with no
source behind it, silently driving a two-year decision.
"""

from __future__ import annotations

import pytest

from fiftyk.catalogue import seed
from fiftyk.feasibility import Verdict, assess
from fiftyk.goal import Profile
from fiftyk.provenance import Confidence, SampleBasis, Source

PROFILE = Profile.default()
CATALOGUE = seed()
BY_KEY = {o.key: o for o in CATALOGUE}


def test_catalogue_loads():
    assert len(CATALOGUE) >= 10
    assert len({o.key for o in CATALOGUE}) == len(CATALOGUE), "keys must be unique"


@pytest.mark.parametrize("opportunity", CATALOGUE, ids=lambda o: o.key)
def test_every_stated_figure_is_sourced(opportunity):
    """No fabrication: a value either has evidence behind it or does not exist."""
    for name, obs in opportunity.observations().items():
        if obs.confidence is Confidence.UNVERIFIED:
            assert obs.value is None, f"{opportunity.key}.{name} is unverified but carries a value"
        else:
            assert obs.value is not None
            if obs.source is not Source.OPERATOR:
                assert obs.evidence_url, f"{opportunity.key}.{name} has no source URL"


@pytest.mark.parametrize("opportunity", CATALOGUE, ids=lambda o: o.key)
def test_every_figure_declares_its_sample_basis(opportunity):
    """Survivor bias is only visible if the basis is recorded."""
    for name, obs in opportunity.observations().items():
        if obs.is_known:
            assert isinstance(obs.basis, SampleBasis)


def test_categories_the_research_closed_are_actually_blocked():
    """Regression guard on the findings that cost real research to establish."""
    for key in ("chrome_extension", "devtool_plugins", "figma_community", "steam_game"):
        verdict = assess(BY_KEY[key], PROFILE.goal, PROFILE.constraints).verdict
        assert verdict is Verdict.BLOCKED, f"{key} should be ruled out"


def test_routes_needing_promotion_are_blocked():
    """The operator's hardest constraint, applied consistently."""
    for key in ("gumroad", "steam_game", "productised_freelance"):
        a = assess(BY_KEY[key], PROFILE.goal, PROFILE.constraints)
        assert any(b.gate == "demand_mechanism" for b in a.blockers), key


def test_the_excluded_freelance_route_is_costed_rather_than_hidden():
    """Kept in the catalogue so the cost of excluding it stays visible."""
    freelance = BY_KEY["productised_freelance"]
    assert freelance.economics.net_per_unit_inr.is_known
    # A one-time build stops paying the month after delivery.
    assert freelance.economics.annual_decay.value == 1.0


def test_no_catalogue_entry_claims_a_median_it_does_not_have():
    """Every blog claiming a median for these platforms is fabricating one."""
    for opportunity in CATALOGUE:
        median = opportunity.economics.median_seller_net_monthly_inr
        if median.is_known:
            assert median.evidence_url or median.source is Source.OPERATOR
            assert median.basis is not SampleBasis.NOT_APPLICABLE, (
                f"{opportunity.key}: an earnings figure must declare what kind of sample it is"
            )


def test_nothing_is_viable_under_the_real_constraints():
    """Documents the actual finding, so a future change that 'fixes' it is noticed.

    Under ₹1 lakh capital, no promotion, no audience and a 5 h/week ceiling,
    nothing in the researched catalogue clears every gate. That is the result —
    and `fiftyk relax` exists precisely because of it.
    """
    verdicts = [assess(o, PROFILE.goal, PROFILE.constraints).verdict for o in CATALOGUE]
    assert Verdict.VIABLE not in verdicts
    assert Verdict.BLOCKED in verdicts
    assert Verdict.NEEDS_EVIDENCE in verdicts
