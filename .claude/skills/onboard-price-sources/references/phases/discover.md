# Phases 0.5 → 2.5 — depth audit, inventory, candidate list, classification

You are here because the ask was a country, a region, or a commodity gap. If you
were handed a single URL or a ready-made candidate list, you are in the wrong
file — go to `probe.md`.

---

## Phase 0 — Pre-flight

1. The country slug appears in `src/configs/regions.yaml` under some
   `<region>.subregions.<subregion>.countries:` list. Ambiguous slugs are in
   `../slug_traps.md`.
2. The same slug has an entry in `src/configs/countries.yaml` with non-empty
   `currency:` and at least one `languages:` value. If either is missing or
   stubbed, **stop and surface it** — scaffolding silently misbehaves otherwise
   (currency defaults to `null`, language falls through to `"en"`).

## Phase 0.5 — Depth audit: is this actually a sourcing gap?

**Run this before any discovery whenever the ask names a commodity, a COICOP leaf,
or a coverage hole.** Cheapest phase, and the one that most often cancels the rest
of the run.

The recurring finding across every expansion pass: *the item is already listed by a
source we scrape, and the spider does not crawl deep enough.* Confirmed on Vietnam
(winmart/coopmart carried fresh produce the spider never reached), Korea (fresh
seaweed and yam already on oasis_kr and kurly_kr), and a 29-leaf "sourcing gap" list
of which the majority were already inside scraped catalogs.

A depth gap and a sourcing gap need opposite fixes. Onboarding a new source to solve
a depth gap adds maintenance surface and does not fill the leaf.

1. **Search the raw collected corpus with `scripts/leaf_corpus_search.py`**, not
   the classified output and not by hand:

   ```bash
   ~/venv/bin/python scripts/leaf_corpus_search.py --country vietnam \
       --leaves targets.tsv --terms vi_terms.tsv --out leaf_audit.tsv
   ```

   It matches each leaf's enrich sub-labels (English, modifiers like "fresh" and
   "canned" stripped) plus your `--terms` (`leaf<TAB>term`, local language and
   local brands) against `products_input.parquet`, drops non-food, menu and
   aggregator rows, and follows every hit into the build: `leaf=` (classified
   right, lost at trust/QA), `other=` (classified elsewhere, code named),
   `not_built=`. Only `[absent]` leaves go on to Phase 2. It prints the terms it
   used: a thin list is your cue to add `--terms` and re-run, not to conclude
   absence. Read the three samples per leaf before trusting a match.
   On the 2026-09-27 leaf runs (60 leaves, Philippines / Vietnam / Solomon
   Islands) it found all 43 leaves the hand audits had found in the corpus, in
   seconds and ~2.5k tokens of output per country, against ~130k tokens per
   hand audit. Vietnamese names need `--terms`: English labels alone found 9 of 19.
   - **Naive substring search lies badly.** Real false positives from this audit:
     `yam` matches "Tom Yam", `uni` matches "United", `杏` matches almond and
     cosmetics, `螺` matches screws. Add exclusion terms and eyeball the matches.
     Two commodities came back INCONCLUSIVE purely from bad search terms.
2. **If rows are absent, check the source's own site.** If the retailer lists it but
   our data lacks it, the spider's category coverage or pagination is the bug.
   Verify *which* source carries it rather than trusting a claim — items are
   routinely found at a different already-scraped source than assumed. A config
   existing does not mean data exists: `coles` (AU) has a manifest and **zero rows**.
3. **Classify the outcome explicitly** and report it in Phase 8:

| Outcome | Signal | Fix — and it is not a new source in three of four cases |
|---|---|---|
| **Classifier / gold gap** | Product **is** collected, but the leaf sits below `MIN_SUPPORT` in gold, so matching products get force-routed to a neighbour leaf or dropped (`state=nan`) | **Seed gold for that leaf**, then retrain. Dominant cause in the most recent audit. |
| **Depth gap** | Retailer lists it; our crawl never reaches it | Deepen the existing spider's categories/pagination |
| **Sourcing gap** | Nobody we scrape carries it | Proceed to Phase 2 |
| **Structural absence** | Not sold through the channels we scrape at all (live animals in supermarkets, non-native berries in EAP) | A wholesale/official feed, or an honest "true zero". Record it; don't chase it. |

`src/prices/build/leaf_support.py` produces the leaf worklist, but **treat its
`sourcing_gap` verdict as a hypothesis** — it derives from "zero rows classified to
this leaf", which the first row of the table also produces.

> **Trap:** do not onboard a new source before running this audit. Most reported
> sourcing gaps are depth gaps, and a new source does not fix those.

## Phase 1 — Resolve country, inventory coverage, upgrade old manifests

1. Resolve the input to a canonical slug from `regions.yaml`. Determine the
   subregion — that is the path component for `<region>/<subregion>/<country>`.
2. List **already-covered sources**: `src/prices/configs/<region>/<subregion>/<country>/*.yaml`.
   Cross-check `src/prices/price_scraping/spiders/<source>.py` (flat) and
   `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py`. Note which
   `_shared/<region>/<source>.py` aggregators *cover* this country — those count too.
3. **Upgrade old-schema manifests in place.** Many YAMLs predate the four-axis schema
   and carry only `spider: + language:` or `source_type: + coicop_divisions:`. For each:
   - Look the source up in `../inventories/<region>/<country>.md`.
   - **Translate the inventory's column vocabulary — it predates the schema**, and one
     column is a false friend:

     | Inventory column | Maps to | Watch out |
     |---|---|---|
     | `Source type` | informs `analytical_role` | **Not** the retired YAML `source_type:` field. The column holds free text ("NSO CPI reports"); the banned key held A–F letters. Same name, unrelated. Never copy it into a manifest. |
     | `COICOP divisions covered` | informs `coicop_codes` | Divisions are 2-digit; `coicop_codes` wants actual codes. Narrow, don't transcribe. |
     | `Cadence` | `cadence:` | Declared in prices manifests, enforced only by the `fuel` pipeline. Documentation, not behaviour. |
     | `Machine-readable?` | hints `extraction_pattern` | "HTML/PDF" means you still have to probe which one holds the price table. |
   - Backfill `scaffolding`, `extraction_pattern`, `analytical_role`,
     `coicop_classification`, `coicop_codes`, and where applicable `source_key`,
     `module`, `function`, `url`, `fallback_date`.
   - Spider-backed: `scaffolding: spider`, `extraction_pattern: scrapy_*`,
     `analytical_role: retailer_sku`, `coicop_classification: classifier`. Keep `spider:`.
   - Remove `source_type:`, `priority:`, `observation_level:`, `coicop_divisions:`.
   - If the source is not in the inventory, leave it and record "unknown coverage".
4. Read `countries.yaml` for `languages:` and `currency:`.
5. Compute the **COICOP gap set**: divisions [01..13] minus those covered by the
   upgraded `coicop_codes:` union.

6. **Check every covered domain for a second surface before you subtract it.**
   Coverage is per *surface*, not per *domain*. A tenant already in the corpus can serve
   a second priced surface with a different `analytical_role` and different COICOP
   codes — and Phase 2's subtraction removes the whole domain from the candidate pool
   before anything is probed.

   Measured 2026-09-17: `bluesky_prepaid_as.yaml` covered `bluesky.as` at
   `/personal/prepaid/plans/` — `analytical_role: tariff`, `coicop_codes: ["08.1.0"]`.
   The same host served an open, unauthenticated WooCommerce Store API at
   `/wp-json/wc/store/v1/products`: 97 devices in USD, sitting at 08.2/08.3 and 09.
   Two American Samoa passes missed it. The first because the domain read as covered;
   the second found it only through an unrelated ccTLD sweep. That is luck, not method.

   `scripts/second_surface_check.py --config-dir <country configs dir>` does this:
   it reads every URL out of the manifests, fingerprints each host against
   `../platform_fingerprints.md`, and splits the hits for you. One HTTP request per
   domain you already hold — there is no discovery spend.

   **Read the hit against the existing manifest's `analytical_role`, or the check is
   mostly noise.** A platform hit on a domain already filed `retailer_sku` is almost
   always the same catalog the manifest scrapes. A platform hit on a domain filed
   `tariff`, `official_avg` or `cpi_benchmark` is a genuinely different surface, because
   those roles never describe a product catalog. Run over American Samoa's 19 covered
   domains this returned three hits and exactly one signal: `givemesamoa.com` and
   `samoamarket.com` were both `retailer_sku` re-finding themselves, while
   `bluesky.as` was `tariff` with a real device catalog behind it. Onboard the second
   surface as its own source when its codes land in the step-5 gap set.

   **This blind spot grows with coverage.** The more manifests a country has, the more
   domains get subtracted unexamined, so run it on every country — established or not.
   Step 5 already computes the gap set; this is the step that spends it.

### Coverage density decides what to chase

Two opposite target-selection rules. The switch is **per country**, not a project phase.

| Country's state | Rule | Why |
|---|---|---|
| **Little or no coverage** (default outside EAP) | **Take whatever verifies.** Onboard every candidate that passes, cheapest first. Do not rank by COICOP gap. | When every leaf is empty, gap-ranking sorts by a constant. Real cost, no return. |
| **Established coverage** | **Rank by gap.** Target leaves and divisions nothing reaches. | Once the easy cells are full, an unranked source mostly re-covers ground you have. |

**Trigger to flip a country:** its sweeps stop opening new leaves. Judge per country,
from that country's own results.

## Phase 2 — Build the candidate list, then let a script probe it

**Generators write a file. A script probes every row. You read two tables.**

The cost of discovery is you reading candidates one at a time, not the probing. On
the Jamaica blind A/B (2026-09-17, audited 2026-09-25) an agent-led arm paid
**19,907 tokens per accepted source**; a script-first arm paid **4,690** — and 19
of its 27 false positives failed a check that needs no reading: prices in another
currency, most prices zero, fewer than 10 items. `scripts/triage_candidates.py`
makes those checks.

1. **Generate at volume into a file.** Generators 1, 2 and 6 below. Aim for
   150–300 hosts; a raw `ddgs` sweep is fine as-is, triage drops the noise.
2. **Triage it on a8:**

   ```bash
   ~/venv/bin/python scripts/triage_candidates.py --from-sweep sweep.jsonl \
       --currency FJD --symbol 'FJ$' --run-id <id> --country <country> --out triage.jsonl
   ```

   Every host goes through the `curl_cffi` ladder, the platform probes, a
   10-item sample, and `html_catalog_check.py` when there is no platform
   endpoint. Every host lands in the probe log with a verdict and a
   `rank_predicted`, so nothing is silently dropped.
3. **`accept`** — local currency, priced, ≥10 items. Classification is already
   fixed by the platform; go to Phase 3 without opening the page.
4. **`adjudicate`** — the only rows you read: an unknown or shared currency, or
   priced HTML without proof of enumeration. One line each: title and three
   products. Log your decision with `probe_log.py append`.
5. **`reject`** — logged with the reason (`foreign_currency`, `zero_prices`,
   `too_small`, `no_catalog`, `blocked`, `unreachable`). Read the counts, not the rows.
   `foreign_currency` trusts the store's own currency setting: in Jamaica it
   rejected 16 diaspora and tourist shops correctly and one real JMD orchid shop
   whose WooCommerce was set to USD. Prices in the thousands under a "USD" label
   are worth one look.

**Generator 5, institutional verticals, runs separately and by hand.** A tariff
page has no platform endpoint and no product list; triage would reject every one
of them. In Jamaica the only sources the script arm could never find were JPS,
NWC and Petrojam.

Full doctrine — candidate generators vs cost multipliers, the inverse-correlation law,
the two source regimes, wholesale-feed guidance, the cold-start 17-category table —
is in `../discovery.md`. Read it when you are actually discovering.

**1. Inventory first.** `../inventories/<region>/<country>.md` is a pre-verified seed.
Read it plus `../inventories/<region>/_aggregators.md`, then subtract Phase 1's
already-covered set — but only after Phase 1 step 6 has checked those domains for a
second surface. Subtracting a domain is not the same as subtracting a surface.
Free candidates, no search.

> **The dead ends in that file are findings too** — but they now have a second home.
> Rows like "No online supermarket found" are the record of a search that came back
> empty. Honour a *recent* one and move on. A null older than roughly six months is
> worth one cheap re-check, and the cheap re-check is the `recover` route: those rows
> enter the probe log with `lever_tried: null` and fall into the recheck view by
> construction. Every inventory carries an `_Inventory written: YYYY-MM-DD_` line.
>
> "No online supermarket found" is precisely the claim the Botswana sweep proved false
> three times in four.

**2. Marketplace enumeration.** The default first move for anything wider than one
country. Its yield is regional, so measure it rather than assume it: in Botswana and
EAP it found sites nobody handed us; in Jamaica (2026-09-17) it produced **zero**
verified sources and every retail source came from `ddgs`.

> **A marketplace is a directory, not a source.** The deliverable is its **seller/store
> list** — the first-party retailers behind it, each onboarded as its own source.
> Scraping the marketplace's own catalog is the consolation prize: those rows are
> seller-authored, and `src/prices/enrich/census.py` excludes `channel: marketplace`
> from the corpus census outright. Onboard the marketplace itself only when its
> directory is unreachable, and tag it `channel: marketplace`.
>
> This also softens the inverse-correlation law: hardened market leaders are hardened
> against *catalog* scraping. Their store directories are frequently a much lighter
> surface, so a leader can be worth a visit as a directory even when it is hopeless
> as a source.

Then **platform-fingerprint each name the directory gives you** — that is what makes
scaffolding near-free, but it finds nothing on its own. Endpoints:
`../platform_fingerprints.md`.

**3. Apply the inverse-correlation law before spending probe budget.** In EAP,
aggregator size and scrapeability are inversely correlated — Coupang, Naver, JD,
Tmall, HKTVmall, Shopee, GrabMart are WAF-hardened, while mid-tier and small-market
grocers on off-the-shelf platforms verify first try. Aim the budget at the second
group.

**4. Wholesale / `official_avg` feeds** whenever the gap involves fresh produce, fish,
tubers or live animals. Retail supermarkets structurally do not carry these, and only
a handful of `official_avg` manifests exist against 140+ retailer ones. Build them as
**whole-catalog walkers**, not targeted extractors — the other 1,900 commodities are
nearly free and fill leaves nobody has audited.

**5. Institutional verticals — the price data that is not in a shop.** A government
agency, utility, school, hospital, telecom or port publishes a rate schedule. There is
no store, no cart, no catalog, and **no platform fingerprint** — nothing on a power
authority answers `/products.json`. Every other generator above is blind to them by
construction.

Measured on American Samoa, 2026-09-17: **15 of 21 shipped sources were institutional,
and a cold retail-shaped sweep surfaced none of them.** The smaller the territory the
higher that fraction — few shops, but the same ministry, utility, carrier, college and
hospital as anywhere.

You find these by searching the **body**, not the product. One query per row, English
plus local language, run regardless of what the marketplace sweep returned:

| Vertical | Who publishes it | Query shape |
|---|---|---|
| Government statistics | statistics office, dept of commerce | `<country> consumer price index average prices`, `<country> statistical bulletin retail prices` |
| Utilities | power / water authority | `<country> electricity tariff schedule`, `<utility> rate schedule` |
| Telecom | incumbent + challenger | `<country> prepaid plans`, `<operator> roaming rates` |
| Education | colleges, private schools | `<country> tuition and fees schedule` |
| Health | hospital, health ministry | `<country> hospital charges`, `price transparency chargemaster` |
| Transport | port authority, ferry, taxi regulator | `<country> ferry fares`, `taxi rate schedule` |
| Primary production | fisheries, agriculture board | `<country> fish landings prices`, `produce market report` |

Seven queries. They are the only route to these sources, and they cost minutes.

What they look like once found, from the six American Samoa manifests:

- **`analytical_role: tariff`** — a regulator-set price. Distinct from `official_avg`,
  which is a statistical office's *measured average*. `doc_cpi_avg_prices` is
  `official_avg`; `aspa_utility_rates`, `ascc_tuition_as`, `lbj_charges_as`,
  `astca_prepaid_as` and `port_wtd_fares` are all `tariff`.
- **`channel: null`.** Channel is a retail concept. Do not invent one.
- **`scaffolding: fetcher`**, usually. Five of those six are fetchers over a PDF, an
  HTML table or a tabular download — one static document, not a catalog to walk. Route
  to `scaffold_fetcher.md`, not `scaffold_spider.md`.
- **Cadence is annual, quarterly or monthly — never daily.** A tariff changes when the
  regulator says so. Scheduling one daily buys 364 identical pulls a year.

**6. Search — run it with `ddgs`, English *and* local languages.** Last in the order,
because inventory and marketplace directories are cheaper and better-targeted. Full
recipe: `../ddgs_search.md`.

WebSearch's session-wide call cap is shared across every sub-agent in the run and
forces a handful of narrow queries. `ddgs` is a local library, so a 20–60 query sweep
costs minutes and no session budget.

Four rules, all measured:

- **Pin `backend=`.** `ddgs` rotates through `wikipedia`/`grokipedia`, which return no
  storefronts and DNS-fail on `region="wt-wt"` — 9 of 23 Botswana queries returned 0
  results for that reason alone. Pin
  `backend="duckduckgo, google, brave, mojeek, startpage, yahoo"`.
- **A 0-result query is not a dead end** until it has been re-run with backends pinned.
  It is indistinguishable from a backend failure.
- **Look for the storefront on a sibling domain.** `shopsefalana.com` not
  `sefalana.co.bw`; `echoppies.com` not `choppies.co.bw`; `spar2u.co.bw` not
  `spar.co.bw`. A prior Botswana run wrote off Choppies and Sefalana on the corporate
  domain alone; Sefalana turned out to serve ~316,600 products from an open JSON API.
- **Tag every result with the query that produced it.** `triage_candidates.py
  --from-sweep` carries the `q` tag into the probe log's `discovery_detail`. Exactly one
  candidate corpus-wide currently carries a query tag. That is why the ordering gate
  has nothing to calibrate against.

Local-language search does not pay the same everywhere: strongest generator after
marketplaces in CJK / Thai / Vietnamese / Arabic / Indonesian markets, mostly academic
noise in an anglophone one (Botswana: 46 local-only domains, ~42 junk, 1 real). Run it
either way — it costs minutes — but measure the yield instead of assuming it.

Never list the cost-of-living aggregators (Numbeo, LivingCost, Expatistan,
MyLifeElsewhere, Nomad List) as candidates. They already exist for most countries,
carry no real SKUs, and inflate coverage tables.

Aim for 150–300 candidate hosts into the triage file, plus the seven institutional
queries worked by hand.

### Working from a supplied candidate list

Phase 2 is already done. The work that replaces it is **disambiguation** — probe budget
spent on a duplicate is pure loss.

1. **Resolve each row to a registrable domain.** The domain is the only key that joins.
2. **De-duplicate within the list**, then **against the corpus**
   (`src/prices/configs/**/*.yaml`). Match on registrable domain plus path prefix — a
   storefront under `/th/` is not the same source as one under `/my/`.
3. **Collapse multi-TLD tenants** (`lazada.co.th` / `lazada.com.my`, the AS-Watson
   properties). One platform with N country storefronts: one probe answers for the
   tenant, and blocking is organised the same way.
4. **Drop the cost-of-living survey publishers** on sight.
5. Feed survivors into Phase 2.5.

> **Not yet built:** no automated resolver, no candidate table, no fuzzy name matcher,
> no alias file for multi-TLD tenants. Do the above by hand. Name-keyed and
> domain-keyed lists need different matchers; one will not serve both.

## Phase 2.5 — Classify candidates

Full axis definitions: `../classification.md`. Triage `accept` rows are already
classified by their platform: `spider`, `retailer_sku`, `classifier`. Open only
`adjudicate` rows and institutional candidates, and assign:

| Confirm by looking at… | Assign to |
|---|---|
| Product detail pages with SKU IDs, add-to-cart, per-unit price | `spider`, `retailer_sku`, `classifier` |
| Filterable price endpoint returning many commodities per call | `fetcher`, `rest_api`, `official_avg` or `aggregate_proxy` |
| A page listing CSV / XLS / PDF downloads of national averages | `fetcher`, `tabular_download`, `official_avg`, `source_curated` (stable items) or `classifier` (long free-text) |
| A static page or PDF of utility / telco / transport plans | `fetcher`, `html_scrape` or `pdf`, `tariff`, `source_curated` |
| Paginated listing of properties / vehicles / classifieds | `spider`, `scrapy_listing`, `retailer_sku`, `source_curated` |
| A national CPI publication with COICOP division indexes | `fetcher`, `rest_api`/`tabular_download`/`pdf`, `cpi_benchmark`, `publisher_labeled` |

If two shapes coexist on one site (an NSO publishing both CPI indexes and an
average-retail-prices table), **split into two manifests**. They emit different row
schemas — IndexObservation vs PriceObservation.

If a "supermarket" shows only category pages with no per-product price (common for
legacy retail sites), demote to skip.

> **Trap:** do not count a catalog that is not consumer retail as coverage.
> `estore.swasa.co.sz` is a real, paginating SZL WooCommerce store selling ISO
> conformity-assessment documents. 349 products the classifier can only route into
> residual leaves. The downstream consumer is a PPP basket, and a country publishing
> 10 cells is exactly where that temptation is strongest.

> **Trap:** do not let a search engine's country match stand in for the country. `ddgs`
> matches the *word*: a Chad query pack returns a US appliance store, Dominica a US
> grocery chain, Gibraltar a US drum-hardware brand. The cheap discriminator is the
> storefront's own pricing currency (`prices.currency_code`, `priceCurrency`,
> `Shopify.currency`) — on the 2026-09-11 sweep it removed **331 of 410** candidates.
> For countries on USD, EUR or GBP currency cannot discriminate: fall back to the ccTLD
> plus the shipping policy. `fitjeans.as` looked like an American Samoa retailer and is
> a global Shopify brand on a vanity ccTLD whose shipping policy excludes American Samoa.

## Ordering gate — rank before you probe, never filter

Between 2.5 and 3. Score each candidate and probe in rank order against an explicit
budget.

The score is a **live measurement**, not a historical model: one cheap HTTP request per
candidate against the endpoints in `../platform_fingerprints.md`.

1. Open platform catalog endpoint returning priced products (WooCommerce Store API,
   Shopify `products.json`, Magento REST, nopCommerce `/api/products`)
2. Open endpoint, prices unverified
3. Server-rendered HTML with visible prices
4. Reachable, shape unknown
5. Non-200 on the `curl_cffi` ladder

**Institutional candidates are not scored by this ladder.** The fingerprint probe is
the wrong instrument for a tariff page: `/products.json` 404s on a power authority, so
a real source lands at rank 4-5 and never gets probed. Score an institutional candidate
at **rank 3** (server-rendered HTML with visible prices) on the evidence of the page
itself, and note the reason. Letting the platform probe demote them is how a sweep
returns four apparel stores and misses the electricity tariff.

**Hard constraint: this orders and budgets. It never filters.** The sibling-domain
storefronts that `ddgs` was added to catch rank low on any corporate-domain-shaped
heuristic and were the entire prize. A gate that discards low-rank candidates
reintroduces the exact false negative the `ddgs` work removed.

Record the rank you assigned with `--rank-predicted` when you log the probe. The
ordering ships **provisional and self-auditing** — `scripts/probe_log.py audit` prints
pass rate by predicted rank, and until a few hundred ranked probes exist, the gate is
hand-set ordering, not measurement. Do not dress it up as measurement.

---

**STOP. Read `probe.md` before continuing.**
