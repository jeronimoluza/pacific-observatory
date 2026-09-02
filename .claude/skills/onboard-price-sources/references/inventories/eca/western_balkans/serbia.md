# Serbia (eca/western_balkans/serbia)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. Starting state: 1 food source (`lidl_rs`,
hypermarket) plus `ananas_rs`/`maxi_wolt_rs` (marketplaces),
`tehnomanija_rs` (electronics) and Eurostat sources (9 total).

## Sources built this pass

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `dis_rs` | supermarket | retailer_sku | DIS -- distinct company from lidl_rs/maxi_wolt_rs. Next.js App Router SPA that returns an identical app-shell for every `/artikli/<code>` route; a Playwright network trace found the real open backend: `GET /api/Dis/Articles?page=<N>&pageSize=20` (server-clamps pageSize to 20, page is 1-indexed, naturally terminates at page 341 with empty data -- confirmed, not guessed) and `GET /api/Dis/Categories` (33 top-level departments, food-led). Price field is `discountedPrice` (carries the real current price on every sampled row; `price` is 0 on most rows). Full run: 6,799 rows, RSD. Cold re-fetch (2 products) confirmed live. |

## Dead ends / candidates examined, none built

- **idea.rs** -- HTTP 200, 141KB, but the entire site is corporate/store-
  locator content (`/Prodavnice/Prodavnice-Beograd`, `/Aktuelno` news,
  `/O-Idei` about-us) -- no product catalog, no per-SKU pricing anywhere.
  IDEA (major Serbian grocery chain) does not appear to run its own
  transactional e-commerce site.
- **univerexport.rs** -- HTTP 200, 46KB, Next.js corporate site (only a
  phone-contact footer component found); no shop/catalog links in the raw
  fetch.
- **roda.rs** -- HTTP 200, 243KB. Only price-like text found was
  installment-payment terms copy ("Minimalni iznos rate: 1.000 RSD"), not
  a real product price. `href`s under `/akcije/...-cat-NNN` are weekly
  PDF-style flyer/catalog pages, not a browsable SKU catalog.
- **tempo.rs** -- HTTP 200, 362KB, no shop/catalog-shaped links found in a
  first pass; not probed deeper.
- No Wolt/Glovo grocery-vertical listing beyond the two already onboarded
  (`ananas_rs`, `maxi_wolt_rs`) was checked for a THIRD first-party seller
  this pass -- the seller-directory angle (rule: marketplace is a
  directory, scrape the sellers not the marketplace) was not explored for
  Serbia and is a reasonable next step.
