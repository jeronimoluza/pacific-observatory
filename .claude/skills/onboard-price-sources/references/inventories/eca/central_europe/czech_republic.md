# Czech Republic (eca/central_europe/czech_republic)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. Starting state at pickup: 1 food source
(`billa_cz`, supermarket) plus `albert_wolt_cz` (marketplace) and Eurostat
tariff/PPP sources (7 total).

## Sources built this pass

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `rohlik_cz` | supermarket | retailer_sku | Rohlik.cz -- Czechia's largest online-only grocery delivery service (Rohlik Group; distinct company/platform from billa_cz and albert_wolt_cz). Tier 1B: `/api/v1/categories/normal/{categoryId}/products?page=N&size=100` for id lists + `/api/v1/products/card?products=<id>...` for batch product detail (name, slug, prices.originalPrice/salePrice/currency=CZK), found via a Playwright network trace. PDP url `/c{categoryId}/{slug}` confirmed live. 17 top-level department category ids walked. NOTE: an earlier draft of this spider (also written to the same path this same day) assumed the category page's embedded `__NEXT_DATA__` React-Query cache grew cumulatively with a `?page=N` query param -- that assumption was re-verified FALSE (page=0 and page=1 embedded the identical id set) and the spider was rewritten to use the real API instead. See the YAML's own notes for the full corrected account, including a 2-product cold re-fetch. |

## Dead ends / deferred this pass

- **penny.cz** -- 200 OK, large homepage (486KB) with Nuxt `product-price-wrapper` CSS classes, but no real per-product JSON/data on the homepage -- only component style definitions. Not probed further to a category page in this pass (budget went to Rohlik once it verified).
- **kosik.cz** -- 200 OK but only 12.7KB, Vue chunk references only (`ProductGroup`, `ProductRow` JS bundle names) -- no server-rendered content at all in the raw fetch, would need a full Playwright render. Not pursued.
- **makro.cz** -- 200 OK, 317KB -- METRO/Makro Cash & Carry, B2B wholesale membership storefront, not probed (would be `channel: wholesale` at best, lower priority than a genuine retail grocer and Rohlik already cleared the pass's bar for this country).
- **kaufland.cz** -- HTTP 403 under `curl_cffi impersonate=chrome124` (also 403 under `chrome120`; `safari17_0` not tried). Real block candidate, not re-probed with Playwright this pass -- worth a future look per rule 9.
