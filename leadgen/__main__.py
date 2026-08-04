"""Command line entry point.

    python -m leadgen discover --city bangalore --category dental
    python -m leadgen verify --limit 50
    python -m leadgen draft
    python -m leadgen dashboard --live
    python -m leadgen validate

There is deliberately no `send` command. See CLAUDE.md rule 4.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .config import (
    CANDIDATE_CATEGORIES,
    CITIES,
    MISSING_OPERATOR_HELP,
    SKU_BUDGETS,
    Operator,
    Settings,
)
from .dashboard import build_dashboard
from .discover.places import PlacesClient, PlacesUnavailable
from .pipeline import run_discover, run_draft, run_verify, score_only
from .store import LeadStore
from .validate import format_report, validate
from .verify.ads import operator_ads
from .verify.search import operator_search


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader — avoids a dependency for six lines of parsing."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _client(settings: Settings, store: LeadStore) -> PlacesClient:
    try:
        return PlacesClient(settings, store)
    except PlacesUnavailable as exc:
        sys.exit(f"error: {exc}")


def _require_operator() -> Operator:
    operator = Operator.from_env()
    if operator is None:
        sys.exit(f"error: {MISSING_OPERATOR_HELP}")
    return operator


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="leadgen", description=__doc__)
    parser.add_argument("--db", default=None, help="SQLite path (default: leads.db)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("discover", help="sweep a city for candidate places")
    p.add_argument("--city", default="bangalore", choices=sorted(CITIES))
    p.add_argument("--category", action="append", dest="categories")
    p.add_argument("--max-centres", type=int, default=None, help="cap grid cells (for a cheap trial run)")

    p = sub.add_parser("verify", help="visit each site, collect evidence, and score")
    p.add_argument("--limit", type=int, default=None)

    sub.add_parser("score", help="re-score from stored evidence, no network")
    sub.add_parser("draft", help="draft outreach for qualified leads (never sends)")
    sub.add_parser("validate", help="audit provenance and staleness across the database")
    sub.add_parser("budget", help="show API usage against the free tier")
    sub.add_parser("categories", help="list candidate categories and why each is included")

    p = sub.add_parser("dashboard", help="render the tracker to HTML")
    p.add_argument("--out", default="out/index.html")
    p.add_argument("--live", action="store_true", help="fetch business names live (costs API calls)")

    p = sub.add_parser("ads", help="record a manual ad-library check")
    p.add_argument("place_id")
    p.add_argument("--google", choices=["yes", "no"], default=None)
    p.add_argument("--meta", choices=["yes", "no"], default=None)

    p = sub.add_parser("search", help="record a manual search check")
    p.add_argument("place_id")
    p.add_argument("--ranks", choices=["yes", "no"], default=None)
    p.add_argument("--domain", choices=["yes", "no"], default=None)

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    db_path = args.db or settings.db_path

    if args.command == "categories":
        for probe in CANDIDATE_CATEGORIES:
            print(f"{probe.key:22} [{probe.ticket_size:6}] {probe.query}")
            print(f"{'':22} {probe.rationale}")
        return 0

    store = LeadStore(db_path)
    try:
        return _dispatch(args, settings, store)
    finally:
        store.close()


def _tri(value: str | None) -> bool | None:
    return None if value is None else value == "yes"


def _dispatch(args: argparse.Namespace, settings: Settings, store: LeadStore) -> int:
    if args.command == "discover":
        client = _client(settings, store)
        result = run_discover(store, client, args.city, args.categories, args.max_centres)
        print(f"discovered {result['added']} new places ({result['already_known']} already known)")
        return 0

    if args.command == "verify":
        client = _client(settings, store)
        result = run_verify(store, client, args.limit)
        print(
            f"verified {result['verified']}: {result['qualified']} qualified, "
            f"{result['rejected']} rejected, {result['skipped']} skipped"
        )
        return 0

    if args.command == "score":
        result = score_only(store)
        print(f"rescored {result['rescored']}: {result['qualified']} qualified, {result['rejected']} rejected")
        return 0

    if args.command == "draft":
        operator = _require_operator()
        client = None
        try:
            client = PlacesClient(settings, store)
        except PlacesUnavailable:
            print("note: no API key — drafts will not include business names")
        result = run_draft(store, operator, client)
        print(f"drafted {result['drafted']} ({result['no_defect']} had no citable defect)")
        print("Nothing was sent. Review, edit, and send by hand from your own mail client.")
        return 0

    if args.command == "dashboard":
        client = None
        if args.live:
            client = _client(settings, store)
        out = build_dashboard(store, args.out, live_client=client)
        print(f"wrote {out}")
        return 0

    if args.command == "validate":
        report = validate(store)
        print(format_report(report))
        return 0 if report.ok else 1

    if args.command == "budget":
        usage = store.usage_this_month()
        for sku, budget in SKU_BUDGETS.items():
            used = usage.get(sku, 0)
            if budget.free_per_month > 100_000_000:
                print(f"{sku:26} {used:>7} calls   (unlimited free)")
            else:
                pct = 100 * used / budget.free_per_month
                print(f"{sku:26} {used:>7} / {budget.free_per_month} free  ({pct:.1f}%)  {budget.note}")
        return 0

    if args.command in ("ads", "search"):
        lead = store.get(args.place_id)
        if lead is None:
            sys.exit(f"error: no lead with place_id {args.place_id}")
        # Names are not stored, so manual-check URLs are rebuilt from place_id.
        if args.command == "ads":
            lead.ads = operator_ads(None, _tri(args.google), _tri(args.meta))
        else:
            lead.search = operator_search(None, lead.city, _tri(args.ranks), _tri(args.domain))
        store.upsert(lead)
        print(f"recorded {args.command} check for {args.place_id}; re-run `score` to update")
        return 0

    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
