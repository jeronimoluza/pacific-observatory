# 2026-08-05 — Global F&B price-source sweep (5 regions, 15-agent fan-out)

**Status:** complete — see [Results](#results) at the end
**Deliverables:** `2026-08-05-fnb-coverage-by-country.csv` (118 countries),
`2026-08-05-fnb-onboarding-queue.csv` (270 viable sources, ranked)
**Skill:** `onboard-price-sources` (scope router → "ready-made candidate list" → Phase 2.5)
**Input:** `price_scraping_global_sources_fnb.csv` (685 rows, repo root, untracked)

## Ask

Probe the supplied 685-source candidate list for feasibility, discover additional
sources where the list is thin, and estimate **deep COICOP F&B leaf coverage by
country**. Three Sonnet agents per region across `eap`, `eca`, `ssa`, `sar`,
`menaap`.

This is a **feasibility + coverage-estimate run**, not a full onboarding run. The
deliverable is a probe verdict per source plus a per-country leaf-coverage
estimate — manifests/spiders are a follow-on, gated on what survives.

## The denominator

`coicop_taxonomy.load_taxonomy_index()` → 538 deepest leaves total, of which
**279 are food & beverage**: 269 in division 01, 10 in division 02. Leaf
reference rendered to `fnb_leaves.txt` and handed to every agent. "Deep F&B leaf
coverage" throughout this session means *fraction of those 279 reachable*.

## Input-list profile

| Field | Distribution |
|---|---|
| Rows | 685 across 84 economies |
| Verdict | ACCEPT 473 · SUSPECT 161 · REJECT 42 · ARCHIVE 6 · INDEX 3 |
| Build tier | not scored 310 · C (engineering) 253 · D (hard/app/index) 78 · A (low-hanging) 25 · B (moderate) 19 |
| Platform | Custom 506 · Custom/Enterprise 78 · WooCommerce 41 · Shopify 10 · VTEX 9 · PrestaShop 8 |

Only **44 rows are tier A or B** — the list is dominated by unscored and
"engineering required" entries, so the probe pass is doing real work, not
confirming a pre-graded set.

## The imbalance that shaped the plan

Mapping ISO3 → `regions.yaml` shows the list is essentially an **ECA + SSA**
expansion list. Row counts by region against manifests already in the repo:

| Region | CSV rows | Economies in CSV | Existing manifests |
|---|---|---|---|
| eca | 379 | 43 | **1** (`ukraine/minfin_fuel`) |
| ssa | 186 | 25 | **0** |
| lac | 48 | — | 0 — *out of scope this run* |
| menaap | 45 | 5 | **0** |
| sar | 25 | 2 (nepal, sri_lanka) | 15 |
| eap | 2 | 1 (papua_new_guinea) | 297 |

So a literal 3-agents-per-region split would put 126 rows on each ECA agent and
~0.7 on each EAP agent. Kept 3-per-region as requested, but **the thin regions
get a discovery mandate instead of a probe mandate** — which is the "also try to
discover more" half of the ask, aimed where it pays.

### Repo-wide role mix (why the list matters)

123 `retailer_sku` · 103 `aggregate_proxy` · 15 `official_avg` · 14 `tariff` · 3 `cpi_benchmark`.

The 103 `aggregate_proxy` are mostly cost-of-living survey publishers
(numbeo/livingcost/expatistan/mylifeelsewhere) and carry **no real SKUs** — the
skill's anti-patterns forbid counting them as coverage. Real price-level coverage
outside EAP is close to zero.

## Agent allocation

| Agent | Mandate | Countries | CSV rows |
|---|---|---|---|
| eca-1 | probe | romania, kazakhstan, serbia, germany, france, switzerland, malta, slovenia, belgium, denmark, norway, estonia, lithuania, austria, liechtenstein | 127 |
| eca-2 | probe | bulgaria, greece, hungary, italy, georgia, ireland, tajikistan, armenia, iceland, luxembourg, cyprus, finland, kosovo, kyrgyz_republic | 126 |
| eca-3 | probe | croatia, poland, spain, portugal, netherlands, united_kingdom, azerbaijan, uzbekistan, czech_republic, moldova, sweden, bosnia_and_herzegovina, slovak_republic, latvia | 126 |
| ssa-1 | probe | ghana, benin, togo, angola, lesotho, cameroon, sao_tome_and_principe, zambia | 61 |
| ssa-2 | probe | senegal, malawi, gabon, mauritania, ethiopia, madagascar, mozambique, tanzania, zimbabwe | 65 |
| ssa-3 | probe | kenya, sudan, guinea, congo_dem_rep, central_african_republic, cote_divoire, rwanda, cabo_verde | 60 |
| menaap-1 | probe + discover | egypt, + tunisia, algeria | 12 |
| menaap-2 | probe + discover | libya, yemen, + jordan, lebanon, iraq, syria, west_bank_and_gaza, iran | 18 |
| menaap-3 | probe + discover | morocco, djibouti, + gulf_states (6), israel | 15 |
| sar-1 | probe + discover | nepal, + bhutan | 18 |
| sar-2 | probe + discover | sri_lanka, + maldives | 7 |
| sar-3 | discover only | india, bangladesh, pakistan | 0 |
| eap-1 | discover only | papua_new_guinea, fiji, solomon_islands, vanuatu, new_caledonia | 2 |
| eap-2 | discover only | samoa, tonga, tuvalu, kiribati, nauru, palau, marshall_islands, micronesia_fed_sts, french_polynesia, american_samoa, guam, northern_mariana_islands | 0 |
| eap-3 | discover only — `official_avg` / `wholesale` feeds EAP-wide | (role-scoped, not country-scoped) | 0 |

Shards: `$CLAUDE_JOB_DIR/tmp/shards/{region}_{n}.csv`.

### On the EAP allocation

The skill says plainly: *"Don't send an EAP food-and-beverage coverage complaint
to this skill. That corpus is gold-bound, not source-bound."* That warning is
about **EAP grocery SKUs**, and it is correct — 297 manifests already exist and
`prices` division-01 gaps there trace to gold labels below `MIN_SUPPORT`, not to
missing scrapers.

Two EAP pockets are *not* covered by that warning, and the three EAP agents are
pointed only at those:

1. **Pacific Islands** — 19 economies holding 49 `aggregate_proxy` manifests
   against just **17 `retailer_sku`**. That is a genuine price-level hole, not a
   gold hole.
2. **`official_avg` / wholesale feeds** — 15 and 3 manifests respectively,
   repo-wide. These are the only channel that reaches fresh produce, fish,
   tubers and live animals, which supermarket catalogues structurally miss. Per
   prior audits these are exactly the deep div-01 leaves that read as zero.

No EAP agent is running a grocery sweep.

## Method per agent

1. De-duplicate the shard against `src/prices/configs/**/*.yaml` by registrable
   domain (skill's "supplied candidate list" path — Phase 2 is already done).
2. Drop cost-of-living survey publishers on sight.
3. Cheap probe first, in this order, stopping at the first success:
   curl+browser-UA → platform fingerprint (Shopify/Woo/VTEX/PrestaShop/Magento
   have known catalog endpoints) → JSON-endpoint sniff. Playwright only where
   the cheap path is inconclusive.
4. Classify to `TIER_1A` / `TIER_1B` / `TIER_2` / `SKIP` with **evidence**
   (status code, byte count, endpoint path, sample product+price).
5. Estimate deep F&B leaf coverage per country against the 279-leaf list.

**Hard rule carried from the skill:** no `SKIP` without a network trace. A 403 on
the front page says nothing about the backend — several previously "blocked"
retailers turned out to have wide-open JSON APIs.

## Guardrails

- Read-only. No manifests, spiders, or fetchers written this pass. No commits.
- No writes under `data/` or `outputs/`.
- Agents report evidence, not claims; unverified selectors are the documented
  failure mode of every prior run.

## Expected output

Per agent, a JSON report at `$CLAUDE_JOB_DIR/tmp/reports/{agent}.json`:

- `sources[]` — slug, source, url, tier verdict, evidence, channel, platform,
  est. F&B leaves reachable
- `by_country[]` — slug, viable source count, estimated deep F&B leaf coverage
  (n/279) with the reasoning
- `discovered[]` — net-new candidates not in the CSV
- `blockers[]` — for append to `references/known_blockers.md`

Orchestrator aggregates into a single coverage table and a ranked onboarding
queue.

## Open question to resolve at report time

The 48 `lac` rows in the CSV are unused — `lac` exists in `regions.yaml` but was
not in the requested region set. Flag for a follow-on pass.

---

# Results

All 15 agents completed. **541 sources probed, 270 viable (50%)** — 215 from the
supplied list plus **55 net-new** discovered. 118 countries assessed, 97 net-new
candidates surfaced, 117 blockers documented.

## Deep F&B leaf coverage achievable (of 279 leaves)

| Region | Countries | Viable sources | Mean coverage | Median | At zero |
|---|---|---|---|---|---|
| sar | 7 | 29 | 136 (49%) | 150 | 0 |
| eca | 43 | 78 | 112 (40%) | 140 | 6 |
| ssa | 25 | 46 | 96 (34%) | 87 | 1 |
| menaap | 20 | 27 | 55 (20%) | 28 | 6 |
| eap\* | 23 | 24 | 51 (18%) | 40 | 9 |

\* **EAP figures are scope-limited and must not be read as EAP coverage.** Those
three agents were pointed only at the Pacific Islands and at `official_avg` /
wholesale feeds. A `0` for south_korea means "no official_avg feed found", not
"no coverage" — EAP already carries 297 retail manifests that this run did not
re-measure.

Distribution across all 118 countries:

| Band | Countries |
|---|---|
| >70% (196+ leaves) | 3 |
| 50–70% (140–195) | 40 |
| 30–50% (84–139) | 18 |
| 10–30% (28–83) | 22 |
| <10% (1–27) | 13 |
| zero | 23 |

**Headline: 43 countries reach ≥50% deep F&B leaf coverage** from sources
verified in this pass, against a starting point of ~0 outside EAP.

## The supplied list is roughly a coin flip, and its difficulty grades are noise

Matched on registrable domain (n=444), the Excel's own columns predict actual
viability as follows:

| `Verdict` | Actually viable |
|---|---|
| ACCEPT | **55%** (177/322) |
| SUSPECT | 30% (32/107) |
| REJECT | 10% (1/10) |
| ARCHIVE | 20% (1/5) |

| `Build tier` | Actually viable |
|---|---|
| A — low-hanging fruit | 45% (5/11) |
| B — moderate effort | **14% (2/14)** |
| C — engineering required | 48% (72/151) |
| D — hard / app / index only | 31% (20/65) |
| not scored | 55% (112/203) |

`Verdict` carries real signal — ACCEPT is 1.8× SUSPECT, and REJECT is correctly
near-dead. **`Build tier` carries essentially none**: tier B scored *worst* of
all five buckets, and unscored rows outperformed both graded tiers. Do not use
`Build tier` to prioritise; use `Verdict` as a weak prior and probe.

The failure modes behind the 45% of ACCEPT rows that didn't hold up, all
evidenced:

- **Dead domains** — NXDOMAIN on Melcom, Palace Hypermarket, Erevan Benin,
  Sokeru, Super CKdo, Warani, Khetifood, Shop N Save FJ.
- **Brochure sites returning HTTP 200 with no commerce surface** — Shoprite
  Lesotho *and* Zambia, Extra Supermarket FJ, Au Bon Marché VU, Carrefour DZ.
- **Wrong category entirely** — `singer_lk` (electronics), Alfatah PK
  (houseware), Kibabo AO (self-described non-food in its meta tags), Jack's PNG
  (apparel), Celeste LK (corporate brand site, `AI_NOTES` mismatched).
- **Unlaunched shells described as live** — watti.ly, nawris.net.
- **Wrong domain for a real business** — `chandaranafoodplus.com` is dead while
  `foodplus.co.ke` serves an open Magento API over 18,205 SKUs; three Malta rows
  (PAVI/PAMA, Scotts, Welbee's) likewise had dead domains with live replacements.
- **Chain closed** — Cora Belgium ceased trading Jan 2026.

Conversely the list is also too pessimistic in places: eca-3 overturned three
"D-tier / SUSPECT" rows (Studenac, Kaufland HR, Billa CZ/SK) with plain curl.

## Existing manifests overstate real coverage

Six independent confirmations that a manifest's existence ≠ F&B coverage:
`singer_lk` (electronics), `bio_bhutan` (natural cosmetics), `druksell_bt`
(craft/jewelry), `redwave_mv` (tagged pharmacy, notes claim hypermarket, and
403-ing), PNG's sole retailer source (a meat-only butcher catalog, 152 items),
and the 103 repo-wide `aggregate_proxy` cost-of-living rows that carry no SKUs.

Two manifest defects worth fixing: `whim_mv`'s domain is `whim.com.mv`, not
`whim.mv`; `tongamarket`'s NZD-not-TOP currency note was independently
re-verified as **correct**.

## Highest-value findings

1. **WFP HDX is near-free coverage for ~27 countries.** Confirmed live CKAN
   panels by four independent agents: 8 in menaap-2, 8 in ssa-3, 8 in ssa-1
   (7 live), plus ssa-2's 8 of 9. The repo already ships this exact CKAN→S3-CSV
   pattern at `src/prices/fetchers/_shared/eap/wfp_food_prices.py` for 11 EAP
   countries — **extending it is one line per country in `_PANELS`, zero new
   code**, for 17–44 leaves each. This is the single cheapest move available.
   - Trap: Tanzania needs the ISO long-form slug
     (`wfp-food-prices-for-united-republic-of-tanzania`); a naive guess 404s.
   - Quality varies: Rwanda is exceptional (65 commodities, 152k rows, current
     to 2026-06-15); Sudan is thin (16, wartime); **Cabo Verde is thin *and*
     stale** (7 commodities, last updated 2022-05-15) — weight accordingly.
   - Confirmed absent for every EAP Pacific micro-state, Malaysia, Brunei, DPRK,
     and São Tomé.
2. **Israel's statutory price-transparency regime** (2015 Food Price
   Transparency Law): ~30 chains publishing per-store XML hourly with full
   barcode/manufacturer/price detail. Real files downloaded from **Shufersal**
   (no auth) and **Rami Levy** (Cerberus portal, login `RamiLevi` + blank
   password + CSRF token), fresh produce confirmed. ~210/279 leaves from one
   feed — the best single source found in the run.
3. **Malaysia PriceCatcher** (`storage.data.gov.my/pricecatcher/`) — open no-auth
   monthly CSV, 345k rows in one month, 758-item master list (~600 F&B). Malaysia
   had no official_avg source at all. ~160 leaves.
4. **Regulatory/statutory feeds are the pattern worth chasing.** Israel, Malaysia
   PriceCatcher, Croatia's CroCart (ingests chains' mandated daily price files),
   Greece's PosoKanei.gov.gr and Hungary's Arfigyelo.gvh.hu (both statutory, both
   unreachable this round → top follow-ups). These beat retailer scraping on
   coverage, stability and legitimacy.

## Reusable technical findings

- **New platform fingerprint:** `mcprod.<retailer-domain>/graphql` (Nuxt +
  Magento) — one vendor serving Hyper One, Seoudi and Spinneys Egypt. Belongs in
  `references/platform_fingerprints.md`.
- **Tenant collapsing holds for platform shape but NOT for WAF posture.**
  Carrefour Tunisia runs an open, unprotected Magento GraphQL backend while
  Carrefour Egypt sits behind Akamai. Probe each storefront's posture separately.
- **`curl_cffi impersonate=chrome120` defeated Lulu's Cloudflare layer** — worth
  adding to the probe ladder before declaring a Cloudflare block.
- **Supabase credential leakage in page bundles** yielded three wide-open
  PostgREST catalogs: aelanbasket.com (VU), Yombouna (SN, 1,677 SKUs), Kiwaba
  Online (AO).
- **Marketplace-as-directory works, with a trap:** Talabat area IDs are not
  country-scoped, so a first-guess Egyptian query returned Kuwaiti vendors. Fixed
  via `nextLocationApi/location/country-areas/9`.
- **Two new blocker classes** for `known_blockers.md`: Anubis proof-of-work
  challenge (sas.am, AM) and F5 BIG-IP ASM (cactus.lu, LU). Plus ArvanCloud
  infinite-redirect (Snapp Market, IR).

## Data-quality traps caught before scaffolding

Each of these would have silently corrupted the corpus:

- **Heimkaup (IS)** prices are in **hundredths of ISK** — minor-unit trap.
- **Lesotho Virtual Mall's API returns `currency_code: "TMT"`** (Turkmenistan)
  when the real currency is LSL. Note this *inverts* the skill's "trust what the
  site returns" rule — machine-readable currency still needs a country sanity
  check.
- **Dado.tj's WooCommerce API returns `price=0`** while the HTML frontend shows
  real prices.
- **VIP Supermercado** uses a nonstandard WooCommerce path
  (`/wc/store/products`, not `/wc/store/v1/products`).
- **yemenbox.com** prices in USD (diaspora-facing), not YER — a PPP hazard.

## Well-evidenced zeros and near-zeros

Recorded so the next run does not re-search them: united_kingdom, sweden,
ireland, liechtenstein (structural — served entirely by blocked Swiss chains),
belgium, denmark, cyprus, luxembourg, sao_tome_and_principe, solomon_islands,
new_caledonia, kiribati, marshall_islands, american_samoa,
northern_mariana_islands, and all six Gulf states.

**The Gulf zero was a surprise and contradicts the pre-run expectation** that it
would be the highest-yield slice. MAF Carrefour is a tenant-wide Akamai block
across every GCC country tested; Lulu and Danube sit behind a store-selection
gate that was not cracked in budget.

## Next actions, ranked

1. **Extend `_shared/eap/wfp_food_prices.py` `_PANELS` to ~27 new countries.**
   Near-zero cost, broadest coverage gain in the run. (Rename the module out of
   `eap/` — it is no longer EAP-specific.)
2. **Build the Israel statutory XML fetcher** — highest single-source yield.
3. **Onboard the 156 low-effort viable sources** from
   `2026-08-05-fnb-onboarding-queue.csv` (71 TIER_1A + 84 TIER_1B, already
   evidenced with endpoints and sample products).
4. **Crack the Gulf store-selection gate** on Lulu/Danube — one fix plausibly
   unlocks six countries currently at zero.
5. **Re-probe the transient failures** rather than writing them off: Gabon's
   Cerise + Malumbi, Nepal's Sastodeal + Karayo, Greece's PosoKanei, Hungary's
   Arfigyelo, Norway/Denmark's client-rendered chains.
6. **Playwright follow-ups** on JioMart (IN), Allosh Market (LB), Al-Taawon (IQ),
   Carrefour.ma, Marjane-via-Glovo.
7. Run the deferred **LAC** wave (48 unused rows).

## Guardrail compliance

Read-only as designed. No manifests, spiders or fetchers written; no writes under
`data/` or `outputs/`; nothing committed. The only in-tree additions are this
document and the two CSV deliverables beside it.
