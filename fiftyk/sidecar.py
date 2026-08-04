"""Research sidecar.

Runs the already-authenticated Claude Code CLI as a subprocess instead of
calling the Anthropic API. No API key to manage, and the sidecar inherits web
search and fetch, which is what makes it able to actually establish a figure
rather than recall one.

The important property is that **the sidecar is not trusted**. It returns a
structured claim; that claim is then pushed through the same provenance schema
as everything else, and a figure without a source URL is rejected before it can
reach the store. A model recalling "Gumroad's median is about $70" from memory
is exactly the fabrication this codebase exists to prevent — so the contract
demands a URL it had to fetch, and the schema enforces it.

Every call reports its cost. Spend is capped, checked before each invocation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field

from .provenance import Confidence, Observation, SampleBasis, Source
from .research import ResearchItem

#: Where the CLI lives. The session's own binary is preferred.
CLAUDE_BIN = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude") or "claude"

#: Per-question ceiling. Research questions are bounded; a call that runs longer
#: than this has gone wandering.
DEFAULT_TIMEOUT_S = 420

#: Default spend ceiling for one `research --run`, in USD. Deliberately low —
#: this is meant to answer a handful of questions, not audit the internet.
DEFAULT_BUDGET_USD = 3.0

TOOLS = "WebSearch,WebFetch"

#: Appended to the sidecar's system prompt. The rules that make its output
#: usable rather than plausible.
SYSTEM_RULES = (
    "You are establishing a single factual figure for a decision engine. "
    "Rules, in order of importance: "
    "(1) Never state a number you did not read from a source you actually fetched "
    "in this session. Recalling a figure from memory is a failure, not an answer. "
    "(2) If you cannot find it, return found=false. That is a correct, expected, "
    "and useful answer — do not substitute an estimate. "
    "(3) Prefer platform-published or aggregate data. Creator-economy blogs and "
    "'how I earn $X' posts are marketing and are survivor-biased; if such a source "
    "is all that exists, report it with basis=anecdote so it is discounted. "
    "(4) Report what kind of sample the number is. A mean of a power-law "
    "distribution is not a typical outcome. "
    "(5) Output only the JSON object requested, with no prose around it."
)


class SidecarUnavailable(RuntimeError):
    """The CLI could not be found or run."""


class BudgetExhausted(RuntimeError):
    """The spend ceiling for this run has been reached."""


@dataclass
class Finding:
    """One answer from the sidecar, before it is trusted."""

    item: ResearchItem
    found: bool
    value: float | None = None
    source_url: str | None = None
    basis: str | None = None
    method: str | None = None
    note: str | None = None
    cost_usd: float = 0.0
    error: str | None = None

    def as_observation(self) -> Observation[float] | None:
        """Convert to a stored fact, or None if it does not meet the bar.

        This is the gate. A finding without a value, a URL or a recognisable
        sample basis does not become an Observation — it stays a gap.
        """
        if not self.found or self.value is None or not self.source_url:
            return None
        try:
            basis = SampleBasis(self.basis or "aggregate")
        except ValueError:
            basis = SampleBasis.ANECDOTE  # unrecognised basis is treated as weak
        return Observation[float](
            value=float(self.value),
            source=Source.INDUSTRY_REPORT,
            method=(self.method or "established by research sidecar")[:400],
            confidence=Confidence.VERIFIED,
            basis=basis,
            evidence_url=self.source_url,
            note=self.note,
        )

    @property
    def rejected_reason(self) -> str | None:
        if not self.found:
            return self.note or self.error or "not found"
        if self.value is None:
            return "no value returned"
        if not self.source_url:
            return "no source URL — rejected rather than stored unsourced"
        return None


@dataclass
class RunReport:
    findings: list[Finding] = field(default_factory=list)
    spent_usd: float = 0.0
    stopped_early: str | None = None

    @property
    def accepted(self) -> list[Finding]:
        return [f for f in self.findings if f.as_observation() is not None]

    @property
    def rejected(self) -> list[Finding]:
        return [f for f in self.findings if f.as_observation() is None]


def _prompt_for(item: ResearchItem, context: str) -> str:
    return f"""Establish one figure for a decision engine.

Context: {context}
Field:   {item.field}
Question: {item.question}
Why it matters: {item.why_it_matters}

Search the web and fetch real sources. Then output ONLY this JSON object:

{{
  "found": true or false,
  "value": <number in the unit described below, or null>,
  "source_url": "<the URL you actually fetched, or null>",
  "basis": "aggregate" | "median" | "mean" | "top_decile" | "anecdote",
  "method": "<one sentence: what the number is and how the source measured it>",
  "note": "<caveats, or why you could not find it>"
}}

Units: any money figure must be a MONTHLY amount in Indian rupees, converting
from USD at 84 INR/USD. A rate or fraction (like annual decay) must be a decimal
between 0 and 1. An hours figure must be hours.

If no credible source gives this figure, return found=false with a note saying
so. Do not estimate, interpolate, or recall it from memory."""


def available() -> bool:
    return shutil.which(CLAUDE_BIN) is not None or os.path.exists(CLAUDE_BIN)


def ask(item: ResearchItem, context: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> Finding:
    """Put one question to the sidecar."""
    if not available():
        raise SidecarUnavailable(
            f"Claude Code CLI not found at {CLAUDE_BIN}. Set CLAUDE_CODE_EXECPATH."
        )

    command = [
        CLAUDE_BIN,
        "-p",
        _prompt_for(item, context),
        "--output-format",
        "json",
        "--allowed-tools",
        TOOLS,
        "--append-system-prompt",
        SYSTEM_RULES,
    ]

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout_s, cwd="/tmp"
        )
    except subprocess.TimeoutExpired:
        return Finding(item=item, found=False, error=f"timed out after {timeout_s}s")
    except OSError as exc:
        raise SidecarUnavailable(f"could not run {CLAUDE_BIN}: {exc}") from exc

    if completed.returncode != 0:
        return Finding(
            item=item, found=False, error=f"exit {completed.returncode}: {completed.stderr[:300]}"
        )

    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return Finding(item=item, found=False, error="sidecar did not return JSON")

    cost = float(envelope.get("total_cost_usd") or 0.0)
    if envelope.get("is_error"):
        return Finding(item=item, found=False, cost_usd=cost, error=str(envelope.get("result"))[:300])

    payload = _extract_json(envelope.get("result") or "")
    if payload is None:
        return Finding(item=item, found=False, cost_usd=cost, error="no JSON object in the reply")

    return Finding(
        item=item,
        found=bool(payload.get("found")),
        value=payload.get("value"),
        source_url=payload.get("source_url"),
        basis=payload.get("basis"),
        method=payload.get("method"),
        note=payload.get("note"),
        cost_usd=cost,
    )


def _extract_json(text: str) -> dict | None:
    """Pull the JSON object out of a reply that may have prose around it."""
    text = text.strip()
    if text.startswith("```"):
        # Strip a fenced block, keeping whatever is inside it.
        parts = text.split("```")
        text = max(parts, key=len)
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run(
    items: list[ResearchItem],
    contexts: dict[str, str],
    budget_usd: float = DEFAULT_BUDGET_USD,
    limit: int | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> RunReport:
    """Work through a brief, highest-value questions first, inside a spend cap."""
    report = RunReport()
    queue = items[:limit] if limit is not None else items

    for item in queue:
        if report.spent_usd >= budget_usd:
            report.stopped_early = (
                f"spend ceiling reached (${report.spent_usd:.2f} of ${budget_usd:.2f})"
            )
            break
        finding = ask(item, contexts.get(item.opportunity_key, item.opportunity_key), timeout_s)
        report.spent_usd += finding.cost_usd
        report.findings.append(finding)

    return report
