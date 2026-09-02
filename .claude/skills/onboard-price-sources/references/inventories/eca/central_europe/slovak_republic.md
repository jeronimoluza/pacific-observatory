# Slovak Republic (eca/central_europe/slovak_republic)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. Starting state: 1 food source (`billa_sk`,
supermarket) plus `tesco_wolt_sk` (marketplace) and Eurostat sources (7
total).

## Sources built this pass

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `metro_sk` | wholesale | retailer_sku | METRO Slovakia cash-and-carry. Does NOT count toward the sweep's food-source tally (`wholesale` is not in the allowed retail-channel list) but shipped anyway -- real, unblocked, food-and-beverage-led (13,889 SKUs per the site's own search API). SPA storefront (`sortiment.metro.sk`) with a fully anonymous two-endpoint JSON API found via Playwright trace: `GET /searchdiscover/articlesearch/search?...&filter=category:potraviny` for id+price, `GET /evaluate.article.v1/betty-variants?ids=...` (batched) for name+category. storeId=00021 (Bratislava-area default, no location cookie). Slovak Republic's counted food-source tally is still just `billa_sk` after this pass. |

## Dead ends / candidates examined, none built

- **kaufland.sk** -- HTTP 403 under `curl_cffi` on all three profiles
  tried (chrome124, chrome120, safari17_0). Real block, not a bare-curl
  TLS artifact (matches the sibling kaufland.cz 403 in Czech Republic --
  likely a shared Kaufland-group WAF policy across country TLDs). Not
  escalated to Playwright this pass.
- **terno.sk** -- connection timed out (curl exit 28) on all three
  impersonation profiles; domain may be dead/parked or geo-restricted at
  the network layer, not a WAF challenge.
- **cba.sk** -- HTTP 200 but the entire response body is a 179-byte
  `window.location.href="index.php"` redirect stub; following it wasn't
  attempted this pass (low-value, looked like a stale/parked page).
- **potravinydomov.sk** -- resolves to `itesco.sk` (Tesco's Slovak
  grocery-delivery brand, "Potraviny domov" = "groceries at home"),
  confirmed via an embedded link to `potravinydomov.itesco.sk`. **Same
  operator as the already-onboarded `tesco_wolt_sk`** (rule 10) -- not
  pursued as a second Tesco source without first sampling both product
  sets to confirm they're genuinely disjoint catalogs, which this pass
  didn't have budget for.
- **coop.sk** -- HTTP 200, real product cards found (`product-card__title`,
  a genuine price e.g. "15,33 €/kg") but they come from a dated weekly
  leaflet widget (`/letaky/potraviny-supermarket-a-tempo-1`, ~30 items) on
  the homepage, not a persistent per-SKU catalog -- the leaflet's own page
  is a 6.6KB image-flip viewer with zero product cards. Too thin (~30
  items sitewide) to confirm as a genuine full-catalog retailer this pass;
  worth a second look if COOP publishes a proper catalog page elsewhere.
- **lidl.sk** -- HTTP 200, 713KB, but the only price hits found were inside
  a marketing-banner image `alt` attribute (a weekly-deals graphic), not a
  product listing. Not pursued further.
- **fresh.sk** -- HTTP 200 but 2-byte body (empty/parked).
- **hyper.sk** -- connection timeout.
- **jednota.sk** (COOP Jednota corporate site) -- loaded (200, 35KB) but
  not probed past that; likely a corporate/store-locator site given the
  size, similar to jednota's sibling coop.sk leaflet pattern. Deferred, not
  confirmed dead.
- **rohlik.sk** -- parked/for-sale domain (Rohlik Group does not operate a
  Slovak storefront under this name; Kifli is the group's HU brand,
  Knuspr/DE, Gurkerl/AT -- no SK brand exists).
- **yeme.sk** -- brand/marketing site with no visible catalog.
