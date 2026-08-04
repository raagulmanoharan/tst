"""The seeded catalogue.

Every figure here is sourced or `UNVERIFIED`. Nothing is estimated to fill a
gap — a plausible-looking number would silently drive a two-year decision. Where
research found no credible median, that is recorded as an absence, because "no
platform publishes this and every blog that claims to is fabricating" is itself
a finding.

Researched 2026-08-04. Platform economics move fast; `fiftyk research` reports
what has gone stale.
"""

from __future__ import annotations

from .goal import USD_TO_INR, DemandMechanism
from .models import Assumption, Economics, Opportunity
from .provenance import Confidence, Observation, SampleBasis, Source


def usd(amount: float) -> float:
    return amount * USD_TO_INR


def fact(
    value: float,
    source: Source,
    method: str,
    url: str,
    basis: SampleBasis = SampleBasis.NOT_APPLICABLE,
    note: str | None = None,
) -> Observation[float]:
    return Observation[float](
        value=value,
        source=source,
        method=method,
        confidence=Confidence.VERIFIED,
        basis=basis,
        evidence_url=url,
        note=note,
    )


def unknown(method: str, note: str, url: str | None = None) -> Observation[float]:
    return Observation[float].unverified(Source.INDUSTRY_REPORT, method, note=note, evidence_url=url)


NO_CAPITAL = fact(
    0.0, Source.PLATFORM_DOCS, "no upfront platform cost", "https://gumroad.com/pricing"
)

_NO_MEDIAN = (
    "no platform publishes a median and every public figure is self-selected success "
    "reporting — treated as unknown rather than guessed"
)


def _catalogue() -> list[Opportunity]:
    items: list[Opportunity] = []

    # ---------------------------------------------------------------- assets
    items.append(
        Opportunity(
            key="unity_asset_store",
            name="Unity Asset Store",
            category="digital assets",
            summary="Sell game-ready assets, tools and shaders into Unity's own store search.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="licence sold",
                listing_name="asset",
                capital_required_inr=fact(
                    0.0, Source.PLATFORM_DOCS, "no publishing fee; $4.99 minimum price",
                    "https://assetstore.unity.com/publishing/publish-and-sell-assets",
                ),
                median_seller_net_monthly_inr=unknown(
                    "searched for platform transparency data and contributor surveys", _NO_MEDIAN
                ),
                net_per_unit_inr=unknown(
                    "70% split is documented, but median selling price is not",
                    "seller keeps 70% (documented); typical asset price not established",
                    "https://assetstore.unity.com/publishing/publish-and-sell-assets",
                ),
                units_per_listing_per_month=unknown(
                    "no per-asset sales data published", _NO_MEDIAN
                ),
                build_hours_per_listing=unknown(
                    "varies enormously by asset type", "depends entirely on what is being built"
                ),
                months_to_first_revenue=unknown("no data published", _NO_MEDIAN),
                annual_decay=fact(
                    0.66, Source.SELLER_REPORT,
                    "publisher reported sales down 66% in a year, attributed to not updating",
                    "https://discussions.unity.com/t/asset-store-sales-dropping/581052",
                    basis=SampleBasis.ANECDOTE,
                    note="single seller report; directionally consistent with ranking-by-recency",
                ),
                fixed_upkeep_hours_per_week=unknown(
                    "engine version churn requires periodic rework", "not quantified"
                ),
            ),
            assumptions=[
                Assumption(
                    claim="Unity store search alone can deliver sales without any promotion",
                    why_it_matters="the entire premise — no promotion will be done",
                    fatal_if_false=True,
                ),
                Assumption(
                    claim="an asset keeps selling without constant updates",
                    why_it_matters="determines whether this is passive income or a treadmill",
                    fatal_if_false=True,
                ),
            ],
            fit_notes=["graphics and creative-coding skills transfer directly"],
        )
    )

    items.append(
        Opportunity(
            key="fab_marketplace",
            name="FAB (Epic's asset marketplace)",
            category="digital assets",
            summary="Epic's merged asset store. Best documented revenue split of any marketplace.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="licence sold",
                listing_name="asset",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=unknown(
                    "total creator payouts published, but not a per-creator distribution",
                    "$24M paid across all creators in 2025, with no median disclosed",
                    "https://www.strayspark.studio/blog/fab-marketplace-12-month-retrospective-seller-2026",
                ),
                net_per_unit_inr=unknown(
                    "88% split documented; median price not published",
                    "seller keeps 88% (documented); typical price not established",
                    "https://www.unrealengine.com/en-US/blog/fab-content-marketplace-launches-in-october-publishing-portal-opens-today",
                ),
                units_per_listing_per_month=unknown("no per-asset data", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies by asset type", "not generalisable"),
                months_to_first_revenue=fact(
                    3.0, Source.PLATFORM_DOCS,
                    "60-day hold applies to the first three months of earnings",
                    "https://www.strayspark.studio/blog/fab-marketplace-12-month-retrospective-seller-2026",
                ),
                annual_decay=unknown(
                    "featured placement is algorithmic and favours first-30-day performance",
                    "recency is structurally rewarded, but the decay rate is not published",
                ),
                fixed_upkeep_hours_per_week=unknown("engine churn", "not quantified"),
            ),
            assumptions=[
                Assumption(
                    claim="FAB's algorithm surfaces assets beyond their first 30 days",
                    why_it_matters="if placement is launch-weighted, revenue is a spike not an income",
                    fatal_if_false=True,
                ),
            ],
            fit_notes=["88% is the best split found anywhere", "graphics skills transfer"],
        )
    )

    items.append(
        Opportunity(
            key="envato_market",
            name="Envato Market (ThemeForest / GraphicRiver)",
            category="digital assets",
            summary="Large established marketplace — moving to a flat 50% seller share in July 2026.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="licence sold",
                listing_name="item",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=fact(
                    usd(154.0), Source.PLATFORM_DATA,
                    "$96M paid across 52,000 authors in 12 months — this is a MEAN, and under a "
                    "power law the mean sits far above the median, so the real median is lower",
                    "https://www.envato.com/blog/1-billion-envato-author-community-milestone/",
                    basis=SampleBasis.MEAN,
                    note="~1,500 of 81,000+ authors 'earn a living' — roughly 2%",
                ),
                net_per_unit_inr=unknown(
                    "50% flat share from 1 July 2026; median item price not published",
                    "split documented, price distribution not",
                    "https://www.therepository.email/envato-ends-exclusive-author-model-moves-all-marketplace-sellers-to-flat-50-revenue-share",
                ),
                units_per_listing_per_month=unknown("no per-item data", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies by item type", "not generalisable"),
                months_to_first_revenue=unknown("no data", _NO_MEDIAN),
                annual_decay=unknown(
                    "marketplace traffic declining plus Elements subscription cannibalisation",
                    "platform-level decline documented directionally, rate not quantified",
                ),
                fixed_upkeep_hours_per_week=unknown("item support obligations", "not quantified"),
            ),
            assumptions=[
                Assumption(
                    claim="Envato will not cut the seller share again after work is sunk in",
                    why_it_matters="they just did exactly that, effective July 2026",
                    fatal_if_false=True,
                ),
            ],
        )
    )

    items.append(
        Opportunity(
            key="gumroad",
            name="Gumroad",
            category="digital assets",
            summary="A checkout, not a demand engine — its economics assume you bring the traffic.",
            demand_mechanism=DemandMechanism.PERSONAL_AUDIENCE,
            economics=Economics(
                unit_name="sale",
                listing_name="product",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=fact(
                    usd(72.0), Source.INDUSTRY_REPORT,
                    "third-party analysis of ~146,000 products; revenue estimated from ratings, "
                    "so treat the exact figure as soft and the shape as reliable",
                    "https://insightraider.com/en/state-of-gumroad-2026",
                    basis=SampleBasis.MEDIAN,
                    note="99.5% of platform revenue goes to the top 1%; 44% of products earn $0",
                ),
                net_per_unit_inr=unknown(
                    "90% direct minus $0.50, or 70% via Discover", "median price not published",
                    "https://gumroad.com/pricing",
                ),
                units_per_listing_per_month=unknown("not published", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies", "not generalisable"),
                months_to_first_revenue=unknown("not published", _NO_MEDIAN),
                annual_decay=unknown("not published", _NO_MEDIAN),
                fixed_upkeep_hours_per_week=unknown("not published", _NO_MEDIAN),
            ),
        )
    )

    items.append(
        Opportunity(
            key="figma_community",
            name="Figma Community paid resources",
            category="digital assets",
            summary="Closed twice over: not approving new paid creators, and India is not a payout country.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="sale",
                listing_name="resource",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=unknown("not applicable", "cannot participate"),
                net_per_unit_inr=unknown(
                    "15% commission documented, but participation is closed",
                    "Figma is not approving new creators to sell paid resources, and India is "
                    "absent from the supported payout country list",
                    "https://help.figma.com/hc/en-us/articles/12067637274519-About-selling-Community-resources",
                ),
                units_per_listing_per_month=unknown("not applicable", "cannot participate"),
                build_hours_per_listing=unknown("not applicable", "cannot participate"),
                months_to_first_revenue=unknown("not applicable", "cannot participate"),
                annual_decay=unknown("not applicable", "cannot participate"),
                fixed_upkeep_hours_per_week=unknown("not applicable", "cannot participate"),
            ),
            assumptions=[
                Assumption(
                    claim="an Indian creator can receive payouts from Figma at all",
                    why_it_matters="India is not on the supported payout list — this is a hard stop",
                    fatal_if_false=True,
                    resolved=False,
                ),
            ],
        )
    )

    # ------------------------------------------------------------ software
    items.append(
        Opportunity(
            key="mobile_app_ads",
            name="Mobile app funded by ads",
            category="software",
            summary="Store-search discovery, but organic installs skew to the worst-paying geography.",
            demand_mechanism=DemandMechanism.APP_STORE_SEARCH,
            economics=Economics(
                unit_name="ad impression day",
                listing_name="app",
                capital_required_inr=fact(
                    8_300.0, Source.PLATFORM_DOCS,
                    "Apple developer programme $99/year; Google Play $25 one-time",
                    "https://developer.apple.com/app-store/small-business-program/",
                ),
                median_seller_net_monthly_inr=unknown(
                    "no first-party store discloses per-app medians",
                    "trackers suggest ~83% of apps never cross $1,000/month, but this is not auditable",
                ),
                net_per_unit_inr=unknown(
                    "eCPM varies 8-15x by geography", "India banner ~$0.10 vs US ~$0.85 eCPM",
                    "https://www.playwire.com/blog/admob-ecpm-benchmarks-what-publishers-should-expect",
                ),
                units_per_listing_per_month=unknown("depends entirely on installs", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies by app", "not generalisable"),
                months_to_first_revenue=fact(
                    1.0, Source.INDUSTRY_REPORT, "revenue can begin within weeks of listing",
                    "https://www.playwire.com/blog/admob-ecpm-benchmarks-what-publishers-should-expect",
                ),
                annual_decay=unknown(
                    "ranking decay plus forced delisting",
                    "Apple now removes stagnant apps; Play requires target API 36 from Aug 2026 — "
                    "stopping work means delisting, not merely stagnating",
                ),
                fixed_upkeep_hours_per_week=unknown(
                    "annual SDK and API migrations are mandatory", "not quantified but non-optional",
                ),
            ),
            assumptions=[
                Assumption(
                    claim="organic store search can reach 20,000-50,000 DAU with no promotion",
                    why_it_matters="India-skewed ad rates mean that is the scale needed for the goal",
                    fatal_if_false=True,
                ),
                Assumption(
                    claim="the app survives mandatory annual SDK migrations without major rework",
                    why_it_matters="Apple and Google both now delist apps that stop being updated",
                    fatal_if_false=True,
                ),
            ],
            fit_notes=["front-end and graphics skills transfer to app work"],
        )
    )

    items.append(
        Opportunity(
            key="chrome_extension",
            name="Chrome extension",
            category="software",
            summary="No in-store payments since 2021, and the median extension has 17 installs.",
            demand_mechanism=DemandMechanism.APP_STORE_SEARCH,
            economics=Economics(
                unit_name="sale",
                listing_name="extension",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=fact(
                    0.0, Source.INDUSTRY_REPORT,
                    "median extension has ~17 installs and ~70% have under 100 users; with "
                    "in-store payments removed there is no monetisation path at that scale",
                    "https://www.debugbear.com/blog/counting-chrome-extensions",
                    basis=SampleBasis.MEDIAN,
                ),
                net_per_unit_inr=unknown(
                    "Chrome Web Store Payments shut down 1 February 2021",
                    "every paid extension now needs its own backend, billing and tax handling",
                    "https://www.techradar.com/news/google-kills-off-paid-for-chrome-extensions",
                ),
                units_per_listing_per_month=unknown("not published", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies", "not generalisable"),
                months_to_first_revenue=unknown("not established", _NO_MEDIAN),
                annual_decay=unknown("manifest migrations force rework", "not quantified"),
                fixed_upkeep_hours_per_week=unknown("not established", _NO_MEDIAN),
            ),
        )
    )

    items.append(
        Opportunity(
            key="devtool_plugins",
            name="Editor and dev-tool plugins",
            category="software",
            summary="Obsidian, Blender and Figma have no open paid path; the economy is donations.",
            demand_mechanism=DemandMechanism.APP_STORE_SEARCH,
            economics=Economics(
                unit_name="sale",
                listing_name="plugin",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=fact(
                    0.0, Source.PLATFORM_DOCS,
                    "Obsidian offers no built-in payment and is not accepting new closed-source "
                    "plugins; Blender extensions are free and GPL-only; Figma is closed to new "
                    "paid creators",
                    "https://obsidian.md/blog/future-of-plugins/",
                    basis=SampleBasis.AGGREGATE,
                ),
                net_per_unit_inr=unknown("no monetisation path", "these are donation economies"),
                units_per_listing_per_month=unknown("not applicable", "no paid path"),
                build_hours_per_listing=unknown("varies", "not generalisable"),
                months_to_first_revenue=unknown("not applicable", "no paid path"),
                annual_decay=unknown("not applicable", "no paid path"),
                fixed_upkeep_hours_per_week=unknown("not applicable", "no paid path"),
            ),
        )
    )

    items.append(
        Opportunity(
            key="steam_game",
            name="Indie game on Steam",
            category="software",
            summary="Median 2025 release netted about $74 lifetime, and the algorithm rewards demand you bring it.",
            demand_mechanism=DemandMechanism.PERSONAL_AUDIENCE,
            economics=Economics(
                unit_name="copy sold",
                listing_name="game",
                capital_required_inr=fact(
                    usd(100.0), Source.PLATFORM_DOCS, "Steam Direct fee per title",
                    "https://www.gamesradar.com/games/over-5-000-games-released-on-steam-this-year-didnt-make-enough-money-to-recover-the-usd100-fee-to-put-a-game-on-valves-store-research-estimates/",
                ),
                median_seller_net_monthly_inr=fact(
                    usd(74.0) / 12.0, Source.INDUSTRY_REPORT,
                    "median 2025 release grossed $249 lifetime; after Valve's 30% and the $100 "
                    "Steam Direct fee that is roughly $74 lifetime, spread here across a year",
                    "https://www.gamesradar.com/games/over-5-000-games-released-on-steam-this-year-didnt-make-enough-money-to-recover-the-usd100-fee-to-put-a-game-on-valves-store-research-estimates/",
                    basis=SampleBasis.MEDIAN,
                    note="66% of 2025 releases earned under $1,000; ~40% did not recoup the fee",
                ),
                net_per_unit_inr=unknown("depends on price point", "seller keeps 70%"),
                units_per_listing_per_month=unknown("launch spike then long tail", _NO_MEDIAN),
                build_hours_per_listing=unknown("a game is not a unit of predictable effort", "varies wildly"),
                months_to_first_revenue=unknown("revenue starts at launch", "build time dominates"),
                annual_decay=unknown(
                    "revenue is a launch spike, not recurring income",
                    "Steam visibility rounds are finite impression batches at launch and updates",
                ),
                fixed_upkeep_hours_per_week=unknown("not established", _NO_MEDIAN),
            ),
            assumptions=[
                Assumption(
                    claim="Steam's algorithm can surface a game without pre-existing wishlists",
                    why_it_matters=(
                        "Popular Upcoming needs roughly 7,000-10,000 wishlists, which requires "
                        "exactly the promotion that is excluded"
                    ),
                    fatal_if_false=True,
                    resolved=False,
                ),
            ],
        )
    )

    # ------------------------------------------------------------- media
    items.append(
        Opportunity(
            key="stock_media",
            name="Stock media contribution",
            category="media",
            summary="A measurably shrinking market: fewer downloads, lower rates, more contributors.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="download",
                listing_name="asset",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=unknown(
                    "no agency discloses contributor medians", _NO_MEDIAN
                ),
                net_per_unit_inr=fact(
                    usd(0.30), Source.PLATFORM_DOCS,
                    "Shutterstock documents a $0.10 minimum per download and concedes bulk packs "
                    "price at $0.20-0.30; Adobe Stock minimum is $0.33",
                    "https://submit.shutterstock.com/help/en/articles/12136655-why-am-i-still-seeing-0-10-earnings-at-higher-levels",
                    basis=SampleBasis.AGGREGATE,
                ),
                units_per_listing_per_month=unknown(
                    "per-asset download rates are not published", _NO_MEDIAN
                ),
                build_hours_per_listing=unknown("varies by medium", "not generalisable"),
                months_to_first_revenue=fact(
                    1.0, Source.INDUSTRY_REPORT, "downloads can begin within weeks of upload",
                    "https://helpx.adobe.com/stock/contributor/payments-earnings/royalties-pricing/royalty-rates-assets.html",
                ),
                annual_decay=fact(
                    0.14, Source.PLATFORM_DATA,
                    "Shutterstock paid downloads fell from 120.9M to 104.1M year on year — a "
                    "market-level contraction that no individual effort offsets",
                    "https://investor.shutterstock.com/news-releases/news-release-details/shutterstock-reports-first-quarter-2026-financial-results",
                    basis=SampleBasis.AGGREGATE,
                    note="Shutterstock revenue -18% YoY; contributor levels also reset every January",
                ),
                fixed_upkeep_hours_per_week=unknown("continuous uploading required", "not quantified"),
            ),
            assumptions=[
                Assumption(
                    claim="the stock market stabilises rather than continuing to contract",
                    why_it_matters="building a portfolio into a shrinking market compounds badly",
                    fatal_if_false=True,
                ),
            ],
        )
    )

    items.append(
        Opportunity(
            key="seo_content_site",
            name="Ad-funded content site",
            category="media",
            summary="Organic search referral has collapsed since AI Overviews; ad networks are cutting thresholds to compensate.",
            demand_mechanism=DemandMechanism.WEB_SEARCH,
            economics=Economics(
                unit_name="thousand pageviews",
                listing_name="article",
                capital_required_inr=fact(
                    3_000.0, Source.PLATFORM_DOCS, "domain and hosting for a year",
                    "https://www.mediavine.com/mediavine-requirements/",
                ),
                median_seller_net_monthly_inr=unknown(
                    "no credible median for independent publishers", _NO_MEDIAN
                ),
                net_per_unit_inr=unknown(
                    "RPM is US-weighted and vendor-reported, not disclosed",
                    "Indian traffic earns a fraction of US traffic",
                    "https://www.mediavine.com/mediavine-requirements/",
                ),
                units_per_listing_per_month=unknown(
                    "traffic per article is entirely ranking-dependent", _NO_MEDIAN
                ),
                build_hours_per_listing=unknown("varies", "not generalisable"),
                months_to_first_revenue=fact(
                    12.0, Source.INDUSTRY_REPORT,
                    "ad networks require meaningful traffic before acceptance; Raptive needs "
                    "25,000 monthly views with 50% from US/UK/CA/NZ/AU",
                    "https://www.searchenginejournal.com/raptive-drops-traffic-requirement-by-75-to-25000-views/558780/",
                ),
                annual_decay=fact(
                    0.30, Source.INDUSTRY_REPORT,
                    "Pew measured result clicks falling from 15% to 8% of searches when an AI "
                    "summary appears; small publishers report multi-year referral decline",
                    "https://www.pewresearch.org/short-reads/2025/07/22/google-users-are-less-likely-to-click-on-links-when-an-ai-summary-appears-in-the-results/",
                    basis=SampleBasis.AGGREGATE,
                    note="rate is indicative of a documented downward trend, not a published figure",
                ),
                fixed_upkeep_hours_per_week=unknown("continuous refreshing required", "not quantified"),
            ),
        )
    )

    items.append(
        Opportunity(
            key="print_on_demand",
            name="Print on demand",
            category="media",
            summary="Amazon now pays roughly double to sellers who bring external traffic, which is the excluded behaviour.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="item sold",
                listing_name="design",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=unknown(
                    "neither Amazon nor Redbubble disclose seller earnings distributions", _NO_MEDIAN
                ),
                net_per_unit_inr=fact(
                    usd(2.44), Source.INDUSTRY_REPORT,
                    "reported June 2026 Amazon Merch tiers: Creator tier (under 15% external "
                    "traffic) earns $2.44 on a $19.99 shirt versus $5.27 at Premium",
                    "https://merchtitans.com/blog/amazon-merch-royalty-changes-june-2026",
                    basis=SampleBasis.AGGREGATE,
                    note="REPORTED ONLY — could not be verified against Amazon's own documentation",
                ),
                units_per_listing_per_month=unknown("no per-design data published", _NO_MEDIAN),
                build_hours_per_listing=unknown("varies by design complexity", "not generalisable"),
                months_to_first_revenue=unknown(
                    "Merch has a waitlist and tiered slot limits", "approval time not published"
                ),
                annual_decay=unknown("saturation-driven", "not quantified"),
                fixed_upkeep_hours_per_week=unknown("continuous uploading", "not quantified"),
            ),
            assumptions=[
                Assumption(
                    claim="marketplace search alone sells enough without external traffic",
                    why_it_matters=(
                        "Amazon's tier system explicitly halves the royalty for sellers who "
                        "bring under 15% external traffic — the constraint is priced in"
                    ),
                    fatal_if_false=True,
                ),
            ],
        )
    )

    items.append(
        Opportunity(
            key="kdp_fiction",
            name="Amazon KDP (fiction)",
            category="media",
            summary="The least-bad marketplace route, but fiction is the most discovery-dependent segment.",
            demand_mechanism=DemandMechanism.MARKETPLACE_SEARCH,
            economics=Economics(
                unit_name="book sold",
                listing_name="title",
                capital_required_inr=NO_CAPITAL,
                median_seller_net_monthly_inr=unknown(
                    "the widely-quoted ALLi figure surveys paying members of an authors' "
                    "association — committed, multi-book, promoting authors",
                    "no median exists for an unpromoted new entrant; the popular figure is "
                    "survivor-biased and must not be used for planning",
                    "https://www.allianceindependentauthors.org/media-releases/alliance-independent-authors-survey-reveals-self-publishing-authors-earn-more/",
                ),
                net_per_unit_inr=fact(
                    usd(2.0), Source.PLATFORM_DOCS,
                    "70% royalty within Amazon's price band, less delivery cost; note that "
                    "titles outside KDP Select earn only 35% on Amazon.in sales",
                    "https://kdp.amazon.com/en_US/help/topic/G200634500",
                    basis=SampleBasis.AGGREGATE,
                    note="assumes a mid-band price; actual net depends on the price chosen",
                ),
                units_per_listing_per_month=unknown("no per-title data published", _NO_MEDIAN),
                build_hours_per_listing=unknown("writing a book is not a fixed effort", "varies wildly"),
                months_to_first_revenue=unknown("depends on writing speed", _NO_MEDIAN),
                annual_decay=unknown(
                    "AI-generated flooding is degrading discovery",
                    "roughly 14,000 AI-generated titles a day reported across platforms",
                ),
                fixed_upkeep_hours_per_week=unknown("not established", _NO_MEDIAN),
            ),
            assumptions=[
                Assumption(
                    claim="Amazon's algorithm surfaces fiction without ads or series read-through",
                    why_it_matters="fiction discovery is the most promotion-dependent segment there is",
                    fatal_if_false=True,
                ),
            ],
        )
    )

    # ------------------------------------------------------- for comparison
    items.append(
        Opportunity(
            key="productised_freelance",
            name="Productised freelance web work",
            category="services",
            summary=(
                "Included so the excluded option is costed honestly rather than quietly ignored: "
                "reaching the goal needs roughly 4-6 builds a month at Bangalore rates."
            ),
            demand_mechanism=DemandMechanism.OUTBOUND_SALES,
            economics=Economics(
                unit_name="website built",
                listing_name="client",
                capital_required_inr=fact(
                    3_000.0, Source.MARKET_OBSERVATION, "domain plus a portfolio site",
                    "https://www.zauca.com/website-design-cost-in-bangalore-rs-3800-web-designing-charges-in-bangalore-karnataka/",
                ),
                median_seller_net_monthly_inr=unknown(
                    "freelance earnings are not published as a distribution", _NO_MEDIAN
                ),
                net_per_unit_inr=fact(
                    10_000.0, Source.MARKET_OBSERVATION,
                    "Bangalore agencies advertise ₹999-13,000 per small business site; a "
                    "freelancer at the upper end of that band",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                    basis=SampleBasis.AGGREGATE,
                ),
                units_per_listing_per_month=fact(
                    1.0, Source.OPERATOR, "one build is one client, delivered once",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                ),
                build_hours_per_listing=fact(
                    20.0, Source.OPERATOR,
                    "operator estimate for a small static build",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                ),
                months_to_first_revenue=fact(
                    2.0, Source.INDUSTRY_REPORT, "time to first closed client via cold outreach",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                ),
                annual_decay=fact(
                    1.0, Source.OPERATOR,
                    "a one-time build stops paying the month after delivery — income resets to "
                    "zero every month",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                ),
                fixed_upkeep_hours_per_week=fact(
                    0.0, Source.OPERATOR, "no ongoing obligation on a one-time build",
                    "https://rdswebtech.com/website-design-company-bengaluru",
                ),
            ),
        )
    )

    return items


def seed() -> list[Opportunity]:
    """The researched catalogue as of 2026-08-04."""
    return _catalogue()


def keys() -> list[str]:
    return [o.key for o in _catalogue()]
