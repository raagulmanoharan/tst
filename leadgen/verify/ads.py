"""Whether a business is actively paying for traffic.

This is the strongest buying signal available — money already flowing to a
destination that does not convert — and it is also the one we cannot honestly
automate.

Google's Ads Transparency Center has no public API. Meta's Ad Library API covers
all ads only in jurisdictions with a DSA-style mandate; for India it is limited
to political and issue ads, which is not what we are looking for.

So rather than guess, these checks return UNVERIFIED carrying the exact URL a
human should open. The dashboard renders them as one-click checks, and
`operator_ads()` records the answer with OPERATOR provenance. See CLAUDE.md
rule 2 — an invented value here would silently corrupt the highest-weighted
scoring axis.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ..store.models import AdsEvidence, Confidence, Observation, Source

GOOGLE_TRANSPARENCY = "https://adstransparency.google.com/?region=IN&query={query}"
META_AD_LIBRARY = (
    "https://www.facebook.com/ads/library/"
    "?active_status=active&ad_type=all&country=IN&q={query}&search_type=keyword_unordered"
)


def manual_check_urls(business_name: str | None) -> dict[str, str]:
    """Pre-built search URLs for the two ad libraries."""
    query = quote_plus(business_name or "")
    return {
        "google_ads_transparency": GOOGLE_TRANSPARENCY.format(query=query),
        "meta_ad_library": META_AD_LIBRARY.format(query=query),
    }


def unchecked_ads(business_name: str | None) -> AdsEvidence:
    """The honest default: not yet established, with links to establish it."""
    urls = manual_check_urls(business_name)
    reason = "no public API covers commercial ad activity in India; needs a human look"
    return AdsEvidence(
        google_ads_active=Observation.unverified(
            Source.GOOGLE_ADS_TRANSPARENCY,
            "Ads Transparency Center has no public API",
            note=reason,
            evidence_url=urls["google_ads_transparency"],
        ),
        meta_ads_active=Observation.unverified(
            Source.META_AD_LIBRARY,
            "Meta Ad Library API covers only political/issue ads for India",
            note=reason,
            evidence_url=urls["meta_ad_library"],
        ),
    )


def operator_ads(
    business_name: str | None,
    google_active: bool | None = None,
    meta_active: bool | None = None,
) -> AdsEvidence:
    """Record what the operator saw in the ad libraries.

    Passing None for either leaves that one UNVERIFIED, so a partial check stays
    partial rather than being rounded to False.
    """
    urls = manual_check_urls(business_name)
    method = "operator checked the public ad library by hand"

    def record(value: bool | None, source: Source, url: str) -> Observation[bool]:
        if value is None:
            return Observation.unverified(source, method, note="not checked yet", evidence_url=url)
        return Observation[bool](
            value=value,
            source=Source.OPERATOR,
            method=method,
            confidence=Confidence.VERIFIED,
            evidence_url=url,
        )

    return AdsEvidence(
        google_ads_active=record(
            google_active, Source.GOOGLE_ADS_TRANSPARENCY, urls["google_ads_transparency"]
        ),
        meta_ads_active=record(meta_active, Source.META_AD_LIBRARY, urls["meta_ad_library"]),
    )
