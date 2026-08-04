"""The goal and the constraints every verdict is computed against.

Nothing in this system is ranked in the abstract. An opportunity is not "good"
or "bad" — it is reachable or unreachable *for this operator, with this capital,
in this time, under these exclusions*. All of that lives here.

Change these values and every verdict in the system changes with them. That is
the intended behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

#: Rough conversion for reading foreign-denominated research. Not a live rate —
#: precision here would be false precision given everything else is an estimate.
USD_TO_INR = 84.0


class DemandMechanism(str, Enum):
    """How a customer arrives.

    This is the axis that matters most for this operator, who will not chase
    demand under any circumstances. Everything is classified by who does the
    finding: the platform, or you.
    """

    MARKETPLACE_SEARCH = "marketplace_search"    # buyer searches Gumroad/Envato/Etsy
    APP_STORE_SEARCH = "app_store_search"        # buyer browses an app or plugin store
    WEB_SEARCH = "web_search"                    # organic search to a site you own
    STOREFRONT_CURATION = "storefront_curation"  # platform editorial or algorithmic featuring
    WORD_OF_MOUTH = "word_of_mouth"              # existing users bring new ones
    PERSONAL_AUDIENCE = "personal_audience"      # you must build and feed a following
    OUTBOUND_SALES = "outbound_sales"            # you contact people and convince them
    PAID_ACQUISITION = "paid_acquisition"        # you buy traffic


#: Demand must arrive on its own. These are the mechanisms where the platform
#: does the finding.
PULL_MECHANISMS = frozenset(
    {
        DemandMechanism.MARKETPLACE_SEARCH,
        DemandMechanism.APP_STORE_SEARCH,
        DemandMechanism.WEB_SEARCH,
        DemandMechanism.STOREFRONT_CURATION,
        DemandMechanism.WORD_OF_MOUTH,
    }
)


class Exclusion(str, Enum):
    """Categories ruled out up front, so nothing keeps recommending them."""

    CHASING_DEMAND = "chasing_demand"
    ON_CAMERA_OR_AUDIENCE = "on_camera_or_audience"
    TEACHING_OR_COURSES = "teaching_or_courses"
    SPECULATION = "speculation"
    SUBSCRIPTION_SOFTWARE = "subscription_software"


EXCLUSION_REASONS: dict[Exclusion, str] = {
    Exclusion.CHASING_DEMAND: (
        "demand has to arrive on its own — no outreach, no demos, no convincing anyone"
    ),
    Exclusion.ON_CAMERA_OR_AUDIENCE: (
        "no appearing on camera and no building or feeding a personal following"
    ),
    Exclusion.TEACHING_OR_COURSES: "no courses, tutorials or educational products",
    Exclusion.SPECULATION: "no trading, crypto or market-dependent income — that is variance, not income",
    Exclusion.SUBSCRIPTION_SOFTWARE: "no subscription software business",
}


@dataclass(frozen=True)
class Goal:
    """What counts as done."""

    net_monthly_inr: float = 50_000.0
    horizon_months: int = 24

    def annual_inr(self) -> float:
        return self.net_monthly_inr * 12


@dataclass(frozen=True)
class Constraints:
    """What the operator can actually bring to bear."""

    capital_ceiling_inr: float = 100_000.0

    #: Hours a week available during the build phase — "heavy now".
    build_hours_per_week: float = 25.0

    #: The most the operator is willing to spend once it is running. Above this
    #: an opportunity is a job, not passive income, however well it pays.
    max_maturity_hours_per_week: float = 5.0

    exclusions: frozenset[Exclusion] = field(
        default_factory=lambda: frozenset(
            {
                Exclusion.CHASING_DEMAND,
                Exclusion.ON_CAMERA_OR_AUDIENCE,
                Exclusion.TEACHING_OR_COURSES,
                Exclusion.SPECULATION,
                Exclusion.SUBSCRIPTION_SOFTWARE,
            }
        )
    )

    #: What the operator can already do well. Used to shorten build estimates,
    #: never to justify an opportunity that fails on economics.
    skills: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {"frontend", "javascript", "creative_coding", "graphics", "webgl", "python"}
        )
    )

    base_city: str = "Bangalore"

    def allows(self, mechanism: DemandMechanism) -> bool:
        if Exclusion.CHASING_DEMAND in self.exclusions and mechanism not in PULL_MECHANISMS:
            return False
        if Exclusion.ON_CAMERA_OR_AUDIENCE in self.exclusions:
            if mechanism is DemandMechanism.PERSONAL_AUDIENCE:
                return False
        return True


@dataclass(frozen=True)
class Profile:
    """Goal plus constraints — the lens everything is judged through."""

    goal: Goal = field(default_factory=Goal)
    constraints: Constraints = field(default_factory=Constraints)

    @classmethod
    def default(cls) -> Profile:
        return cls()
