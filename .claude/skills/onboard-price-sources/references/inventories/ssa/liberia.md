# Liberia

_Inventory written: 2026-09-02_ (search-starved re-run; supersedes the
2026-09-01 zero-budget pass, which recorded itself as "essentially
unexamined")

Before this pass: `fews_net` + `wfp_prices` only, 0 retail sources.
**Result: 2 shipped.** One English-language search surfaced four live
candidates the domain-guessing pass had no way to find.

## Shipped

| Source name | URL | Channel / role | Status | Notes |
|---|---|---|---|---|
| `libdelivery_lr` | https://libdelivery.com/ | marketplace / `retailer_sku` | **SHIPPED** | Monrovia delivery marketplace: groceries, local products and restaurant plates under `/item/`. WooCommerce with **no exposed Store API**, so the spider walks `sitemap_index.xml` → 14 child maps → ~3,300 `/item/` URLs and parses PDP JSON-LD. Test run scraped 7 items in USD (Bagels $5.00, a $12.50 restaurant side). Catalog mixes COICOP 01 and 11.1; the classifier assigns per product. |
| `banjoo_lr` | https://banjoosuperstore.com/ | supermarket / `retailer_sku` | **SHIPPED** | Banjoo SuperStore, 19th Street Sinkor Monrovia; delivers across Montserrado with pickup in 12 further towns. WooCommerce, Store API not exposed; `product-sitemap.xml` holds **615 product URLs**. Test run scraped 7 items in USD ($44.50 and $89.40 bundles). |

## Anti-bot note (important for the next run)

`libdelivery.com` **403s on the repo-pinned `chrome120` TLS profile** and
returns 200 on chrome124 / chrome123 / safari17_0. Pinning the profile took
all three of: disabling `scrapy_impersonate`'s `RandomBrowserMiddleware`
(it overwrites `meta["impersonate"]` on every request), setting a matching
chrome124 `USER_AGENT` (curl_cffi forwards Scrapy's headers verbatim, so a
chrome124 handshake under a chrome120 UA draws the 403 by itself), and
setting `IMPERSONATE_PROFILE`. Setting only one or two of the three still
403s. Also request `sitemap_index.xml` directly — `/sitemap.xml` 301s there
and the redirect hop was where the block first showed up.
_Inventory written: 2026-09-01_

SSA sweep, agent A. Country had `fews_net` + `wfp_prices` (shared regional
humanitarian fetchers) before this pass — 0 retail sources. **Result: 0
sources shipped.** **This pass ran with zero WebSearch budget** (session-wide
cap exhausted before this country's turn) — every candidate below came from
direct domain probing only, no real search sweep ran at all for this
country. Treat this inventory as essentially unexamined.

## Dead ends

| Candidate | URL | Status | Notes |
|---|---|---|---|
| Harbel Supermarket | harbelsupermarket.com | **BROCHURE** | Carried forward from 2026-09-01: live WordPress, no Store API, no `/shop/`, zero currency mentions across 144KB of `/product-range/`. |
| Liberia Food Delivery | https://liberiafooddelivery.com/ | **reCAPTCHA / Cloudflare wall** | Serves "Checking your browser before accessing. Just a moment…" (HTTP 403). Not re-probed past that; a genuine challenge, not a curl-TLS artefact. |
| Xpress It Liberia | https://www.xpressliberia.com/ | **NO CATALOG SURFACE** | 300KB page with price markup present, but `/sitemap.xml` 404s and no platform endpoint matched. Would need a Playwright trace. |
| Uber Eats "Liberia" | ubereats.com | **FALSE POSITIVE** | The Uber Eats hit is Liberia, **Guanacaste, Costa Rica** — not the country. Worth remembering: this name collides. |
| Jumia | jumia.com.lr / jumia.lr | **NXDOMAIN** | Carried forward. |

## Next steps

- `xpressliberia.com` Playwright network trace for a third source.

## Common Crawl coverage

Probed 2026-09-02 by the common_crawl session: 8 crawls spanning 2019-2026,
`max_blocks=40`. Counts are host records in the CC index and, separately, the
subset matching the manifest's `archive_path_re`.

| Source | Crawls with host | Host records | Matching PDP regex | Verdict |
|---|---|---|---|---|
| `banjoo_lr` (WooCommerce, sitemap walk) | 8/8 | 936 | 202 | Series 2019-2026. Best of the batch. |
| `libdelivery_lr` (WooCommerce, sitemap walk) | 4/8 | 346 | 115 | Usable series. |


`archive_prefix` on both sources was shortened to the bare registrable host on
2026-09-02. It is a plain **string** prefix applied to cdx lines *before*
`archive_path_re` is consulted, so a path in the prefix hard-caps what any regex
can see, and a wrong one fails silently — no manifest, no miss record, no error.
Filtering is `archive_path_re`'s job. Over-inclusion is free (`surt_prefix`
rstrips the trailing slash regardless), and a bare host survives the URL-scheme
migrations that break path prefixes.
| Jumia | jumia.com.lr, jumia.lr | **NOT FOUND — NXDOMAIN (both)** | |
| Glovo | glovoapp.com/lr/ | **DEAD — 404, no LR route** | |
| Harbel Supermarket Corporation | harbelsupermarket.com | **DEAD — brochure site, 0 products/prices** | Live WordPress site (200, 85KB), mentions "product"/"price"/"cart" in page copy but has no WooCommerce Store API (`/wp-json/wc/store/v1/products` -> 404), no `/shop/` page (404), and its `/product-range/` page — the closest thing to a catalogue — has zero currency mentions (0x "LRD"/"USD") and zero "add to cart" occurrences across 144KB of markup. Confirmed brochure-only, same pattern as Martínez Hermanos' own site in Equatorial Guinea. |
| Exclusive Supermarket (Monrovia) | exclusivesupermarketliberia.com | **NOT FOUND — NXDOMAIN** | |

**Conclusion:** No candidates confirmed either way beyond the one dead
brochure site. This inventory is essentially unexamined — the next pass
should start Liberia from scratch with a proper English-language search
(Liberia is anglophone, so this is a comparatively low-cost re-run) before
concluding anything about the country's online grocery sector.
