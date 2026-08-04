# Platform fingerprints

Most storefronts are off-the-shelf software. Identify the platform and the endpoint is already known — no selector work, no Playwright at runtime. This is the second-best discovery method on the ladder and by far the cheapest to scaffold.

## Fingerprint first

Before probing selectors, check what the site is running:

```bash
curl -sI "$URL" | grep -iE "x-powered-by|server|x-shopify|x-magento|set-cookie"
curl -s "$URL" | grep -oiE "shopify|woocommerce|wp-content|magento|vendure|ecwid|bizweb|sapo|opencart|cs-cart|nuxt|next" | sort -u
```

Then try the platform's catalog endpoint directly.

## Known endpoints

| Platform | Endpoint | Notes |
|---|---|---|
| **Shopify** | `/products.json?limit=250&page=N` | Open on most stores. Paginate until empty. If a custom domain is WAF'd, try the `*.myshopify.com` origin — it is often open (verified on gounders_samoa). |
| **WooCommerce** | `/wp-json/wc/store/v1/products?per_page=100&page=N` | Store API needs no auth. **Prices are integer minor units** — divide by `10**currency_minor_unit` from the same payload. |
| **Sapo / Bizweb** (VN) | `/products.json` | Shopify-derived; same shape and pagination. |
| **Magento 2** | `/graphql` (`products(search:…)`) | SSR product cards also usually parse. Verified via GraphQL on mm_mega_market, sm_markets_savemore. |
| **Vendure** | `/shop-api` (GraphQL) | Needs a per-store `vendure-token` header. **Prices in thousandths** — divide by 1000 (verified New World Fiji). |
| **Ecwid** | REST API, else SSR HTML | REST is often auth-gated; fall back to the rendered category HTML. |
| **OpenCart / CS-Cart** | SSR product cards | No API; plain HTML extraction. |
| **Algolia** | `/1/indexes/*/queries` | Search-as-a-service behind many storefronts. App ID + search-only API key sit in the page JS (verified chemist_warehouse). |
| **Typesense** | `/multi_search` | Same shape as Algolia; search-only key in page JS (verified makro_pro). |
| **Elasticsearch** (Cody.mn) | store search endpoint | Guest basic-auth in page JS; ~59k SKUs on shoppy_mn. |
| **Blazor** | REST backing the component | Verified farro_fresh. |
| **Next.js** | `__NEXT_DATA__` in page HTML | When the JSON API is WAF'd or robots-blocked, the hydration payload is embedded in the HTML and readable. See the id-walk pattern below. |
| **Freshop** | app-key-scoped API | **Check which stores the key actually covers** — the `cost_u_less` key returns Caribbean stores, not Guam. A key that resolves is not proof of the right geography. |

## Playwright to discover, plain HTTP to scrape

The single highest-yield probing pattern. Render the SPA **once** to read the network trace, find the internal JSON endpoint, then build a fast `scrapy_api` spider that hits it directly. Playwright does not run at collection time.

Many fronts that look WAF-blocked have a completely open JSON backend. Confirmed on chemist_warehouse, makro_pro, mm_mega_market, sm_markets_savemore, lazada.ph, shoppy_mn, farro_fresh, basic_homemart. **Always network-trace before declaring a site blocked.**

## Numeric-id-walk

When both the JSON backend is WAF-blocked *and* `robots.txt` disallows `/*.json`, but individual product pages are robots-allowed: walk numeric product ids over the HTML pages and parse the embedded hydration payload.

Verified on Talaad Thai — `/en/products/<id>` with `__NEXT_DATA__` → `props.pageProps.product`. Ids are sparse and clustered (~1–2500 and 4500–5500 live, dead in between); the full walk of 1–5600 took ~10.5 minutes and yielded 1,523 priced products. Note that url_key-only slugs soft-404 — the full slug form (`cassava-9805-2613`) is required for direct hits, but the numeric route works alone.

This beats category and search routes on client-hydrated sites, where those routes render empty.

## Anti-bot cross-checks

- **UA ↔ TLS consistency.** Cloudflare cross-checks them: a Chrome TLS fingerprint with a Scrapy UA gets 403; the same fingerprint with a Chrome UA gets 200 (verified gmarket).
- **TLD is not the tenant.** `lazada.ph` is open while `lazada.vn` is blocked — same platform, different WAF config. Probe each TLD.
- **Burst throttling ≠ blocking.** smmarkets.ph serves GraphQL fine at `concurrency=1` with a browser UA and IP-throttles bursts. Slow down before concluding a block.
- **Route-gated storefronts.** Some Laravel sites 302 every `/shop`, `/category/*`, `/product-detail/*` back to home even under headless Chromium (bnf_mart MM). Only a homepage carousel is reachable — treat as blocked.
- Do not reach for `scrapy-impersonate` reflexively; it is not the general fix for a WAF-blocked source.

## Do not re-probe

`known_blockers.md` holds the confirmed-blocked list (residential-IP / captcha / HMAC territory). Check it before probing anything, and append to it after every run.
