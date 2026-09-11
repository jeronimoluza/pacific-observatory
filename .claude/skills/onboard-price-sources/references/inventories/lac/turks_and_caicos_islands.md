# Turks and Caicos Islands — food/beverage source inventory

_Inventory written: 2026-09-11_

Currency USD, language en. Coverage density: near-zero — "take whatever verifies" regime, not
gap-ranked. 3 sources onboarded as of this pass (all `channel: supermarket`, all tourist/guest
grocery-delivery storefronts — no source reaches the resident/local-shopper channel yet).

| Source | Status | Notes |
|---|---|---|
| goods2door_tc | **Onboarded** (spider, Wix) | Grocery-delivery-for-guests site. Sitemap-driven whole-catalog walk, ~1,511 PDPs, schema.org JSON-LD prices. ~4,438 rows in corpus (pre-existing). |
| islandselects_tc | **Onboarded** (spider, WooCommerce Store API, `islandselectstci.com`) | 1,400 products (`X-WP-Total`), paginates cleanly. Verified 100/100 rows, 100 distinct PDP URLs, real USD SKUs (IGA-branded + national brands). |
| tcgrocerydelivery_tc | **Onboarded** (spider, WooCommerce Store API, `turksandcaicosgrocerydelivery.com`) | 946 products, paginates cleanly. Verified 100/100 rows, 100 distinct PDP URLs. Sibling domain `turksandcaicosgrocerydeliveryservice.com` serves an identical catalog — deliberately not onboarded as a second source (same shelf). |
| gracewaysupermarkets.com (Graceway Supermarkets / Graceway IGA) | Dead end — brochure only | Dominant TCI chain, multiple locations. Squarespace site; sitemap has no `/shop`/`/cart`/`/order-online` path. FAQ confirms no delivery/online ordering; only a manual PDF-list + in-store-payment service from one location. `/iga`, `/smart`, `/graceway-gourmet` are static brand pages, not storefronts. Re-check in 6-12mo for an e-commerce launch — this is the one gap that matters (resident-shopper channel, not just tourist delivery). |
| CaribeEats (backend.caribeeats.com) | Dead end — platform doesn't reach TCI | `/api/init` lists 21 regions; TCI is not one of them. Nearest coverage: Bahamas, BVI, Barbados, Trinidad, Jamaica, Guyana. Already onboarded elsewhere in LAC (Grenada, Dominica, St Kitts, Antigua) via `_caribeeats_base.py`. |
| shopiga.com / myigastore.com / iga.com store-locator | Dead end | No LocalExpress-style IGA online-ordering platform found for the Graceway IGA franchise (unlike Grenada/Barbados/PR IGA-adjacent sibling entries in known_blockers.md). shopiga.com is an unrelated SaaS; myigastore.com doesn't resolve; iga.com locator 404s on TCI. |
| stockmyvilla.com | Not TCI | Real Wix grocery catalog (`/shop?Category=GROCERY`) but it's "Time Saver VI" — St Thomas, US Virgin Islands, wrong island. |
| turksandcaicosconcierge.com | Dead end | Domain-for-sale parking page. |
| tcprovisions.com | Dead end | Parked domain, redirects to generic lander. |
| provoconcierge.com | Dead end | Cloudflare-proxied, origin 526 (dead/invalid SSL). |
| ~25 further guessed grocery-delivery/concierge/provisioning domains (provogrocerydelivery.com, tcigroceries.com, tcigrocer.com, provofresh.com, provomarket.com, tcimarket.com, islandprovisionstci.com, villaprovisionstc.com, graceybayconcierge.com, etc.) | No online supermarket found | All NXDOMAIN. |
| Al's Fresh Market | No qualifying public source found | No resolvable domain under any of the guessed patterns (alsfreshmarket.com, alsfreshmarkettci.com). |
| Smart Shop | No qualifying public source found | No resolvable domain (smartshoptci.com, smartshop.tc). Note: "/smart" on gracewaysupermarkets.com is an unrelated Graceway sub-brand page, not this business. |
| Turks and Caicos Tourism Board business directory (Shopping category, 31 listings) | No qualifying public source found | Local grocery/convenience listings (Kathleen's 7-11, Middle Caicos Co-op, Jai's, Greensleeves) carry phone numbers only, zero website URLs. Confirms ~46k-population territory's local grocers have no web presence. |

## Cross-country aggregators checked

- CaribeEats — does not cover TCI (see above). Covers: Nevis, St Kitts, Grenada, Anguilla,
  Dominica (incl. Portsmouth), St Eustatius, Montserrat, St Lucia, Antigua, Trinidad, Jamaica,
  Guyana, Barbados, BVI, The Bahamas, plus USA/UK/Nigeria regions — no Caribbean expansion into
  TCI as of 2026-09-11.

## Verdict

Genuine sourcing gap, now partly filled: the tourist/guest grocery-delivery niche has three
independent WooCommerce/Wix storefronts (goods2door_tc, islandselects_tc, tcgrocerydelivery_tc),
all verified. The resident-shopper channel is still a structural gap — Graceway (the real chain
locals use) remains brochure-only with no online catalog, and no local grocer has a website at
all. Re-check Graceway in 6-12 months.
