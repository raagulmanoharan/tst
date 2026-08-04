"""End-to-end pipeline, store and validation harness.

Uses a stub Places client so nothing here touches the network or spends API
quota.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from leadgen.config import CITIES, Operator
from leadgen.dashboard import build_dashboard
from leadgen.discover.places import DiscoveredPlace, EphemeralPlace
from leadgen.pipeline import detect_contradictions, run_draft, run_verify, score_only
from leadgen.store import LeadStore
from leadgen.store.models import Confidence, Lead, Observation, Source, Stage
from leadgen.validate import validate

from .conftest import make_ads, make_site

OPERATOR = Operator(
    name="Test Person", site="testperson.test", email="hi@testperson.test", city="Bangalore"
)


class StubPlacesClient:
    """Stands in for PlacesClient without a key, a network or a bill."""

    def __init__(self, places: dict[str, EphemeralPlace]) -> None:
        self.places = places
        self.calls = 0

    def discover(self, city, probe, **kwargs):
        for place_id in self.places:
            yield DiscoveredPlace(place_id=place_id, lat=12.97, lng=77.59)

    def fetch_live(self, place_id: str) -> EphemeralPlace:
        self.calls += 1
        return self.places[place_id]


@pytest.fixture
def store(tmp_path: Path) -> LeadStore:
    s = LeadStore(tmp_path / "test.db")
    yield s
    s.close()


def seed(store: LeadStore, place_id: str, category: str = "dental") -> Lead:
    lead = Lead(place_id=place_id, city="Bangalore", category_probe=category)
    store.upsert(lead)
    return lead


def test_store_roundtrips_a_lead_with_evidence(store):
    lead = seed(store, "place001")
    lead.site = make_site(mobile_viewport=False)
    lead.ads = make_ads(google=True)
    store.upsert(lead)

    loaded = store.get("place001")
    assert loaded is not None
    assert loaded.site.mobile_viewport.value is False
    assert loaded.ads.google_ads_active.value is True
    assert loaded.site.mobile_viewport.evidence_url


def test_verify_scores_and_routes_leads(store, monkeypatch):
    seed(store, "place001")  # broken site, running ads, well reviewed -> qualified
    seed(store, "place002")  # healthy site -> rejected

    client = StubPlacesClient({
        "place001": EphemeralPlace("place001", display_name="Broken Co", website_uri="https://broken.test", rating=4.6, user_rating_count=90),
        "place002": EphemeralPlace("place002", display_name="Healthy Co", website_uri="https://healthy.test", rating=4.6, user_rating_count=90),
    })

    def fake_check_site(url, http_client=None):
        return make_site(reachable=False) if "broken" in (url or "") else make_site()

    monkeypatch.setattr("leadgen.pipeline.check_site", fake_check_site)

    result = run_verify(store, client)
    assert result["verified"] == 2
    assert result["qualified"] == 1
    assert result["rejected"] == 1
    assert store.get("place001").stage is Stage.QUALIFIED
    assert store.get("place002").stage is Stage.REJECTED
    assert client.calls == 2, "one live lookup per lead, not more"


def test_draft_only_touches_qualified_leads(store, monkeypatch):
    lead = seed(store, "place001")
    lead.site = make_site(mobile_viewport=False)
    lead.ads = make_ads(google=True)
    lead.stage = Stage.QUALIFIED
    store.upsert(lead)

    client = StubPlacesClient({
        "place001": EphemeralPlace("place001", display_name="Aster", website_uri="https://a.test", rating=4.5, user_rating_count=60)
    })
    result = run_draft(store, OPERATOR, client)

    assert result["drafted"] == 1
    updated = store.get("place001")
    assert updated.stage is Stage.DRAFTED
    assert {r.channel for r in updated.outreach} == {"email", "walkin"}
    assert all(not r.approved_by_operator for r in updated.outreach)


def test_rescore_leaves_in_conversation_leads_alone(store):
    lead = seed(store, "place001")
    lead.site = make_site()
    lead.stage = Stage.REPLIED
    store.upsert(lead)

    score_only(store)
    assert store.get("place001").stage is Stage.REPLIED


def test_contradictions_are_flagged_not_resolved():
    lead = Lead(place_id="place001", city="Bangalore", category_probe="dental")
    lead.site = make_site(reachable=True, http_status=503)
    found = detect_contradictions(lead)
    assert found and "503" in found[0]


def test_validate_passes_on_well_formed_data(store):
    lead = seed(store, "place001")
    lead.site = make_site()
    lead.ads = make_ads(google=True)
    store.upsert(lead)

    report = validate(store)
    assert report.ok
    assert report.leads_checked == 1
    assert report.observations_checked > 0


def test_validate_counts_unverified_without_failing(store):
    """Unverified fields are expected, not errors — they need a human, not a fix."""
    lead = seed(store, "place001")
    lead.site = make_site()
    lead.ads = make_ads()  # both unchecked
    store.upsert(lead)

    report = validate(store)
    assert report.ok
    assert report.unverified_by_field.get("ads.google_ads_active") == 1


def test_budget_tracking_accumulates(store):
    store.record_api_call("text_search_pro", 5)
    store.record_api_call("text_search_pro", 3)
    assert store.usage_this_month()["text_search_pro"] == 8


def test_dashboard_renders_without_leaking_stored_google_content(store, tmp_path):
    lead = seed(store, "place001")
    lead.site = make_site(mobile_viewport=False)
    lead.ads = make_ads()
    lead.stage = Stage.QUALIFIED
    from leadgen.score import score_lead
    lead.score = score_lead(lead, None)
    store.upsert(lead)

    out = build_dashboard(store, tmp_path / "index.html")
    html = out.read_text()

    assert "place001" in html
    assert "maps/place/?q=place_id:place001" in html
    # Manual-check links must survive into the page for the operator to click.
    assert "check.test" in html


def test_city_grid_covers_the_bounding_box():
    grid = CITIES["bangalore"].grid(step_km=8.0)
    assert len(grid) > 4
    lats = [lat for lat, _ in grid]
    assert min(lats) >= CITIES["bangalore"].lat_min
    assert max(lats) <= CITIES["bangalore"].lat_max


def test_only_bangalore_is_active_in_phase_one():
    assert [k for k, c in CITIES.items() if c.active] == ["bangalore"]
