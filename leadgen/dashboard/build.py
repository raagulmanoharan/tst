"""Static dashboard generation.

Renders the tracker to a single self-contained HTML file. Business names and
addresses are not in the database and are not written here either — each lead
links out to Google Maps by place ID, which is both free and compliant. Passing
`live_client` enriches the labels for one render, in memory only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..discover.places import PlacesClient, PlacesUnavailable
from ..score.rules import qualifies
from ..store import LeadStore
from ..store.models import Lead

TEMPLATE_DIR = Path(__file__).parent / "templates"
MAPS_PLACE_URL = "https://www.google.com/maps/place/?q=place_id:{place_id}"


def _open_checks(lead: Lead) -> list[dict[str, str]]:
    """Observations that need a human, surfaced as one-click links.

    These are the signals no free, terms-compliant API can establish — ad spend
    and search ranking. Rather than guess them, we hand the operator the URL.
    """
    checks: list[dict[str, str]] = []
    for key, observation in lead.observations().items():
        if observation.is_known or not observation.evidence_url:
            continue
        checks.append(
            {
                "label": key.replace("_", " ").replace(".", " · "),
                "url": observation.evidence_url,
                "note": observation.note or observation.method,
            }
        )
    return checks


def build_dashboard(
    store: LeadStore,
    out_path: Path | str = Path("out/index.html"),
    limit: int = 200,
    live_client: PlacesClient | None = None,
) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("index.html.j2")

    items: list[dict[str, Any]] = []
    for lead in store.ranked(limit=limit):
        label = lead.place_id
        if live_client is not None:
            try:
                place = live_client.fetch_live(lead.place_id)
                label = place.display_name or lead.place_id
            except PlacesUnavailable:
                pass  # Fall back to the place_id; a label is not worth failing a render.
        items.append(
            {
                "lead": lead,
                "label": label,
                "maps_url": MAPS_PLACE_URL.format(place_id=lead.place_id),
                "qualified": qualifies(lead.score) if lead.score else False,
                "observations": sorted(lead.observations().items()),
                "checks": _open_checks(lead),
            }
        )

    html = template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        total=sum(store.counts_by_stage().values()),
        stage_counts=sorted(store.counts_by_stage().items()),
        usage=sorted(store.usage_this_month().items()),
        leads=items,
    )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
