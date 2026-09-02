# Belarus (eca/eastern_europe/belarus)

_Inventory written: 2026-09-01_

Final F&B sweep, ECA agent B. Starting state at pickup: 1 source
(`foodstore_by`, supermarket). A concurrent wave (same day, prior to this
pass) separately added `green_dostavka_by` (supermarket) via the sitemap +
JSON-LD pattern -- see that YAML's own notes for detail. This entry covers
only the incremental work done in this pass.

## Sources built this pass

| Source | channel | analytical_role | Notes |
|---|---|---|---|
| `re_store_by` | specialty-food | retailer_sku | Re-store.by ("Ресторация", OOO "Vodny Mir"), Minsk delicatessen/specialty-food delivery. Distinct legal entity from foodstore_by and green_dostavka_by. 1C-Bitrix, curl_cffi impersonate=chrome124 clears clean, no anti-bot. 215 leaf `/catalog/<slug>/` categories; card-level `data-analytics='{"id":..,"name":..,"price":..}'` JSON blob parsed directly. Currency hardcoded BYN at spider level (the blob's own "currency" field reads a stale "RUB" stub on every sampled card -- confirmed wrong by price magnitude, e.g. a 150ml soy sauce at 24.30 "RUB" would be ~$0.25, implausible; at BYN ~$7.6, plausible for an imported specialty item). Pagination via `?PAGEN_1=N` confirmed real (disjoint product-id sets page1 vs page2). Full unbounded run + 2-product cold re-fetch: see Phase-8 chat report for final counts. |

## Dead ends / deferred this pass

- **e-dostavka.by** (Евроопт/Eurotorg -- Belarus's largest retail chain) --
  Next.js SSR, homepage clears `curl_cffi impersonate=chrome124` (200,
  `__NEXT_DATA__` present) but `/categories` and any `/category/<id>` path
  return a client-side JS proof-of-work "Verification" challenge
  (`hg-security` cookie, checks `navigator.webdriver`, computes a busy-loop
  hash, sets cookie, reloads). A stealth-patched Playwright pass
  (`navigator.webdriver` overridden) still resolved to a real "403 Access
  denied" page keyed to the requesting IP -- this is a genuine IP/session
  block on non-homepage paths, not a curl-TLS artifact (curl_cffi AND a
  stealth Playwright browser both landed on the block -> stop per rule).
  Real find, real product data structure documented (productId, productName,
  price.basePrice, BYN) -- worth a future pass with an in-country egress or
  a solved challenge-cookie replay.
- **gippo-market.by** (Гиппо/Hippo chain) -- 200 OK but only 17.8KB, no
  category nav or price signal in the raw fetch; likely a store-locator/
  corporate shell rather than a live storefront. Not pursued past that.
- **a-dostavka.by** -- 1C-Bitrix confirmed (UNP 192606557), homepage and
  `/catalog/` nav both live, but the one leaf category probed
  (`/catalog/bakaleya/chipsy_sukhariki_sneki_sushenaya_ryba/sukhariki/`)
  rendered zero product cards on a cold fetch -- possibly an empty/renamed
  leaf rather than a dead site. Deferred, not confirmed dead; worth a
  category-list re-derivation in a future pass rather than reusing this
  probe's specific URL.
- **p24.by** ("ПерекрестОК") -- 1C-Bitrix + Alpine.js hybrid theme;
  category-page HTML ships only the Alpine component template
  (`x-show="product.PRICE"`), no real per-product data server-rendered --
  needs a client-side API sniff (Alpine pulls from an endpoint at runtime)
  that this pass didn't have budget for.
