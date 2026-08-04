"""Which constraint is actually costing you the goal.

If every opportunity comes back BLOCKED, "nothing works" is a useless answer.
The useful answer is *which single constraint, if relaxed, opens the most* — and
by how much.

This re-runs the whole catalogue with one constraint loosened at a time and
reports what changes. It converts a dead end into a decision: the operator picks
which thing they are willing to give up, rather than being told no.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .feasibility import Verdict, assess
from .goal import Constraints, Exclusion, Goal
from .models import Opportunity


@dataclass(frozen=True)
class Relaxation:
    """One loosened constraint and what it buys."""

    label: str
    description: str
    cost_to_operator: str
    opportunities_opened: list[str]
    newly_viable_count: int

    @property
    def is_worthwhile(self) -> bool:
        return self.newly_viable_count > 0


def _actionable_keys(
    opportunities: list[Opportunity], goal: Goal, constraints: Constraints
) -> set[str]:
    return {
        o.key
        for o in opportunities
        if assess(o, goal, constraints).verdict in (Verdict.VIABLE, Verdict.MARGINAL)
    }


def analyse(
    opportunities: list[Opportunity],
    goal: Goal,
    constraints: Constraints,
) -> list[Relaxation]:
    """Report what each single relaxation would open up.

    Deliberately one at a time: relaxing everything at once tells you nothing
    about which sacrifice is actually buying the result.
    """
    baseline = _actionable_keys(opportunities, goal, constraints)
    results: list[Relaxation] = []

    def evaluate(
        label: str, description: str, cost: str, new_goal: Goal, new_constraints: Constraints
    ) -> None:
        opened = _actionable_keys(opportunities, new_goal, new_constraints) - baseline
        results.append(
            Relaxation(
                label=label,
                description=description,
                cost_to_operator=cost,
                opportunities_opened=sorted(opened),
                newly_viable_count=len(opened),
            )
        )

    # -- the target itself ----------------------------------------------
    for fraction, label in ((0.5, "half"), (0.2, "a fifth")):
        lowered = Goal(
            net_monthly_inr=goal.net_monthly_inr * fraction,
            horizon_months=goal.horizon_months,
        )
        evaluate(
            f"target ₹{lowered.net_monthly_inr:,.0f}/mo",
            f"aim for {label} the income, at least at first",
            "less money — but a smaller portfolio is reachable far sooner, and can compound",
            lowered,
            constraints,
        )

    # -- time ------------------------------------------------------------
    longer = Goal(net_monthly_inr=goal.net_monthly_inr, horizon_months=goal.horizon_months * 2)
    evaluate(
        f"{longer.horizon_months}-month horizon",
        "give it twice as long",
        "years of your life, and the risk that platforms change under you meanwhile",
        longer,
        constraints,
    )

    # -- attention at maturity -------------------------------------------
    for hours in (10.0, 20.0):
        evaluate(
            f"{hours:.0f} h/week at maturity",
            "accept ongoing upkeep rather than true hands-off",
            "it stops being passive income and becomes a part-time job that pays well",
            goal,
            replace(constraints, max_maturity_hours_per_week=hours),
        )

    # -- capital ----------------------------------------------------------
    for capital in (500_000.0, 2_000_000.0):
        evaluate(
            f"₹{capital:,.0f} capital",
            "raise or save more capital before starting",
            "delay, and real downside risk — capital you can lose, unlike time",
            goal,
            replace(constraints, capital_ceiling_inr=capital),
        )

    # -- exclusions --------------------------------------------------------
    relaxable = {
        Exclusion.CHASING_DEMAND: (
            "do some promotion or outreach",
            "the thing you most wanted to avoid — but it is the single biggest "
            "multiplier on every marketplace route",
        ),
        Exclusion.ON_CAMERA_OR_AUDIENCE: (
            "build an audience",
            "public visibility and a content treadmill, but it makes demand yours "
            "rather than the platform's",
        ),
        Exclusion.TEACHING_OR_COURSES: (
            "make educational products",
            "you said no — included only so the cost of that no is visible",
        ),
    }
    for exclusion, (description, cost) in relaxable.items():
        if exclusion not in constraints.exclusions:
            continue
        evaluate(
            f"allow: {exclusion.value.replace('_', ' ')}",
            description,
            cost,
            goal,
            replace(constraints, exclusions=constraints.exclusions - {exclusion}),
        )

    return sorted(results, key=lambda r: -r.newly_viable_count)


def summarise(relaxations: list[Relaxation]) -> str:
    worthwhile = [r for r in relaxations if r.is_worthwhile]
    if not worthwhile:
        return (
            "No single relaxation opens anything. Either the catalogue is too thin "
            "to judge, or the goal needs more than one constraint to move at once."
        )
    lines = ["Relaxing one constraint at a time:", ""]
    for r in worthwhile:
        lines.append(f"  {r.label} — opens {r.newly_viable_count}: {', '.join(r.opportunities_opened)}")
        lines.append(f"      {r.description}. Cost: {r.cost_to_operator}")
    return "\n".join(lines)
