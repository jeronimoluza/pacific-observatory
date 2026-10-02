---
name: onboard-price-sources
version: 5
description: "Discover, scaffold, and end-to-end-test new price-data sources for the `prices` pipeline, targeting full COICOP 2018 basket coverage for PPP / Real-Exchange-Rate analysis. Use whenever the user wants to expand price-source coverage — for one country ('find new sources for Indonesia', 'add supermarkets in Brunei', 'we have no sources for Korea'), for a region ('expand EAP retail', 'more wholesale feeds'), for a commodity gap ('nothing covers fresh seaweed', 'fill the live-animal leaves'), for one named URL, or to re-probe sources previously written off ('recover blocked sources', 'anything we gave up on'). Also triggers on references to `src/prices/configs/`, price spiders, or price fetchers. Runs: depth audit of existing sources → marketplace-first discovery → feasibility probing → spider OR fetcher scaffolding + YAML manifest → automated test → coverage report."
---

# Onboard Price Sources

Deliver working spider files **or** Python fetcher modules plus YAML manifests under
`src/prices/configs/<region>/<subregion>/<country>/`, each verified by an end-to-end
test run. The downstream consumer is a cross-country PPP / Real-Exchange-Rate pipeline,
so coverage is measured against the full COICOP 2018 basket — not just supermarket SKUs.

**The objective is fewest total billed tokens across the whole run — main agent plus
every sub-agent — per verified source onboarded.** Phase 8 emits a cost line; that is
how the run reports against it.

**Check you are not on a stale copy.** The frontmatter says `version: 5`. Several
worktrees still carry a pre-`ddgs`, pre-probe-log lineage with a monolithic
`references/known_blockers.md`. If you see that file, you are on an old copy.

## Scope router — start here

The unit of *scaffolding* is a source. The unit of *discovery* is usually **not** a
country. Route on what you were given, and read only the file the route names.

| You were given | Read | Notes |
|---|---|---|
| **A coverage-gap complaint** ("we have nothing for X", "more sources") | `references/phases/recover.md` **first** | Cheapest yield in the skill. Zero discovery cost, and the inherited verdicts are measurably wrong — 45 of 50 re-probed clean in 33 s. Then fall through to the row below. |
| **A country** ("sources for Indonesia") | `discover.md` → `probe.md` → one scaffold file → `report.md` | The classic path. Discovery is script-first: generate hosts into a file, `triage_candidates.py` probes them all, you read only the `adjudicate` table. |
| **A region or "expand coverage"** | `discover.md` (Phase 2 sweep only) → then loop the per-source files | Do **not** re-run per-country discovery N times. Sweep once across the region, then onboard each hit. Countries only decide where the YAML lands. |
| **A commodity or COICOP gap** ("nothing covers fresh seaweed") | `discover.md` — **Phase 0.5 first, this saves the most work** | Most "sourcing gaps" are depth gaps in sources already scraped. |
| **A single named URL** | `probe.md` → one scaffold file → `report.md` | Skip discovery entirely. Do not read `discover.md`. |
| **A ready-made candidate list** (spreadsheet, hand-off) | `discover.md` § "Working from a supplied candidate list", then `probe.md` | Discovery is done; the work is disambiguation, not search. |

Anti-bot infrastructure clusters by *tenant* and storefront software clusters by
*platform* — both cut across borders. Country-by-country discovery rediscovers the same
platform and re-loses to the same WAF once per country. Per-country work is right for
probing, selector extraction and scaffolding; it is wrong for finding candidates.

**Do not proceed past a phase whose file you have not read.** Each file ends with the
next one to load.

**EAP food-and-beverage has already flipped, and adding sources there is close to
worthless.** Of 22 division-01 leaves flagged `sourcing_gap`, most were *already
collected* and merely sitting below `MIN_SUPPORT` in gold, so the classifier never routed
anything to them. Roughly 7 were genuinely unscraped. The binding constraint in EAP F&B is
**gold labels, not sources**. Route that ask to gold-growth, not here.

## Phase index

| File | Phases | Load when |
|---|---|---|
| `references/phases/recover.md` | the `recover` route | A coverage-gap ask, or any time the recheck queue is non-empty |
| `references/phases/discover.md` | 0, 0.5, 1, 2, 2.5, ordering gate | You have to *find* candidates |
| `references/phases/probe.md` | 3, 3-fetcher, 4 | You have candidates to test |
| `references/phases/scaffold_spider.md` | 5A, 7 | `scaffolding: spider` |
| `references/phases/scaffold_fetcher.md` | 5B, 7-fetcher | `scaffolding: fetcher` |
| `references/phases/report.md` | 6, 8 | Testing and writing everything back |

Spider and fetcher are mutually exclusive paths. Read one, never both.

## Classification, in six lines

Four axes go into every manifest. Full definitions, the enrichment-operational fields,
the narrowness rule and worked examples: `references/classification.md`. You do not need
them to pick a route — Phase 2.5 is where they get assigned.

- `scaffolding` — `spider` (Scrapy, retailer SKU catalogues and listings) or `fetcher` (plain Python, everything else)
- `extraction_pattern` — `scrapy_html` / `scrapy_api` / `scrapy_playwright` / `scrapy_listing` / `rest_api` / `tabular_download` / `pdf` / `html_scrape`
- `analytical_role` — `retailer_sku` / `official_avg` / `tariff` / `cpi_benchmark` / `aggregate_proxy`. Complements, not a ranking: the PPP analyst wants all roles populated.
- `coicop_classification` — `classifier` / `source_curated` / `publisher_labeled`. Declares who tags COICOP.
- Plus `channel:` — **required on every manifest, `null` included.** A missing key or an out-of-enum value breaks the *global* `prices collect --list`, not just that source.
- Retired keys, never write them: `priority:`, `source_type:`, `observation_level:`, `coicop_divisions:`, and `region/subregion/country/source` in a manifest body.

## The nine traps that destroy yield

The rest live inline in the phase file where they bite. These nine are here because
violating them silently loses sources rather than wasting a cycle.

1. **Pin `ddgs backend=`.** It rotates through `wikipedia`/`grokipedia`, which find no storefronts and DNS-fail on `region="wt-wt"` — 9 of 23 Botswana queries returned 0 for that reason alone. Pin `backend="duckduckgo, google, brave, mojeek, startpage, yahoo"`.
2. **A 0-result `ddgs` query is not absence.** It is indistinguishable from a backend failure. Re-run with backends pinned before writing any dead end.
3. **Never record a dead end after probing only the corporate domain.** `shopsefalana.com` not `sefalana.co.bw`; `echoppies.com` not `choppies.co.bw`; `spar2u.co.bw` not `spar.co.bw`. A prior Botswana run wrote off Choppies and Sefalana this way; Sefalana serves ~316,600 products from an open JSON API.
4. **Never write a block verdict from bare `curl`.** It measures curl's TLS handshake, not the site's defenses. Run the ladder — `chrome124`, `chrome120`, `safari17_0`, **`firefox133`** — first. The appender refuses a `blocked` verdict that names no lever.
5. **Log every candidate probed, pass or fail.** `scripts/probe_log.py append`. A win is a manifest and a dead end used to be a markdown bullet, which is why no run could learn from the last one. This is the one habit the whole design rests on.
6. **A 200 is not a catalog, and an open platform API is not a priced catalog.** Prove a *category* page paginates — page 2 must return a different set. Fetch an actual product and look at its price: six dead ends in one wave were WooCommerce stores where every price was 0.
7. **Never rank targets by COICOP gap in a low-coverage country.** Every division is a gap there, so the ranking sorts by a constant while costing real analysis time. Take whatever verifies until the country stops opening new leaves.
8. **Never count cost-of-living aggregators as coverage.** Numbeo, LivingCost, Expatistan, MyLifeElsewhere, Nomad List carry no real SKUs, already exist for most countries, and inflate every table they appear in. Same for a catalog that is not consumer retail — `estore.swasa.co.sz` sells ISO standards documents.
9. **A covered domain is not a covered surface.** Phase 2 subtracts already-covered sources, which drops the whole *domain* from the pool unprobed. `bluesky_prepaid_as` covered `bluesky.as` at `/personal/prepaid/plans/` (`tariff`, `08.1.0`) while the same host served 97 USD devices from an open WooCommerce Store API at 08.2/08.3/09. Two American Samoa passes missed it. Fingerprint every covered domain once — this blind spot grows with coverage.

## Orchestrator mode — how large expansions actually run

The proven pattern, and the one that built most of the corpus: 84% of manifests are under
30 days old and the entire `ssa` region (523 manifests) came from wave campaigns. Leaving
this as a footnote is why every wave re-invents the brief.

- **One country per worker.** Keeps the blast radius of a bad shard to one country's YAML.
- **The orchestrator commits; workers do not.** N agents committing into one git index is a race that produces silently untracked files — already a recorded failure mode here, where a bare `build/` in `.gitignore` swallowed source directories.
- **A worker reads `probe.md` + one scaffold file + `classification.md`, and explicitly not `discover.md`.** The orchestrator did the discovery.
- **A probe scout reads no skill file at all.** Its job is ~40 lines of prompt, not a 15 KB reference:

  > Probe `https://<host>/` with `curl_cffi`, profiles in order: `chrome124`, `chrome120`,
  > `safari17_0`, `firefox133`. Stop at the first HTTP 200 with a body over 2 KB.
  > If you get one, try `/wp-json/wc/store/v1/products?per_page=5`, `/products.json?limit=5`,
  > `/rest/V1/store/storeConfigs`, `/api/products` and report which returns priced products.
  > Then fetch one category URL and its page 2, and say whether page 2 returns a *different*
  > set. Report exactly: host, verdict (ok|blocked|no_catalog|unreachable), the profile that
  > worked or the full list tried, the tell you saw (status code, server header, challenge
  > name), platform if any, and the endpoint shape. Do not scaffold anything. Do not guess
  > selectors. A bare-curl 403 is not a verdict.

- **Workers write their own probe-log shard** (`probe_log/<run_id>-<country>.jsonl`); the orchestrator commits the directory. Shards are new files, so parallel waves never conflict in git.
- **Pace the waves.** In a multi-host campaign, late failures are not independent of early success — `handla.ica.se` failed three acceptance runs against a challenge its own campaign triggered from one IP.

## Environment — check this before Phase 3, not during it

Run on a8 with `~/venv/bin/python`: it carries `curl_cffi`, `ddgs`, `playwright` and
Chromium, and is the only environment verified end to end (2026-09-17). A stock
`poetry install` is **not** a working probe environment:

| Need | State | If missing |
|---|---|---|
| `curl_cffi` | locked via `scrapy-impersonate` | arrives with `poetry install` |
| `playwright` | declared `>=1.40` — **the package is not the browser** | `poetry run playwright install chromium` |
| `ddgs` | **absent from `pyproject.toml` and `poetry.lock`** | `pip install ddgs` |

`ddgs` being undeclared is a defect, not a footnote: Phase 2 generator 6 mandates it,
so a fresh environment silently loses the entire search phase. Surface it rather than
pip-installing around it again.

## Repo entry points

- Country topology / slug validation: `src/configs/regions.yaml`, `src/configs/countries.yaml`. Ambiguous slugs: `references/slug_traps.md`.
- Existing manifests: `src/prices/configs/<region>/<subregion>/<country>/<source>.yaml`
- **Probe log** (every candidate ever probed): `references/probe_log/*.jsonl` — query with `scripts/probe_log.py`
- **Discovery inventories**: `references/inventories/<region>/<country>.md`, plus `<region>/_aggregators.md`. 143 files; regions without one cold-start and write a seed back at Phase 8.
- **Spider code**: `src/prices/price_scraping/spiders/` — flat, one file per source, keyed by the spider's `name = ...`
- **Centralized CSS selectors** (Tier 1A HTML spiders only): `src/prices/price_scraping/selectors.py`. API and listing-card spiders bypass this.
- **Fetcher code** — mirrors `src/fuel/fetchers/`: country-bound `src/prices/fetchers/<region>/<subregion>/<country>/<source>.py`; regional `_shared/<region>/<source>.py` + thin wrappers; global `_global/<source>.py`.
- **COICOP classifier**: `src/prices/enrich/classifier/`, run by `python run.py prices process --stage classify`. Do not route anything to `src/cpi/coicopping/` — retired.
- Scrapy + Playwright settings: `src/prices/price_scraping/settings.py` (do not edit unless asked)
- CLI: `python run.py prices collect --source <name> --max-items N` runs **both** scaffoldings; `--list` lists everything. There is **no separate `prices fetch` command**.
- Data output: spiders → `data/prices/<region>/<subregion>/<country>/<source>/raw_items/<source>_<ts>.jsonl`; fetchers → `price_observations.csv` or `index_observations.csv` in the same directory.

## Scripts

| Script | Does |
|---|---|
| `scripts/probe_log.py` | `append` a probe (refuses a block verdict with no lever), `lookup` a host's history, `recheck` the re-probe queue, `stats`, `audit` the ordering gate |
| `scripts/recover_sweep.py` | Sharded bulk re-probe of the recheck view. Runs on a8 under `setsid nohup` |
| `scripts/second_surface_check.py` | Phase 1 step 6 — fingerprints every domain you already cover, flagging the ones whose manifest role is not a catalog role. Found `bluesky.as` after two passes missed it |
| `scripts/leaf_corpus_search.py` | Phase 0.5 — is a missing leaf already in our raw corpus, and where was it lost |
| `scripts/triage_candidates.py` | Phase 2 — probes every candidate in a sweep file, tiers each as accept / adjudicate / reject, writes the probe log |
| `scripts/html_catalog_check.py` | The HTML fallback triage calls when a host has no platform endpoint |
| `scripts/blockers_to_probe_log.py` | One-off 2026-09-17 migration; precedent for the next schema change |

## Other references

| File | Load when |
|---|---|
| `references/classification.md` | Phase 2.5 — the four axes in full, operational fields, narrowness rule |
| `references/discovery.md` | Phase 2 — generators vs cost multipliers, marketplace-as-directory, inverse-correlation law, cold-start table |
| `references/ddgs_search.md` | Phase 2 — the `ddgs` library, pinned backends, query packs, off-domain storefront rule |
| `references/platform_fingerprints.md` | Phase 2–3 — storefront platform endpoints, open JSON backends, id-walk |
| `references/blocker_classes.md` | Phase 3 — which CDN family behaves how, which tell means what, which walls are not walls |
| `references/probe_patterns.md` | Phase 3 — curl, Playwright dump, API sniffer, PDF/XLS inspectors |
| `references/spider_templates.md` | Phase 5A — the three spider skeletons |
| `references/fetcher_pattern.md` | Phase 5B — fetcher contract, helpers, worked examples |
| `references/yaml_schema.md` | Phase 5 — manifest field table + six worked examples |
| `references/testing.md` | Phase 6 — test harness and per-scaffolding checklists |
