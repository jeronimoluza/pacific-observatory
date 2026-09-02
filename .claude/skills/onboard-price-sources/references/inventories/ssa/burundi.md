# Burundi

_Inventory written: 2026-09-01_

Final F&B sweep, wave (2026-09), agent B. Cold-start (no prior inventory file
existed). Already-covered before this pass: `wfp_prices` (official_avg,
shared SSA fetcher) — 1 source / 0 food, no retail coverage.

**Result: 1 source shipped (kilakitu_bi, marketplace, food-relevant categories only).**

| Candidate | URL | Channel / role | Status | Notes |
|---|---|---|---|
| Kilakitu | https://kilakitu.bi | `marketplace`, retailer_sku | **SHIPPED** as `kilakitu_bi` | General cross-division online store for Bujumbura on the Yo-Kart multi-vendor platform (confirmed via a broken `/sitemap.xml` that still points at the vendor's demo `v8.demo.yo-kart.com`, plus seller-subscription i18n strings in the page bundle). Tier 1A, curl_cffi impersonate=chrome124, no Playwright. Spider scoped to 14 food/beverage/alcohol category slugs only (out of ~200+ total categories spanning electronics/clothing/toys/cosmetics) — food-items, canned/jarred foods, candies & chocolates, cookies & biscuits, milk/tea/coffee, nutrition, quick bites, water/soft drinks/juices, beers, gin, red wine, vodka, whiskey, wines & spirits. Currency BIF confirmed from JSON-LD `priceCurrency`. **Two bugs found and fixed in the spider, both in the vendor's own markup, not ours**: (1) every product's JSON-LD embeds a raw unescaped newline inside the `description` field, which fails strict JSON parsing and silently zeroed the spider (fixed with `json.loads(..., strict=False)`); (2) `<script>` is a raw-text HTML element, so the page's own HTML entities (e.g. `&eacute;`) are never decoded by parsel's `::text` extraction the way normal markup is — every accented French product name arrived HTML-escaped (fixed with `html.unescape()`). JSON-LD `sku` field is a static `"1"` on every product (vendor template bug) — do not trust it; product_id is derived from the canonical PDP URL slug instead. Full unbounded run (post-fix): 284 rows, 284 distinct product_id/url, 0 blank names, 0 zero/negative prices (2 literal-"0.00" olive-oil rows dropped by a price>0 guard added to the spider), currency 100% BIF, range 6,000-550,000 (median 20,000). Cold re-fetch of 2 products matched the live site exactly. |
| BAZA Burundi | app store only | **NOT PROBED — app-only** | Delivery app (food, flowers, daily needs); no web catalog found. |
| Kobo360 / other pan-African aggregators | — | **NOT FOUND — do not operate in Burundi** | Standard SSA delivery marketplaces (Jumia, Glovo, Bolt Food, Yango) do not list Burundi. |

## COICOP / channel coverage after this pass

Burundi: 2 sources / 1 food (source-count basis) — `kilakitu_bi` (marketplace,
retailer_sku, COICOP 01/02 scope by category selection) + pre-existing
`wfp_prices` (official_avg). Everything outside food/beverage/alcohol
remains uncovered at the retail level for Burundi after this pass (housing,
utilities, health, transport, communication, recreation, education,
restaurants, misc — COICOP 03-13 ex-01/02). Kilakitu itself DOES carry
non-food departments (electronics, clothing, cosmetics, toys) that this
spider deliberately does not crawl — a follow-up pass targeting those
category slugs on the same site would be a cheap way to fill several of
those divisions with the platform template already built.
