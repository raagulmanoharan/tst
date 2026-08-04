"""Qualification rules.

The scenarios here encode the research findings that shaped the scorer. The two
false positives it originally produced — a healthy site qualifying, and a
badly-rated business qualifying — are pinned as regression tests.
"""

from __future__ import annotations

from leadgen.discover.places import EphemeralPlace
from leadgen.score.rules import qualifies, score_lead
from leadgen.store.models import Lead

from .conftest import DOWN_SITE, make_ads, make_search, make_site


def lead(place_id: str, category: str = "dental", **kwargs) -> Lead:
    kwargs.setdefault("ads", make_ads())
    kwargs.setdefault("search", make_search())
    return Lead(place_id=place_id, city="Bangalore", category_probe=category, **kwargs)


def place(place_id: str, website: str | None, rating: float | None, reviews: int | None):
    return EphemeralPlace(
        place_id=place_id, display_name="Test Business", website_uri=website,
        rating=rating, user_rating_count=reviews,
    )


def test_no_website_alone_never_qualifies():
    """The filter that has been dead since 2016 — pinned so it stays dead."""
    score = score_lead(lead("place001"), place("place001", None, 4.6, 3))
    assert not qualifies(score)
    assert any("dead end" in d for d in score.disqualifiers)


def test_healthy_site_is_not_a_lead():
    """No problem to solve means no sale, however willing and active they are."""
    score = score_lead(
        lead("place002", site=make_site()), place("place002", "https://x.test", 4.5, 80)
    )
    assert score.will_spend >= 0.5 and score.will_engage >= 0.5
    assert score.needs_customers == 0.0
    assert not qualifies(score)
    assert any("nothing measurably wrong" in d for d in score.disqualifiers)


def test_badly_rated_business_is_vetoed_outright():
    """A good site cannot fix a bad business — the research says walk away."""
    score = score_lead(
        lead("place003", site=make_site(**DOWN_SITE)),
        place("place003", "https://x.test", 2.9, 40),
    )
    assert score.needs_customers == 1.0
    assert not qualifies(score)
    assert any("walk away" in d for d in score.disqualifiers)


def test_broken_site_plus_ad_spend_is_the_strongest_lead():
    score = score_lead(
        lead("place004", site=make_site(**DOWN_SITE), ads=make_ads(google=True)),
        place("place004", "https://x.test", 4.7, 120),
    )
    assert qualifies(score)
    assert score.axes_passed == 3
    assert any("already paying for ads" in r for r in score.reasons)


def test_dated_site_qualifies_on_accumulated_defects():
    score = score_lead(
        lead(
            "place005", category="architect",
            site=make_site(mobile_viewport=False, copyright_year=2019, load_seconds=7.4, has_contact_path=False),
        ),
        place("place005", "https://x.test", 4.4, 60),
    )
    assert qualifies(score)
    assert score.needs_customers >= 0.5


def test_parked_domain_maxes_the_need_axis():
    score = score_lead(
        lead("place006", site=make_site(parked_or_expired=True)),
        place("place006", "https://x.test", 4.2, 45),
    )
    assert score.needs_customers == 1.0
    assert qualifies(score)


def test_unverified_evidence_never_counts_against_a_lead():
    """Absence of evidence is not evidence of absence."""
    all_unknown = make_site(**{k: None for k in DOWN_SITE})
    score = score_lead(
        lead("place007", site=all_unknown), place("place007", "https://x.test", 4.5, 50)
    )
    assert score.needs_customers == 0.0
    assert not score.reasons or all("no website" not in r for r in score.reasons)


def test_score_cites_the_evidence_it_used():
    score = score_lead(
        lead("place008", site=make_site(mobile_viewport=False, load_seconds=9.0)),
        place("place008", "https://x.test", 4.4, 60),
    )
    assert "site.mobile_viewport" in score.evidence_used
    assert "site.load_seconds" in score.evidence_used


def test_rescoring_without_live_signals_does_not_resurrect_a_veto():
    """Rating lives only in live data — dropping it must not un-veto a lead."""
    subject = lead("place009", site=make_site(**DOWN_SITE))
    subject.score = score_lead(subject, place("place009", "https://x.test", 2.5, 40))
    assert not qualifies(subject.score)

    rescored = score_lead(subject, None)
    assert not qualifies(rescored)
    assert any("walk away" in d for d in rescored.disqualifiers)
