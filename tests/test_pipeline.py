"""Provenance enforcement, the store, sensitivity and the model-vs-actual loop."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fiftyk.catalogue import seed
from fiftyk.dashboard import build_dashboard
from fiftyk.economics import net_monthly_at
from fiftyk.goal import Constraints, DemandMechanism, Exclusion, Goal, Profile
from fiftyk.models import DipCheck, MonthlyActual, Stage
from fiftyk.provenance import Confidence, Observation, SampleBasis, Source
from fiftyk.research import brief
from fiftyk.sensitivity import analyse
from fiftyk.validate import validate

from .conftest import economics, opportunity

PROFILE = Profile.default()


# -- provenance ---------------------------------------------------------


def test_a_figure_without_a_source_is_rejected():
    with pytest.raises(ValidationError, match="evidence_url"):
        Observation[float](
            value=100.0, source=Source.INDUSTRY_REPORT, method="a claim",
            confidence=Confidence.VERIFIED,
        )


def test_unverified_may_not_carry_a_value():
    with pytest.raises(ValidationError, match="must not carry a value"):
        Observation[float](
            value=100.0, source=Source.INDUSTRY_REPORT, method="a guess",
            confidence=Confidence.UNVERIFIED,
        )


@pytest.mark.parametrize("basis", [SampleBasis.TOP_DECILE, SampleBasis.ANECDOTE, SampleBasis.MEAN])
def test_winner_and_average_figures_are_not_planning_grade(basis):
    obs = Observation[float](
        value=10_000.0, source=Source.SELLER_REPORT, method="someone's blog post",
        confidence=Confidence.VERIFIED, basis=basis, evidence_url="https://x.test",
    )
    assert obs.is_known
    assert not obs.is_planning_grade


def test_median_and_aggregate_are_planning_grade():
    for basis in (SampleBasis.MEDIAN, SampleBasis.AGGREGATE):
        obs = Observation[float](
            value=100.0, source=Source.PLATFORM_DATA, method="platform disclosure",
            confidence=Confidence.VERIFIED, basis=basis, evidence_url="https://x.test",
        )
        assert obs.is_planning_grade


# -- store --------------------------------------------------------------


def test_store_roundtrips_with_evidence_intact(store):
    opp = opportunity()
    store.upsert(opp)
    loaded = store.get(opp.key)
    assert loaded is not None
    assert loaded.economics.net_per_unit_inr.value == 250.0
    assert loaded.economics.net_per_unit_inr.evidence_url


def test_verdict_history_is_appended_not_overwritten(store):
    store.log_verdict("k", "needs_evidence", "first look")
    store.log_verdict("k", "blocked", "median found, far too low")
    history = store.verdict_history("k")
    assert [h["verdict"] for h in history] == ["needs_evidence", "blocked"]


def test_total_net_sums_the_latest_month_of_live_ventures(store):
    for key, net in (("a", 3000.0), ("b", 2000.0)):
        opp = opportunity(key=key)
        opp.stage = Stage.LIVE
        opp.actuals = [
            MonthlyActual(month="2026-08", net_inr=1.0, hours_spent=1, listings_live=1),
            MonthlyActual(month="2026-09", net_inr=net, hours_spent=1, listings_live=1),
        ]
        store.upsert(opp)
    assert store.total_net_monthly() == 5000.0


# -- model vs actual ----------------------------------------------------


def test_model_and_reality_can_be_compared_directly():
    """The correction signal: when reality disagrees, the model is wrong."""
    econ = economics()
    assert net_monthly_at(econ, 10) == pytest.approx(5000)
    actual = 1200.0
    assert actual / net_monthly_at(econ, 10) == pytest.approx(0.24)


# -- dip checks ---------------------------------------------------------


def test_dip_check_requires_kill_criteria_up_front():
    with pytest.raises(ValidationError):
        DipCheck(tests_assumption="x", method="try it", time_box_hours=8, kill_criteria=[])


def test_riskiest_assumption_prefers_the_fatal_one():
    from fiftyk.models import Assumption

    opp = opportunity()
    opp.assumptions = [
        Assumption(claim="minor", why_it_matters="a little"),
        Assumption(claim="fatal", why_it_matters="a lot", fatal_if_false=True),
    ]
    assert opp.riskiest_open_assumption.claim == "fatal"


# -- sensitivity --------------------------------------------------------


def test_relaxing_the_demand_rule_opens_outbound_routes():
    blocked = opportunity(key="outbound", mechanism=DemandMechanism.OUTBOUND_SALES)
    results = analyse([blocked], PROFILE.goal, PROFILE.constraints)
    demand = next(r for r in results if "chasing demand" in r.label)
    assert "outbound" in demand.opportunities_opened


def test_relaxing_the_hours_ceiling_opens_treadmill_routes():
    treadmill = opportunity(key="treadmill", annual_decay=0.30)
    results = analyse([treadmill], PROFILE.goal, PROFILE.constraints)
    hours = next(r for r in results if "h/week at maturity" in r.label)
    assert "treadmill" in hours.opportunities_opened


def test_sensitivity_reports_nothing_when_a_block_is_structural():
    """A zero median is not a constraint problem — no relaxation fixes it."""
    dead = opportunity(key="dead", median_seller_net_monthly_inr=0.0)
    results = analyse([dead], PROFILE.goal, PROFILE.constraints)
    assert all(not r.is_worthwhile for r in results)


# -- research briefs ----------------------------------------------------


def test_brief_skips_blocked_opportunities():
    """No point researching something the block is structural on."""
    blocked = opportunity(key="blocked_one", mechanism=DemandMechanism.OUTBOUND_SALES,
                          units_per_listing_per_month=None)
    open_one = opportunity(key="open_one", units_per_listing_per_month=None)
    items = brief([blocked, open_one], PROFILE.goal, PROFILE.constraints)
    assert {i.opportunity_key for i in items} == {"open_one"}


def test_median_is_the_highest_priority_question():
    opp = opportunity(median_seller_net_monthly_inr=None, units_per_listing_per_month=None)
    items = brief([opp], PROFILE.goal, PROFILE.constraints)
    top = [i for i in items if i.priority == 1]
    assert any(i.field == "median_seller_net_monthly_inr" for i in top)


# -- validation and rendering -------------------------------------------


def test_the_seeded_catalogue_passes_validation(store):
    for opp in seed():
        store.upsert(opp)
    report = validate(store)
    assert report.ok, [f.detail for f in report.findings if f.kind == "missing_provenance"]
    assert report.checked == len(seed())


def test_validation_flags_figures_that_are_not_planning_grade(store):
    for opp in seed():
        store.upsert(opp)
    report = validate(store)
    assert report.unsafe_basis, "the catalogue contains a mean and an anecdote; both should be flagged"


def test_dashboard_renders_the_blocked_arithmetic(store, tmp_path):
    for opp in seed():
        store.upsert(opp)
    out = build_dashboard(store, PROFILE, tmp_path / "index.html")
    html = out.read_text()
    assert "Ruled out" in html
    assert "What to relax" in html
    assert "chrome_extension" in html


def test_goal_and_constraints_drive_everything():
    """Change the profile, change every verdict — the intended behaviour."""
    from fiftyk.feasibility import Verdict, assess

    opp = opportunity(median_seller_net_monthly_inr=6_000.0)
    assert assess(opp, Goal(), Constraints()).verdict is Verdict.BLOCKED
    modest = Goal(net_monthly_inr=20_000.0)
    assert assess(opp, modest, Constraints()).verdict is not Verdict.BLOCKED
