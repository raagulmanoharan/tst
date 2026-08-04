"""Outreach voice and safety rules. See CLAUDE.md rules 4 and 5."""

from __future__ import annotations

import re

from leadgen.config import Operator
from leadgen.discover.places import EphemeralPlace
from leadgen.draft import draft_email, draft_walkin, pick_headline_defect
from leadgen.store.models import Lead

from .conftest import DOWN_SITE, make_ads, make_search, make_site

OPERATOR = Operator(
    name="Test Person", site="testperson.test", email="hi@testperson.test",
    phone="+91 90000 00000", city="Bangalore",
)

PLACE = EphemeralPlace(
    place_id="place001", display_name="Aster Dental Care",
    formatted_address="12 Residency Rd, Bangalore", website_uri="https://aster.test",
    rating=4.4, user_rating_count=60,
)

#: Agency register. Owners report 5-10 of these a day and delete them on sight.
AGENCY_TELLS = [
    r"\bwe\b", r"\bour team\b", r"\bour agency\b", r"\bwe're\b", r"\bwe noticed\b",
    r"\bour services\b", r"\bwe specialize\b", r"\bwe specialise\b",
]


def lead(**kwargs) -> Lead:
    kwargs.setdefault("ads", make_ads())
    kwargs.setdefault("search", make_search())
    return Lead(place_id="place001", city="Bangalore", category_probe="dental", **kwargs)


def test_draft_leads_with_the_actual_observed_defect():
    record = draft_email(lead(site=make_site(mobile_viewport=False)), PLACE, OPERATOR)
    assert record is not None
    assert "mobile" in record.body.lower()
    assert "Aster Dental Care" in record.body


def test_draft_never_uses_agency_voice():
    for site in (
        make_site(mobile_viewport=False),
        make_site(**DOWN_SITE),
        make_site(load_seconds=9.0),
        make_site(has_contact_path=False),
        make_site(parked_or_expired=True),
    ):
        record = draft_email(lead(site=site), PLACE, OPERATOR)
        assert record is not None
        body = record.body.lower()
        for pattern in AGENCY_TELLS:
            assert not re.search(pattern, body), f"agency voice {pattern!r} in: {record.body}"


def test_no_draft_when_there_is_nothing_honest_to_say():
    """A healthy site produces silence, not a generic pitch."""
    assert draft_email(lead(site=make_site()), PLACE, OPERATOR) is None
    assert draft_walkin(lead(site=make_site()), PLACE, OPERATOR) is None


def test_no_website_alone_is_not_a_reason_to_write():
    no_site = EphemeralPlace(place_id="place001", display_name="X", website_uri=None)
    assert pick_headline_defect(lead(), no_site) is None


def test_no_website_plus_live_ads_is_worth_writing_about():
    no_site = EphemeralPlace(place_id="place001", display_name="X", website_uri=None)
    defect = pick_headline_defect(lead(ads=make_ads(google=True)), no_site)
    assert defect is not None and defect.key == "adsnosite"


def test_defect_priority_puts_the_worst_problem_first():
    site = make_site(parked_or_expired=True, mobile_viewport=False, load_seconds=9.0)
    assert pick_headline_defect(lead(site=site), PLACE).key == "parked"


def test_drafts_are_never_pre_approved():
    """Approval is the operator's act. Nothing may default to approved."""
    for record in (
        draft_email(lead(site=make_site(**DOWN_SITE)), PLACE, OPERATOR),
        draft_walkin(lead(site=make_site(**DOWN_SITE)), PLACE, OPERATOR),
    ):
        assert record.approved_by_operator is False
        assert record.sent_manually_at is None


def test_walkin_brief_steers_away_from_the_illegal_channel():
    record = draft_walkin(lead(site=make_site(**DOWN_SITE)), PLACE, OPERATOR)
    assert "email address, not a phone number" in record.body
    assert "TRAI" in record.body


def test_walkin_flags_a_lead_outside_the_operators_city():
    far = lead(site=make_site(**DOWN_SITE))
    far.city = "Chennai"
    record = draft_walkin(far, PLACE, OPERATOR)
    assert "not Bangalore" in record.body


def test_no_send_function_exists_anywhere():
    """CLAUDE.md rule 4: drafts are for human review. There is no send path."""
    import leadgen.draft.email as email_mod
    import leadgen.draft.walkin as walkin_mod
    import leadgen.pipeline as pipeline_mod

    for module in (email_mod, walkin_mod, pipeline_mod):
        for name in dir(module):
            assert "send" not in name.lower() or name.startswith("__"), (
                f"{module.__name__}.{name} looks like a send path"
            )
