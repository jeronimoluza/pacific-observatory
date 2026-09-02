# El Salvador

_Inventory written: 2026-09-01_

Wave 10 pass. Cold start — no `lac/el_salvador.md` inventory existed before this file.
Already covered before this pass: `walmart_sv` (supermarket, USD), `wfp_prices`
(shared regional `official_avg` fetcher), `farmaciasannicolas_sv` (pharmacy),
`siman_sv` (dept-store) — 4 sources / 1 food. Target: >=5 sources AND >=2 food. Only
one workbook candidate existed for this country (`outputs/sources_pending_will.xlsx`,
"Pending sources" sheet): **Vidrí** (hardware/home-improvement, tier C, does not
solve food) — not built this pass since a genuine food source landed instead.

El Salvador is dollarized (USD since 2001); no local-currency confusion risk. Bitcoin
was legal tender 2021-2025 but no probed site showed a BTC price.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Super Selectos | https://www.superselectos.com/ | supermarket | **SHIPPED** as `superselectos_sv` | El Salvador's largest domestic chain, operated by Calleja, S.A. de C.V. (confirmed via footer) — independent of Walmart Centroamerica, confirmed via a disjoint platform (ASP.NET Blazor Server vs VTEX) and disjoint product_id namespace. **Known site defect, confirmed live 2026-09-01**: the `?category=<code>` query param on `/products` does not filter — verified three ways (persistent-session curl_cffi, a real Playwright click-through, and unrelated category codes returning the same generic pool). `category` is therefore emitted as `null`. What is real: `&page=N` genuinely changes the result set (~232 distinct IDs surfaced across just 20 sample fetches), so the spider walks ~50 homepage-seeded (category-code, page) combinations as a broad sample and relies on a canonicalized `?productId=` URL for dedup. Full unbounded run 2026-09-01: 3,685 rows, 3,685 distinct `product_id`, 3,685 distinct `url` (zero dupes; DuplicationPipeline dropped 2,771 repeat fetches), 0 zero/negative price, 0 blank name, 100% USD, price range $0.11-$434.95 (median $3.35). Product-name keyword scan: ~73% food/beverage-keyword rows (dairy, meat, grains, beverages, alcohol), ~24% non-food (personal/home care, pet, baby) — food-dominant, correctly `channel: supermarket`. 3/3 cold re-fetch spot checks confirmed via `og:title` metadata matching the scraped name exactly (price meta not exposed on cold fetch, but identity resolution confirmed real). |
| Despensa de Don Juan | https://www.ladespensadedonjuan.com.sv/ | — | **DEAD END — same shelf as `walmart_sv`, do not onboard** | VTEX tenant (`vtex.render-server`); CSS class names literally include `--search-mobile-walmart` / `--search-walmart-header`, i.e. this storefront runs on the same Walmart Centroamerica VTEX workspace, just re-skinned. Measured: pulled 500-item samples from each of `ladespensadedonjuan.com.sv` and `walmart.com.sv`'s `/api/catalog_system/pub/products/search` — 213 of 499 Don Juan productIds (42.7%) also appear in the Walmart sample, with **identical `productName` on every matched ID** (e.g. productId 4063633 = "Queso Crema Dos Pinos Original - 210 g" on both). This is the exact wave-9 Puerto Rico defect (rule 19) — same backend, shared product_id namespace. Do not onboard as an independent source. |
| Despensa Familiar / Maxi Despensa | maxidespensa.com.sv | — | **DEAD END — confirmed Walmart Centroamerica banner, same family as `maxidespensa_gt`** | WebSearch surfaced the corporate announcement directly on `walmartcentroamerica.com` ("Maxi Despensa lanza nuevo sitio para compras en línea") — Walmart's own press site names Despensa Familiar/Maxi Despensa El Salvador as its banner. Same corporate family already documented for `maxidespensa_gt` (Guatemala). Not probed further given the corporate confirmation and the Don Juan precedent above; do not onboard. |
| Hiper Europa | (none — chain defunct) | — | **DEAD — chain no longer exists** | WebSearch confirms Hiper Europa was a 1990s-era chain (founders Edmundo/Óscar Saca) that has since disappeared from the Salvadoran market; press retrospectives list it among extinct supermarkets. No current domain or storefront. |
| La Colonia | https://www.lacolonia.com/ | — | **DOES NOT COUNT — Honduras-only** | Already onboarded as `lacolonia_hn`. Live site has zero mentions of "El Salvador" or any Salvadoran city; store list is Tegucigalpa + San Pedro Sula only. Confirms the brief's suspicion — does not trade into El Salvador. |
| PriceSmart El Salvador | (not probed — out of scope) | wholesale | **Excluded by definition** | Brief flags this as `wholesale` channel, which does not count as food per the country's definition of done even if built. Not probed this pass since the food bar was already cleared by Super Selectos. |
| PedidosYa (El Salvador) | https://www.pedidosyasv.com.sv/ | — | **App-only for the supermarket vertical — no web catalogue found** | Public web root only exposes restaurant/food-delivery paths (`/restaurantes`, `/comidas`, `/home-page`); `/supermercados`, `/mercado`, `/market` all 404. "PedidosYa Market" (their dark-store grocery vertical, confirmed via WebSearch to exist) has no reachable web listing — app-only per confirmed WebSearch summary. Rule 14 (named supermarket behind a delivery app counts as `supermarket`) does not apply here since there is no web-reachable per-merchant listing to scrape. |
| Vidrí | https://www.vidri.com.sv/ | home-improvement | **NOT BUILT this pass** | Workbook candidate (`sources_pending_will.xlsx`, tier C). Would add a 5th/6th source but is non-food; not needed once Super Selectos landed. Left for a future pass if a bonus non-food source is wanted. |

## Bonus non-food fallbacks (not built this pass — food bar was cleared)

Brief lists these as cheap bonus builds once food is landed: **DIGESTYC / BCR CPI**
(`cpi_benchmark`), **SIGET** electricity tariff (`tariff`, COICOP `04.5.1`), **MINEC**
biweekly regulated fuel reference price. None were probed this pass — the country
reached its target (5 sources / 2 food) with Super Selectos alone, and probe budget
was spent instead on the Don Juan/Despensa Familiar duplication check (rule 19) and
the Super Selectos category-filter defect investigation. A future pass targeting
non-retail COICOP depth (04.5, 07.2.2) could start here.

## Outcome after this pass

El Salvador ends at **5 sources / 2 food** (`walmart_sv` + `superselectos_sv`,
both `channel: supermarket`), clearing both bars. `siman_sv` (dept-store),
`farmaciasannicolas_sv` (pharmacy), and `wfp_prices` (official_avg, no channel)
remain non-food per the country's definition of done. Despensa de Don Juan and
Despensa Familiar/Maxi Despensa were both confirmed Walmart-Centroamerica-adjacent
and deliberately NOT onboarded (rule 19) despite being live, scrapeable VTEX
storefronts — onboarding either would have double-counted a large fraction of
`walmart_sv`'s catalog under a different brand name.
