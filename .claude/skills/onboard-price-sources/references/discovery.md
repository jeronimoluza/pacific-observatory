# Discovery — finding price sources worth probing

Load this when the scope is "find sources" rather than "onboard this specific URL."

## The unit of discovery is a platform, not a country

Scaffolding is per-source and probing is per-site, but **discovery is not per-country**. Anti-bot infrastructure clusters by *tenant* (every AS-Watson property, every Lazada TLD, every Cloudflare-strict account), and storefront software clusters by *platform* (every Shopify store answers `/products.json`). Both cut across borders. Working country-by-country means rediscovering the same platform twenty times and re-probing the same WAF twenty times.

Practical consequence: when the ask is "expand coverage," resolve it into **marketplace enumerations first** — then platform-fingerprint whatever they return — and only fall back to per-country search for what that doesn't reach.

## Two kinds of method — and only one of them finds anything

An earlier version of this file ranked all discovery methods on a single ladder. That was a mistake, and it hid the actual constraint. The methods do two different jobs:

**Candidate generators — these produce site names we didn't have.** Measured across the 2026-07-30 and 2026-07-31 EAP expansion passes, best to worst:

| Rank | Generator | Why it wins |
|---|---|---|
| 1 | **Marketplace / aggregator enumeration** | One seller directory surfaces 5–20 retailers at once. Highest yield per unit of effort by a wide margin. **Walk the directory, don't scrape the catalog** — see below. |
| 2 | **Local-language search** | Native-language queries surface national chains that English queries never return. |
| 3 | **Wikipedia / listicle** ("list of supermarket chains in X") | Decent recall, poor signal on whether anything is scrapeable. |
| 4 | **App-store charts** | Finds the market leaders, which are usually the *least* scrapeable — see the inverse-correlation law. |
| — | **Generic English search** ("grocery in X") | **Worst.** This is what the per-country 17-category sweep degenerates into. Cold-start fallback only. |
| — | **A supplied list** (spreadsheet, other team's inventory) | Not a method, but it occupies this slot — and it is the scarcest input we have. Handle per the disambiguation steps in `SKILL.md`. |

**Cost multipliers — these find nothing, but make a candidate you already have far cheaper.** Never count them as discovery:

| Multiplier | What it does |
|---|---|
| **Platform fingerprinting** | Identify the storefront software and the catalog endpoint is already known — see `platform_fingerprints.md`. Turns a probe-and-guess into a known Tier 1B. Scaffolding becomes near-free. |
| **`known_blockers.md` cross-check** | Removes candidates before you spend probe budget on them. Negative yield avoided is yield. |

**Why the distinction matters.** We have exactly *one* strong generator and three weak ones. Platform fingerprinting used to sit at rank 2 on the old ladder, which made discovery look better resourced than it is — it multiplies whatever the generators return and contributes nothing when they return nothing. In a cold-start country with no reachable marketplace, the honest position is that we are down to local-language search, and the run should say so rather than grinding through a generic sweep.

## A marketplace is a directory, not a source

The point of marketplace enumeration is the **seller/store list** — the first-party retailers behind the platform, each onboarded separately. The marketplace's own catalog is the consolation prize: `src/prices/enrich/census.py` excludes `channel: marketplace` from the corpus census because seller-authored long-tail names are unreliable tier-a input.

Practical consequence for the inverse-correlation law below: the hardened market leaders are hardened against *catalog* scraping. Their store directories are often a much lighter surface, so a leader can be worth a visit as a directory even when it is hopeless as a source.

## The inverse-correlation law

**In EAP, aggregator size and scrapeability are inversely correlated.** Market leaders are WAF-hardened; mid-tier and small-market grocers running off-the-shelf platforms verify clean on the first try.

Confirmed hardened (do not spend probe budget here without a dedicated anti-bot effort): Korea Naver / 11st / Gmarket / Coupang, China JD / Tmall, HK HKTVmall and the whole AS-Watson family, SG sheng_siong / redmart, ID segari, VN aeon / lottemart, TH villamarket, PH landers, plus foodpanda / GrabMart / Shopee across every market.

So: **budget probe time toward mid-tier and regional players**, and treat the market leaders as a separate, explicitly-scoped Playwright/stealth project. A run that spends its afternoon losing to Cloudflare on Coupang and never probes the four mid-tier chains has inverted its own returns.

## Two source regimes — the discovery method depends on the division

COICOP divisions do not all get their prices from the same kind of place, and the two kinds have very different cost curves. Worth knowing even while the active focus is food and beverages, because the second regime is where "map all of COICOP" eventually goes.

| | **Retail regime** | **Administered regime** |
|---|---|---|
| Divisions | 01, 02, 03, 05, 06, 09, 13 | 04, 07, 08, 10, 11, 12 |
| Leaves (of the 498 in scope) | ~400 — **80%** | ~98 — **20%** |
| A source is… | a storefront | an **institution**: a regulator, a utility, a telco, a transit authority, a university, a bank |
| How you find one | not globally enumerable — you need a generator, and you pay the WAF tax | **registry join.** There is no world list of supermarkets, but there are world lists of telecom regulators, statistics offices, and agriculture ministries |
| Cost | the whole probe-and-scaffold machinery, per site | ~5 sources per country, little anti-bot resistance |
| Current state | ~122 `retailer_sku` manifests | **21 manifests worldwide** (14 `tariff`, 4 `official_avg`, 3 `cpi_benchmark`) |

Two consequences worth remembering:

- **Institutions are enumerable; companies are not.** For the administered regime the cold-start problem largely dissolves — you are looking up a known list, not searching. This is why that regime is cheap despite being neglected.
- **Administered coverage is declarative.** Those sources carry their COICOP codes in the manifest (`coicop_codes`), so you can read coverage straight off the YAML without the classifier or any gold labels. The retail regime's coverage can only be *measured* downstream, and today only for division 01.

Scope note as of 2026-08-05: the active generator is marketplace enumeration for the retail regime. Registry enumeration for the administered regime is **documented here but not wired into the workflow** — the phases below do not implement it.

## Cold-start: the 17-category per-country sweep

Use this only when a country has no inventory file and the marketplace angle came up empty. It is the lowest-yield generator available — a completeness net, not a first move.

Note that this table **mixes both regimes**: the `spider` rows are retail-regime work with all of its cost, while most `fetcher` rows are administered-regime institutions that a registry lookup would find directly. Reading them as one flat list of equally-hard tasks understates how cheap the second group is.

| Default scaffolding | Category | Probe these |
|---|---|---|
| spider | Online supermarket / hypermarket / fresh-grocery | National grocery chains, hypermarkets, q-commerce |
| spider | Online pharmacy | Pharmacy chains with browseable PDPs |
| spider | E-commerce / marketplace | National general-merchandise sites (clothing, appliances, electronics) |
| spider | Personal-care / beauty retailers | National drugstore-style chains |
| spider | Streaming / app-store country pricing | Netflix, Spotify, Apple, Google country pages |
| fetcher | Official food / commodity price tracker | Central bank or trade-ministry daily/weekly trackers |
| fetcher | Fuel pump-price tracker | Regulator / state oil-company monthly/weekly retail fuel |
| fetcher | National statistics office datasets | Average-price tables, retail-price surveys, HBS unit-value tables |
| fetcher | Customs / trade unit-value tables | Wholesale or import unit values where published |
| fetcher | Utility tariff pages | Electricity, water, gas — regulator or operator |
| fetcher | Telco / ISP tariff pages | Mobile and fixed-broadband plans |
| fetcher | Public-transport fare schedules | National rail, urban transit, ferry |
| fetcher | Airline / car / motorcycle list prices | National carrier flight prices; dealer list prices |
| fetcher | University tuition pages | Per-program annual tuition, major national universities |
| fetcher | Bank fee schedules / FX boards | Retail bank fee PDFs; central bank FX tables |
| spider | Real-estate / rental portal | Per-city rental listings with median rent by bedrooms |
| spider | Classifieds | National classifieds covering vehicles, electronics, household |
| fetcher | NSO CPI division indexes | Monthly/quarterly CPI by COICOP division — `analytical_role: cpi_benchmark` |

Plus, where they cover the country: restaurant-delivery aggregators, hotel booking sites, insurance comparison sites.

Aim for 12–25 candidates across `analytical_role` values. Cast wide for `retailer_sku` / `official_avg` / `tariff`; for `cpi_benchmark`, **one strong CPI source is enough** — it's the benchmark, not a coverage axis.

Prefer English-translated landing pages where they exist (`global.oliveyoung.com` over `oliveyoung.co.kr`) — usually easier to scrape. Same for stats-office portals.

## Wholesale and official-average feeds

Consistently the highest-yield sources for the hard COICOP leaves — live animals, fresh fish, tubers, dried seafood — which retail supermarkets structurally do not carry. Only a handful of `official_avg` manifests exist against 140+ retailer ones, so this is where the marginal source is worth most.

What to look for: agriculture-ministry and wholesale-market daily price feeds.

**Already shipped in EAP** (check before rediscovering): Taiwan MOA `data.moa.gov.tw` — JSON API family, one endpoint per commodity class, unauthenticated; Hong Kong AFCD `Wholesale_Prices.csv` — one daily CSV covering live cattle/pig/chicken plus fish/veg/fruit; Thailand Talaad Thai — ~2,000 commodities via numeric-id walk. Between them the live-animal leaves retail structurally cannot reach are covered.

**Verified candidates, not yet built:** PH Bantay Presyo (`bantaypresyo.da.gov.ph`, DataTables fed by POST AJAX per category), MY FAMA (`fama.gov.my`, Malay path only — `/en/` 404s), KR KAMIS (`kamis.or.kr`, 17 sub-APIs, broadest EAP ag+fishery catalog, gated on a free key signup), JP MAFF (best route to persimmons), ID panelharga (national daily panel, Angular SPA — needs a network-trace pass first).

**Build these as general catalog walkers, not targeted extractors.** When you find a wholesale feed, take its *whole* catalog rather than only the commodities that motivated the search. The marginal cost of the other 1,900 commodities is near zero and they fill leaves you haven't audited yet. Set `analytical_role: official_avg`, **`channel: wholesale`** (the enum value shipped 2026-08-04 alongside the Taiwan MOA and HK AFCD fetchers), and `coicop_classification: classifier` when the catalog is too broad to hand-map. Older wholesale manifests predating the enum value use `channel: null` — migrate them when you touch them.

## Record the dead ends

A search that came back empty is a finding, and it is worth as much as a hit — it is the only thing that stops the next run from repeating the search. Write it into `inventories/<region>/<country>.md` as a row whose source name states the negative ("No online supermarket found", "No marketplace with a reachable seller directory"), with the reason in Notes, under the file's `_Inventory written: YYYY-MM-DD_` line.

The date is what makes the null usable later: storefronts launch and WAF posture drifts, so a null is a claim with a shelf life, not a permanent fact. Roughly six months is a reasonable point to re-check one cheaply. Countries already recorded as having no viable retail e-commerce include North Korea, Brunei, Lao PDR, Kiribati, Marshall Islands, Micronesia, Northern Mariana Islands, Palau, Vanuatu, and Macao (no catalog distinct from HK).

Site-level blocks go somewhere else — `known_blockers.md`, keyed by blocker class. Note that blocking is done per *tenant*: search that file by operator or brand, not only by exact domain.

## Do not onboard as "coverage"

Cost-of-living survey aggregators — Numbeo, LivingCost, Expatistan, MyLifeElsewhere, Nomad List — are already present for most countries and are **not** price-level sources. They inflate source counts and coverage tables without adding a single real SKU. Exclude them from candidate lists and from any coverage statistic meant to show retail breadth.
