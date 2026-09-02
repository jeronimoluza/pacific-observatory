# Hungary (eca/central_europe/hungary)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. Starting state: 1 food source (`coop_hu`,
supermarket) plus `benu_hu` (pharmacy), `emag_hu`/`spar_wolt_hu`
(marketplaces), `praktiker_hu` and Eurostat sources (10 total).

## Sources built this pass

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `kifli_hu` | supermarket | retailer_sku | Kifli -- Rohlik Group's Hungarian online grocery brand (same group/platform as rohlik_cz in Czech Republic; distinct company from coop_hu/spar_wolt_hu/emag_hu/praktiker_hu). Runs the IDENTICAL Next.js + JSON API as rohlik_cz: `/api/v1/categories/normal/{id}/products?page=N&size=100` + `/api/v1/products/card?products=<id>...`, PDP `/c{categoryId}/{slug}`, confirmed live. 17 top-level category ids, deduped by product_id within the crawl (same cross-listing behaviour as rohlik_cz -- verified some product_ids exist ONLY under thematic categories like plant-based, so those are NOT excluded). Currency HUF. |

## Dead ends / candidates examined, none built

- **cba.hu** -- WordPress + WooCommerce (`ast-loop-product__link`,
  `woocommerce-loop-product__title` -- Astra theme), and the WooCommerce
  Store API is wide open and unauthenticated
  (`/wp-json/wc/store/v1/products`). BUT the total catalog is only 17
  products site-wide (`X-WP-Total: 17` header), of which only 5 carry a
  nonzero structured price (`prices.price`, `currency_minor_unit=0` so no
  scaling needed) -- the rest are informational-only. This is a small
  "current weekly offers" teaser page, not a genuine full-basket grocery
  catalog; real per-unit prices for the other 12 items exist only as free
  text inside the product `description` field (e.g. "819 Ft/10 dkg; 8190
  Ft/kg"), which would need bespoke text-regex extraction for a catalog
  this thin. Judged not worth a slot -- documented here so the next pass
  doesn't re-discover the same open API and assume it's a real catalog.
- **auchan.hu** -- HTTP 200, 578KB, genuine `/shop` and `/shop/list/...`
  paths exist, but the specific `/shop/list/<slug>` URLs found in the raw
  homepage nav are curated promotional list pages (e.g.
  "jobban-megeri-ajanlat", "napinditok-reggelire"), not a plain category
  browse; the only Ft price text found on the homepage itself was coupon/
  delivery-fee marketing copy, not product data. A `/shop` category-tree
  entry point exists and is worth a further pass with a proper category-id
  walk (not attempted this pass).
- **penny.hu** -- same Nuxt CSS-class-only signature as penny.cz (see
  Czech Republic inventory); not probed to a category page this pass.
- **metro.hu** -- METRO Cash & Carry, B2B wholesale membership storefront;
  not probed (lower priority than a genuine retail grocer, and none of the
  above cleared the pass's bar for this country in the time available).
- **tesco.hu** (`bevasarlas.tesco.hu`) -- only 2.7KB response, likely a
  redirect/JS-shell stub; not investigated further.
