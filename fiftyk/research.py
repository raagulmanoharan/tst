"""Research work orders.

There is no Anthropic API key in this environment, so this module does not
pretend to run research itself. It does the part that is actually hard to do
well by hand: work out **what is worth finding out next**, and emit it as a
brief precise enough to hand to a researcher (human or agent) without further
explanation.

Priority is by decision value, not by how many gaps a row has. A missing figure
on an already-blocked opportunity is worth nothing; the median-earnings figure on
a live candidate can settle the whole question.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from .feasibility import Verdict, assess
from .goal import Constraints, Goal
from .models import Opportunity
from .provenance import utcnow

#: How long a platform economics figure stays trustworthy. Splits and algorithms
#: change fast — Envato re-cut its seller share with months of notice.
FIGURE_TTL = timedelta(days=120)


@dataclass(frozen=True)
class ResearchItem:
    opportunity_key: str
    field: str
    question: str
    why_it_matters: str
    priority: int  # 1 = highest

    def as_line(self) -> str:
        return f"[P{self.priority}] {self.opportunity_key}.{self.field} — {self.question}"


#: What each field actually means, phrased as a question a researcher can act on.
FIELD_QUESTIONS: dict[str, str] = {
    "median_seller_net_monthly_inr": (
        "What does a MEDIAN participant net per month? Aggregate or platform-published only — "
        "reject success stories and self-selected surveys."
    ),
    "net_per_unit_inr": "What does a typical sale net after platform cut and withholding?",
    "units_per_listing_per_month": "How many sales does a typical listing make per month?",
    "annual_decay": (
        "How much revenue does a static listing lose per year? Look for ranking decay, "
        "platform traffic trends and forced-update policies."
    ),
    "months_to_first_revenue": "How long from first upload to first payout?",
    "capital_required_inr": "What must be paid upfront — fees, accounts, tooling?",
}


def _stale_fields(opportunity: Opportunity) -> list[str]:
    return sorted(
        name
        for name, obs in opportunity.economics.known_fields().items()
        if obs.is_known and obs.is_stale(FIGURE_TTL)
    )


def brief(
    opportunities: list[Opportunity], goal: Goal, constraints: Constraints
) -> list[ResearchItem]:
    """What to find out next, ordered by how much the answer would change."""
    items: list[ResearchItem] = []

    for opportunity in opportunities:
        assessment = assess(opportunity, goal, constraints)

        # Nothing found about a blocked opportunity changes the verdict — the
        # block is structural. Skip rather than generate busywork.
        if assessment.verdict is Verdict.BLOCKED:
            continue

        economics = opportunity.economics
        for field in economics.missing_market_facts():
            # The median is the one figure that can settle a candidate outright.
            priority = 1 if field == "median_seller_net_monthly_inr" else 2
            items.append(
                ResearchItem(
                    opportunity_key=opportunity.key,
                    field=field,
                    question=FIELD_QUESTIONS.get(field, f"Establish {field}."),
                    why_it_matters=(
                        "decides whether this is viable at all"
                        if priority == 1
                        else "needed before the goal can be modelled"
                    ),
                    priority=priority,
                )
            )

        for field in _stale_fields(opportunity):
            items.append(
                ResearchItem(
                    opportunity_key=opportunity.key,
                    field=field,
                    question=f"Re-check {field}; the stored figure is over {FIGURE_TTL.days} days old.",
                    why_it_matters="platform economics change without notice",
                    priority=3,
                )
            )

        for assumption in opportunity.open_assumptions:
            if assumption.fatal_if_false:
                items.append(
                    ResearchItem(
                        opportunity_key=opportunity.key,
                        field="assumption",
                        question=f"Is this true: {assumption.claim}",
                        why_it_matters=assumption.why_it_matters,
                        priority=1,
                    )
                )

    return sorted(items, key=lambda i: (i.priority, i.opportunity_key, i.field))


def format_brief(items: list[ResearchItem]) -> str:
    if not items:
        return "Nothing worth researching — every open candidate is fully modelled."

    lines = [
        f"{len(items)} open questions, highest value first.",
        "",
        "Answer these and write them back with `fiftyk record`, or hand this brief",
        "to a research agent. Every answer needs a source URL — unsourced figures",
        "are rejected by the schema.",
        "",
    ]
    current = None
    for item in items:
        if item.opportunity_key != current:
            current = item.opportunity_key
            lines.append(f"\n{current}")
        lines.append(f"  [P{item.priority}] {item.field}")
        lines.append(f"        {item.question}")
        lines.append(f"        why: {item.why_it_matters}")
    return "\n".join(lines)


def staleness_report(opportunities: list[Opportunity]) -> dict[str, list[str]]:
    """Which stored figures have aged past the point of being trustworthy."""
    now = utcnow()
    report: dict[str, list[str]] = {}
    for opportunity in opportunities:
        stale = _stale_fields(opportunity)
        if stale:
            report[opportunity.key] = stale
    return report
