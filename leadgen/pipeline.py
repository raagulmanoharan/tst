"""Pipeline stages: discover → verify → score → draft.

`verify` and `score` are fused into one pass over the network because scoring
reads live Google signals (rating, review count) that may not be stored. Doing
them separately would mean paying the scarce Enterprise SKU twice per lead.
`score_only` exists for re-scoring after a rules change, using persisted
evidence alone.
"""

from __future__ import annotations

import logging

from .config import CANDIDATE_CATEGORIES, CITIES, Operator
from .discover.places import BudgetExceeded, PlacesClient, PlacesUnavailable
from .draft.email import draft_email
from .draft.walkin import draft_walkin
from .score.rules import qualifies, score_lead
from .store import LeadStore
from .store.models import Lead, Stage, utcnow
from .verify.ads import unchecked_ads
from .verify.search import unchecked_search
from .verify.site import check_site

log = logging.getLogger(__name__)


def run_discover(
    store: LeadStore,
    client: PlacesClient,
    city_key: str,
    category_keys: list[str] | None = None,
    max_centres: int | None = None,
) -> dict[str, int]:
    """Sweep a city for candidate places. Stores place_ids and nothing else."""
    city = CITIES[city_key]
    probes = [p for p in CANDIDATE_CATEGORIES if not category_keys or p.key in category_keys]
    if not probes:
        raise ValueError(f"no category matched {category_keys}")

    added = skipped = 0
    for probe in probes:
        try:
            for found in client.discover(city, probe, max_centres=max_centres):
                if store.exists(found.place_id):
                    skipped += 1
                    continue
                store.upsert(
                    Lead(
                        place_id=found.place_id,
                        city=city.name,
                        category_probe=probe.key,
                        lat=found.lat,
                        lng=found.lng,
                        geo_observed_at=utcnow() if found.lat is not None else None,
                    )
                )
                added += 1
        except BudgetExceeded as exc:
            log.warning("stopping discovery: %s", exc)
            break
    return {"added": added, "already_known": skipped}


def run_verify(
    store: LeadStore,
    client: PlacesClient,
    limit: int | None = None,
) -> dict[str, int]:
    """Verify and score. One live Places call per lead, then a direct site visit."""
    counts = {"verified": 0, "qualified": 0, "rejected": 0, "skipped": 0}
    pending = list(store.by_stage(Stage.DISCOVERED))
    if limit is not None:
        pending = pending[:limit]

    for lead in pending:
        try:
            place = client.fetch_live(lead.place_id)
        except BudgetExceeded as exc:
            log.warning("stopping verification: %s", exc)
            break
        except PlacesUnavailable as exc:
            log.warning("skipping %s: %s", lead.place_id, exc)
            counts["skipped"] += 1
            continue

        lead.site = check_site(place.website_uri)
        lead.ads = unchecked_ads(place.display_name)
        lead.search = unchecked_search(place.display_name, lead.city)
        lead.last_verified_at = utcnow()
        lead.contradictions = detect_contradictions(lead)

        lead.score = score_lead(lead, place)
        lead.stage = Stage.QUALIFIED if qualifies(lead.score) else Stage.REJECTED
        counts["verified"] += 1
        counts["qualified" if lead.stage is Stage.QUALIFIED else "rejected"] += 1
        store.upsert(lead)

    return counts


def score_only(store: LeadStore) -> dict[str, int]:
    """Re-score from persisted evidence, without touching the network.

    Live signals are unavailable here, so prior vetoes are carried forward
    rather than silently dropped — see `score_lead`.
    """
    counts = {"rescored": 0, "qualified": 0, "rejected": 0}
    for lead in list(store.all()):
        if lead.stage in (Stage.CONTACTED, Stage.REPLIED, Stage.WON, Stage.LOST):
            continue  # Never re-litigate a lead already in conversation.
        if lead.site is None:
            continue
        lead.score = score_lead(lead, None)
        lead.stage = Stage.QUALIFIED if qualifies(lead.score) else Stage.REJECTED
        counts["rescored"] += 1
        counts["qualified" if lead.stage is Stage.QUALIFIED else "rejected"] += 1
        store.upsert(lead)
    return counts


def run_draft(store: LeadStore, operator: Operator, client: PlacesClient | None = None) -> dict[str, int]:
    """Draft outreach for qualified leads. Never sends. Never auto-approves."""
    counts = {"drafted": 0, "no_defect": 0}
    for lead in store.by_stage(Stage.QUALIFIED):
        if lead.outreach:
            continue  # Already drafted; editing is the operator's job.
        place = None
        if client is not None:
            try:
                place = client.fetch_live(lead.place_id)
            except (PlacesUnavailable, BudgetExceeded):
                pass

        drafts = [
            d
            for d in (
                draft_email(lead, place, operator),
                draft_walkin(lead, place, operator),
            )
            if d is not None
        ]
        if not drafts:
            counts["no_defect"] += 1
            continue

        lead.outreach.extend(drafts)
        lead.stage = Stage.DRAFTED
        store.upsert(lead)
        counts["drafted"] += 1
    return counts


def detect_contradictions(lead: Lead) -> list[str]:
    """Flag internally inconsistent evidence for a human rather than resolving it.

    Silently picking a winner is how a tracker starts lying to you.
    """
    found: list[str] = []
    site = lead.site
    if site is None:
        return found

    reachable = site.reachable.value if site.reachable.is_known else None
    status = site.http_status.value if site.http_status.is_known else None
    if reachable is True and status is not None and status >= 400:
        found.append(f"site reported reachable but returned HTTP {status}")
    if reachable is False and status is not None and status < 400:
        found.append(f"site reported unreachable but returned HTTP {status}")

    parked = site.parked_or_expired.value if site.parked_or_expired.is_known else None
    if parked is True and reachable is False:
        found.append("site flagged as parked but also recorded as unreachable")

    return found
