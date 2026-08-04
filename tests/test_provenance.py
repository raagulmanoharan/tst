"""Nothing enters the tracker without provenance. See CLAUDE.md rule 2."""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError

from leadgen.store.models import Confidence, Lead, Observation, Source, utcnow


def test_claim_without_evidence_url_is_rejected():
    with pytest.raises(ValidationError, match="evidence_url"):
        Observation[int](
            value=404, source=Source.BUSINESS_SITE, method="HTTP GET",
            confidence=Confidence.VERIFIED,
        )


def test_confident_claim_without_a_value_is_rejected():
    with pytest.raises(ValidationError, match="unverified"):
        Observation[int](
            value=None, source=Source.BUSINESS_SITE, method="HTTP GET",
            confidence=Confidence.VERIFIED, evidence_url="https://x.test",
        )


def test_unverified_may_not_smuggle_in_a_value():
    """A guess with a disclaimer is still a guess."""
    with pytest.raises(ValidationError, match="must not carry a value"):
        Observation[int](
            value=7, source=Source.BUSINESS_SITE, method="HTTP GET",
            confidence=Confidence.UNVERIFIED,
        )


def test_operator_entry_needs_no_url():
    obs = Observation[bool](
        value=True, source=Source.OPERATOR, method="operator checked by hand",
        confidence=Confidence.VERIFIED,
    )
    assert obs.is_known


def test_unverified_is_a_usable_first_class_state():
    obs = Observation[int].unverified(Source.BUSINESS_SITE, "request timed out")
    assert obs.value is None
    assert not obs.is_known
    assert obs.confidence is Confidence.UNVERIFIED


def test_unverified_can_carry_a_url_for_a_human_to_check():
    obs = Observation[bool].unverified(
        Source.META_AD_LIBRARY, "no public API", evidence_url="https://adlib.test/q"
    )
    assert obs.evidence_url == "https://adlib.test/q"
    assert not obs.is_known


def test_method_must_actually_describe_something():
    with pytest.raises(ValidationError):
        Observation[int](
            value=1, source=Source.OPERATOR, method="x", confidence=Confidence.VERIFIED
        )


def test_staleness_is_measured_not_assumed():
    fresh = Observation[bool](
        value=True, source=Source.BUSINESS_SITE, method="HTTP GET",
        confidence=Confidence.VERIFIED, evidence_url="https://x.test",
    )
    assert not fresh.is_stale(timedelta(days=30))

    old = fresh.model_copy(update={"observed_at": utcnow() - timedelta(days=45)})
    assert old.is_stale(timedelta(days=30))


def test_cached_coordinates_expire_after_thirty_days():
    """Maps Service Specific Terms 14.3 caps lat/long caching at 30 days."""
    stale = Lead(
        place_id="place001", city="Bangalore", category_probe="dental",
        lat=12.97, lng=77.59, geo_observed_at=utcnow() - timedelta(days=31),
    )
    assert stale.lat is None and stale.lng is None and stale.geo_observed_at is None

    fresh = Lead(
        place_id="place002", city="Bangalore", category_probe="dental",
        lat=12.97, lng=77.59, geo_observed_at=utcnow() - timedelta(days=5),
    )
    assert fresh.lat == 12.97
