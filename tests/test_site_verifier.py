"""Golden-fixture tests for the site verifier.

These pin the verdicts a human confirmed by reading the fixtures in
`tests/golden/`. If a change to the verifier moves one of these, the verifier
changed its mind about a page nobody edited — investigate before updating.
"""

from __future__ import annotations

import httpx
import pytest

from leadgen.verify.site import check_site


def transport_for(body: str, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, html=body)

    return httpx.MockTransport(handler)


def client_for(body: str, status: int = 200) -> httpx.Client:
    return httpx.Client(transport=transport_for(body, status), follow_redirects=True)


def test_modern_healthy_site(golden_dir):
    body = (golden_dir / "modern_healthy.html").read_text()
    with client_for(body) as client:
        ev = check_site("https://aster.test", client)

    assert ev.reachable.value is True
    assert ev.http_status.value == 200
    assert ev.mobile_viewport.value is True
    assert ev.has_contact_path.value is True
    assert ev.copyright_year.value == 2026
    assert ev.parked_or_expired.value is False
    assert ev.https_valid.value is True


def test_dated_site_without_mobile_support(golden_dir):
    body = (golden_dir / "dated_no_mobile.html").read_text()
    with client_for(body) as client:
        ev = check_site("https://sharma.test", client)

    assert ev.reachable.value is True
    assert ev.mobile_viewport.value is False, "no viewport meta tag in this fixture"
    assert ev.has_contact_path.value is False, "fixture has no contact link, mailto or tel"
    assert ev.copyright_year.value == 2018


def test_parked_domain(golden_dir):
    body = (golden_dir / "parked.html").read_text()
    with client_for(body) as client:
        ev = check_site("https://parked.test", client)

    assert ev.parked_or_expired.value is True


def test_error_page_is_recorded_as_unreachable(golden_dir):
    body = (golden_dir / "modern_healthy.html").read_text()
    with client_for(body, status=503) as client:
        ev = check_site("https://down.test", client)

    assert ev.http_status.value == 503
    assert ev.reachable.value is False


def test_missing_url_yields_all_unverified():
    """No website listed is a starting signal, not a set of observations."""
    ev = check_site(None)
    for name in type(ev).model_fields:
        obs = getattr(ev, name)
        assert not obs.is_known
        assert obs.value is None


def test_remote_failure_is_attributed_to_the_site():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ev = check_site("https://refused.test", client)

    assert ev.reachable.value is False
    assert ev.reachable.is_known


def test_local_transport_failure_is_never_blamed_on_the_site():
    """A proxy failure on our side says nothing about their website."""
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ProxyError("502 Bad Gateway")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ev = check_site("https://unknown.test", client)

    assert ev.reachable.value is None
    assert not ev.reachable.is_known
    assert "not attributable" in (ev.reachable.note or "")


def test_tls_failure_marks_https_invalid():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate has expired")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        ev = check_site("https://expired.test", client)

    assert ev.https_valid.value is False
    assert ev.reachable.value is False


@pytest.mark.parametrize("year_html", ["&copy; 1823 Old", "&copy; 3099 Future"])
def test_implausible_copyright_years_are_not_believed(year_html):
    body = f"<html><head><title>t</title></head><body><footer>{year_html}</footer></body></html>"
    with client_for(body) as client:
        ev = check_site("https://x.test", client)

    assert not ev.copyright_year.is_known


def test_every_observation_carries_provenance(golden_dir):
    body = (golden_dir / "modern_healthy.html").read_text()
    with client_for(body) as client:
        ev = check_site("https://aster.test", client)

    for name in type(ev).model_fields:
        obs = getattr(ev, name)
        assert obs.method and len(obs.method) >= 3
        if obs.is_known:
            assert obs.evidence_url, f"{name} claims a value with no evidence_url"
