"""The validation harness.

Answers one question across the whole database: is anything in here being taken
on trust? Every finding is something a human should look at — nothing is
auto-repaired, because silently fixing data is how a tracker drifts away from
reality without anyone noticing.

Run after any change to the store or the verifiers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from .store import LeadStore
from .store.models import (
    FORBIDDEN_PERSISTED_FIELDS,
    Confidence,
    Lead,
    PersistedModel,
    Source,
)

#: How long each kind of evidence stays trustworthy before it needs re-checking.
TTLS: dict[str, timedelta] = {
    "site": timedelta(days=30),
    "ads": timedelta(days=14),     # ad campaigns start and stop quickly
    "search": timedelta(days=30),
}


@dataclass
class Finding:
    place_id: str
    kind: str
    detail: str


@dataclass
class Report:
    leads_checked: int = 0
    observations_checked: int = 0
    findings: list[Finding] = field(default_factory=list)
    unverified_by_field: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Provenance and ToS problems are failures. Staleness and gaps are not."""
        return not any(
            f.kind in ("missing_provenance", "tos_violation") for f in self.findings
        )

    def add(self, place_id: str, kind: str, detail: str) -> None:
        self.findings.append(Finding(place_id, kind, detail))

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for f in self.findings:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        return counts


def _check_schema_boundary(report: Report) -> None:
    """Walk every persisted model and confirm none has grown a Google field.

    `PersistedModel` already refuses these at class-definition time; this is the
    belt to that braces, and it catches a model that bypassed the base class.
    """
    def walk(cls: type[PersistedModel]) -> None:
        offending = set(cls.model_fields) & FORBIDDEN_PERSISTED_FIELDS
        if offending:
            report.add(
                "-", "tos_violation",
                f"{cls.__name__} declares {', '.join(sorted(offending))}",
            )
        for sub in cls.__subclasses__():
            walk(sub)

    walk(PersistedModel)


def validate(store: LeadStore) -> Report:
    report = Report()
    _check_schema_boundary(report)

    for lead in store.all():
        report.leads_checked += 1
        _check_lead(lead, report)

    return report


def _check_lead(lead: Lead, report: Report) -> None:
    observations = lead.observations()
    report.observations_checked += len(observations)

    for key, observation in observations.items():
        group = key.split(".", 1)[0]

        # The schema should make this impossible; if it ever happens, the schema
        # was bypassed and that is a hard failure.
        if observation.confidence is not Confidence.UNVERIFIED:
            if observation.value is None:
                report.add(lead.place_id, "missing_provenance", f"{key} claims confidence but has no value")
            if observation.source is not Source.OPERATOR and not observation.evidence_url:
                report.add(lead.place_id, "missing_provenance", f"{key} has no evidence_url")

        if observation.confidence is Confidence.UNVERIFIED:
            report.unverified_by_field[key] = report.unverified_by_field.get(key, 0) + 1
        else:
            ttl = TTLS.get(group)
            if ttl and observation.is_stale(ttl):
                report.add(lead.place_id, "stale", f"{key} is older than {ttl.days}d and needs re-checking")

        if not observation.method or len(observation.method) < 3:
            report.add(lead.place_id, "missing_provenance", f"{key} has no usable method description")

    for contradiction in lead.contradictions:
        report.add(lead.place_id, "contradiction", contradiction)

    if lead.geo_observed_at is not None and lead.lat is None:
        report.add(lead.place_id, "inconsistent", "geo timestamp present but coordinates missing")

    # Anything drafted but not approved is waiting on the operator, by design.
    for record in lead.outreach:
        if record.sent_manually_at and not record.approved_by_operator:
            report.add(lead.place_id, "inconsistent", f"{record.channel} marked sent but never approved")


def format_report(report: Report) -> str:
    lines = [
        f"Checked {report.leads_checked} leads, {report.observations_checked} observations.",
        "",
    ]
    counts = report.by_kind()
    if not counts:
        lines.append("No findings. Every stored fact carries provenance.")
    else:
        for kind, n in sorted(counts.items()):
            marker = "FAIL" if kind in ("missing_provenance", "tos_violation") else "note"
            lines.append(f"  [{marker}] {kind}: {n}")

    if report.unverified_by_field:
        lines += ["", "Unverified fields (expected — these need a human):"]
        for key, n in sorted(report.unverified_by_field.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {key}: {n}")

    shown = [f for f in report.findings if f.kind in ("missing_provenance", "tos_violation", "contradiction")]
    if shown:
        lines += ["", "Detail:"]
        for f in shown[:40]:
            lines.append(f"  {f.place_id}  {f.kind}  {f.detail}")
        if len(shown) > 40:
            lines.append(f"  ... and {len(shown) - 40} more")

    lines += ["", "PASS" if report.ok else "FAIL — provenance or ToS problems found"]
    return "\n".join(lines)
