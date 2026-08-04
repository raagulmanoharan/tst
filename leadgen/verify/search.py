"""Whether the business can be found at all.

Same honesty constraint as `ads.py`: there is no free, terms-compliant search
API that returns ranking position, and scraping a results page to assert "they
rank on page 3" would be both a ToS problem and an unreliable claim.

These checks therefore return UNVERIFIED with the query URL attached, and
`operator_search()` records what the operator saw.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from ..store.models import Confidence, Observation, SearchEvidence, Source

SEARCH_URL = "https://www.google.com/search?q={query}"


def manual_check_urls(business_name: str | None, city: str) -> dict[str, str]:
    name = business_name or ""
    return {
        "own_name": SEARCH_URL.format(query=quote_plus(f"{name} {city}")),
        "domain": SEARCH_URL.format(query=quote_plus(f'"{name}" official website')),
    }


def unchecked_search(business_name: str | None, city: str) -> SearchEvidence:
    urls = manual_check_urls(business_name, city)
    reason = "no terms-compliant free API returns ranking position; needs a human look"
    return SearchEvidence(
        ranks_for_own_name=Observation.unverified(
            Source.WEB_SEARCH,
            "search ranking cannot be established programmatically",
            note=reason,
            evidence_url=urls["own_name"],
        ),
        independent_domain_found=Observation.unverified(
            Source.WEB_SEARCH,
            "search ranking cannot be established programmatically",
            note=reason,
            evidence_url=urls["domain"],
        ),
    )


def operator_search(
    business_name: str | None,
    city: str,
    ranks_for_own_name: bool | None = None,
    independent_domain_found: bool | None = None,
) -> SearchEvidence:
    urls = manual_check_urls(business_name, city)
    method = "operator ran the search by hand"

    def record(value: bool | None, url: str) -> Observation[bool]:
        if value is None:
            return Observation.unverified(
                Source.WEB_SEARCH, method, note="not checked yet", evidence_url=url
            )
        return Observation[bool](
            value=value,
            source=Source.OPERATOR,
            method=method,
            confidence=Confidence.VERIFIED,
            evidence_url=url,
        )

    return SearchEvidence(
        ranks_for_own_name=record(ranks_for_own_name, urls["own_name"]),
        independent_domain_found=record(independent_domain_found, urls["domain"]),
    )
