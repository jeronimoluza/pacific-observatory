# Guam

_Inventory written: 2026-08-04_

| Source name                                 | URL                                                                                                                                                                                  | COICOP divisions covered                                 | Source type             | Cadence        | Auth required? | Machine-readable? | Anti-bot risk | Wayback coverage | Per-SKU IDs?     | Notes                                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------- | ----------------------- | -------------- | -------------- | ----------------- | ------------- | ---------------- | ---------------- | ---------------------------------------------------------------------------------------------- |
| Guam Bureau of Statistics and Plans CPI     | https://bsp.guam.gov/cpi/                                                                                                                                                            | 01–13 CPI groups                                         | Territorial CPI reports | Quarterly      | No             | PDF               | Low           | Yes              | No               | Archive of Guam Quarterly CPI reports. ([The Bureau of Statistics and Plans Guam][17])         |
| Pay-Less Supermarkets Guam                  | https://www.paylessmarkets.com/                                                                                                                                                      | —                                                          | No online store          | —              | —               | —                  | —             | —                 | —                 | **DEAD END (confirmed 2026-08-11):** despite being Guam's main supermarket chain, the site has no e-commerce catalog — Laravel/Vue corporate/community site only. `/departments/grocery` is a landing page + feedback form (zero product links, zero prices even rendered via Playwright network trace). `/promos` links recipe-cookbook PDFs, not price flyers. See `known_blockers.md` "No products on the site". |
| Guam Power Authority / GTA / Docomo Pacific | https://guampowerauthority.com/ ; https://www.gta.net/ ; https://www.docomopacific.com/                                                                                              | 04 electricity, 08 telecom                               | Utility/telco tariffs   | Monthly/annual | No             | HTML/PDF          | Low           | Yes              | Plan IDs partial | Guam uses US-linked pricing for some digital services; flag as territory/metropolitan overlap. |
| Pacific Unlimited Guam                      | https://shop.pacificunlimitedguam.com/                                                                                                                                               | 01 food-service (bulk pastries, cakes, gelato, BBQ/meat)  | Wholesale/HORECA distributor | Daily      | No             | Shopify JSON       | Low           | —                 | Yes               | **ONBOARDED 2026-08-11** as spider `pacificunlimitedguam`. `/products.json` open, 132+ SKUs. |
| CMC Wholesaler Guam                         | https://cmcwholesalerguam.com/shop/                                                                                                                                                  | 01 food-service wholesale (bakery/grocery/packaging)      | Wholesale distributor   | Daily          | No             | WooCommerce Store API | Low       | —                 | Yes               | **ONBOARDED 2026-08-11** as spider `cmcwholesalerguam`. Store API lives at the older `/wp-json/wc/store/products` namespace (not `/v1/`), 132 SKUs (X-WP-Total). |
| Trademaster Guam                            | https://www.trademasterguam.com/                                                                                                                                                     | 01/11 prepared Filipino meals                             | Specialty food retailer | Daily          | No             | Wix + JSON-LD       | Low           | —                 | Yes               | **ONBOARDED 2026-08-11** as spider `trademasterguam`. No public catalog API; each PDP server-renders schema.org Product JSON-LD. ~29 SKUs, JSON-LD seller name "New Fresh Bread". |
| Cokonut Express                             | https://www.cokonutexpress.com/                                                                                                                                                      | 01 specialty Asian/Pacific grocery                        | Specialty food retailer | Daily          | No             | Squarespace JSON     | Low         | —                 | Yes               | **ONBOARDED 2026-08-11** as spider `cokonutexpress`. `/products?format=json` returns full ~57-item catalog. Also ships to CNMI (onboarded under Guam only; do not duplicate). |
| Guam Shopping Network                       | https://www.guamshoppingnetwork.com/food                                                                                                                                             | 01 food (small, cross-category storefront otherwise)      | Dept-store / GrooveKart | Daily          | No             | Server-rendered HTML | Low         | —                 | Yes               | **ONBOARDED 2026-08-11** as spider `guamshoppingnetwork`, scoped to /food. THIN: only 6 SKUs in this category ("Showing 1-6 of 6 items"), no pagination. |
| Farm to Table Guam (CSA)                    | https://farmtotableguam.org/csa-app/                                                                                                                                                 | 01.1.7 vegetables (CSA farm-box share pricing)             | CSA farm-share fetcher  | Irregular      | No             | Static HTML (`<select>`) | Low     | —                 | No (8 fixed tiers) | **ONBOARDED 2026-08-11** as fetcher `farmtotableguam` (`gu_farmtotableguam_csa`). WooCommerce plugin present but Store API returns 0 rows — the 8 CSA share-price tiers are hard-coded in a sign-up form `<select>`, not real WC products. |
| DeCA Guam Commissary Click2Go               | https://shop.commissaries.com/shop/                                                                                                                                                  | —                                                          | US military commissary  | —              | —               | —                  | —             | —                 | —                 | **UNRESOLVED (2026-08-11) — environment issue, not a site block:** `shop.commissaries.com` returned DNS `SERVFAIL` from this sandbox (system resolver AND Cloudflare 1.1.1.1 DoH both failed; general internet connectivity otherwise fine). WebSearch confirms the site is live (`shop.commissaries.com/shop`, `/my-account` indexed). Retry from an unrestricted network before concluding blocked. If reached: it is a subsidized/at-cost US military commissary — tag with a distinct channel so it is never blended with Guam civilian retail in PPP analysis. |
| MNF Market                                  | https://mnfmarket.com/                                                                                                                                                               | —                                                          | Shopify store (suspended) | —            | —               | —                  | —             | —                 | —                 | **DEAD END (confirmed 2026-08-11):** Shopify storefront returns `HTTP 402 Payment Required` on every path (billing-suspended, not a WAF — see `known_blockers.md` "Shopify store suspended"). Business (Korean fresh food/wholesale, Tamuning) appears active on Instagram/Facebook via pre-order pickup, but has no live web storefront to scrape. |

## Wave (2026-09-01) -- DeCA Commissary resolved and onboarded

The 2026-08-11 "UNRESOLVED -- environment issue" entry above for
`shop.commissaries.com` is now resolved: `shop.commissaries.com` and
`api.prd.freshop.retail.ncrgov.com` both resolve and respond normally from
this session (`34.160.32.70`, HTTP 200) -- the prior DNS SERVFAIL was
transient/environment-specific, not a real block. The storefront runs on a
Freshop-family catalog API (same family as `_freshop_base`, but at a
DIFFERENT host: `api.prd.freshop.retail.ncrgov.com`, app_key=`deca`,
discovered by reading the storefront's own embedded script tag, which
explicitly sets `allow_bots=true`). No auth, no WAF.

**ONBOARDED 2026-09-01** as spider `deca_commissary_gu`
(`src/prices/configs/eap/pacific_islands/guam/deca_commissary_gu.yaml`).
DeCA runs 238 commissary stores worldwide (`/2/stores?app_key=deca`); Guam
has exactly two, store_id 5944 (Andersen AFB, 8,418 items) and 5947
(Orote/Naval Base, 8,387 items) -- spot-checked 2,000 items from each and
found 1,239 overlapping SKUs with ZERO price differences, confirming these
are the same operator's near-duplicate catalog. Only the larger (5944) is
onboarded, per the do-not-duplicate-the-same-shelf rule.

Full unbounded run: **8,418 rows**, 8,418 distinct `product_id` (upc-keyed),
8,418 distinct `url`, 0 blank names, 0 zero/negative prices, 100% USD,
price range $0.32-$102.61 (median $3.82). Food share (by top-level
`/shop/<dept>/` URL segment): pantry/frozen/beverage/bread_snacks/dairy/
meat_seafood/produce/deli_bakery/sushi/meat/bakery = 6,534 of 8,418 = 77.6%
(conservative -- excludes `baby`, which is part food/part non-food).
Cold re-fetch verified live 2026-09-01 against 2 sampled rows via the API's
`q=` search param: "Degree Men UltraClear Black and White MotionSense 48H
... Stick 2.7 oz tube" ($4.26) and "DELI SALAD TUB - MACARONI" ($14.99) --
both name and price matched the stored rows exactly.

**Channel caveat (deliberate, not an oversight):** tagged `channel: wholesale`,
not `supermarket`/`hypermarket`, because DeCA commissaries sell at
subsidized/at-cost prices to authorized US military-affiliated patrons only
-- not an open civilian market. This follows the existing `costuless_ky` /
`malaeimi_wholesale_as` precedent of substituting `wholesale` when the
schema's retail-channel enum has no dedicated non-market value, and is what
the 2026-08-11 note above already anticipated ("tag with a distinct channel
so it is never blended with Guam civilian retail in PPP analysis"). Because
of this, per the sweep brief's own channel-enum rule, **this source does NOT
count toward Guam's "food channel" source tally** even though its catalog is
substantively food-and-beverage. It is still real, useful COICOP 01/02
coverage and a legitimate new source -- just not a "win" under the brief's
strict channel-enum scoring.
