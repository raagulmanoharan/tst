# CLAUDE.md

**Read this file at the start of every session, before doing anything else.**

This repo is a decision engine for one operator with one goal: **₹50,000/month
net income**, from under ₹1 lakh of capital, within about two years. It models
opportunities as economics, eliminates what cannot work, runs due diligence on
what might, and tracks what is actually deployed against the goal.

---

## Rule 1 — Never assume. Ask.

The operator's standing instruction, and it overrides convenience.

- If a requirement is ambiguous, **ask** — do not pick the sensible-looking
  default and proceed.
- Do not infer goals, thresholds, exclusions or preferences that were not
  explicitly stated.
- Do not expand scope because something "would obviously be useful".
- If you find yourself writing "presumably", "likely intended", or "I'll assume"
  — stop and ask instead.

## Rule 2 — Never fabricate a number.

This domain is drowning in invented figures. Almost every "how much can you earn
from X" article is content marketing for a tool that sells X. A plausible number
with no source behind it is worse than no number, because it will silently drive
a two-year decision.

- Every figure carries `value, source, method, observed_at, confidence, basis,
  evidence_url`. The schema **rejects** a write without provenance.
- If something cannot be established, it is `UNVERIFIED`. That is a legitimate,
  expected state — and often the honest finding is *"no platform publishes this
  and everyone claiming otherwise is fabricating"*.
- **Record the sample basis.** `MEDIAN` and `AGGREGATE` are plannable. `MEAN`,
  `TOP_DECILE` and `ANECDOTE` are not — in a power-law market the mean describes
  almost nobody. Gumroad's top 1% take 99.5% of revenue.
- Never estimate a median, a royalty rate, a conversion figure or a timeline.
- If two sources disagree, flag it. Do not silently pick a winner.

## Rule 3 — Eliminate before you list.

A list of opportunities is useless when the binding constraint is capital or
attention. The engine's first job is to say **no**, and to show the arithmetic
that produced the no so the operator can argue with it.

A blocked opportunity stays in the catalogue with its reason attached. Deleting
it just means rediscovering it in six months.

When everything is blocked, that is a **result**, not a failure. Run the
sensitivity analysis and report which single constraint buys the most if
relaxed. Never soften a verdict to produce a more encouraging answer.

## Rule 4 — The operator's constraints are not negotiable without asking.

- **Goal:** ₹50,000/month *net, in pocket* — not revenue.
- **Capital:** under ₹1 lakh. Every capital-yield route (property, FD, REIT,
  dividends, cloud kitchen) is arithmetically closed by one to two orders of
  magnitude. Do not re-propose them.
- **Time:** heavy now, hands-off later. Above ~5 h/week at maturity it is a job,
  not passive income.
- **No chasing demand.** No outreach, no demos, no convincing anyone. Demand must
  arrive via marketplace, app store or search. This is the hardest constraint and
  the one most platforms have stopped rewarding.
- **No on-camera work or audience building. No teaching or courses. No trading,
  crypto or speculation. No subscription software.**

Excluded options stay in the catalogue, costed honestly, so the price of the
exclusion is visible. They are never quietly re-recommended.

## Rule 5 — Distinguish market facts from operator estimates.

"No research exists" and "you haven't told me how fast you work" are different
problems with different fixes. `Economics.OPERATOR_ESTIMABLE` marks the fields
only the operator can answer. Conflating them leaves everything stuck at
`NEEDS_EVIDENCE` forever.

---

## What the research established (2026-08-04)

Findings that cost real work and are pinned by tests. Do not quietly contradict
them; if new evidence arrives, record it with provenance and let the verdict move.

- **Median outcomes are near zero across the board.** Gumroad: median creator
  $72/month, 44% of products earn $0, top 1% take 99.5% of revenue. Envato: ~1,500
  of 81,000+ authors "earn a living". Steam: median 2025 release netted ~$74
  lifetime, and ~40% did not recoup the $100 fee.
- **Platforms de-monetised organic discovery between 2024 and 2026.** Amazon Merch
  now pays roughly double to sellers bringing external traffic. Google's AI
  Overviews cut result clicks from 15% to 8%. This directly attacks the operator's
  no-promotion constraint.
- **Structurally closed:** Chrome extensions (in-store payments ended 2021, median
  17 installs), Obsidian/Blender/Figma plugins (no open paid path), Figma Community
  (India absent from payout countries).
- **Decay is the deciding variable.** A portfolio built at rate B against decay d
  settles at B/d. If the portfolio needed exceeds that equilibrium, the goal is
  unreachable at *any* horizon — a result naive division hides completely.

## Working agreements

- Run `python -m fiftyk validate` after any change to the store or catalogue.
- Run `pytest` before committing.
- There is no Anthropic API key here, so `fiftyk research` emits a **brief** for
  a researcher to fill, rather than pretending to run research itself.
- Secrets go in `.env`, which is gitignored.
