"""Provenance-enforcing schema.

Two invariants are enforced here, at the type level, because both are easy to
erode by accident and expensive to discover later:

1. Nothing is stored without provenance. See `Observation`.
2. No Google Maps Content is ever persisted. See `PersistedModel`.

Read CLAUDE.md rules 2 and 3 before changing anything in this file.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Provenance vocabulary
# --------------------------------------------------------------------------


class Source(str, Enum):
    """Where a fact came from.

    GOOGLE_PLACES is deliberately absent from `PERSISTABLE_SOURCES`: Places data
    may inform a run but may not be written to disk.
    """

    GOOGLE_PLACES = "google_places"
    BUSINESS_SITE = "business_site"
    GOOGLE_ADS_TRANSPARENCY = "google_ads_transparency"
    META_AD_LIBRARY = "meta_ad_library"
    WEB_SEARCH = "web_search"
    DNS = "dns"
    OPERATOR = "operator"


#: Sources whose *content* we may persist. A business's own website is their
#: publication (DPDP s.3(c)(ii)); Google's index is not ours to keep.
PERSISTABLE_SOURCES = frozenset(
    {
        Source.BUSINESS_SITE,
        Source.GOOGLE_ADS_TRANSPARENCY,
        Source.META_AD_LIBRARY,
        Source.WEB_SEARCH,
        Source.DNS,
        Source.OPERATOR,
    }
)


class Confidence(str, Enum):
    """How much weight a fact carries.

    UNVERIFIED is a first-class, expected outcome — not a gap to be filled in.
    """

    VERIFIED = "verified"      # directly observed by us, this run
    REPORTED = "reported"      # a source asserts it; we did not independently confirm
    UNVERIFIED = "unverified"  # we tried and could not establish it


class Stage(str, Enum):
    DISCOVERED = "discovered"
    VERIFIED = "verified"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    DRAFTED = "drafted"
    CONTACTED = "contacted"
    REPLIED = "replied"
    WON = "won"
    LOST = "lost"


# --------------------------------------------------------------------------
# The unit of evidence
# --------------------------------------------------------------------------


class Observation(BaseModel, Generic[T]):
    """A single fact plus everything needed to audit it later.

    There is no way to construct one of these without saying where it came from,
    which is the entire point. `unverified()` is the honest escape hatch.
    """

    model_config = ConfigDict(frozen=True)

    value: T | None
    source: Source
    method: str = Field(min_length=3, description="How it was obtained, e.g. 'HTTP GET, status 404'")
    observed_at: datetime = Field(default_factory=utcnow)
    confidence: Confidence
    evidence_url: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _enforce_provenance(self) -> Observation[T]:
        if self.confidence is Confidence.UNVERIFIED:
            if self.value is not None:
                raise ValueError(
                    "an UNVERIFIED observation must not carry a value — "
                    "a guess with a disclaimer is still a guess"
                )
            return self

        if self.value is None:
            raise ValueError(
                f"observation has no value but claims confidence={self.confidence.value}; "
                "use Observation.unverified() instead"
            )

        # A machine-made claim has to point at something a human can re-check.
        if self.source is not Source.OPERATOR and not self.evidence_url:
            raise ValueError(
                f"observation from {self.source.value} requires an evidence_url "
                "so the claim can be independently re-checked"
            )
        return self

    @classmethod
    def unverified(
        cls,
        source: Source,
        method: str,
        note: str | None = None,
        evidence_url: str | None = None,
    ) -> Observation[T]:
        """The correct result when a check ran and established nothing.

        `evidence_url` here means "where a human could establish this", which is
        how signals we cannot automate (ad spend, search rank) surface as a
        one-click check in the dashboard instead of a fabricated value.
        """
        return cls(
            value=None,
            source=source,
            method=method,
            confidence=Confidence.UNVERIFIED,
            note=note,
            evidence_url=evidence_url,
        )

    @property
    def is_known(self) -> bool:
        return self.confidence is not Confidence.UNVERIFIED

    def is_stale(self, ttl: timedelta) -> bool:
        return utcnow() - self.observed_at > ttl


# --------------------------------------------------------------------------
# The Google boundary, enforced at class-definition time
# --------------------------------------------------------------------------

#: Field names that would mean we had stored Google Maps Content. Matched as
#: whole words against snake_case field names, so `site_load_seconds` is fine
#: while `business_name` is not.
FORBIDDEN_PERSISTED_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "business_name",
        "display_name",
        "formatted_address",
        "address",
        "vicinity",
        "phone",
        "phone_number",
        "national_phone_number",
        "international_phone_number",
        "rating",
        "user_rating_count",
        "review_count",
        "reviews",
        "review_text",
        "website",
        "website_uri",
        "website_url",
        "site_url",
        "editorial_summary",
        "opening_hours",
        "photos",
    }
)


class TosViolation(TypeError):
    """Raised at import time if a persisted model would store Google content."""


class PersistedModel(BaseModel):
    """Base for anything that reaches disk.

    Subclassing runs the Google-boundary check immediately, so a violation fails
    at import rather than silently shipping. If a feature appears to need one of
    these fields, the feature is wrong — re-fetch it live instead. See CLAUDE.md
    rule 3.

    The hook is `__pydantic_init_subclass__` rather than `__init_subclass__`:
    the latter fires before pydantic has collected `model_fields`, so the check
    would pass vacuously on every class.
    """

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        offending = sorted(set(cls.model_fields) & FORBIDDEN_PERSISTED_FIELDS)
        if offending:
            raise TosViolation(
                f"{cls.__name__} declares {', '.join(offending)}, which would persist "
                f"Google Maps Content — prohibited by Maps Platform ToS 3.2.3(a)(iii). "
                f"Fetch these live at render time instead. See CLAUDE.md rule 3."
            )


# --------------------------------------------------------------------------
# Evidence collected about a lead
# --------------------------------------------------------------------------


class SiteEvidence(PersistedModel):
    """What we observed by visiting the business's own website.

    Note there is no field for the URL itself: it comes from Places and is
    therefore re-fetched live on every run rather than stored.
    """

    reachable: Observation[bool]
    http_status: Observation[int]
    load_seconds: Observation[float]
    https_valid: Observation[bool]
    mobile_viewport: Observation[bool]
    has_contact_path: Observation[bool]
    copyright_year: Observation[int]
    parked_or_expired: Observation[bool]
    title_length: Observation[int]


class AdsEvidence(PersistedModel):
    """Whether they are actively paying for traffic.

    The strongest buying signal available: money already flowing to a
    destination that does not convert.
    """

    google_ads_active: Observation[bool]
    meta_ads_active: Observation[bool]


class SearchEvidence(PersistedModel):
    """Whether they can be found at all."""

    ranks_for_own_name: Observation[bool]
    independent_domain_found: Observation[bool]


class ScoreBreakdown(PersistedModel):
    """The 2-of-3 motivation test, made explicit and auditable.

    Each axis records the evidence keys it consulted, so a score can always be
    traced back to observations rather than taken on trust.
    """

    needs_customers: float = Field(ge=0.0, le=1.0)
    will_spend: float = Field(ge=0.0, le=1.0)
    will_engage: float = Field(ge=0.0, le=1.0)
    axes_passed: int = Field(ge=0, le=3)
    total: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    #: Hard vetoes. Any entry here disqualifies the lead outright, whatever the
    #: axis scores say — a high total cannot buy its way past one of these.
    disqualifiers: list[str] = Field(default_factory=list)
    evidence_used: list[str] = Field(default_factory=list)
    scored_at: datetime = Field(default_factory=utcnow)

    @property
    def passes_two_of_three(self) -> bool:
        return self.axes_passed >= 2


class OutreachRecord(PersistedModel):
    """Outreach history. Drafts only — this system never sends.

    `channel` is constrained to the two legally permitted cold channels; see
    CLAUDE.md rule 4.
    """

    channel: str = Field(pattern="^(email|walkin)$")
    drafted_at: datetime = Field(default_factory=utcnow)
    subject: str | None = None
    body: str
    approved_by_operator: bool = False
    sent_manually_at: datetime | None = None
    outcome_note: str | None = None


class Lead(PersistedModel):
    """A candidate business.

    Identified only by `place_id`, which Google explicitly exempts from the
    caching restrictions. Everything Google knows about this business is fetched
    live when needed and discarded.
    """

    place_id: str = Field(min_length=6)
    city: str
    category_probe: str = Field(description="The search term that surfaced this place")

    # Lat/long is the one Google field with an explicit cache allowance, capped
    # at 30 consecutive days (Maps Service Specific Terms 14.3).
    lat: float | None = None
    lng: float | None = None
    geo_observed_at: datetime | None = None

    site: SiteEvidence | None = None
    ads: AdsEvidence | None = None
    search: SearchEvidence | None = None
    score: ScoreBreakdown | None = None

    stage: Stage = Stage.DISCOVERED
    contradictions: list[str] = Field(default_factory=list)
    operator_notes: str | None = None
    outreach: list[OutreachRecord] = Field(default_factory=list)

    first_seen_at: datetime = Field(default_factory=utcnow)
    last_verified_at: datetime | None = None

    #: Maps Service Specific Terms 14.3 caps lat/long caching at 30 days.
    GEO_TTL: ClassVar[timedelta] = timedelta(days=30)

    @model_validator(mode="after")
    def _expire_geo(self) -> Lead:
        """Drop cached coordinates once the 30-day allowance lapses."""
        if self.geo_observed_at is not None:
            if utcnow() - self.geo_observed_at > self.GEO_TTL:
                self.lat = None
                self.lng = None
                self.geo_observed_at = None
        return self

    def observations(self) -> dict[str, Observation[Any]]:
        """Flatten every observation on this lead, keyed as 'group.field'."""
        found: dict[str, Observation[Any]] = {}
        for group in ("site", "ads", "search"):
            block = getattr(self, group, None)
            if block is None:
                continue
            for field_name in type(block).model_fields:
                value = getattr(block, field_name)
                if isinstance(value, Observation):
                    found[f"{group}.{field_name}"] = value
        return found


_SNAKE = re.compile(r"[^a-z0-9]+")


def normalise_key(text: str) -> str:
    """Lowercase snake_case, for comparing field names and category labels."""
    return _SNAKE.sub("_", text.strip().lower()).strip("_")
