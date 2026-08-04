from __future__ import annotations

from pathlib import Path

import pytest

from leadgen.store.models import (
    AdsEvidence,
    Confidence,
    Observation,
    SearchEvidence,
    SiteEvidence,
    Source,
)

GOLDEN = Path(__file__).parent / "golden"

HEALTHY_SITE = dict(
    reachable=True, http_status=200, load_seconds=0.8, https_valid=True,
    mobile_viewport=True, has_contact_path=True, copyright_year=2026,
    parked_or_expired=False, title_length=44,
)

#: A site that failed to load: reachability is known, everything else is not.
DOWN_SITE = dict(
    reachable=False, http_status=None, load_seconds=None, https_valid=None,
    mobile_viewport=None, has_contact_path=None, copyright_year=None,
    parked_or_expired=None, title_length=None,
)


def observed(value):
    return Observation(
        value=value,
        source=Source.BUSINESS_SITE,
        method="fixture observation",
        confidence=Confidence.VERIFIED,
        evidence_url="https://fixture.test",
    )


def unknown():
    return Observation.unverified(Source.BUSINESS_SITE, "fixture check established nothing")


def make_site(**overrides) -> SiteEvidence:
    fields = {**HEALTHY_SITE, **overrides}
    return SiteEvidence(**{k: (unknown() if v is None else observed(v)) for k, v in fields.items()})


def make_ads(google: bool | None = None, meta: bool | None = None) -> AdsEvidence:
    def field(value, source: Source):
        if value is None:
            return Observation.unverified(source, "not checked", evidence_url="https://check.test")
        return Observation(
            value=value, source=Source.OPERATOR, method="operator checked by hand",
            confidence=Confidence.VERIFIED, evidence_url="https://check.test",
        )

    return AdsEvidence(
        google_ads_active=field(google, Source.GOOGLE_ADS_TRANSPARENCY),
        meta_ads_active=field(meta, Source.META_AD_LIBRARY),
    )


def make_search(ranks: bool | None = None, domain: bool | None = None) -> SearchEvidence:
    def field(value):
        if value is None:
            return Observation.unverified(Source.WEB_SEARCH, "not checked", evidence_url="https://check.test")
        return Observation(
            value=value, source=Source.OPERATOR, method="operator searched by hand",
            confidence=Confidence.VERIFIED, evidence_url="https://check.test",
        )

    return SearchEvidence(ranks_for_own_name=field(ranks), independent_domain_found=field(domain))


@pytest.fixture
def golden_dir() -> Path:
    return GOLDEN
