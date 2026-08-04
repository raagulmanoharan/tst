"""Projection maths.

The important thing this module does is refuse to model a decaying portfolio by
naive division. If you need 500 listings and can build 100 a year, the naive
answer is "five years". The real answer depends on decay, because you are losing
listings while you build.

A portfolio built at rate `B` listings/year and decaying at fraction `d`/year
follows dP/dt = B − d·P, which settles at an **equilibrium of P* = B/d**. If the
portfolio you need is larger than that equilibrium, the goal is not slow — it is
**unreachable at any time horizon**, and no amount of persistence changes it.
That result is invisible to division and is exactly what an operator needs to
know before spending two years finding out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .goal import Constraints, Goal
from .models import Economics

WEEKS_PER_YEAR = 52.0
MONTHS_PER_YEAR = 12.0


@dataclass(frozen=True)
class Projection:
    """What the economics imply, given a goal and a set of constraints."""

    listings_needed: float
    build_rate_per_year: float
    #: Largest portfolio sustainable at this build rate against this decay.
    #: Infinite when nothing decays.
    equilibrium_portfolio: float
    reachable: bool
    months_to_goal: float | None          # None when unreachable
    total_build_hours: float
    #: Hours a week needed *forever* to hold the portfolio at goal size —
    #: replacing what decays, plus fixed upkeep.
    maintenance_hours_per_week: float
    hands_off: bool
    #: Build hours per rupee of durable monthly income. The attention price.
    hours_per_monthly_rupee: float
    notes: list[str]


def net_monthly_at(economics: Economics, listings: float) -> float:
    """Monthly net from a portfolio of `listings` items."""
    per_unit = economics.net_per_unit_inr.value or 0.0
    units = economics.units_per_listing_per_month.value or 0.0
    return listings * units * per_unit


def project(economics: Economics, goal: Goal, constraints: Constraints) -> Projection:
    """Model this opportunity against the goal. Assumes `economics.is_modellable`."""
    notes: list[str] = []

    per_unit = economics.net_per_unit_inr.value or 0.0
    units_per_listing = economics.units_per_listing_per_month.value or 0.0
    hours_per_listing = economics.build_hours_per_listing.value or 0.0
    decay = economics.annual_decay.value or 0.0
    fixed_upkeep = (
        economics.fixed_upkeep_hours_per_week.value
        if economics.fixed_upkeep_hours_per_week.is_known
        else 0.0
    ) or 0.0

    monthly_per_listing = units_per_listing * per_unit
    if monthly_per_listing <= 0:
        return Projection(
            listings_needed=math.inf, build_rate_per_year=0.0, equilibrium_portfolio=0.0,
            reachable=False, months_to_goal=None, total_build_hours=math.inf,
            maintenance_hours_per_week=math.inf, hands_off=False,
            hours_per_monthly_rupee=math.inf,
            notes=["a listing earns nothing per month — the goal is unreachable by definition"],
        )

    listings_needed = goal.net_monthly_inr / monthly_per_listing

    if hours_per_listing <= 0:
        build_rate = math.inf
        notes.append("build effort recorded as zero — treat the timeline as optimistic")
    else:
        build_rate = (constraints.build_hours_per_week * WEEKS_PER_YEAR) / hours_per_listing

    equilibrium = math.inf if decay <= 0 else build_rate / decay

    # Reachability, then time.
    if decay <= 0:
        reachable = True
        years = listings_needed / build_rate if build_rate > 0 else math.inf
        months_to_goal = years * MONTHS_PER_YEAR
    elif listings_needed >= equilibrium:
        reachable = False
        months_to_goal = None
        notes.append(
            f"at {build_rate:.0f} {economics.listing_name}s a year against {decay:.0%} annual decay, "
            f"the portfolio settles at ~{equilibrium:.0f} — but {listings_needed:.0f} are needed. "
            f"This never gets there, however long you work."
        )
    else:
        reachable = True
        # P(t) = (B/d)(1 - e^(-dt))  =>  t = -(1/d)·ln(1 - P·d/B)
        years = -(1.0 / decay) * math.log(1.0 - (listings_needed * decay / build_rate))
        months_to_goal = years * MONTHS_PER_YEAR

    if months_to_goal is not None:
        months_to_goal += economics.months_to_first_revenue.value or 0.0

    total_build_hours = listings_needed * hours_per_listing

    # Holding the portfolio steady means replacing what decays, forever.
    replacements_per_year = listings_needed * decay
    maintenance_hours_per_week = (
        replacements_per_year * hours_per_listing / WEEKS_PER_YEAR
    ) + fixed_upkeep

    hands_off = maintenance_hours_per_week <= constraints.max_maturity_hours_per_week
    if reachable and not hands_off:
        notes.append(
            f"holding this at goal size costs about {maintenance_hours_per_week:.0f} h/week forever "
            f"(replacing {replacements_per_year:.0f} {economics.listing_name}s a year). "
            f"That is a job, not passive income."
        )

    hours_per_monthly_rupee = (
        total_build_hours / goal.net_monthly_inr if goal.net_monthly_inr else math.inf
    )

    return Projection(
        listings_needed=listings_needed,
        build_rate_per_year=build_rate,
        equilibrium_portfolio=equilibrium,
        reachable=reachable,
        months_to_goal=months_to_goal,
        total_build_hours=total_build_hours,
        maintenance_hours_per_week=maintenance_hours_per_week,
        hands_off=hands_off,
        hours_per_monthly_rupee=hours_per_monthly_rupee,
        notes=notes,
    )


def capital_gap(economics: Economics, constraints: Constraints) -> float | None:
    """How far the required capital exceeds what is available. None when unknown."""
    required = economics.capital_required_inr
    if not required.is_known:
        return None
    return max(0.0, (required.value or 0.0) - constraints.capital_ceiling_inr)


def yield_capital_needed(goal: Goal, annual_yield: float) -> float:
    """Capital needed to hit the goal from yield alone, at a given annual rate.

    Used to state plainly why capital-yield routes are closed rather than
    asserting it.
    """
    if annual_yield <= 0:
        return math.inf
    return goal.annual_inr() / annual_yield
