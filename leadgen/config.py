"""Market, category and budget configuration.

Everything here is a deliberate, reviewable choice rather than a default that
crept in. Category selection in particular is research-backed — see the
`EXCLUDED_CATEGORIES` note before adding anything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Markets
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class City:
    name: str
    # Approximate municipal bounding box, used only to generate search centres.
    # Widen or narrow freely; this is a search parameter, not a claim about
    # administrative boundaries.
    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float
    active: bool
    note: str = ""

    def grid(self, step_km: float = 4.0) -> list[tuple[float, float]]:
        """Search centres covering the box, spaced roughly `step_km` apart."""
        # 1 degree latitude is ~111 km everywhere; longitude shrinks with
        # latitude, but at ~13 degrees N the cosine correction is under 3%, so a
        # flat divisor keeps the grid slightly dense rather than leaving gaps.
        step_deg = step_km / 111.0
        centres: list[tuple[float, float]] = []
        lat = self.lat_min
        while lat <= self.lat_max:
            lng = self.lng_min
            while lng <= self.lng_max:
                centres.append((round(lat, 5), round(lng, 5)))
                lng += step_deg
            lat += step_deg
        return centres


CITIES: dict[str, City] = {
    "bangalore": City(
        name="Bangalore",
        lat_min=12.83, lat_max=13.14, lng_min=77.46, lng_max=77.78,
        active=True,
        note="Phase 1. Walk-in radius — the highest-converting, lowest-risk channel.",
    ),
    "chennai": City(
        name="Chennai",
        lat_min=12.83, lat_max=13.23, lng_min=80.15, lng_max=80.32,
        active=False,
        note="Phase 2. Tamil advantage; email plus periodic trips.",
    ),
    "pondicherry": City(
        name="Pondicherry",
        lat_min=11.88, lat_max=12.03, lng_min=79.75, lng_max=79.85,
        active=False,
        note="Phase 3. Hospitality niche only — customers are out-of-state and foreign.",
    ),
    "hyderabad": City(
        name="Hyderabad",
        lat_min=17.29, lat_max=17.55, lng_min=78.32, lng_max=78.60,
        active=False,
        note="Parked. No Telugu — weakest of the four markets for this operator.",
    ),
}


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CategoryProbe:
    """A search term plus why it is worth spending calls on.

    `rationale` exists so that a category can be argued with later rather than
    inherited unquestioned.
    """

    key: str
    query: str
    rationale: str
    ticket_size: str  # "high" | "medium" — informs whether a build fee is trivial to them


CANDIDATE_CATEGORIES: tuple[CategoryProbe, ...] = (
    # Healthcare — high lifetime value, heavily researched, trust-gated.
    CategoryProbe("dental", "dental clinic", "Patients research before booking; high per-patient value.", "high"),
    CategoryProbe("dermatology", "dermatology clinic", "Elective, appearance-driven, price-insensitive.", "high"),
    CategoryProbe("fertility", "fertility clinic IVF", "Very high ticket; patients research for months.", "high"),
    CategoryProbe("physiotherapy", "physiotherapy clinic", "Repeat visits; local search driven.", "medium"),
    CategoryProbe("veterinary", "veterinary clinic", "Trust-gated; owners research before first visit.", "medium"),
    # Professional services — credibility-driven and email-native.
    CategoryProbe("chartered_accountant", "chartered accountant firm", "Credibility purchase; email-native.", "high"),
    CategoryProbe("law_firm", "law firm", "Trust-gated, high ticket, reputation sensitive.", "high"),
    CategoryProbe("architect", "architecture firm", "Portfolio-driven — a bad site actively costs them work.", "high"),
    CategoryProbe("interior_design", "interior design studio", "Visual purchase; portfolio is the product.", "high"),
    # Home improvement — considered purchase, high contract value.
    CategoryProbe("modular_kitchen", "modular kitchen showroom", "High contract value; heavily compared.", "high"),
    CategoryProbe("packers_movers", "packers and movers", "Out-of-area customers who cannot walk in.", "medium"),
    # Education — parents research extensively.
    CategoryProbe("coaching", "coaching institute", "Parents research; admission cycles create urgency.", "medium"),
    CategoryProbe("preschool", "preschool", "Parents research heavily before enrolling.", "high"),
    # Hospitality — the one segment whose customers genuinely cannot substitute
    # a WhatsApp catalogue, because they are out-of-state or foreign.
    CategoryProbe("boutique_hotel", "boutique hotel", "Out-of-state and foreign guests search before booking.", "high"),
    CategoryProbe("homestay", "homestay", "Same as above; direct booking avoids OTA commission.", "medium"),
)

#: Research-backed dead ends. One operator spent a month on restaurants with
#: hand-built demos and got zero replies. Google Business Profile, Instagram and
#: WhatsApp Business already serve these categories completely.
EXCLUDED_CATEGORIES: frozenset[str] = frozenset(
    {"restaurant", "cafe", "salon", "kirana", "grocery", "gym", "fast_food", "bakery"}
)


# --------------------------------------------------------------------------
# API budget — India price list free tiers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SkuBudget:
    sku: str
    free_per_month: int
    note: str


#: India has its own, much cheaper Places price list with per-SKU monthly free
#: caps. The old shared $200 credit is retired.
SKU_BUDGETS: dict[str, SkuBudget] = {
    "text_search_pro": SkuBudget("text_search_pro", 35_000, "Discovery sweeps."),
    "place_details_enterprise": SkuBudget(
        "place_details_enterprise", 7_000, "websiteUri/rating/userRatingCount — the scarce one."
    ),
    "place_details_essentials": SkuBudget(
        "place_details_essentials", 1_000_000_000, "IDs only; unlimited and free."
    ),
}

#: Stop well before the cliff so a long run cannot silently start costing money.
BUDGET_WARN_RATIO = 0.80
BUDGET_STOP_RATIO = 0.95


@dataclass(frozen=True)
class Operator:
    """Who the outreach is from.

    Deliberately has no defaults. Inventing a name, domain or phone number would
    be fabricated data in the one artefact that reaches a stranger — so drafting
    refuses to run until these are set. See CLAUDE.md rule 2.
    """

    name: str
    site: str
    email: str
    phone: str | None = None
    city: str = "Bangalore"

    @classmethod
    def from_env(cls) -> Operator | None:
        name = os.environ.get("OPERATOR_NAME")
        site = os.environ.get("OPERATOR_SITE")
        email = os.environ.get("OPERATOR_EMAIL")
        if not (name and site and email):
            return None
        return cls(
            name=name,
            site=site,
            email=email,
            phone=os.environ.get("OPERATOR_PHONE"),
            city=os.environ.get("OPERATOR_CITY", "Bangalore"),
        )


MISSING_OPERATOR_HELP = (
    "Outreach drafting needs OPERATOR_NAME, OPERATOR_SITE and OPERATOR_EMAIL in .env "
    "(OPERATOR_PHONE optional). These appear verbatim in messages to strangers, so this "
    "system will not guess them."
)


@dataclass
class Settings:
    api_key: str | None = field(default=None)
    db_path: str = "leads.db"
    request_timeout_s: float = 15.0
    user_agent: str = "leadgen/0.1 (+solo freelance web developer; contact via site)"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            api_key=os.environ.get("GOOGLE_MAPS_API_KEY"),
            db_path=os.environ.get("LEADGEN_DB", "leads.db"),
        )


def active_cities() -> list[City]:
    return [c for c in CITIES.values() if c.active]
