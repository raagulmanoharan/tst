"""Opportunities as economics, not ideas.

An "idea" is not a candidate here. To enter the catalogue an opportunity has to
state what a unit is, what one nets, how many sell, how long one takes to build,
and how fast the whole thing decays without new work. Anything unstated is
`UNVERIFIED` — never a plausible-looking guess.

The decay field is the one that decides most verdicts. A portfolio that loses
30% of its revenue a year is not passive income; it is a treadmill with a
salary, and the engine computes exactly how fast you have to run.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field

from .goal import DemandMechanism
from .provenance import Observation, utcnow


class Stage(str, Enum):
    CANDIDATE = "candidate"      # in the catalogue, not yet examined
    RESEARCHING = "researching"  # gathering evidence
    DIP_CHECK = "dip_check"      # running a cheap experiment against the riskiest assumption
    COMMITTED = "committed"      # chosen; building
    LIVE = "live"                # earning
    KILLED = "killed"            # abandoned, with a recorded reason
    BLOCKED = "blocked"          # fails a hard constraint; kept so it is not rediscovered


class Economics(BaseModel):
    """The numbers that decide whether an opportunity can reach the goal.

    A "unit" is whatever this opportunity sells once: one asset licence, one app
    download, one book, one template. A "listing" is one thing in the portfolio
    that produces units repeatedly.
    """

    unit_name: str = Field(description="What one sale is, in plain words")
    listing_name: str = Field(description="What one portfolio item is, in plain words")

    capital_required_inr: Observation[float]

    #: What a *median* participant on this platform actually nets per month.
    #: The most decision-relevant number there is, and usually the most damning:
    #: it is directly comparable to the goal, and in power-law markets it is a
    #: rounding error next to it. Kept separate from the listing model because
    #: platforms publish per-seller data, not per-listing data.
    median_seller_net_monthly_inr: Observation[float]

    #: What actually reaches the operator's bank after platform cut and withholding.
    net_per_unit_inr: Observation[float]
    #: Median sales per listing per month. Median, not the winners.
    units_per_listing_per_month: Observation[float]
    build_hours_per_listing: Observation[float]
    months_to_first_revenue: Observation[float]
    #: Fraction of revenue a static portfolio loses each year. 0.0 means a
    #: listing earns forever untouched; 1.0 means it is worthless after a year.
    annual_decay: Observation[float]
    #: Hours a week of unavoidable upkeep at goal scale, excluding the
    #: replacement work implied by decay — that is computed, not stated.
    fixed_upkeep_hours_per_week: Observation[float]

    #: Fields nobody publishes because they are not market facts — they are the
    #: operator's judgement about their own speed and tolerance. Keeping these
    #: separate matters: "no research exists" and "you haven't told me how fast
    #: you work" are different problems with different fixes, and conflating
    #: them leaves every opportunity stuck at NEEDS_EVIDENCE forever.
    OPERATOR_ESTIMABLE: ClassVar[frozenset[str]] = frozenset(
        {"build_hours_per_listing", "fixed_upkeep_hours_per_week"}
    )

    def known_fields(self) -> dict[str, Observation]:
        return {
            name: getattr(self, name)
            for name in type(self).model_fields
            if isinstance(getattr(self, name), Observation)
        }

    def missing_operator_estimates(self) -> list[str]:
        """Gaps only the operator can close."""
        return sorted(
            name
            for name, obs in self.known_fields().items()
            if name in self.OPERATOR_ESTIMABLE and not obs.is_known
        )

    def missing_market_facts(self) -> list[str]:
        """Gaps that need research."""
        return sorted(
            name
            for name, obs in self.known_fields().items()
            if name not in self.OPERATOR_ESTIMABLE and not obs.is_known
        )

    @property
    def is_modellable(self) -> bool:
        """Whether enough is known to project anything at all."""
        required = (
            self.net_per_unit_inr,
            self.units_per_listing_per_month,
            self.build_hours_per_listing,
            self.annual_decay,
        )
        return all(o.is_known for o in required)

    @property
    def is_planning_grade(self) -> bool:
        """Whether the numbers are sound enough to bet two years on.

        Distinct from `is_modellable`: a projection built on top-decile figures
        computes fine and means nothing.
        """
        return self.is_modellable and all(
            o.is_planning_grade for o in self.known_fields().values() if o.is_known
        )


class Assumption(BaseModel):
    """Something that must be true for this to work, stated so it can be tested.

    Ranked by damage rather than likelihood: the assumption worth checking first
    is the one whose failure is fatal, not the one most likely to be wrong.
    """

    claim: str
    why_it_matters: str
    fatal_if_false: bool = False
    evidence: list[Observation] = Field(default_factory=list)
    resolved: bool | None = None  # None = still open

    @property
    def is_open(self) -> bool:
        return self.resolved is None


class DipCheck(BaseModel):
    """A cheap, time-boxed experiment against the riskiest assumption.

    Kill criteria are recorded *before* the experiment runs. Deciding what would
    change your mind after you have sunk two weekends into something is how
    people talk themselves into bad bets.
    """

    tests_assumption: str
    method: str = Field(description="What you will actually do")
    time_box_hours: float
    cost_inr: float = 0.0
    kill_criteria: list[str] = Field(min_length=1)
    started_on: date | None = None
    finished_on: date | None = None
    result: str | None = None
    passed: bool | None = None

    @property
    def is_complete(self) -> bool:
        return self.passed is not None


class MonthlyActual(BaseModel):
    """What really happened in one month. The correction signal."""

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    net_inr: float
    hours_spent: float
    listings_live: int
    units_sold: int | None = None
    note: str | None = None


class Opportunity(BaseModel):
    """One way of reaching the goal, with everything needed to judge it."""

    key: str
    name: str
    category: str
    summary: str
    demand_mechanism: DemandMechanism
    economics: Economics

    stage: Stage = Stage.CANDIDATE
    assumptions: list[Assumption] = Field(default_factory=list)
    dip_checks: list[DipCheck] = Field(default_factory=list)

    #: Populated when committed.
    actuals: list[MonthlyActual] = Field(default_factory=list)
    capital_deployed_inr: float = 0.0
    hours_invested: float = 0.0
    killed_reason: str | None = None

    fit_notes: list[str] = Field(default_factory=list)
    first_seen_at: datetime = Field(default_factory=utcnow)
    last_researched_at: datetime | None = None

    @property
    def open_assumptions(self) -> list[Assumption]:
        return [a for a in self.assumptions if a.is_open]

    @property
    def riskiest_open_assumption(self) -> Assumption | None:
        """Fatal-if-false first, since that is what a dip-check should attack."""
        openish = self.open_assumptions
        if not openish:
            return None
        return sorted(openish, key=lambda a: (not a.fatal_if_false,))[0]

    @property
    def latest_actual(self) -> MonthlyActual | None:
        return sorted(self.actuals, key=lambda a: a.month)[-1] if self.actuals else None

    def observations(self) -> dict[str, Observation]:
        found = {f"economics.{k}": v for k, v in self.economics.known_fields().items()}
        for i, assumption in enumerate(self.assumptions):
            for j, evidence in enumerate(assumption.evidence):
                found[f"assumptions[{i}].evidence[{j}]"] = evidence
        return found
