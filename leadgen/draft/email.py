"""Outreach drafting.

Two hard rules, both from CLAUDE.md:

* **Rule 4 — there is no send function here, and there must never be one.**
  Everything below produces text for the operator to read, edit and send by
  hand from their own mail client.
* **Rule 5 — first person singular.** The market is saturated with agency spam
  at five to ten pitches a day per owner. "We noticed your business could
  benefit from our services" is the exact register that gets deleted. A named
  local person describing one specific broken thing is not.

Only defects that were actually observed at VERIFIED confidence are ever
mentioned. A draft that cannot cite a real, checkable defect is not produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import Operator
from ..discover.places import EphemeralPlace
from ..score.rules import SLOW_LOAD_SECONDS, STALE_COPYRIGHT_YEARS
from ..store.models import Lead, Observation, OutreachRecord


@dataclass(frozen=True)
class Defect:
    """One observed problem, phrased for a non-technical business owner."""

    key: str
    subject: str
    observation: str   # what I saw
    consequence: str   # why it costs them money
    offer: str         # what I would do about it


def _known(obs: Observation | None):
    if obs is None or not obs.is_known:
        return None
    return obs.value


def pick_headline_defect(lead: Lead, place: EphemeralPlace | None) -> Defect | None:
    """The single most compelling verified defect, or None.

    Ordered by how obviously the problem costs the owner money, not by how
    technically severe it is. Returning None is correct and common — no defect
    means no honest reason to write.
    """
    site = lead.site
    has_site = bool(place.website_uri) if place else False

    if site is not None:
        if _known(site.parked_or_expired) is True:
            return Defect(
                "parked",
                "your website domain looks like it's lapsed",
                "your web address currently loads a holding page rather than your site",
                "anyone who looks you up sees a blank placeholder, which reads as closed down",
                "get a proper site back up on that same address",
            )
        if _known(site.reachable) is False:
            return Defect(
                "down",
                "your website isn't loading",
                "your website didn't load when I tried it",
                "anyone searching for you right now hits a dead end",
                "get it back online, or rebuild it properly if it's beyond repair",
            )
        status = _known(site.http_status)
        if status is not None and status >= 400:
            return Defect(
                "error",
                f"your site returns an error ({status})",
                f"your homepage returns an HTTP {status} error",
                "search engines drop pages that error out, so you slowly disappear from results",
                "fix the error and make sure the important pages actually resolve",
            )
        if _known(site.https_valid) is False:
            return Defect(
                "nohttps",
                "browsers are warning people about your site",
                "your site doesn't have a valid HTTPS certificate",
                'Chrome shows a "Not secure" warning before people reach your page, and most turn back',
                "get HTTPS set up properly so the warning goes away",
            )
        if _known(site.mobile_viewport) is False:
            return Defect(
                "nomobile",
                "your site on a phone",
                "your site isn't set up for mobile screens",
                "most people will find you on a phone, and right now they have to pinch and zoom to read anything",
                "rebuild it so it works properly on a phone",
            )
        load = _known(site.load_seconds)
        if load is not None and load > SLOW_LOAD_SECONDS:
            return Defect(
                "slow",
                f"your site takes {load:.0f} seconds to load",
                f"your homepage took about {load:.0f} seconds to load for me",
                "a large share of visitors leave before a slow page finishes loading",
                "make it load in about a second",
            )
        if _known(site.has_contact_path) is False:
            return Defect(
                "nocontact",
                "no way to get in touch on your site",
                "I couldn't find a phone number, enquiry form or booking link anywhere on your homepage",
                "someone ready to get in touch has nothing to click, so they go back to the search results",
                "put a clear way to contact or book you on every page",
            )
        year = _known(site.copyright_year)
        current_year = datetime.now(timezone.utc).year
        if year is not None and year < current_year - STALE_COPYRIGHT_YEARS:
            return Defect(
                "stale",
                f"your site still says {year}",
                f"the footer on your site still reads {year}",
                "it's a small thing, but it makes people wonder whether you're still operating",
                "refresh the site so it reflects what you're doing now",
            )

    # No site at all is only worth writing about when something else proves
    # they are actively buying customers — otherwise this is the dead-end
    # profile the scorer already rejects.
    ads = lead.ads
    ads_running = ads is not None and (
        _known(ads.google_ads_active) is True or _known(ads.meta_ads_active) is True
    )
    if not has_site and ads_running:
        return Defect(
            "adsnosite",
            "your ads don't have anywhere to land",
            "you're running ads, but there's no website behind them",
            "you're paying for clicks that land on a listing rather than somewhere built to convert them",
            "build you a simple site for those ads to point at",
        )

    return None


def draft_email(
    lead: Lead,
    place: EphemeralPlace | None,
    operator: Operator,
) -> OutreachRecord | None:
    """Compose one email. Returns None when there is nothing honest to say."""
    defect = pick_headline_defect(lead, place)
    if defect is None:
        return None

    business = (place.display_name if place else None) or "your business"
    signoff = f"{operator.name}\n{operator.site}"
    if operator.phone:
        signoff += f"\n{operator.phone}"

    body = (
        f"Hi,\n\n"
        f"I was looking up {business} and noticed {defect.observation}.\n\n"
        f"Mentioning it because {defect.consequence}.\n\n"
        f"I'm a freelance web developer here in {operator.city} — I build small sites for "
        f"local businesses, one at a time. If it's useful, I can {defect.offer}. "
        f"Happy to show you what I'd change first, no charge.\n\n"
        f"If you'd rather not, genuinely no problem — but it's worth getting fixed either "
        f"way, and whoever looks after your site can probably sort it.\n\n"
        f"{signoff}\n"
    )

    return OutreachRecord(channel="email", subject=defect.subject, body=body)
