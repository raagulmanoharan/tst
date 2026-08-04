"""Evidence with provenance.

Ported from the previous project's store layer, with one addition this domain
badly needs: `SampleBasis`.

Passive-income research is drowning in survivor bias. "I make $10k/month from
Gumroad" is a real number from a real person and still tells you nothing about
what *you* will earn, because you only ever hear from the winners. So every
figure here records not just where it came from but **what kind of sample it
is** — an aggregate, a median, a top-decile outlier, or one person's anecdote.
The feasibility engine weights them differently and the dashboard shows the
basis next to the number.

See CLAUDE.md rule 2: never fabricate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(str, Enum):
    PLATFORM_DOCS = "platform_docs"        # official pricing, fees, policy
    PLATFORM_DATA = "platform_data"        # published aggregate/transparency data
    INDUSTRY_REPORT = "industry_report"    # third-party research
    SELLER_REPORT = "seller_report"        # individuals reporting their own numbers
    MARKET_OBSERVATION = "market_observation"  # directly observed listings, prices, counts
    OPERATOR = "operator"                  # the operator's own measurement
    COMPUTED = "computed"                  # derived from other observations


class Confidence(str, Enum):
    VERIFIED = "verified"      # directly observed, or from primary documentation
    REPORTED = "reported"      # asserted by a source we did not independently confirm
    UNVERIFIED = "unverified"  # we looked and could not establish it


class SampleBasis(str, Enum):
    """What kind of number this is. The guard against survivor bias."""

    AGGREGATE = "aggregate"      # whole-population data
    MEDIAN = "median"            # explicit median or typical case
    MEAN = "mean"                # an average — see the warning below
    TOP_DECILE = "top_decile"    # known to describe high performers only
    ANECDOTE = "anecdote"        # a single self-reported case
    ESTIMATE = "estimate"        # the operator's own judgement about their own work
    NOT_APPLICABLE = "n/a"       # fees, rates, policy — not a sample at all


#: How much to trust a figure when projecting *our* likely outcome. A top-decile
#: number is real but nearly worthless for planning, so it is heavily discounted
#: rather than silently treated like a median.
BASIS_WEIGHT: dict[SampleBasis, float] = {
    SampleBasis.AGGREGATE: 1.0,
    SampleBasis.MEDIAN: 1.0,
    SampleBasis.NOT_APPLICABLE: 1.0,
    SampleBasis.ESTIMATE: 0.7,
    # In a power-law market the mean sits far above the median — Gumroad's top 1%
    # take 99.5% of revenue, so "average earnings" describes almost nobody. A mean
    # is real data and still a bad planning number.
    SampleBasis.MEAN: 0.4,
    SampleBasis.TOP_DECILE: 0.15,
    SampleBasis.ANECDOTE: 0.10,
}

#: Bases that describe winners or averages-of-winners rather than a likely
#: outcome. Displayed, but never allowed to silently drive a projection.
UNSAFE_FOR_PLANNING = frozenset({SampleBasis.TOP_DECILE, SampleBasis.ANECDOTE, SampleBasis.MEAN})


class Observation(BaseModel, Generic[T]):
    """A single fact plus everything needed to audit it later."""

    model_config = ConfigDict(frozen=True)

    value: T | None
    source: Source
    method: str = Field(min_length=3, description="How it was obtained")
    observed_at: datetime = Field(default_factory=utcnow)
    confidence: Confidence
    basis: SampleBasis = SampleBasis.NOT_APPLICABLE
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
        """The correct result when a check ran and established nothing."""
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

    @property
    def is_planning_grade(self) -> bool:
        """Whether this number is sound enough to plan against.

        Top-decile figures, one-off anecdotes and means of skewed distributions
        are not. They may still be displayed, but they must never silently drive
        a projection.
        """
        return self.is_known and self.basis not in UNSAFE_FOR_PLANNING

    @property
    def weight(self) -> float:
        return BASIS_WEIGHT[self.basis] if self.is_known else 0.0

    def is_stale(self, ttl: timedelta) -> bool:
        return utcnow() - self.observed_at > ttl
