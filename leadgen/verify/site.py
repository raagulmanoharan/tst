"""Direct observation of a business's own website.

This is the one evidence source we can fully automate, because we are simply a
visitor fetching a public page. Everything returned carries provenance, and a
check that establishes nothing returns `UNVERIFIED` rather than a default.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from ..store.models import Confidence, Observation, SiteEvidence, Source

METHOD_GET = "HTTP GET of the business's own homepage"

#: Phrases that indicate a registrar parking page or an abandoned domain rather
#: than a real site. Matched case-insensitively against visible text.
PARKED_MARKERS = (
    "this domain is for sale",
    "buy this domain",
    "domain for sale",
    "parked free",
    "parked domain",
    "future home of something quite cool",
    "under construction",
    "coming soon",
    "website is currently unavailable",
    "default web page",
    "it works!",
    "welcome to nginx",
    "apache2 ubuntu default page",
)

CONTACT_HINTS = ("contact", "enquiry", "enquire", "inquiry", "appointment", "book", "reach-us", "reach_us")

_COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(\d{4})", re.IGNORECASE)


def _unverified_evidence(reason: str) -> SiteEvidence:
    """Every field UNVERIFIED, with the reason recorded on each."""
    def u(_type: type) -> Observation:
        return Observation.unverified(Source.BUSINESS_SITE, METHOD_GET, note=reason)

    return SiteEvidence(
        reachable=u(bool),
        http_status=u(int),
        load_seconds=u(float),
        https_valid=u(bool),
        mobile_viewport=u(bool),
        has_contact_path=u(bool),
        copyright_year=u(int),
        parked_or_expired=u(bool),
        title_length=u(int),
    )


def check_site(url: str | None, client: httpx.Client | None = None) -> SiteEvidence:
    """Visit `url` and record what is actually observable.

    `url` comes from a live Places lookup and is never stored — see CLAUDE.md
    rule 3. Passing None is normal: it means Google lists no website for this
    business, which is itself only a starting signal, not a qualification.
    """
    if not url:
        return _unverified_evidence("Google lists no website for this place")

    owned_client = client is None
    client = client or httpx.Client(timeout=15.0, follow_redirects=True)

    https_valid: Observation[bool]
    started = time.perf_counter()
    try:
        response = client.get(url, follow_redirects=True)
        elapsed = time.perf_counter() - started
        https_valid = Observation[bool](
            value=str(response.url).startswith("https://"),
            source=Source.BUSINESS_SITE,
            method="final URL scheme after redirects, TLS chain verified by httpx",
            confidence=Confidence.VERIFIED,
            evidence_url=str(response.url),
        )
    except httpx.HTTPError as exc:
        if owned_client:
            client.close()
        note = f"{type(exc).__name__}: {exc}"

        # A failure on our side of the wire says nothing about their site. Only
        # attribute unreachability when the remote host is what failed —
        # otherwise this reports our own outage as their broken website.
        if isinstance(exc, (httpx.ProxyError, httpx.UnsupportedProtocol, httpx.InvalidURL)):
            return _unverified_evidence(f"local/transport failure, not attributable to the site — {note}")

        evidence = _unverified_evidence(note)
        tls_failure = "ssl" in note.lower() or "certificate" in note.lower()
        return evidence.model_copy(
            update={
                "reachable": Observation[bool](
                    value=False,
                    source=Source.BUSINESS_SITE,
                    method=f"{METHOD_GET} — remote host raised {type(exc).__name__}",
                    confidence=Confidence.VERIFIED,
                    evidence_url=url,
                    note=note,
                ),
                "https_valid": Observation[bool](
                    value=False,
                    source=Source.BUSINESS_SITE,
                    method="TLS handshake or certificate validation failed",
                    confidence=Confidence.VERIFIED,
                    evidence_url=url,
                    note=note,
                )
                if tls_failure
                else Observation.unverified(Source.BUSINESS_SITE, METHOD_GET, note=note),
            }
        )

    final_url = str(response.url)
    html = response.text or ""
    soup = BeautifulSoup(html, "html.parser")
    visible = soup.get_text(" ", strip=True).lower()

    def obs(value, method: str) -> Observation:
        return Observation(
            value=value,
            source=Source.BUSINESS_SITE,
            method=method,
            confidence=Confidence.VERIFIED,
            evidence_url=final_url,
        )

    title_tag = soup.title.string if soup.title and soup.title.string else ""
    title_text = title_tag.strip()

    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})

    contact_found = any(
        hint in (a.get("href", "") + " " + a.get_text(" ", strip=True)).lower()
        for a in soup.find_all("a")
        for hint in CONTACT_HINTS
    ) or any(
        a.get("href", "").lower().startswith(("mailto:", "tel:")) for a in soup.find_all("a")
    )

    parked = any(marker in visible for marker in PARKED_MARKERS) and len(visible) < 2000

    copyright_match = _COPYRIGHT.search(html)
    if copyright_match:
        year = int(copyright_match.group(1))
        current_year = datetime.now(timezone.utc).year
        # A year outside a sane window means we matched something else.
        if 1995 <= year <= current_year + 1:
            copyright_obs: Observation = obs(year, "regex match on a copyright notice in page HTML")
        else:
            copyright_obs = Observation.unverified(
                Source.BUSINESS_SITE, METHOD_GET, note=f"implausible year {year} matched; ignored"
            )
    else:
        copyright_obs = Observation.unverified(
            Source.BUSINESS_SITE, METHOD_GET, note="no copyright notice found in page HTML"
        )

    if owned_client:
        client.close()

    return SiteEvidence(
        reachable=obs(response.status_code < 400, f"{METHOD_GET} returned {response.status_code}"),
        http_status=obs(response.status_code, "HTTP status of the final response after redirects"),
        load_seconds=obs(round(elapsed, 3), "wall-clock seconds for the full response, single sample"),
        https_valid=https_valid,
        mobile_viewport=obs(viewport is not None, "presence of a <meta name=viewport> tag"),
        has_contact_path=obs(contact_found, "anchor hrefs/text scanned for contact, booking, mailto and tel links"),
        copyright_year=copyright_obs,
        parked_or_expired=obs(parked, "parking-page phrase match on a page under 2000 visible characters"),
        title_length=obs(len(title_text), "character length of the <title> element"),
    )
