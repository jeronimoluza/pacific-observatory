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
