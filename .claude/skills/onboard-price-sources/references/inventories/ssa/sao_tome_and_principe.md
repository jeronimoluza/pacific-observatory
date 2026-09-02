# Sao Tome and Principe

_Inventory written: 2026-09-01_

Wave 13 pass. Country had ZERO manifests and no config directory before this pass
(`sao_tome_and_principe` verified against `src/configs/regions.yaml` under
`ssa.central_africa` before creating the path). Started from 3 workbook candidates
(`outputs/sources_pending_will.xlsx`; `sources_pending_jero.xlsx` had no STP rows) plus
the brief's own DISCOVER list (INE, EMAE, ENCO, CST, Unitel, wfp_prices/fews_net).
Target: >=5 sources AND >=2 food-and-beverage. **Result: 5 sources / 0 food** — the
5-source bar is cleared, the food bar is not, despite an exhaustive search (see below).

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `ine_ipc` (`stp_ine_ipc`) | https://ine.st/index.php/informacoes-estatisticas/ipc | null / `cpi_benchmark` | **SHIPPED** | INE STP's monthly IPC via a Joomla + Phoca Download document tree. 780 rows, 65 distinct months (2021-01 to 2026-07, missing only 2021-11/2021-12 which genuinely have no category folder on the site), 12 COICOP-1999 divisions, 0 duplicate hashes, 0 nulls, 0 non-positive values. Two real bugs found and fixed during build: (1) Phoca Download's per-file POST has an anti-abuse hidden field whose NAME (not value) is a random hex string regenerated every page load — must be re-parsed fresh before every download, never cached; (2) the month-subcategory list is **not reliably in calendar order** (2022 and 2023 list months by creation-id order, e.g. "...outubro, dezembro, novembro") — resolving "the latest month" by list position instead of by parsing the month name from the label text silently dropped Sep-Dec in some years until fixed. Cold re-fetch of 5 spot-checked (date, coicop_code) values against a fresh download matched the shipped CSV exactly. |
| `emae_electricity_tariff` (`stp_emae_electricity_tariff`) | https://emae.st/PT/clientes/tarifarios | null / `tariff` | **SHIPPED** | EMAE (national water+electricity utility) post-paid + pre-paid electricity rate tables, `pandas.read_html` off static HTML, no anti-bot. 50 rows (10 customer categories x 3 consumption bands post-paid + 10 x 2 meter-phase pre-paid), 0 duplicates, 0 nulls, price range 1.67-9.87 STN/kWh. No effective date printed on page -> `period_kind: snapshot`. |
| `emae_water_tariff` (`stp_emae_water_tariff`) | https://emae.st/PT/clientes/tarifarios | null / `tariff` | **SHIPPED** | Same EMAE page, water table (10 categories x 2 consumption bands). 20 rows, 0 duplicates, 0 nulls, 3.90-6.83 STN/m3. One site visit -> 2 sources, as the brief predicted. |
| `cst_turbo_tariff` (`stp_cst_turbo_tariff`) | https://cst.st/PT/turbo/tarifarios | null / `tariff` | **SHIPPED** | CST (incumbent telecom) prepaid "Turbo" bundle family — 4 tiers (Turbinho/Turbo+Net/Superturbo+Net/Turbo Max+Net) x 3 durations = 12 plans, 10-330 STN. `pandas.read_html` returns 8 tables in duplicate pairs (a compact rendering + a wider responsive re-rendering of the SAME 3 rows) — only the even-indexed tables are used, confirmed this yields exactly 12 rows, not 24. |
| `cst_voice_tariff` (`stp_cst_voice_tariff`) | https://cst.st/PT/clientes/tarifarios | null / `tariff` | **SHIPPED** | Sibling to `cst_turbo_tariff`, same operator but a disjoint product line: per-minute/SMS usage rates for CST's "Principe" (postpaid) and "Leve Leve" (prepaid) plans, 9 rows. Each plan's page also renders its rate card as several overlapping tables (partial voice-only / SMS-only splits plus one consolidated table) — only the last (consolidated) table per page is used. |

## Dead ends (workbook candidates)

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Entrega.st | https://www.entrega.st/ | **DEAD — RLS-locked, no public price surface at any layer** | Vite/React SPA over Supabase (`qhakterudpcyieehzacn.supabase.co`). Querying `products`/`establishments` with the shipped anon `sb_publishable_...` key returns `401 permission denied for table establishments` (grants never issued to the anon role) — matches the workbook's own "catalogue behind login" flag. The site's public `/lojas` store-directory route (found via sitemap.xml, confirmed via a live network trace to hit an explicit public RPC `rpc/list_public_establishment_directory`, i.e. a deliberately curated public surface, not raw table leakage) lists only **4 total registered merchants platform-wide** (1 restaurant, 1 "loja geral"/general store, 1 pharmacy, 1 bakery/restaurant) with ratings/open-status only — no product names or prices anywhere, confirming the JS bundle's own "Espaço futuro para divulgar estabelecimentos" (future space) copy. The full RPC allowlist visible in the bundle (`get_current_customer_order_courier_reputation`, `get_current_establishment_contexts`, `list_orderable_establishments`, etc.) contains no products/catalog RPC. Genuinely too new and too locked-down to be a source today ("pronta para receber os primeiros clientes" per the workbook's own note). |
| Sokeru | https://sokeru.st/ | **DEAD — NXDOMAIN** | `dig sokeru.st @8.8.8.8` and `@1.1.1.1` both return nothing — confirmed against two independent public resolvers per rule 15 (not a sandbox DNS lie). |
| Super CKdo | http://www.superckdo.com/ | **DEAD — NXDOMAIN** | Same double-resolver confirmation as Sokeru; the workbook's own note ("promotions posted to Facebook rather than a catalogue") plus the plain-HTTP flag both correctly predicted this would not be a real catalogue even before the domain died outright. |

## Dead ends (brief's DISCOVER list)

| Candidate | URL | Status | Notes |
|---|---|---|---|
| ENCO | https://enco.st/ | **DEAD — brochure site, no price data at any level** | Custom Vite SPA over `encoserver.exportech.com.pt`, which sits behind a JS "checking your browser" challenge that beats `curl_cffi` on chrome124/chrome120/safari17_0/chrome99/chrome131 — but a Playwright render clears it (mandatory gate: curl AND Playwright both failing is the "stop" condition; only curl failed here). Once past the challenge, the API returns exactly **1 product** (a Galp motor-oil lubricant) with **no price field in the schema at all** (title/shortDesc/html/image/category/tags only), and exactly 1 category. The `servicos.html` page confirms ENCO's site describes storage **capacity** (m3 of gasoline/diesel/JET-A1 held, number of filling stations) — never retail pump prices. Administered fuel prices are not published anywhere on this domain. |
| Unitel STP | https://unitel.st/ | **DEAD — stale/no inline price data found** | `tarifario-maxibin.php` and `tarifarios.php` carry only INTERNATIONAL roaming/calling rates (no local bundle prices). `internet-no-telemovel.php`, the local mobile-data landing page, has **zero `<table>` tags and zero price-bearing text** in its raw server-rendered HTML — the page only lists plan NAMES with "Data de modificação" stamps as old as 2016-2017, suggesting the actual figures live in an image, PDF, or JS-only widget not reachable via a static fetch. Not pursued further given CST already covers the same `tariff`/08.1.0 role for STP with genuinely live, dated-2026 data. |
| Ministerio das Financas (fuel-price decree hope) | http://www.financas.gov.st/ | **DEAD — genuine 403, not a false WAF verdict** | Domain resolves fine (`197.159.191.x`), but returns HTTP 403 under `curl_cffi` with chrome124/chrome120/safari17_0 impersonation AND under a real Playwright-driven Chromium (`status 403`, body "403 - Forbidden / Access to this page is forbidden") — satisfies the mandatory curl+Playwright-both-fail gate before recording as blocked. `gov.st` itself (the main government portal) timed out entirely rather than resolving. No official fuel-price gazette/decree was found via any other path. |
| wfp_prices (HDX) | https://data.humdata.org/api/3/action/package_show?id=wfp-food-prices-for-sao-tome-and-principe | **NO DATASET — confirmed via CKAN API, not a guess** | `package_show` for the STP slug returns `404 Not Found`; a live `package_search` for "sao tome" on data.humdata.org returns 10 STP-tagged HDX datasets (settlements, conflict events, 5x World Bank indicator sets, admin boundaries, airports) — **none is a WFP food-prices panel**. STP is not one of the 34 countries in the repo's `_shared.ssa.wfp_food_prices._PANELS` dict, and this confirms it should not be added. |
| fews_net (FEWS NET API) | https://fdw.fews.net/api/marketpricefacts/?country_code=ST | **NO DATA — confirmed via live API call** | `GET .../marketpricefacts/?country_code=ST` returns `{"count":0,"next":null,"previous":null,"results":[]}` — the API itself is reachable and correctly parses the ISO2 country code, it simply holds zero market-price facts for STP. STP is not in `_shared.ssa.fews_net._COUNTRIES`, and this confirms it should not be added. |

## Food-and-beverage: exhaustive search, zero result (structural gap, not a search failure)

Every avenue tried came up dead or produced only false-positive name collisions with
places elsewhere in the world also called "Sao Tome" (Argentina) or where "Principe"
is a common word (Brazil, Portugal):

- All 3 workbook retail candidates (Entrega.st, Sokeru, Super CKdo) — dead, see above.
- Entrega.st's own public store directory (the one legitimately public surface on that
  platform) — 4 total merchants platform-wide, none clearly a supermarket/grocer, and
  no prices exposed for any of them regardless of category.
- `www.paginasamarelas.st` (Sao Tome & Principe Yellow Pages) `/search-results/supermercados`
  — a Next.js app whose listing data is not present in the initial HTML/RSC payload
  (client-fetched), and a Playwright render of the page returned an outright
  "Forbidden" (blocked differently than a plain HTTP fetch) — not pursued further as a
  discovery aid since it is a phone-book directory, not a price source, even if opened.
- `www.stpvendas.st` (STP general classifieds/OLX-style site) — has an
  `agricultura/produtos-agricolas` and `agricultura/hortalicas` category, but this is
  peer-to-peer classified ads (one-off individual asking prices, `channel: marketplace`
  at best), not a systematic retailer catalogue; does not count toward the food bar
  even if built, and was not built given the ratio of effort to expected data quality.
- Direct domain guesses for plausible local supermarket names (panaria.st,
  mister-price.st, miramar.st, supermercadopantufo.st, ossobo.st, shoprite.st,
  camoes.st) — all NXDOMAIN.
- 2 targeted WebSearch queries (Portuguese-language, STP-specific terms) — every
  "supermarket" result returned was a false positive: "Supermercado Petrelli" and
  "Supermercados Santo Tomé" are in Santo Tomé, **Argentina**; "Proença Supermercados"
  and "Mercearia Bom Preço" are in **Brazil**; the Tiendeo.pt "Sao Tome do Castelo"
  result is a village in **Portugal**. No genuine Sao Tome and Principe (Africa)
  supermarket with a web or app catalogue surfaced.
- STP Airways (national airline, domestic Sao Tome<->Principe route) — bookings route
  through a third-party GDS (`fo-emea.ttinteractive.com`, Zenith/TTInteractive), no
  static fare table; would need a full interactive booking-flow automation, judged not
  worth the remaining budget for a `07.3` transport source that still wouldn't be food.
- Sao Tome<->Principe inter-island ferry — no official operator price page found;
  the only figures available (~EUR 45) come from travel-blog prose, not a
  structured, re-fetchable source.

**Conclusion:** as of 2026-09-01, Sao Tome and Principe has no discoverable online
food-and-beverage retail presence (no supermarket, hypermarket, convenience store,
fresh-market aggregator, or specialty-food site with a web/app catalogue this agent
could reach). This reads as a genuine structural absence for a ~230,000-person market
with very low e-commerce penetration (its most-hyped local "first e-commerce platform,"
Entrega.st, has 4 total registered merchants), not a search-effort gap. A future pass
should re-check Entrega.st and Sokeru periodically (both are recent, actively-developed
launches — Entrega.st shipped a v3.9.39 changelog during this very probe) rather than
re-running a fresh web search, which is unlikely to surface anything new that a
web search didn't already surface this wave.

## COICOP / channel gap after this pass

Sao Tome and Principe ends at **5 sources / 0 food**. Coverage by analytical_role:
`cpi_benchmark` (INE, all 12 COICOP-1999 divisions as an index, not price-level),
`tariff` x4 (EMAE electricity 04.5.1, EMAE water 04.4.1, CST bundles 08.1.0, CST
per-use 08.3.0). Zero `retailer_sku` / `official_avg` / `specialty-food` coverage —
division 01 (food) has no price-level source at all, only whatever the classifier
would eventually see if one existed. This is an honest shortfall on the food bar,
not a padded count: no source here was relabeled into a food-qualifying `channel`
that isn't genuinely food-and-beverage retail.
