"""Command line entry point.

    python -m fiftyk seed          # load the researched catalogue
    python -m fiftyk status        # the answer: what to do next
    python -m fiftyk relax         # which constraint to give up
    python -m fiftyk research      # what to find out next
    python -m fiftyk dashboard

Recording your own numbers:

    python -m fiftyk estimate unity_asset_store --build-hours 12 --upkeep-hours 2
    python -m fiftyk record unity_asset_store --field median_seller_net_monthly_inr \\
        --value 4200 --basis median --url https://... --method "platform disclosure"
    python -m fiftyk actual unity_asset_store --month 2026-09 --net 3200 --hours 20 --listings 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .catalogue import seed as catalogue_seed
from .dashboard import build_dashboard
from .feasibility import Verdict, assess, rank
from .goal import Profile
from .models import DipCheck, MonthlyActual, Stage
from .provenance import Confidence, Observation, SampleBasis, Source
from . import sidecar
from .research import brief, format_brief
from .sensitivity import analyse, summarise
from .store import DEFAULT_DB_PATH, Store
from .validate import format_report, validate


def cmd_seed(store: Store, args, profile: Profile) -> int:
    added = skipped = 0
    for opportunity in catalogue_seed():
        if store.get(opportunity.key) and not args.force:
            skipped += 1
            continue
        store.upsert(opportunity)
        added += 1
    print(f"seeded {added} opportunities ({skipped} already present; --force to overwrite)")
    return 0


def cmd_status(store: Store, args, profile: Profile) -> int:
    opportunities = list(store.all())
    if not opportunities:
        print("Nothing loaded. Run: python -m fiftyk seed")
        return 1

    assessments = [assess(o, profile.goal, profile.constraints) for o in opportunities]
    by_key = {o.key: o for o in opportunities}
    ranked = rank(assessments)
    current = store.total_net_monthly()

    print(f"Goal  ₹{profile.goal.net_monthly_inr:,.0f}/month net within {profile.goal.horizon_months} months")
    print(f"Now   ₹{current:,.0f}/month  ({100*current/profile.goal.net_monthly_inr:.0f}%)")
    print()

    if ranked:
        print("Worth pursuing, cheapest attention first:")
        for a in ranked:
            p = a.projection
            months = f"~{p.months_to_goal:.0f} mo" if p and p.months_to_goal else "timeline unknown"
            print(f"  {a.verdict.value:9} {a.opportunity_key:24} {months}")
    else:
        print("Nothing clears every constraint.")
        print("That is a result, not a failure — run `python -m fiftyk relax` to see")
        print("which single constraint opens the most if you give it up.")

    pending = [a for a in assessments if a.verdict is Verdict.NEEDS_EVIDENCE]
    blocked = [a for a in assessments if a.verdict is Verdict.BLOCKED]
    print()
    print(f"{len(pending)} awaiting evidence, {len(blocked)} ruled out.")

    if blocked and args.verbose:
        print("\nRuled out:")
        for a in blocked:
            print(f"  {a.opportunity_key}")
            for b in a.blockers:
                print(f"      {b.reason}")
                if b.arithmetic:
                    print(f"      {b.arithmetic}")
    return 0


def cmd_show(store: Store, args, profile: Profile) -> int:
    opportunity = store.get(args.key)
    if opportunity is None:
        sys.exit(f"error: no opportunity '{args.key}'")
    a = assess(opportunity, profile.goal, profile.constraints)

    print(f"{opportunity.name}  [{a.verdict.value}]")
    print(f"{opportunity.summary}")
    print(f"demand via {opportunity.demand_mechanism.value.replace('_', ' ')} · stage {opportunity.stage.value}")
    print()
    for b in a.blockers:
        print(f"  BLOCKED [{b.gate}] {b.reason}")
        if b.arithmetic:
            print(f"          {b.arithmetic}")
    for w in a.warnings:
        print(f"  note    [{w.gate}] {w.reason}")
    if a.projection:
        p = a.projection
        print()
        print(f"  {p.listings_needed:,.0f} {opportunity.economics.listing_name}s needed")
        print(f"  {p.maintenance_hours_per_week:.1f} h/week to hold it there, forever")
        if p.months_to_goal:
            print(f"  ~{p.months_to_goal:.0f} months to goal")
    print("\n  Evidence:")
    for name, obs in sorted(opportunity.observations().items()):
        shown = f"{obs.value:,.2f}" if obs.value is not None else "—"
        print(f"    {name.replace('economics.',''):34} {shown:>14}  [{obs.confidence.value}/{obs.basis.value}]")
    if opportunity.open_assumptions:
        print("\n  Open assumptions:")
        for assumption in opportunity.open_assumptions:
            flag = "FATAL" if assumption.fatal_if_false else "     "
            print(f"    {flag} {assumption.claim}")
    return 0


def cmd_estimate(store: Store, args, profile: Profile) -> int:
    opportunity = store.get(args.key)
    if opportunity is None:
        sys.exit(f"error: no opportunity '{args.key}'")

    updates = {}
    if args.build_hours is not None:
        updates["build_hours_per_listing"] = args.build_hours
    if args.upkeep_hours is not None:
        updates["fixed_upkeep_hours_per_week"] = args.upkeep_hours
    if not updates:
        sys.exit("error: give --build-hours and/or --upkeep-hours")

    for field, value in updates.items():
        setattr(
            opportunity.economics,
            field,
            Observation[float](
                value=float(value),
                source=Source.OPERATOR,
                method="operator's own estimate of their own working speed",
                confidence=Confidence.VERIFIED,
                basis=SampleBasis.ESTIMATE,
            ),
        )
    store.upsert(opportunity)
    print(f"recorded {', '.join(updates)} for {args.key}")
    return 0


def cmd_record(store: Store, args, profile: Profile) -> int:
    """Write a researched figure back, with its provenance."""
    opportunity = store.get(args.key)
    if opportunity is None:
        sys.exit(f"error: no opportunity '{args.key}'")
    if args.field not in type(opportunity.economics).model_fields:
        sys.exit(f"error: no economics field '{args.field}'")

    setattr(
        opportunity.economics,
        args.field,
        Observation[float](
            value=float(args.value),
            source=Source(args.source),
            method=args.method,
            confidence=Confidence.VERIFIED,
            basis=SampleBasis(args.basis),
            evidence_url=args.url,
            note=args.note,
        ),
    )
    opportunity.last_researched_at = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    )
    store.upsert(opportunity)
    print(f"recorded {args.field} = {args.value} for {args.key} [{args.basis}]")
    return 0


def cmd_dipcheck(store: Store, args, profile: Profile) -> int:
    opportunity = store.get(args.key)
    if opportunity is None:
        sys.exit(f"error: no opportunity '{args.key}'")

    riskiest = opportunity.riskiest_open_assumption
    tested = args.assumption or (riskiest.claim if riskiest else None)
    if tested is None:
        sys.exit("error: no open assumption to test; pass --assumption")

    opportunity.dip_checks.append(
        DipCheck(
            tests_assumption=tested,
            method=args.method,
            time_box_hours=args.hours,
            cost_inr=args.cost,
            kill_criteria=args.kill,
        )
    )
    opportunity.stage = Stage.DIP_CHECK
    store.upsert(opportunity)
    print(f"dip-check opened on {args.key}")
    print(f"  tests: {tested}")
    print(f"  box:   {args.hours}h / ₹{args.cost:,.0f}")
    print(f"  kill:  {'; '.join(args.kill)}")
    return 0


def cmd_actual(store: Store, args, profile: Profile) -> int:
    opportunity = store.get(args.key)
    if opportunity is None:
        sys.exit(f"error: no opportunity '{args.key}'")

    opportunity.actuals = [a for a in opportunity.actuals if a.month != args.month]
    opportunity.actuals.append(
        MonthlyActual(
            month=args.month, net_inr=args.net, hours_spent=args.hours,
            listings_live=args.listings, units_sold=args.units, note=args.note,
        )
    )
    opportunity.hours_invested += args.hours
    if opportunity.stage in (Stage.COMMITTED, Stage.DIP_CHECK) and args.net > 0:
        opportunity.stage = Stage.LIVE
    store.upsert(opportunity)

    # Compare what happened against what the model said would happen.
    economics = opportunity.economics
    if economics.is_modellable and args.listings > 0:
        from .economics import net_monthly_at

        predicted = net_monthly_at(economics, args.listings)
        if predicted > 0:
            ratio = args.net / predicted
            print(f"recorded {args.month}: ₹{args.net:,.0f} from {args.listings} listings")
            print(f"model predicted ₹{predicted:,.0f} — reality is {ratio:.2f}x that")
            if ratio < 0.5 or ratio > 2.0:
                print("The model is wrong. Update units_per_listing_per_month with `record`,")
                print("using Source.OPERATOR — your own data beats any published figure.")
            return 0
    print(f"recorded {args.month}: ₹{args.net:,.0f}")
    return 0


def cmd_relax(store: Store, args, profile: Profile) -> int:
    print(summarise(analyse(list(store.all()), profile.goal, profile.constraints)))
    return 0


def cmd_research(store: Store, args, profile: Profile) -> int:
    opportunities = list(store.all())
    items = brief(opportunities, profile.goal, profile.constraints)

    if not args.run:
        print(format_brief(items))
        if items and sidecar.available():
            print("\nRun `fiftyk research --run` to have the sidecar answer these.")
        return 0

    if not sidecar.available():
        sys.exit(
            "error: Claude Code CLI not found, so the sidecar cannot run.\n"
            "Set CLAUDE_CODE_EXECPATH, or answer the brief by hand with `fiftyk record`."
        )

    # The sidecar establishes figures. Assumptions like "can this algorithm
    # surface a listing without promotion" are judgement calls, not lookups, and
    # are left for a human or a reasoning pass.
    lookups = [i for i in items if i.field != "assumption"]
    judgement = [i for i in items if i.field == "assumption"]
    if not lookups:
        print("Nothing left that a lookup can settle.")
        return 0

    by_key = {o.key: o for o in opportunities}
    contexts = {k: f"{o.name} — {o.summary}" for k, o in by_key.items()}

    print(f"Asking the sidecar {min(len(lookups), args.limit or len(lookups))} questions "
          f"(ceiling ${args.budget:.2f})...\n")
    report = sidecar.run(lookups, contexts, budget_usd=args.budget, limit=args.limit)

    stored = 0
    for finding in report.findings:
        opportunity = by_key.get(finding.item.opportunity_key)
        observation = finding.as_observation()
        if opportunity is None or observation is None:
            print(f"  reject  {finding.item.opportunity_key}.{finding.item.field}"
                  f" — {finding.rejected_reason}")
            continue
        setattr(opportunity.economics, finding.item.field, observation)
        opportunity.last_researched_at = observation.observed_at
        store.upsert(opportunity)
        stored += 1
        print(f"  stored  {finding.item.opportunity_key}.{finding.item.field}"
              f" = {observation.value:,.2f}  [{observation.basis.value}]")

    print(f"\n{stored} stored, {len(report.rejected)} rejected. "
          f"Spent ${report.spent_usd:.2f}.")
    if report.stopped_early:
        print(f"Stopped early: {report.stopped_early}")
    if judgement:
        print(f"\n{len(judgement)} assumptions still need judgement, not lookup:")
        for item in judgement[:5]:
            print(f"  {item.opportunity_key}: {item.question}")
    print("\nRe-run `fiftyk status` to see what moved.")
    return 0


def cmd_validate(store: Store, args, profile: Profile) -> int:
    report = validate(store)
    print(format_report(report))
    return 0 if report.ok else 1


def cmd_dashboard(store: Store, args, profile: Profile) -> int:
    print(f"wrote {build_dashboard(store, profile, args.out)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fiftyk", description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("seed", help="load the researched catalogue")
    p.add_argument("--force", action="store_true", help="overwrite existing entries")
    p.set_defaults(fn=cmd_seed)

    p = sub.add_parser("status", help="what to do next")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("show", help="one opportunity in full")
    p.add_argument("key")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("estimate", help="record your own effort estimates")
    p.add_argument("key")
    p.add_argument("--build-hours", type=float, default=None)
    p.add_argument("--upkeep-hours", type=float, default=None)
    p.set_defaults(fn=cmd_estimate)

    p = sub.add_parser("record", help="write a researched figure back, with provenance")
    p.add_argument("key")
    p.add_argument("--field", required=True)
    p.add_argument("--value", type=float, required=True)
    p.add_argument("--source", default=Source.INDUSTRY_REPORT.value, choices=[s.value for s in Source])
    p.add_argument("--basis", default=SampleBasis.AGGREGATE.value, choices=[b.value for b in SampleBasis])
    p.add_argument("--url", default=None)
    p.add_argument("--method", required=True)
    p.add_argument("--note", default=None)
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("dipcheck", help="open a time-boxed experiment")
    p.add_argument("key")
    p.add_argument("--assumption", default=None, help="defaults to the riskiest open one")
    p.add_argument("--method", required=True)
    p.add_argument("--hours", type=float, required=True)
    p.add_argument("--cost", type=float, default=0.0)
    p.add_argument("--kill", action="append", required=True, help="repeatable; decided in advance")
    p.set_defaults(fn=cmd_dipcheck)

    p = sub.add_parser("actual", help="record a real month")
    p.add_argument("key")
    p.add_argument("--month", required=True, help="YYYY-MM")
    p.add_argument("--net", type=float, required=True)
    p.add_argument("--hours", type=float, required=True)
    p.add_argument("--listings", type=int, required=True)
    p.add_argument("--units", type=int, default=None)
    p.add_argument("--note", default=None)
    p.set_defaults(fn=cmd_actual)

    sub.add_parser("relax", help="which constraint to give up").set_defaults(fn=cmd_relax)
    p = sub.add_parser("research", help="what to find out next")
    p.add_argument("--run", action="store_true",
                   help="have the sidecar answer the brief (uses the authenticated Claude Code CLI)")
    p.add_argument("--budget", type=float, default=sidecar.DEFAULT_BUDGET_USD,
                   help="spend ceiling in USD for this run")
    p.add_argument("--limit", type=int, default=None, help="cap how many questions to ask")
    p.set_defaults(fn=cmd_research)
    sub.add_parser("validate", help="audit provenance").set_defaults(fn=cmd_validate)

    p = sub.add_parser("dashboard", help="render to HTML")
    p.add_argument("--out", default="out/index.html")
    p.set_defaults(fn=cmd_dashboard)

    args = parser.parse_args(argv)
    profile = Profile.default()
    store = Store(Path(args.db))
    try:
        return args.fn(store, args, profile)
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
