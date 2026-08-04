"""The research sidecar, and the gate that stops it being trusted.

No network here — the subprocess is stubbed. What is tested is the contract:
a claim from the sidecar only becomes a stored fact if it carries a value, a
source URL and a recognisable sample basis.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from fiftyk import sidecar
from fiftyk.provenance import SampleBasis, Source
from fiftyk.research import ResearchItem

ITEM = ResearchItem(
    opportunity_key="unity_asset_store",
    field="median_seller_net_monthly_inr",
    question="What does a median participant net per month?",
    why_it_matters="decides whether this is viable at all",
    priority=1,
)


def envelope(result: str, cost: float = 0.1, is_error: bool = False) -> str:
    return json.dumps({"result": result, "total_cost_usd": cost, "is_error": is_error})


def stub_run(monkeypatch, stdout: str, returncode: int = 0):
    def fake(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(sidecar.subprocess, "run", fake)
    monkeypatch.setattr(sidecar, "available", lambda: True)


# -- the trust gate -----------------------------------------------------


def test_a_sourced_finding_becomes_an_observation():
    finding = sidecar.Finding(
        item=ITEM, found=True, value=4200.0, source_url="https://platform.test/report",
        basis="median", method="platform transparency report",
    )
    obs = finding.as_observation()
    assert obs is not None
    assert obs.value == 4200.0
    assert obs.basis is SampleBasis.MEDIAN
    assert obs.source is Source.INDUSTRY_REPORT


def test_a_finding_without_a_url_is_refused():
    """The whole point: an unsourced number never reaches the store."""
    finding = sidecar.Finding(item=ITEM, found=True, value=4200.0, source_url=None, basis="median")
    assert finding.as_observation() is None
    assert "no source URL" in finding.rejected_reason


def test_not_found_is_refused_and_is_not_an_error():
    finding = sidecar.Finding(item=ITEM, found=False, note="no platform publishes this")
    assert finding.as_observation() is None
    assert finding.rejected_reason == "no platform publishes this"


def test_a_found_flag_without_a_value_is_refused():
    finding = sidecar.Finding(item=ITEM, found=True, value=None, source_url="https://x.test")
    assert finding.as_observation() is None


def test_an_unrecognised_basis_is_treated_as_weak():
    """Fail closed: an unknown sample basis must not be treated as plannable."""
    finding = sidecar.Finding(
        item=ITEM, found=True, value=1.0, source_url="https://x.test", basis="vibes"
    )
    obs = finding.as_observation()
    assert obs.basis is SampleBasis.ANECDOTE
    assert not obs.is_planning_grade


def test_a_mean_from_the_sidecar_is_not_planning_grade():
    finding = sidecar.Finding(
        item=ITEM, found=True, value=8400.0, source_url="https://x.test", basis="mean"
    )
    assert not finding.as_observation().is_planning_grade


# -- reply parsing ------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        '{"found": true, "value": 4200, "source_url": "https://x.test", "basis": "median"}',
        '```json\n{"found": true, "value": 4200, "source_url": "https://x.test", "basis": "median"}\n```',
        'Here is the result:\n{"found": true, "value": 4200, "source_url": "https://x.test", "basis": "median"}\nHope that helps.',
    ],
)
def test_json_is_extracted_through_fences_and_prose(monkeypatch, reply):
    stub_run(monkeypatch, envelope(reply))
    finding = sidecar.ask(ITEM, "context")
    assert finding.found
    assert finding.value == 4200


def test_a_non_json_reply_is_a_clean_failure(monkeypatch):
    stub_run(monkeypatch, envelope("I could not find that figure anywhere."))
    finding = sidecar.ask(ITEM, "context")
    assert not finding.found
    assert "no JSON object" in finding.error


def test_a_broken_subprocess_is_a_clean_failure(monkeypatch):
    stub_run(monkeypatch, "not json at all")
    finding = sidecar.ask(ITEM, "context")
    assert not finding.found
    assert finding.as_observation() is None


def test_a_nonzero_exit_is_a_clean_failure(monkeypatch):
    stub_run(monkeypatch, "", returncode=1)
    finding = sidecar.ask(ITEM, "context")
    assert not finding.found


def test_a_timeout_is_a_clean_failure(monkeypatch):
    def fake(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(sidecar.subprocess, "run", fake)
    monkeypatch.setattr(sidecar, "available", lambda: True)
    finding = sidecar.ask(ITEM, "context", timeout_s=1)
    assert not finding.found
    assert "timed out" in finding.error


def test_missing_cli_raises_rather_than_silently_doing_nothing(monkeypatch):
    monkeypatch.setattr(sidecar, "available", lambda: False)
    with pytest.raises(sidecar.SidecarUnavailable):
        sidecar.ask(ITEM, "context")


# -- budget -------------------------------------------------------------


def test_spend_ceiling_stops_the_run(monkeypatch):
    stub_run(
        monkeypatch,
        envelope('{"found": true, "value": 1, "source_url": "https://x.test", "basis": "median"}', cost=0.40),
    )
    items = [ITEM] * 10
    report = sidecar.run(items, {}, budget_usd=1.0)
    assert report.stopped_early is not None
    assert len(report.findings) == 3  # stops once spend reaches the ceiling
    assert report.spent_usd == pytest.approx(1.20)


def test_limit_caps_the_number_of_questions(monkeypatch):
    stub_run(
        monkeypatch,
        envelope('{"found": true, "value": 1, "source_url": "https://x.test", "basis": "median"}', cost=0.01),
    )
    report = sidecar.run([ITEM] * 10, {}, budget_usd=100.0, limit=2)
    assert len(report.findings) == 2


def test_report_separates_accepted_from_rejected(monkeypatch):
    replies = iter([
        envelope('{"found": true, "value": 5, "source_url": "https://x.test", "basis": "median"}'),
        envelope('{"found": false, "note": "nothing published"}'),
    ])

    def fake(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=next(replies), stderr="")

    monkeypatch.setattr(sidecar.subprocess, "run", fake)
    monkeypatch.setattr(sidecar, "available", lambda: True)

    report = sidecar.run([ITEM, ITEM], {})
    assert len(report.accepted) == 1
    assert len(report.rejected) == 1
