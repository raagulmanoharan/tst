# leadgen

A lead-qualification pipeline for a solo freelance web developer in Bangalore.

It finds local businesses whose weak online presence is measurably costing them
customers, verifies that claim with evidence, scores it, and drafts outreach for
you to review and send by hand.

It does **not** send anything, and it does not target businesses simply for
lacking a website.

---

## Why it works this way

Three research findings shaped the design, and all three cut against the obvious
approach.

**"Has no website" is a dead filter.** Practitioners have said so since 2016 and
have inverted it: a business with a *bad* site has already proved it will pay for
one; a business with *none* has usually been pitched fifty times and said no.
Owners report 5–10 identical pitches a day. Google Business Profile, Instagram,
Justdial's free site builder and WhatsApp Business AI already cover what most
small retail wanted a website for. So the scorer treats "no website" as a weak
starting signal that **cannot qualify a lead on its own**, and qualifies instead
on a compound of observed defects, proven willingness to spend, and signs of an
active business.

**Storing Google Maps data is prohibited.** Maps Platform ToS §3.2.3(a)(iii)
forbids copying and saving business names, addresses and reviews; §14.3 permits
caching latitude and longitude *only* — there is no general 30-day cache right.
So this stores `place_id` (explicitly exempt) plus its own observations, and
re-fetches everything else live. India's Places price list gives 35,000 free Pro
and 7,000 free Enterprise calls a month, so a few hundred leads costs nothing.

**Manual beats automated by roughly 100x.** One operator closed 3 clients from
120 hand-researched emails (2.5%); the same team's automated setup closed 2 from
10,000 (0.02%). This is therefore a qualification engine, not a sending tool. It
is designed to hand you a short list worth eight careful emails a day.

## Quick start

```bash
pip install -e ".[dev]"
cp .env.example .env      # then fill it in

python -m leadgen categories                              # what gets searched, and why
python -m leadgen discover --city bangalore --max-centres 2   # cheap trial sweep
python -m leadgen verify --limit 25                       # visit sites, collect evidence, score
python -m leadgen draft                                   # draft outreach (never sends)
python -m leadgen dashboard --live && open out/index.html
python -m leadgen validate                                # audit provenance and staleness
```

## Commands

| Command | What it does |
|---|---|
| `discover` | Sweeps a city grid per category. Stores `place_id`s and nothing else. |
| `verify` | One live lookup per lead, visits their site, records evidence, scores. |
| `score` | Re-scores from stored evidence with no network calls. |
| `draft` | Writes email and walk-in drafts for qualified leads. Never sends. |
| `dashboard` | Renders the tracker to a single HTML file. |
| `validate` | Audits every stored fact for provenance and staleness. |
| `budget` | API usage against the free tier. |
| `ads` / `search` | Records a manual check you did by hand. |

## The two invariants

**Everything carries provenance.** Every stored fact has a source, a method, a
timestamp, a confidence and an evidence URL. The schema *rejects* a write
without them. When a check establishes nothing, the result is `UNVERIFIED` — a
first-class state, never a guess. Two signals cannot be established honestly by
any free API — whether a business is running ads, and where it ranks — so those
stay `UNVERIFIED` and surface in the dashboard as one-click links for you to
check yourself. Record what you find with `leadgen ads` / `leadgen search`.

**No Google Maps Content is ever persisted.** `PersistedModel` refuses any field
named `rating`, `phone`, `business_name`, `website_uri` and so on, at
class-definition time. `tests/test_tos_conformance.py` fails the build if a model
slips past it. If a feature seems to need one of these, the feature is wrong.

## Outreach channels

Only two cold channels are legal and safe here, and the code only supports those.

- **Email** — no Indian statutory equivalent to CAN-SPAM; IT Act s.66A was struck
  down in 2015. Set up SPF, DKIM and DMARC; keep complaints under 0.1%.
- **Walk-in** — unregulated for commercial premises, and the best-converting
  channel in the research.

Cold calling makes you an Unregistered Telemarketer under TRAI's TCCCPR. Since
February 2025 the complainant need not even be on DND, and the escalation ends in
disconnection of *all* your telecom resources for up to two years, blacklisted
across every operator — and it attaches to you, not the SIM, so a second number
does not help. Cold SMS is worse. Cold WhatsApp breaches Meta's policy outright.

Once a prospect replies, phone and WhatsApp are fine — the conversation is theirs.

## Before your first email

1. Register a personal-name domain and put your own one-page site on it. You are
   selling web presence; yours is the proof. Owners flag pitchers with no site of
   their own as instant deletes.
2. Configure SPF, DKIM and DMARC on that domain.
3. Nothing needs registering to freelance in India — no incorporation, no Udyam,
   no trade licence. GST starts at ₹20 lakh, for interstate clients too
   (Notification 10/2017-IT). Until then invoices must carry no GSTIN and no GST
   line.

*Not legal or tax advice — confirm with a CA before scaling.*

## Development

```bash
pytest                    # 61 tests, no network calls
python -m leadgen validate
```

`CLAUDE.md` carries the rules this codebase is built on. Read it before changing
anything — especially the no-assumptions rule and the Google data boundary.
