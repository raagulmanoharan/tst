"""Static dashboard generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..feasibility import Verdict, assess, rank
from ..goal import Profile
from ..sensitivity import analyse
from ..store import Store

TEMPLATE_DIR = Path(__file__).parent / "templates"


def build_dashboard(
    store: Store,
    profile: Profile,
    out_path: Path | str = Path("out/index.html"),
) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html", "xml"])
    )
    template = env.get_template("index.html.j2")

    opportunities = list(store.all())
    assessments = {o.key: assess(o, profile.goal, profile.constraints) for o in opportunities}
    by_key = {o.key: o for o in opportunities}

    def item(key: str) -> dict[str, Any]:
        a = assessments[key]
        p = a.projection
        return {
            "opp": by_key[key],
            "verdict": a.verdict.value,
            "blockers": a.blockers,
            "warnings": a.warnings,
            "months": p.months_to_goal if p else None,
            "listings": p.listings_needed if p and p.reachable else None,
            "maintenance": p.maintenance_hours_per_week if p else None,
            "hands_off": p.hands_off if p else False,
            "observations": sorted(by_key[key].observations().items()),
        }

    ranked = rank(list(assessments.values()))
    viable = [item(a.opportunity_key) for a in ranked]
    pending = [
        item(k) for k, a in assessments.items() if a.verdict is Verdict.NEEDS_EVIDENCE
    ]
    blocked = [item(k) for k, a in assessments.items() if a.verdict is Verdict.BLOCKED]

    relaxations = [r for r in analyse(opportunities, profile.goal, profile.constraints) if r.is_worthwhile]

    current_net = store.total_net_monthly()
    progress = min(100.0, 100.0 * current_net / profile.goal.net_monthly_inr) if profile.goal.net_monthly_inr else 0.0

    html = template.render(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        goal=profile.goal,
        horizon=profile.goal.horizon_months,
        capital=profile.constraints.capital_ceiling_inr,
        max_hours=profile.constraints.max_maturity_hours_per_week,
        current_net=current_net,
        progress_pct=progress,
        viable=viable,
        pending=pending,
        blocked=blocked,
        relaxations=relaxations,
        viable_count=len(viable),
        evidence_count=len(pending),
        blocked_count=len(blocked),
    )

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
