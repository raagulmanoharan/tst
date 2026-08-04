# fiftyk

A decision engine for reaching **₹50,000/month net**, from under ₹1 lakh of
capital, without chasing demand.

It models opportunities as economics rather than ideas, eliminates what cannot
work and shows the arithmetic, runs structured due diligence on what might, and
tracks what is actually deployed against the goal.

---

## The first thing it tells you

Under the real constraints — ₹1 lakh capital, no promotion, no audience, no
teaching, hands-off within 5 h/week — **nothing in the researched catalogue
clears every gate.**

That is the product, not a bug. The useful output is *why*, and *which single
constraint buys the most if you give it up*:

```
$ python -m fiftyk status
Goal  ₹50,000/month net within 24 months
Now   ₹0/month  (0%)

Nothing clears every constraint.
That is a result, not a failure — run `python -m fiftyk relax` to see
which single constraint opens the most if you give it up.

8 awaiting evidence, 6 ruled out.
```

## Why capital-yield routes are closed

₹1 lakh at 8% yields ₹667/month against a ₹50,000 target.

| Route | Capital needed | Verdict |
|---|---|---|
| FD / debt funds @ 7.5% | ~₹80 lakh | closed — 80x over |
| Commercial property @ 7% | ~₹86 lakh | closed |
| Bangalore residential @ 3.5% | ~₹1.7 crore | closed |
| Cloud kitchen | ₹10–25 lakh, and it is a job | closed |

The only open space is sweat equity: build once, sell many times. The binding
constraint is not money — it is your attention. So the engine ranks by
**attention price**: build hours per rupee of durable monthly income.

## What the research found

Every figure in the catalogue is sourced or marked `UNVERIFIED`. Nothing is
estimated to fill a gap.

- **Median outcomes are near zero.** Gumroad's median creator earns **$72/month**;
  44% of products earn exactly $0; the top 1% take 99.5% of revenue. Envato:
  ~1,500 of 81,000+ authors "earn a living". Steam's median 2025 release netted
  about **$74 lifetime**, and ~40% did not recoup the $100 listing fee.
- **Platforms stopped rewarding organic discovery.** Amazon Merch's June 2026
  tiers pay roughly **double** to sellers bringing external traffic. Google's AI
  Overviews cut result clicks from 15% to 8%. Shutterstock's revenue fell 18% YoY
  with downloads down 14%. The no-promotion constraint is precisely the behaviour
  these platforms de-monetised.
- **Some categories are structurally closed**: Chrome extensions (in-store
  payments ended in 2021; the median extension has 17 installs), Obsidian/Blender
  plugins (no paid path), Figma Community (India is not a supported payout
  country).

## The decay model

The one piece of maths worth understanding. A portfolio built at `B` listings a
year, decaying at fraction `d` a year, follows `dP/dt = B − d·P` and settles at
an equilibrium of **`B/d`**.

If the portfolio you need is larger than that equilibrium, the goal is not slow —
it is **unreachable at any time horizon**, however long you work. Division hides
this completely.

The same maths gives the honest answer on passivity: holding a portfolio at goal
size means replacing what decays, forever. At 30% annual decay on a 100-listing
portfolio at 10 hours each, that is **5.8 h/week for life** — a job, not passive
income.

## Usage

```bash
pip install -e ".[dev]"

python -m fiftyk seed                    # load the researched catalogue
python -m fiftyk status                  # what to do next
python -m fiftyk relax                   # which constraint to give up
python -m fiftyk show unity_asset_store  # one opportunity in full
python -m fiftyk research                # what to find out next, by decision value
python -m fiftyk dashboard && open out/index.html
python -m fiftyk validate                # audit provenance
```

Recording what you learn:

```bash
# your own estimates — nobody publishes how fast you work
python -m fiftyk estimate unity_asset_store --build-hours 12 --upkeep-hours 2

# a researched figure, with provenance the schema will enforce
python -m fiftyk record unity_asset_store --field median_seller_net_monthly_inr \
    --value 4200 --basis median --source platform_data \
    --url https://... --method "platform transparency report"

# a time-boxed experiment, with kill criteria decided in advance
python -m fiftyk dipcheck unity_asset_store --method "ship one asset, measure 60 days" \
    --hours 20 --kill "fewer than 5 sales in 60 days" --kill "zero organic impressions"

# a real month — the model corrects itself against reality
python -m fiftyk actual unity_asset_store --month 2026-09 --net 3200 --hours 20 --listings 8
```

## How it avoids lying to you

**Provenance is enforced by the schema.** Every figure carries a source, method,
timestamp, confidence and evidence URL. A write without them is rejected.
`UNVERIFIED` is a first-class state.

**Survivor bias is tracked explicitly.** Every figure declares its sample basis.
`MEDIAN` and `AGGREGATE` can drive projections; `MEAN`, `TOP_DECILE` and
`ANECDOTE` cannot — in a power-law market the average describes almost nobody.
A projection resting on them is downgraded and flagged.

**Missing evidence is split by who can fix it.** "No published figure found" and
"only you know how fast you work" are different problems, reported separately.

**Blocked options stay visible, with their arithmetic.** Including the ones you
excluded — so the price of the exclusion is on screen rather than forgotten.

## Research loop

`fiftyk research` prioritises what is worth finding out next by decision value —
a missing figure on an already-blocked option is worth nothing, while a median on
a live candidate can settle the question outright.

`fiftyk research --run` then answers the brief using a **sidecar**: the
authenticated Claude Code CLI, run headless as a subprocess. No API key to
manage, and it inherits web search and fetch, so it establishes figures rather
than recalling them.

```bash
python -m fiftyk research              # what to find out, highest value first
python -m fiftyk research --run --limit 5 --budget 2.00
```

**The sidecar is not trusted.** Its answer is a claim, and the claim goes through
the same provenance schema as everything else: no value, no source URL, or no
recognisable sample basis, and it is rejected rather than stored. An unrecognised
basis fails closed to `anecdote`. Every call reports its cost, and the run stops
at the spend ceiling.

That gate does real work. On its first live run against FAB, the sidecar found
only aggregate payouts ($24M across ~20,000 publishers), recognised that dividing
them gives a mean of a power-law distribution, and returned `found=false` rather
than pass off ~$100/month as a median. A rejection is a correct answer.

Questions that are judgement rather than lookup — *"can this algorithm surface a
listing without promotion?"* — are held back from the sidecar and reported
separately. They need reasoning, not a search.

Opportunity landscapes do not change minute to minute. Weekly is the honest
cadence; anything faster is dashboard theatre.

## Development

```bash
pytest                   # 83 tests, no network
python -m fiftyk validate
```

`CLAUDE.md` carries the rules this codebase is built on — particularly the
no-assumptions rule, the no-fabrication rule, and the constraint set. Read it
before changing anything.
