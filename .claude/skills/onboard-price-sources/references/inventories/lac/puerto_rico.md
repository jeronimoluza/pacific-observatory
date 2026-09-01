# Puerto Rico

_Inventory written: 2026-09-01_

Wave 9 pass. Cold start — no `lac/` inventory existed for Puerto Rico before this
file. Already covered before this pass: `selectos_pr` (supermarket, Freshop/NCR
platform) — 1 source / 1 food. Target: >=5 sources AND >=2 food. Entered at
Phase 3 (probe) against the wave-9 brief's named leads (Econo, SuperMax, Pueblo,
DACO, Instituto de Estadísticas / DTRH, AEE/LUMA, AAA, Claro/Liberty); the two
retailer leads that panned out (Pueblo, SuperMax) then led to two more sources
(Amigo as Pueblo's sister banner, once confirmed distinct-not-duplicate; DACO's
own homepage linked its fuel-price XLSX and a drug-price site) without further
web search. One frugal WebSearch call was spent finding the correct domains for
Econo/SuperMax/Pueblo (none of the brief's guessed domains resolved to the real
site) and one for locating DTRH's CPI page. AEE/LUMA, AAA, and Claro/Liberty
tariffs were not reached this pass (see "Untried leads" below) — time went to
building and fully measuring the sources that already cleared both bars.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Supermercados Pueblo | https://puebloweb.com/ | supermarket | **SHIPPED** as `pueblo_pr` | Bespoke Alpine.js storefront. Listing grid is client-side-filled from `/controllers/products.html?category_id=<1-9>&category_level=1&type=category&page=<n>` — plain, unauthenticated, cookie-free HTML fragment endpoint (no session/address gate, unlike the LocalExpress platform below). 9 departments, 18 products/page, confirmed to page through genuinely distinct SKUs and terminate cleanly on an empty fragment (no re-served-last-page loop). Full unbounded run 2026-09-01: 20,090 rows, 20,090 distinct `product_id`/`url`, 0 zero/negative price, 0 blank name, 100% USD, price range $0.37-$294.49 (median $4.79). Food share 72.1% (Provisiones 40.2%, Lácteos 13.1%, Cervezas/Vinos/Licores 6.0%, Frutas y Vegetales 4.5%, Panadería 4.3%, Carnes/Aves/Pescados 4.0%); non-food 27.9% (Hogar 15.7%, Salud y Belleza 9.3%, Mascotas 2.9%). 3/3 cold PDP re-fetches matched name+price. |
| SuperMax Online | https://www.supermaxonline.com/ | supermarket | **SHIPPED** as `supermax_pr` | Different bespoke jQuery storefront, same "load more" AJAX-grid shape as Pueblo but a different vendor: department pages ship an empty grid filled by POSTing to `/products-grid-data.html` with `department=<id>&draw=<n>`, no auth. 8 of 9 nav departments expose a working id (organico is a slug id; "cenas" has no products-grid on its own page and was left out rather than guessed at). Confirmed clean pagination termination (draw>=20 empties and stays empty on the smallest department tested). Full unbounded run 2026-09-01: 13,417 rows, 13,229 distinct `product_id`, 13,417 distinct `url` (the ~200-id gap is a handful of SKUs cross-listed under two department views with different URL slugs, not duplicate rows), 0 zero/negative price, 0 blank name, 100% USD, price range $0.39-$286.99 (median $4.99). Food share 78.1% (Provisiones 39.5%, Lácteos 17.3%, Licores 9.1%, Carnes y Mariscos 5.2%, Deli y Bakery 3.4%, Frutas y Vegetales 2.3%, Orgánico 1.4%); non-food 21.9% (Hogar/Salud y Belleza). 3/3 cold PDP re-fetches matched price. |
| Supermercados Amigo | https://www.amigo.com/ | supermarket | **SHIPPED** as `amigo_pr` | Same platform and category_id scheme as `pueblo_pr` — footer confirms "Supermercados Amigo, PO BOX 1967, Carolina, Puerto Rico", same HQ as Pueblo (Wikipedia: "Amigo Supermarkets ... owned by Pueblo"). Built as a **separate** source, not skipped as a duplicate: a live sample of 90 SKUs per domain from category_id=1 found only 84% SKU overlap, and 17 of 76 (22%) SKUs common to both carry genuinely different shelf prices (e.g. sku 127472: Amigo $0.79 vs Pueblo $0.99) — two independently-priced banners on a shared catalog backend, the same pattern this skill already accepts for `*_wolt_*`-style first-party splits. Full unbounded run 2026-09-01: 20,583 rows, 20,583 distinct `product_id`/`url`, 1 zero-price row out of 20,583 (0.005%; verified live — "CAJITA DE REYES INST. DE CULTURA", a genuine $0.00 cultural-donation item, not a parsing defect), 0 blank name, 100% USD, price range $0.00-$294.49 (median $4.79). Food share 72.2%; non-food 27.8% (near-identical mix to Pueblo, as expected from the shared catalog). 3/3 cold PDP re-fetches matched price. |
| DACO gasoline/diesel monthly averages | https://daco.pr.gov/ (file: docs.pr.gov XLSX) | null (non-retail) | **SHIPPED** as `daco_fuel` (fetcher, `analytical_role: official_avg`, COICOP 07.2.2) | DACO's homepage links a single, continuously-updated XLSX of monthly average consumer Regular/Super/Diesel prices, hosted on a docs.pr.gov document store — no auth, plain `requests.get`. One sheet, monthly rows 2000-01 through 2026-07 at probe time. Values are cents/US-gallon (divided by 100 in the fetcher; sense-checked against a Jan-2000 Diesel value of $1.22/gal). First full-history run 2026-09-01: 945 rows (315 months x 3 items: Regular/Super/Diesel), 0 zero/negative price, 100% USD, price range $1.147-$5.5576/gal (median $2.796). Idempotence verified (re-run with rolled-forward cutoff returns 0 new rows). |
| DTRH Índice de Precios al Consumidor (IPC) | https://www.mercadolaboral.pr.gov/Publicaciones/Otras_Publicaciones/Indice_Precio.aspx | null (non-retail) | **SHIPPED** as `dtrh_ipc` (fetcher, `analytical_role: cpi_benchmark`, `coicop_code: "00"` all-items) | Official PR CPI (base Dec-2006=100), published monthly by the Departamento del Trabajo y Recursos Humanos. The publication page is an ASP.NET WebForms year/month picker with `__VIEWSTATE` postback, but the postback resolves to a predictable, directly GET-able static PDF at `mercadolaboral.pr.gov/lmi/pdf/IPC/<year>/Indice de Precios al Consumidor <month>.pdf` — confirmed by submitting the form once and reading the redirect; no postback simulation needed at run time. Extracts only the headline all-items index from each month's "Tabla 1" page (not the ~15 group/subindices in Table 2 — a genuine two-column bilingual layout not attempted this pass). **Non-trivial extraction defect found and fixed during this pass**: `pdfplumber.extract_text()` garbles Table 1's number grid into unreadable interleaved characters for the 2018-2023 publication era specifically (confirmed on the 2022-06 PDF) — the fix reconstructs visual rows from `extract_words()` positions instead, which works uniformly across every era tested (2011, 2018-2023, 2024-2026). Full-history run 2026-09-01: 183 of 187 possible months (2011-01 through 2026-07), with the only 4 gaps being genuine non-publications the PDF's own footnotes name explicitly — Sep/Oct 2017 (Hurricane Maria) and Apr/May 2020 (COVID-19 closure) — not extraction failures. 0 nulls in `index_value`. Idempotence verified. |
| Preciosdemedicamentos.pr.gov | https://preciosdemedicamentos.pr.gov/ | pharmacy | **UNTRIED — not a food source, deferred** | DACO also publishes a drug/medication price-comparison site at this domain, found alongside the fuel XLSX link. Not probed this pass — it's pharmacy-channel (doesn't count toward the food bar) and the bar was already cleared without it. Worth a look in a future pass as a `pharmacy`-channel or `official_avg` source if PR's non-food coverage needs depth. |
| Econo Supermercados (Econo ToGo) | https://www.superecono.com/ / https://econotogo.com/ | supermarket | **DEAD — LocalExpress address-gate, known blocker class** | Real domain (the brief's guessed `economultiahorro.com`/`econo.com` do not resolve/serve). The corporate site (`superecono.com`, WordPress) links out to `econotogo.com`, which is the same LocalExpress platform already logged in `known_blockers.md` for Barbados (`online.imartstores.com`) and Grenada (`shop.realvalueiga.com`): an anonymous JWT is obtainable via `GET /rest-proxy/v2/whoami?anonymous=1` (confirmed, `selectedStore: null`), but every department/product endpoint tried (`/rest-proxy/v2/stores`, `/departments`, `/products`) 404s without an address/store selected first, and there is no way to select one without the JS app. Not re-probed further per the skill's guidance that this platform needs a dedicated Playwright address-selection effort — logged here as a third confirmed instance of the same platform-wide gate. |
| Pueblo Virtual / Amigo weekly "Shopper" | https://www.virtual.puebloweb.com/, https://www.amigo.com/shopper | — | **NOT A SEPARATE SOURCE — folded into `pueblo_pr`/`amigo_pr`** | `virtual.puebloweb.com` is a Webflow marketing microsite for the physical-store locator/loyalty program, not a catalog. The `/shopper` weekly-circular view on both domains uses `type=shopper` on the same `/controllers/products.html` endpoint already scraped via `type=category` — same underlying catalog, so it is not additional coverage. |
| wfmpueblo.com | https://wfmpueblo.com/online-store | — | **DEAD — unrelated GoDaddy site, not the Pueblo chain** | Came up in the initial WebSearch for "Pueblo ... online store" but is a small unrelated business built on GoDaddy Website Builder (`img1.wsimg.com` CDN) — not affiliated with Supermercados Pueblo. Not investigated further. |
| Instituto de Estadísticas de Puerto Rico (estadisticas.pr.gov) | https://estadisticas.pr.gov/ | — | **DEAD END for CPI — wrong agency, redirected to the real one** | The brief named this as the CPI publisher; its own site has no CPI page (`/en/content/consumer-price-index` and the Spanish equivalent both 404). The actual publisher is DTRH via `mercadolaboral.pr.gov` (built above as `dtrh_ipc`). `indicadores.pr`'s CKAN-style CPI dataset pages exist but hit an SSL cert error under `curl_cffi` and were not pursued once the DTRH PDF path worked cleanly. |
| AEE / LUMA Energy (electricity tariff) | https://lumapr.com/ | — | **UNTRIED** | Homepage loads (200, confirmed live), but the tariff-schedule page itself was not located/probed this pass — time went to the sources above once the bar was cleared. Good next-pass candidate (`tariff` / `source_curated`, COICOP 04.5). |
| AAA / Autoridad de Acueductos (water tariff) | https://www.acueductospr.com/ | — | **UNTRIED** | Homepage loads (200, confirmed live). Not probed further this pass. Good next-pass candidate (`tariff`, COICOP 04.4). |
| Claro PR | https://www.claropr.com/ | — | **UNTRIED** | Homepage loads (200, confirmed live, large page ~720KB). Not probed further this pass. Good next-pass candidate (`tariff`, COICOP 08.2/08.3). |
| Liberty PR | https://www.libertypr.com/ | — | **UNTRIED** | Homepage loads (200, confirmed live). Not probed further this pass. Good next-pass candidate (`tariff`, COICOP 08.2/08.3). |

## COICOP / channel gap after this pass

Puerto Rico ends at **6 sources / 4 food** (`selectos_pr`, `pueblo_pr`,
`supermax_pr`, `amigo_pr` — all `channel: supermarket`), clearing both the
5-source and 2-food bars with two sources and two food sources to spare.
`daco_fuel` (COICOP 07.2.2, official_avg) and `dtrh_ipc` (all-items CPI
benchmark, base Dec-2006=100) round out the non-food half with real
non-retail administrative-price coverage, per the brief's guidance that
these are cheap and count toward the 5 even though they don't count toward
food.

Divisions with price-level coverage: 01 (food, all four supermarkets), 02
(alcohol, Cervezas/Vinos/Licores departments), 05/06/12 (Hogar, Salud y
Belleza departments — unclassified pending the downstream classifier),
07.2.2 (fuel, `daco_fuel`). Divisions still uncovered: 03 (clothing), 04
(housing/utilities — `lumapr`/`acueductospr` untried), 08 (communication —
`claropr`/`libertypr` untried), 09/10/11 (recreation, education,
restaurants), 13 (misc/insurance). Index coverage (all-items only, no
division breakdown): `dtrh_ipc`.

## Next gaps to target (priority order, for a future pass)

1. **LUMA (electricity) and AAA (water) tariff fetchers** — both homepages
   confirmed live 2026-09-01; the actual tariff-schedule pages were not
   located this pass. Cheapest remaining wins per the brief's own framing.
2. **Claro PR / Liberty PR telecom plan pages** — both confirmed live;
   untried. Likely SPA-rendered (residual-source bucket 2 in the skill's
   doctrine), so probe with Playwright network-capture before assuming a
   static scrape works.
3. **preciosdemedicamentos.pr.gov** (DACO drug-price comparison) — found
   but not probed; would add `pharmacy`-channel or `official_avg` coverage,
   not food.
4. **DTRH IPC Table 2 group/subgroup indices** — the headline-only fetcher
   built this pass leaves ~15 division-level sub-indices unparsed behind a
   genuinely two-column bilingual PDF layout. Real, but a separate, harder
   effort than this pass budgeted for.
5. **LocalExpress address-gate** (Econo) — same platform already blocked
   for Barbados and Grenada; cracking it once would likely unlock all
   three at once. Needs a dedicated Playwright session-cookie/address-pick
   effort, not a quick re-probe.
