"""The validation harness.

One question across the whole database: is anything here being taken on trust?

Nothing is auto-repaired. Silently fixing data is how a tracker drifts away from
reality without anyone noticing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Opportunity
from .provenance import Confidence, SampleBasis, Source
from .research import FIGURE_TTL
from .store import Store


@dataclass
class Finding:
    key: str
    kind: str
    detail: str


@dataclass
class Report:
    checked: int = 0
    observations: int = 0
    findings: list[Finding] = field(default_factory=list)
    unverified_by_field: dict[str, int] = field(default_factory=dict)
    unsafe_basis: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Provenance failures are errors. Gaps and staleness are information."""
        return not any(f.kind == "missing_provenance" for f in self.findings)

    def add(self, key: str, kind: str, detail: str) -> None:
        self.findings.append(Finding(key, kind, detail))

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        return counts


def validate_opportunity(opportunity: Opportunity, report: Report) -> None:
    observations = opportunity.observations()
    report.observations += len(observations)

    for name, obs in observations.items():
        if obs.confidence is not Confidence.UNVERIFIED:
            if obs.value is None:
                report.add(opportunity.key, "missing_provenance", f"{name} claims a value it does not have")
            if obs.source is not Source.OPERATOR and not obs.evidence_url:
                report.add(opportunity.key, "missing_provenance", f"{name} has no evidence_url")
            if obs.is_stale(FIGURE_TTL):
                report.add(opportunity.key, "stale", f"{name} is over {FIGURE_TTL.days} days old")
            if not obs.is_planning_grade:
                report.unsafe_basis[f"{name} ({obs.basis.value})"] = (
                    report.unsafe_basis.get(f"{name} ({obs.basis.value})", 0) + 1
                )
        else:
            report.unverified_by_field[name] = report.unverified_by_field.get(name, 0) + 1

        if len(obs.method) < 3:
            report.add(opportunity.key, "missing_provenance", f"{name} has no usable method")

    # A dip-check without kill criteria is not an experiment, it is a hope.
    for check in opportunity.dip_checks:
        if not check.kill_criteria:
            report.add(opportunity.key, "unsound_experiment", f"dip-check '{check.method}' has no kill criteria")
        if check.is_complete and check.result is None:
            report.add(opportunity.key, "inconsistent", "dip-check marked complete with no recorded result")

    if opportunity.actuals:
        months = [a.month for a in opportunity.actuals]
        if len(months) != len(set(months)):
            report.add(opportunity.key, "inconsistent", "duplicate months in the actuals ledger")


def validate(store: Store) -> Report:
    report = Report()
    for opportunity in store.all():
        report.checked += 1
        validate_opportunity(opportunity, report)
    return report


def format_report(report: Report) -> str:
    lines = [f"Checked {report.checked} opportunities, {report.observations} observations.", ""]

    counts = report.by_kind()
    if not counts:
        lines.append("No findings. Every stored figure carries provenance.")
    else:
        for kind, n in sorted(counts.items()):
            marker = "FAIL" if kind == "missing_provenance" else "note"
            lines.append(f"  [{marker}] {kind}: {n}")

    if report.unsafe_basis:
        lines += ["", "Figures not safe to plan against (winners, or averages of winners):"]
        for name, n in sorted(report.unsafe_basis.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name}: {n}")

    if report.unverified_by_field:
        lines += ["", "Unestablished — expected, and the research queue:"]
        for name, n in sorted(report.unverified_by_field.items(), key=lambda kv: -kv[1])[:15]:
            lines.append(f"  {name}: {n}")

    hard = [f for f in report.findings if f.kind == "missing_provenance"]
    if hard:
        lines += ["", "Provenance failures:"]
        for f in hard[:20]:
            lines.append(f"  {f.key}  {f.detail}")

    lines += ["", "PASS" if report.ok else "FAIL — provenance problems found"]
    return "\n".join(lines)
