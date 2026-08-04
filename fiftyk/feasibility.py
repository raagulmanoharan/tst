"""Elimination, with the arithmetic attached.

Most passive-income advice fails by being a list. A list is useless when the
binding constraint is capital or attention, because it keeps offering things you
cannot act on. So this module's job is to say **no**, and to show the sum that
produced the no — so the operator can check it rather than take it on faith.

A blocked opportunity stays in the catalogue with its reason. Deleting it just
means rediscovering it in six months.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .economics import Projection, capital_gap, project
from .goal import EXCLUSION_REASONS, Constraints, Exclusion, Goal
from .models import Opportunity


#: How far above the median participant the goal may sit before the plan is
#: really a lottery ticket. Someone has to be top-percentile, but *planning* to
#: be is not a plan. Five is deliberately generous.
MEDIAN_OUTPERFORMANCE_LIMIT = 5.0


class Verdict(str, Enum):
    VIABLE = "viable"                  # clears every gate
    MARGINAL = "marginal"              # clears the hard gates, fails a soft one
    BLOCKED = "blocked"                # fails a hard constraint; no amount of work fixes it
    NEEDS_EVIDENCE = "needs_evidence"  # not enough known to judge


@dataclass(frozen=True)
class Blocker:
    gate: str
    reason: str
    #: The sum behind the verdict, written out so it can be argued with.
    arithmetic: str | None = None


@dataclass(frozen=True)
class Assessment:
    opportunity_key: str
    verdict: Verdict
    blockers: list[Blocker]
    warnings: list[Blocker]
    projection: Projection | None
    #: Lower is better — build hours per rupee of durable monthly income.
    attention_price: float | None

    @property
    def is_actionable(self) -> bool:
        return self.verdict in (Verdict.VIABLE, Verdict.MARGINAL)


def assess(opportunity: Opportunity, goal: Goal, constraints: Constraints) -> Assessment:
    blockers: list[Blocker] = []
    warnings: list[Blocker] = []
    economics = opportunity.economics

    # -- Gate 1: how does demand arrive? --------------------------------
    if not constraints.allows(opportunity.demand_mechanism):
        blockers.append(
            Blocker(
                gate="demand_mechanism",
                reason=(
                    f"demand arrives via {opportunity.demand_mechanism.value.replace('_', ' ')}, "
                    f"and {EXCLUSION_REASONS[Exclusion.CHASING_DEMAND]}"
                ),
            )
        )

    # -- Gate 2: has a fatal assumption already been disproven? ---------
    # An assumption marked fatal and resolved False is a settled question. No
    # amount of favourable economics rescues an opportunity you cannot take part
    # in at all.
    for assumption in opportunity.assumptions:
        if assumption.fatal_if_false and assumption.resolved is False:
            blockers.append(
                Blocker(
                    gate="disproven_assumption",
                    reason=f"tested and false: {assumption.claim}",
                    arithmetic=assumption.why_it_matters,
                )
            )

    # -- Gate 3: capital ------------------------------------------------
    gap = capital_gap(economics, constraints)
    if gap is None:
        warnings.append(
            Blocker("capital", "capital requirement not established", None)
        )
    elif gap > 0:
        required = economics.capital_required_inr.value or 0.0
        multiple = required / constraints.capital_ceiling_inr if constraints.capital_ceiling_inr else float("inf")
        blockers.append(
            Blocker(
                gate="capital",
                reason="needs more capital than is available",
                arithmetic=(
                    f"₹{required:,.0f} required vs ₹{constraints.capital_ceiling_inr:,.0f} available "
                    f"— short by ₹{gap:,.0f} ({multiple:.1f}x over)"
                ),
            )
        )

    # -- Gate 4: what does a typical participant actually earn? ---------
    # Checked before the listing model, because if the median participant earns
    # a fraction of the goal, the portfolio arithmetic is beside the point.
    median = economics.median_seller_net_monthly_inr
    if median.is_known:
        median_value = median.value or 0.0
        if median_value <= 0:
            # A documented zero is the strongest block available, not a missing
            # value. Treating it as "unknown" would let a dead category through.
            blockers.append(
                Blocker(
                    gate="median_outcome",
                    reason="the typical participant here earns nothing at all",
                    arithmetic=(
                        f"median participant nets ₹0/mo against a goal of "
                        f"₹{goal.net_monthly_inr:,.0f}/mo — {median.note or median.method}"
                    ),
                )
            )
        else:
            multiple = goal.net_monthly_inr / median_value
            if multiple > MEDIAN_OUTPERFORMANCE_LIMIT:
                blockers.append(
                    Blocker(
                        gate="median_outcome",
                        reason=(
                            "reaching the goal here means being a top-percentile participant, "
                            "which is an outcome, not a plan"
                        ),
                        arithmetic=(
                            f"median participant nets ₹{median_value:,.0f}/mo; the goal is "
                            f"₹{goal.net_monthly_inr:,.0f}/mo — {multiple:.0f}x the median"
                        ),
                    )
                )
            elif not median.is_planning_grade:
                warnings.append(
                    Blocker(
                        gate="median_outcome",
                        reason=(
                            f"the only earnings figure available is a {median.basis.value}, which "
                            "overstates the typical outcome in a power-law market"
                        ),
                        arithmetic=(
                            f"₹{median_value:,.0f}/mo reported; goal is {multiple:.1f}x that, "
                            "but the true median is lower than the figure used"
                        ),
                    )
                )
    else:
        warnings.append(
            Blocker(
                "median_outcome",
                "what a typical participant earns here has not been established — "
                "the most important number about any marketplace",
            )
        )

    # -- Gate 5: is there enough to model at all? -----------------------
    if not economics.is_modellable:
        gaps: list[Blocker] = []
        needs_research = economics.missing_market_facts()
        needs_you = economics.missing_operator_estimates()
        if needs_research:
            gaps.append(
                Blocker(
                    "needs_research",
                    f"no published figure found for: {', '.join(needs_research)}",
                )
            )
        if needs_you:
            gaps.append(
                Blocker(
                    "needs_your_estimate",
                    f"only you can answer these — how fast you work: {', '.join(needs_you)}. "
                    f"Set them with: fiftyk estimate {opportunity.key}",
                )
            )
        return Assessment(
            opportunity_key=opportunity.key,
            verdict=Verdict.BLOCKED if blockers else Verdict.NEEDS_EVIDENCE,
            blockers=blockers,
            warnings=warnings + gaps,
            projection=None,
            attention_price=None,
        )

    projection = project(economics, goal, constraints)

    # -- Gate 6: is the goal reachable at all? --------------------------
    if not projection.reachable:
        blockers.append(
            Blocker(
                gate="reachability",
                reason="the portfolio decays faster than it can be built",
                arithmetic=(
                    f"{projection.listings_needed:,.0f} {economics.listing_name}s needed, but the "
                    f"portfolio settles at ~{projection.equilibrium_portfolio:,.0f} "
                    f"({projection.build_rate_per_year:,.0f} built/year vs "
                    f"{(economics.annual_decay.value or 0):.0%} annual decay)"
                ),
            )
        )

    # -- Gate 7: can it ever be hands-off? ------------------------------
    if projection.reachable and not projection.hands_off:
        blockers.append(
            Blocker(
                gate="passivity",
                reason="holding this at goal size is ongoing full-time-ish work",
                arithmetic=(
                    f"{projection.maintenance_hours_per_week:.1f} h/week forever vs a "
                    f"{constraints.max_maturity_hours_per_week:.0f} h/week ceiling"
                ),
            )
        )

    # -- Gate 8: does it fit the horizon? -------------------------------
    if projection.months_to_goal is not None and projection.months_to_goal > goal.horizon_months:
        warnings.append(
            Blocker(
                gate="horizon",
                reason="reachable, but slower than the target horizon",
                arithmetic=(
                    f"~{projection.months_to_goal:.0f} months to ₹{goal.net_monthly_inr:,.0f}/mo "
                    f"vs a {goal.horizon_months}-month horizon"
                ),
            )
        )

    # -- Gate 9: are the numbers good enough to bet on? -----------------
    if not economics.is_planning_grade:
        weak = sorted(
            name
            for name, obs in economics.known_fields().items()
            if obs.is_known and not obs.is_planning_grade
        )
        warnings.append(
            Blocker(
                gate="evidence_quality",
                reason=(
                    "projection rests on top-decile or anecdotal figures, which describe "
                    f"winners rather than typical outcomes: {', '.join(weak)}"
                ),
            )
        )

    if blockers:
        verdict = Verdict.BLOCKED
    elif warnings:
        verdict = Verdict.MARGINAL
    else:
        verdict = Verdict.VIABLE

    return Assessment(
        opportunity_key=opportunity.key,
        verdict=verdict,
        blockers=blockers,
        warnings=warnings,
        projection=projection,
        attention_price=projection.hours_per_monthly_rupee,
    )


def rank(assessments: list[Assessment]) -> list[Assessment]:
    """Cheapest durable income first.

    Sorted by attention price — build hours per rupee of monthly income — because
    with capital fixed and near zero, attention is the only currency being spent.
    """
    actionable = [a for a in assessments if a.is_actionable and a.attention_price is not None]
    return sorted(
        actionable,
        key=lambda a: (a.verdict is not Verdict.VIABLE, a.attention_price),
    )
