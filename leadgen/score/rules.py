"""The 2-of-3 motivation test, made explicit.

The heuristic comes from practitioners who have run this business for years: a
prospect buys only if at least two of these are true —

  1. they need more customers
  2. they are willing to part with money
  3. they will put in the time and attention

Fewer than two and they will never buy, however broken their site is.

The single most important rule in this file is that **"has no website" must
never qualify a lead on its own**. That filter has been dead since 2016: a
business with no site has usually been pitched fifty times and said no, whereas
a business with a *bad* site has already proved it will pay for one. See
`_NO_SITE_ALONE` below, which enforces this.

Live Google values (rating, review count) may inform a score but are never
written down — reasons are recorded qualitatively. See CLAUDE.md rule 3.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import CANDIDATE_CATEGORIES
from ..discover.places import EphemeralPlace
from ..store.models import Lead, Observation, ScoreBreakdown

#: An axis counts as passed at or above this value.
AXIS_PASS = 0.5

#: A lead must clear this overall to be worth the operator's time.
QUALIFY_TOTAL = 0.45

#: Slower than this on a single sample is a defect worth mentioning in outreach.
SLOW_LOAD_SECONDS = 3.0

#: A copyright notice this many years stale suggests an unmaintained site.
STALE_COPYRIGHT_YEARS = 2

#: Review counts below this are too thin to read as an active business.
THIN_REVIEW_BASE = 5
HEALTHY_REVIEW_BASE = 20

#: Below this, the research advice is to walk away regardless of fit —
#: "I don't want to work with bad people."
MIN_ACCEPTABLE_RATING = 3.5

_HIGH_TICKET = {p.key for p in CANDIDATE_CATEGORIES if p.ticket_size == "high"}

_NO_SITE_ALONE = (
    "no website is a starting signal only — it does not qualify a lead by itself"
)


def _known(observation: Observation | None) -> bool:
    return observation is not None and observation.is_known


def _value(observation: Observation | None, default=None):
    """The observed value, or `default` when nothing was established.

    UNVERIFIED never counts against a lead — absence of evidence is not
    evidence of absence.
    """
    if observation is None or not observation.is_known:
        return default
    return observation.value


def score_lead(lead: Lead, place: EphemeralPlace | None = None) -> ScoreBreakdown:
    """Score one lead across the three axes.

    `place` carries live Google values. Passing None simply means those signals
    contribute nothing, rather than counting against the lead.

    Re-scoring without `place` (because rating and review count may not be
    stored) must not resurrect a lead that was previously vetoed — so prior
    vetoes that depended on live signals are carried forward.
    """
    reasons: list[str] = []
    evidence_used: list[str] = []
    inherited_vetoes: list[str] = []
    if place is None and lead.score is not None:
        inherited_vetoes = [
            d for d in lead.score.disqualifiers if d.startswith("rated below")
        ]

    site = lead.site
    ads = lead.ads
    search = lead.search

    has_site = bool(place.website_uri) if place else _known(site.reachable) if site else False

    # ---------------------------------------------------------------- axis 1
    needs = 0.0

    if site is not None:
        if _value(site.parked_or_expired) is True:
            needs = 1.0
            reasons.append("their domain resolves to a parking or holding page")
            evidence_used.append("site.parked_or_expired")
        elif _value(site.reachable) is False:
            needs = 1.0
            reasons.append("their website does not load at all")
            evidence_used.append("site.reachable")
        else:
            defects: list[str] = []
            if _value(site.mobile_viewport) is False:
                defects.append("no mobile viewport — the site is unusable on a phone")
                evidence_used.append("site.mobile_viewport")
            load = _value(site.load_seconds)
            if load is not None and load > SLOW_LOAD_SECONDS:
                defects.append(f"homepage took {load:.1f}s to load")
                evidence_used.append("site.load_seconds")
            year = _value(site.copyright_year)
            current_year = datetime.now(timezone.utc).year
            if year is not None and year < current_year - STALE_COPYRIGHT_YEARS:
                defects.append(f"copyright notice still reads {year}")
                evidence_used.append("site.copyright_year")
            if _value(site.has_contact_path) is False:
                defects.append("no contact, booking or enquiry link anywhere on the page")
                evidence_used.append("site.has_contact_path")
            if _value(site.https_valid) is False:
                defects.append("no valid HTTPS — browsers will warn visitors")
                evidence_used.append("site.https_valid")
            status = _value(site.http_status)
            if status is not None and status >= 400:
                defects.append(f"homepage returns HTTP {status}")
                evidence_used.append("site.http_status")

            needs = min(1.0, 0.2 * len(defects))
            reasons.extend(defects)

    if not has_site:
        # Deliberately weak, and deliberately not enough to pass the axis alone.
        needs = max(needs, 0.4)
        reasons.append(_NO_SITE_ALONE)

    if search is not None and _value(search.ranks_for_own_name) is False:
        needs = min(1.0, needs + 0.2)
        reasons.append("does not rank for their own name")
        evidence_used.append("search.ranks_for_own_name")

    # ---------------------------------------------------------------- axis 2
    spend = 0.0
    ads_active = False
    if ads is not None:
        if _value(ads.google_ads_active) is True:
            ads_active = True
            evidence_used.append("ads.google_ads_active")
        if _value(ads.meta_ads_active) is True:
            ads_active = True
            evidence_used.append("ads.meta_ads_active")

    if ads_active:
        spend = 1.0
        reasons.append("already paying for ads — money is flowing to a page that does not convert")
    elif has_site:
        spend = 0.5
        reasons.append("has paid for a website before, so the willingness exists")

    if lead.category_probe in _HIGH_TICKET:
        spend = min(1.0, spend + 0.25)
        reasons.append("high-ticket category — a build fee is small beside one new customer")

    # ---------------------------------------------------------------- axis 3
    engage = 0.0
    disqualifiers: list[str] = list(inherited_vetoes)
    engage_reasons: list[str] = []
    if inherited_vetoes:
        reasons.append("live Google signals unavailable this run — prior veto carried forward")

    if place is not None:
        count = place.user_rating_count
        if count is not None:
            evidence_used.append("live:user_rating_count")
            if count >= HEALTHY_REVIEW_BASE:
                engage += 0.6
                engage_reasons.append("healthy review base — an active business with real customers")
            elif count >= THIN_REVIEW_BASE:
                engage += 0.4
                engage_reasons.append("modest review base")
            else:
                engage_reasons.append("very few reviews — may be dormant or newly opened")

        rating = place.rating
        if rating is not None:
            evidence_used.append("live:rating")
            if rating < MIN_ACCEPTABLE_RATING:
                # A veto, not a low score. Two strong axes must not carry a
                # business the operator should decline to work with.
                engage = 0.0
                engage_reasons = []
                disqualifiers.append(
                    f"rated below {MIN_ACCEPTABLE_RATING} — the research advice is to walk away, "
                    "a good site cannot fix a bad business"
                )
            elif rating >= 4.0:
                engage += 0.3
                engage_reasons.append("well reviewed — worth working with")

    reasons.extend(engage_reasons)
    engage = min(1.0, engage)

    # ---------------------------------------------------------------- verdict
    axes = {"needs_customers": needs, "will_spend": spend, "will_engage": engage}
    passed = sum(1 for v in axes.values() if v >= AXIS_PASS)
    total = round(0.4 * needs + 0.35 * spend + 0.25 * engage, 4)

    # `needs_customers` is a precondition, not one of three interchangeable
    # axes. The 2-of-3 heuristic assumes a problem has already been found and
    # asks only whether they will act on it — so a business with nothing wrong
    # is not a lead however willing and active it looks.
    if needs < AXIS_PASS:
        disqualifiers.append(
            "nothing measurably wrong with their web presence — no problem to sell against"
        )

    # The failure mode this whole file exists to prevent.
    if not has_site and not ads_active and passed < 2:
        disqualifiers.append(
            "classic dead end: no site, no ad spend, no evidence they will pay for one"
        )

    return ScoreBreakdown(
        needs_customers=round(needs, 4),
        will_spend=round(spend, 4),
        will_engage=round(engage, 4),
        axes_passed=passed,
        total=total,
        reasons=reasons,
        disqualifiers=disqualifiers,
        evidence_used=sorted(set(evidence_used)),
    )


def qualifies(score: ScoreBreakdown) -> bool:
    """All four gates must hold.

    No veto, a real problem to solve, two axes passed, and a worthwhile total.
    """
    return (
        not score.disqualifiers
        and score.needs_customers >= AXIS_PASS
        and score.passes_two_of_three
        and score.total >= QUALIFY_TOTAL
    )
