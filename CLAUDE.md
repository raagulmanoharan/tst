# CLAUDE.md

**Read this file at the start of every session, before doing anything else.**

This repo is a lead-qualification pipeline for a **solo freelance web developer based in
Bangalore**. It finds local businesses whose weak online presence is measurably costing
them customers, verifies that claim with evidence, scores the lead, and drafts outreach
for human review.

---

## Rule 1 — Never assume. Ask.

This is the operator's standing instruction and it overrides convenience.

- If a requirement is ambiguous, **ask** — do not pick the sensible-looking default and
  proceed.
- Do not infer business rules, thresholds, prices, categories, or target markets that
  were not explicitly stated.
- Do not expand scope because something "would obviously be useful".
- If you find yourself writing "presumably", "likely intended", or "I'll assume" — stop
  and ask instead.

## Rule 2 — Never fabricate data.

The whole point of this system is that every lead is backed by evidence. A plausible
invented value is worse than no value, because it silently poisons the tracker.

- Every stored fact carries provenance: `value, source, method, observed_at, confidence,
  evidence_url`. The schema **rejects** writes without it.
- If something cannot be verified, it is `UNVERIFIED`. That is a legitimate, expected
  state — not a gap to be filled in.
- Never estimate a rating, review count, phone number, price, or contact name.
- Never invent statistics in code comments, docs, or outreach copy.
- If two sources disagree, flag for human review. Do not silently pick a winner.

## Rule 3 — The Google data boundary. Non-negotiable.

Google Maps Platform ToS §3.2.3(a)(iii) prohibits copying and saving business names,
addresses, and reviews. §14.3 permits caching **latitude and longitude only** — there is
no general 30-day cache right for business fields. §3.2.3(d)(iii) bars use in a
"listings or directory service".

**May be persisted:**
- `place_id` (explicitly exempt from caching restrictions)
- lat/long, with a 30-day TTL, auto-expired
- our own observations, scores, notes, outreach history
- anything observed directly from *the business's own website* or a public ad library —
  that is their published data, not Google Maps Content

**Must never be persisted:** name, address, phone, rating, review count, or website URL
*as returned by the Places API*. These are fetched live at render time and held in memory
only.

There is a test (`tests/test_tos_conformance.py`) that fails the build if a persisted
model gains such a field. Do not weaken it. If a feature seems to require storing Google
content, the feature is wrong — not the rule.

## Rule 4 — Outreach channels are legally constrained.

- **Email — allowed.** No Indian statutory equivalent to CAN-SPAM; IT Act s.66A was
  struck down in 2015. Keep authentication (SPF/DKIM/DMARC) clean and complaints <0.1%.
- **In-person walk-in — allowed.** Commercial premises are unregulated for this.
- **Cold calling — forbidden.** Under TRAI TCCCPR this makes the operator an Unregistered
  Telemarketer. Since Feb 2025 the complainant need not be on DND. Escalation ends in
  disconnection of *all* telecom resources for up to 2 years, blacklisted across every
  operator. The sanction attaches to the person, not the SIM — a second number does not
  help.
- **Cold SMS — forbidden.** Same regime plus DLT registration requirements.
- **Cold WhatsApp — forbidden.** Breaches Meta's Business Messaging Policy outright;
  messaging unsaved contacts is the top ban trigger.

Once a prospect replies or calls, phone and WhatsApp become legitimate — the conversation
is theirs, not unsolicited. **Never build a send function.** Drafts are for human review
and manual sending only.

## Rule 5 — Freelancer voice, not agency voice.

The operator is one named person. This is a deliberate competitive advantage: the market
is saturated with agency spam ("we noticed your business could benefit from our
services") at 5–10 pitches a day per owner.

All generated outreach must be:
- **First person singular.** Never "we", "our team", "our agency".
- **Specific.** Lead with one concrete observed defect on their actual site, never a
  service menu.
- **Low-pressure.** No decks, no capability statements, no proposal templates.
- **Short.** If it reads like a template, it has failed.

---

## Strategy context

**Do not filter on "has no website".** Practitioners have inverted this since 2016: a
business with a *bad* site has proven it will pay for one; a business with *none* has
usually been asked 50 times and said no. Qualify on a compound signal — the 2-of-3
motivation test (needs customers / will spend / will engage). The highest-intent signal
is **running ads that point at a broken site**.

**Excluded categories** (research-backed dead ends): restaurants, cafés, salons, kiranas,
gyms. Google Business Profile, Instagram and WhatsApp already serve them.

**Market sequence:** Bangalore (walk-in radius, English) → Chennai (Tamil) → Pondicherry
(hospitality niche only). Hyderabad is parked — no Telugu.

**Offer:** one-time build, no retainer. The schema carries hosting/domain/renewal fields
so a care plan could be added later, but nothing currently depends on it.

**Registration status:** the operator is an unregistered sole proprietor. GST threshold
is ₹20 lakh for both intra- and inter-State services (Notification 10/2017-IT; Finance
Act 2023 made s.23 override s.24). Invoices must not show a GSTIN or any GST line.

---

## Working agreements

- Run `python -m leadgen validate` after any change to the store or verifiers.
- Run `pytest` before committing. The golden fixtures exist to catch verifier drift.
- Keep API usage inside the India free tier (35,000 Pro + 7,000 Enterprise calls/month).
  `leadgen budget` reports current usage.
- Secrets go in `.env`, which is gitignored. Never commit an API key.
