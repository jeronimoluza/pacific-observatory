# Angola

_Inventory written: 2026-09-01_

Wave 10 pass, working from pre-scouted candidates (`outputs/sources_pending_will.xlsx`),
entered the skill at Phase 3. Already-covered before this pass: `fews_net` (shared
`official_avg` fetcher), `kiwaba_ao` (`supermarket`) -- 2 sources / 1 food. This pass
needed 3 more sources, >=1 food; target was >=5 sources AND >=2 food.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Kibabo Online | https://www.kibabo.co.ao/pt/ | supermarket | **SHIPPED** as `kibabo_ao` | "Redicom Prolepse" custom CMS (AngularJS over server-rendered HTML) -- the site's own meta description ("loja de produtos nao-alimentares") is stale boilerplate; the live nav has a full grocery department (alimentar, bebidas, frutas-legumes, lacticinios) plus non-food. Product pages carry a clean schema.org Product+Offer JSON-LD block (price as plain decimal, e.g. "2545.00", priceCurrency "AOA") -- immune to the on-page Portuguese thousands-comma display format; 5/5 cold re-fetches confirmed name+price match live. CrawlSpider walks a 3-level category tree via `?page=N` pagination. A `--max-items 250` test run is LIFO-skewed (63% Limpeza, a scheduler tail-drain, not the real catalog mix -- see yaml notes); a properly department-stratified sample (each department's own JSON-LD ItemList, not the crawl) put real food share at ~35%. |
| Angoremia | https://angoremia.shop/ | supermarket | **SHIPPED** as `angoremia_ao` | React/Vite storefront over an open Supabase PostgREST API (`gysuaverjqobepozhmnq.supabase.co`). Neither the project URL nor the anon key appear as literal strings in the shipped JS bundle (minified, variable-renamed) -- recovered via a live Playwright network trace of `/catalogo` ("Playwright to discover, plain HTTP to scrape"). Small catalog: `count=exact` confirmed 10 active rows total, not a capped sample. `preco` is whole AOA already (cross-checked "27500" against the live PDP's "27 500 Kz" -- no minor-unit division). **6/10 rows carry a stale slug+categoria_slug that names a different product than the current nome/preco** (e.g. slug="detergente-liquido-2l" but nome="AZEITONA CAMPONES..."). Verified three ways as a genuine site-side data defect, not a scraper join bug: fresh LIST re-pull byte-identical, a per-slug DETAIL query agrees, and live Playwright renders of all 5 non-trivial mismatched PDPs show the same name+price+category as scraped (the site's own PDP for detergente-liquido-2l literally displays "Categoria: higiene" under an olives product). name+price are unaffected and match the live PDP every time; `category` is unreliable for ~half this source's rows. Kept `channel: supermarket` (not `wholesale`) after checking positioning -- FAQ treats reseller pricing as a side inquiry, terms cap per-customer quantities, no minimum order/business ID, VAT-inclusive pricing, and per-unit prices (e.g. 9,167 Kz/bottle olive oil) show no bulk discount; catalog genuinely mixes case-pack SKUs with single retail units. |
| EPAL (water tariff, Luanda) | https://www.epal.co.ao/comercial.php | null (tariff) | **SHIPPED** as `epal_water_tariff_ao` | Static Bootstrap page (no JS, no PDF) embeds the household/commercial "Tarifario" table directly in server-rendered HTML -- 7 rows. AOA CURRENCY TRAP confirmed live: fixed monthly charges use Portuguese formatting ("3.900 Kz" = 3900, not 3.9); parser handles both separators. No printed effective date -- `period_kind: snapshot`. Luanda-only utility, `subnational_area: "Luanda"` on every row. |
| Mena Mart | https://www.menamart-angola.com/ | -- | **DEAD -- login wall** | Laravel B2B wholesale site. Homepage renders ~1,323 product cards server-side (name + pack size only, e.g. "OLEO DE PALMA ALIMO, 12 x 1L") but genuinely carries NO price anywhere in the public HTML -- every "ADICIONAR" (add-to-cart) button links to `/login`, and there is not a single reachable per-product detail page URL outside the login flow (only `/sobre` besides ~1,288 `/login` links). The workbook's "Kz prices" note does not hold on a fresh, unauthenticated fetch. |
| Sonangol Distribuidora ("Observatorio de Mercado") | https://observatoriom-dc.sonangol.co.ao/precos/ | -- | **DEAD -- app stopped** | HTTP 403 with an Azure "Web App - Unavailable ... this web app is stopped" page -- not a WAF, the backend itself is shut down. This is the state fuel company's official pump-price tracker (would have been a strong `tariff`/07.2.2 lead) but is not currently serving. |
| Hiperkupa | https://hiperkupa.ao/ | -- | **SUSPECT -- timeboxed, not built** | Flutter Web "multi-restaurant" delivery app (canvas-rendered, no scrapable DOM) backed by an open StackFood-style Laravel API at `painel.hiperkupa.ao/api/v1/*` (guest auth works: `POST /auth/guest/request` -> 200). However `get-restaurants/all` returns `total_size: 0` with plain lat/lng/zone_id guesses -- the app appears to gate restaurant listings behind a zone-detection flow (Playwright network trace under a plain page load did not surface the exact header/param it needs within the timebox). Per the brief's own "timebox it" instruction, not pursued further this wave. Even if unlocked, workbook flagged "grocery depth unclear" and the app is described as multi-restaurant (COICOP 11.1 prepared food), so its food-retail (COICOP 01) value is uncertain.
| Mamboo | https://site.mamboo.co.ao/ , https://mamboo.co.ao/ | -- | **DEAD -- app-only, no web catalogue** | Both the `site.` marketing subdomain (1,276 bytes) and the bare apex domain (939 bytes) are placeholder shells with no catalogue; `app.`, `loja.`, `shop.` subdomains do not resolve. Confirms the brief's own prediction. P4 surplus candidate -- not needed given the bar was already cleared. |
| Sonangol regulated fuel prices (general) | -- | -- | **NOT PURSUED THIS PASS** | Beyond the dead Observatorio de Mercado app above, no other machine-readable Sonangol pump-price feed was found within budget. News articles (expansao.co.ao, angop.ao) report current headline prices (gasolina 300 Kz/L, gasoleo 400 Kz/L as of Aug/Sep 2026) but are not a stable structured source. Worth a fresh look if Sonangol's Observatorio app comes back online. |
| INE Angola IPCN (CPI) | https://www.ine.gov.ao/publicacoes/Pesquisatag/IPCN | -- | **INFEASIBLE under current IndexObservation schema** | INE publishes a clean monthly "FIR" (short) PDF and a longer "Boletim" PDF, both live and easy to locate (`Publicacao_*.pdf` linked from each publication's detail page). Checked both product types on the Jan-2026 FIR and the May-2025 Boletim: neither publishes a per-COICOP-division **index level** table across months -- only (a) the national headline index time series (Dez.2020=100) and (b) per-division **contribution/participation percentage-point** tables, which are not index levels. Per the skill's own open design question, headline-only CPI has no sanctioned coicop_code slot and is currently dropped -- so a fetcher built against what INE actually publishes would ship zero rows. Would need the Boletim's per-province tables cross-referenced against a division breakdown not present in either PDF type checked. Not built this wave; flag for a future pass if INE ever publishes a division-index annex. |
| ENDE (electricity tariff) | https://www.ende.co.ao/ | -- | **NOT PURSUED THIS PASS** | Angular SPA (`chunk-*.js`, no server-rendered content); the actual tariff table (if published on-site at all, vs. only in scattered news coverage of decree changes) would need Playwright rendering. Not attempted given EPAL water tariff already cleared the non-food-source need cheaply. |
| Unitel (telecom tariff) | https://unitel.ao/netcasa | -- | **NOT PURSUED THIS PASS** | WordPress site reachable only with `verify=False` (incomplete TLS chain); the `/netcasa` plan page returned zero "Kz" mentions in static HTML (JS-rendered pricing widget). Not attempted given the bar was already cleared. |

## COICOP / channel gap after this pass

Angola ends at **5 sources / 3 food** (`kiwaba_ao`, `kibabo_ao`, `angoremia_ao` all
`channel: supermarket`; `fews_net` is `official_avg` food-adjacent but does not count
per the food-channel definition; `epal_water_tariff_ao` is `tariff`/04.4.1, non-food).
Both target bars (>=5 sources, >=2 food) are cleared with one food source to spare.

Remaining gaps for a future pass, in priority order: (1) a working Sonangol/fuel
`tariff` source (07.2.2) if the Observatorio app returns, or a scrape-stable news
source in the interim; (2) INE CPI once/if a division-level index annex is confirmed
to exist in some publication this pass didn't check; (3) ENDE electricity tariff
(04.5.1) via Playwright; (4) Hiperkupa's zone-gated restaurant API, low priority given
its food-retail relevance is unclear even if unlocked.

## fews_net cross-country note (13 countries share this config)

Confirmed **it does respond** for this agent -- a direct `requests.get` against
`https://fdw.fews.net/api/marketpricefacts/?country_code=AO` returned HTTP 200 with a
13.6 MB payload in <15s, so this is not the full connection timeout / unreachable host
two agents hit in wave 9. However, the shared fetcher `_shared.ssa.fews_net:fetch_fews_ago`
itself still failed when actually invoked: `WARNING request failed: Expecting value:
line 1 column 1 (char 0)` -- the fetcher's own request got back an empty/non-JSON body
(0 rows), a different failure mode than a raw connection timeout. Net effect for this
country/session: reachable at the network level, but the shared fetcher does not
currently return usable rows either way. Not investigated further per the brief's
instruction not to fix or remove it.
