# Congo, Rep. (Congo-Brazzaville)

_Inventory written: 2026-09-28_ (weekly run W40 — first institutional-vertical
pass; supersedes nothing below, the two 2026-09 passes were retail-only and
found almost no candidates)

Before this pass: `wfp_prices` (official_avg, division 01) + `mbote_cg`
(retailer_sku, general merchandise) — 2 manifests in this worktree, both
predating the four-axis institutional-vertical doctrine. **Note for the next
run:** the task brief for this pass stated "6 sources, 12,540 trusted rows"
for the a8 trusted build as of 2026-09-15, but only these 2 manifests exist
under `src/prices/configs/ssa/central_africa/congo_rep/` in the
`onboard-refactor` worktree searched this pass — a real discrepancy, not
resolved here (see the run's REPORT for detail). **Result: 3 shipped**, all
`ddgs`-discovered institutional/tariff sources (electricity/telecom retail
search in the prior two passes had been exhausted; this pass pivoted to
utilities, telecom and the national statistics office per discover.md's
institutional-vertical generator, which the prior passes never ran).

## Shipped (2026-09-28, run w40)

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `lcde_water_tariff` | https://lcde-sa.cg/informations-clientele/tarifs/ | utility / `tariff` (04.4.1) | **SHIPPED** | La Congolaise des Eaux, national water utility. Server-rendered "Tarif du metre cube" table (4 rows) plus 10 connection-fee tables (new/existing-connection administrative charges by pipe diameter); 56 rows total, verified by direct-import test. First water/electricity-class (division 04) source for Congo-Brazzaville. |
| `mtn_internet_tariff` | https://www.mtn.cg/particuliers/forfaits/forfaits-internet-classiques/ | telecom / `tariff` (08.3.0) | **SHIPPED** | MTN Congo prepaid data-bundle tariffs, 6 server-rendered tables (1/7/30-day validity plus NUIT/FTT/Résidentielles offers), 33 rows written on the CLI test run. First communication-division (08) source for Congo-Brazzaville. Sibling `airtel.cg/prix-les-plus-bas` is a client-rendered SPA shell (0 tables, 0 price tokens) — probed and logged `needs_work`, not pursued this pass. |
| `ins_congo_cpi` | https://site-ins-congo.vercel.app/stat-prix.html | none / `cpi_benchmark` (all 12 divisions) | **SHIPPED** | INS (Institut National de la Statistique) monthly INHPC bulletin (CEMAC-harmonized CPI, base 100 = 2018). Production site ins-congo.cg links only to per-month HTML articles with no reliable PDF href; a Vercel mirror lists all 17 available bulletin PDFs directly and is used instead. 60 rows (12 COICOP divisions x 5 comparison months) on the CLI test run, cross-checked by hand against the PDF's own printed table. First index-layer (`cpi_benchmark`) source for Congo-Brazzaville. |

## NOT shipped this pass — needs_work / no_catalog

| Candidate | URL | Status | Notes |
|---|---|---|---|
| E2C (Energie Electrique du Congo) | https://e2c.cg/ | **no_catalog** | National electricity utility, confirmed real (govserv.org address listing, blog third-party billing explainer), but no tariff/grille page found in site nav or a direct URL guess (`/facturation-et-paiement/` is billing-process prose, no price table). A future pass should try a `ddgs` search for "E2C grille tarifaire PDF" specifically, or check the Journal Officiel (`sgg.cg`) for the rate-setting arrêté. |
| Airtel Congo | https://www.airtel.cg/prix-les-plus-bas | **needs_work** | Client-rendered SPA shell (7.6 KB, 0 tables, 0 price tokens with a plain `requests` GET). Would need Playwright network-capture to find the internal data endpoint, per probe.md's "Playwright to discover, plain HTTP to scrape" gate. Not attempted this pass (budget). |
| Fil (filcongo.com) | https://filcongo.com/ | **needs_work** | Genuinely promising: JSON-LD confirms `currenciesAccepted: XAF`, Brazzaville-only delivery, "prix du marché traditionnel de Brazzaville" (fresh meat/fish/vegetables/spices — exactly the fresh-produce gap 242market/Tchitunga couldn't fill without the diaspora-EUR trap). No platform fingerprint matched (WooCommerce/Shopify/Magento endpoints all 404), no JSON-LD product catalog, no Next.js data blob on the homepage — looks like a custom SPA. Needs a Playwright network trace to find the product API before it can be scaffolded. **Best next-pass candidate for division 01 depth / fresh produce.** |
| BrazzaMarket, Marché Intelligent Congo (marche.brazzalabs.com), CongoBio | https://brazzamarket.fr/, https://marche.brazzalabs.com/, https://www.congobio.net/ | **not probed** | Surfaced by this pass's `ddgs` sweep, same "Brazzaville grocery marketplace" shape as Fil; not probed for time. Worth a look alongside Fil next pass. |
| Ministère des Hydrocarbures / Ministère des Finances (fuel price) | https://www.finances.gouv.cg/, https://www.hydrocarbures.gouv.cg/ | **no_catalog** | Quarterly "réunion des prix des produits pétroliers" and a specific arrêté page are informational articles only — zero FCFA mentions in the page body, the only PDF link is an unrelated 2008 base decree. Matches the Côte d'Ivoire `dgh_fuel_tariff` precedent exactly: no scrapable primary source, would need a hardcoded `_KNOWN_DECISIONS` cross-checked against press (africa-press.net, koaci.com-style outlets carried a Q4-2024 mention). Not pursued this pass — division 07/fuel is the best next-pass institutional target. |
| Regal Group Congo | https://regal-congo.com/ | **no_catalog** | Resolves the "next steps" note below: Regal's domain is now found (corporate site, 13.8 KB), but it is not an online store — no cart/panier/FCFA/catalogue tokens, no platform fingerprint. Confirms the prior pass's "NO ONLINE STORE" verdict with an actual domain in hand. |
| UNICONGO tariff grid, Ministère de la Santé / hospital fee arrêtés (scribd-hosted) | scribd.com/document/751016592 (Arrêté 250-MSHP-MEPS), scribd.com/document/855697652 | **not probed** | Found via `ddgs`; health-tariff (06.x) candidates hosted as scribd-embedded PDFs, which need a different extraction path (scribd doesn't serve a direct PDF download without auth). Worth a next-pass look for division 06, which remains uncovered. |

## Currently uncovered COICOP divisions after this pass

02 (alcohol/tobacco), 03 (clothing), 05 (furnishings), 06 (health — see
scribd leads above), 07 (transport/fuel — see hydrocarbures leads above),
09 (recreation), 10 (education — campusfrance.org tuition-cost leads
surfaced but not probed), 11 (restaurants/hotels), 12 (misc goods/services),
13 (insurance/finance, structurally absent from the INHPC index too).

Before this pass: `wfp_prices` only, 0 retail sources. **Result: 1 shipped,
plus three diaspora storefronts deliberately NOT shipped — see the currency
note, which is the important finding in this file.**

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `mbote_cg` | https://www.mbote.shop/ | marketplace / `retailer_sku` | **SHIPPED** | Congolese marketplace serving Brazzaville and Kinshasa; `sitemap.xml` holds 448 URLs of which **356 are `/p/` product pages**. PDP JSON-LD prices in **XAF** — Congo-Brazzaville's currency (Kinshasa/DRC transacts in CDF), so rows are attributed to `congo_rep`. Test run scraped 7 items: XAF 16,800 handbag (~US$28), XAF 76,000 projector (~US$126). Mostly general merchandise. |

## NOT shipped — diaspora storefronts priced in EUR

**This is the trap to remember for the whole Francophone-Africa sweep.** Three
of the four live candidates a French-language search returns for Congo are
"send groceries home to your family" services aimed at the diaspora. They have
real catalogs, real product names and real prices — and those prices are
**EUR prices paid by a sender in France**, not what a consumer in Brazzaville
pays. Shipping them as Congolese retail sources would corrupt any PPP or
real-exchange-rate comparison built on this corpus.

| Candidate | URL | Platform | Why not shipped |
|---|---|---|---|
| 242 MARKET | https://242market.com/ | PrestaShop-style `/NNNNNNN-slug.html`, 533 sitemap URLs | Genuinely attractive on the surface — it carries **fresh produce**, which is exactly the structural gap retail supermarkets never fill (gombo, ngai ngai, épinard, tomate grappe, bananes plantains). But the PDP prices in EUR: "Tomate Grappe SALADE Le tas" is **€1.99**, `itemprop="price" content="1.99"`, zero XAF/FCFA tokens on the page. Diaspora-facing. |
| Tchitunga | https://tchitunga.com/ | WooCommerce, **Store API open and working** | Store API returns `currency_code: "EUR"`, `currency_minor_unit: 2` (e.g. 8000 → €80.00) with food categories ("Boisson"). Technically the easiest source in this whole run to onboard, and still wrong to attribute to Congo. Its own homepage describes it as a platform "pour la diaspora congolaise". |
| BantuDelice | https://bantudelice.cg/ | Live, no price markup found | Prepared-meal delivery (20–40 min) in Brazzaville/Pointe-Noire, not grocery retail. |

If a future decision is made to track the diaspora-remittance channel as its
own analytical layer, 242market and Tchitunga are both ready to onboard and
Tchitunga needs no HTML parsing at all. They should not land under
`congo_rep` retail.

## Dead ends (carried forward, and one resolved)

| Candidate | Status | Notes |
|---|---|---|
| "Douka" grocery app | **STILL UNRESOLVED** | The 2026-09-01 file flagged this as its biggest open thread. This pass did not resolve it either — no domain and no Play Store listing surfaced in the French-language search. Genuinely unverified, still not disproven. |
| Jumia `jumia.cg` | **DEAD** | Cloudflare challenge on a domain outside Jumia's active market list. |
| Glovo `glovoapp.com/cg/` | **DEAD — 404** | Carried forward. |
| Casino / Score, Park'n'Shop, Regal | **NO ONLINE STORE** | Real physical chains in Brazzaville/Pointe-Noire/Dolisie per trade press; no e-commerce domain found. |

## Next steps

- ~~Park'n'Shop / Regal are the largest physical chains with no domain found~~
  — **resolved 2026-09-28:** Regal's domain (regal-congo.com) is found and is
  a corporate site with no online store (see the 2026-09-28 section above).
  Park'n'Shop still has no domain found.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `mbote_cg` (WooCommerce, sitemap walk) | 4/8 | 575 | 304 | Good. |


`archive_prefix` on `mbote_cg` was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had only `wfp_prices` (shared regional HDX
fetcher) before this pass — 0 retail sources. **Result: 0 sources shipped.**
**This pass ran with zero WebSearch budget** (the session-wide cap was
exhausted before this country's turn) — every candidate below was found via
direct domain probing (`curl_cffi impersonate=chrome124`) and WebFetch on
directory/search-engine pages, not a real search sweep. Treat this inventory
as a weak/partial pass, not an exhaustive one — a future run with search
budget should redo Phase 2 properly before concluding Congo-Brazzaville has
no online grocery sector.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Jumia | jumia.cg | **DEAD — Cloudflare challenge / no real storefront** | Returns a Cloudflare "Just a moment…" page (403), consistent with a squatted/reserved domain rather than live Jumia infrastructure — Jumia's current active market list does not include Congo-Brazzaville. |
| Glovo | glovoapp.com/cg/ | **DEAD — 404, no CG route** | |
| "Douka" (grocery-delivery app, named in the task brief as a lead worth checking) | douka.cg, doukacongo.com, douka-congo.com, douka.app, mydouka.com | **NOT CONFIRMED TO EXIST** | None of the guessed domains resolve (NXDOMAIN). A Google Play Store search for "douka congo" surfaced no matching app (returned unrelated results: Congo Travel, Congo Ndaku, Congosa, Congo Easy). This candidate could not be verified without WebSearch and should be re-checked properly next pass rather than assumed real or assumed dead. |
| Congo Easy (delivery app) | congoeasy.com | **UNREACHABLE this pass** | HTTP 509 (bandwidth exceeded) on the one probe attempt; not retried. Play Store listing exists ("Jj Group Company") but scope (courier vs. grocery) not confirmed. |
| Congosa | — | **NOT PURSUED — appears to be a taxi/parcel courier app, not grocery retail** | Surfaced only via the Play Store search snippet above; not independently probed. |
| Simba Supermarché | simbasupermarche.cg, simba.cg | **NOT FOUND** | Neither guessed domain resolves. |

**Conclusion:** No viable food-and-beverage retail source confirmed this
pass. Unlike Chad/Guinea-Bissau/Niger/Gambia/Liberia below, this country's
dead ends are especially weak evidence (zero real search queries ran) — the
"Douka" lead in particular is unresolved, not disproven.
