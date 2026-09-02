# Guyana

_Inventory written: 2026-09-01_

LAC wave-13 sweep, agent B. Cold start — no `lac/guyana.md` inventory existed
before this file. Already covered before this pass: `gtplaza` (supermarket),
`guystar_gy` (supermarket), `courts_gy` (dept-store), `moa_market_prices`,
`statisticsguyana_cpi` — 2 food / 5 total.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Francis De Gossiper | https://francisdegossiper.com/ | marketplace | **SHIPPED** as `francisdegossiper_gy` | WooCommerce multi-vendor marketplace, 425 products total across many vendor stores, confirmed live via `wp-json/wc/store/v1/products`. **Important correction made mid-pass**: categories with grocery-sounding names — "beef-and-mutton", "chicken", "pork", "seafood", "vegetable" — were sampled and found to be ENTIRELY Chinese-restaurant prepared dishes ("Kung Pao Chicken", "Crispy ToFu", "Stir Fried Mutton With Cumin" — COICOP 11, not retail). The first test run included them (158 rows) before this was caught; the shipped spider excludes all five and keeps only 9 category IDs confirmed as genuine packaged-grocery/beverage retail (Carnation evaporated milk, 2L Coca-Cola/Pepsi/7up/Sprite, cereal, cookies, cooking oil, seasoning) — 75 rows. Full unbounded run 2026-09-01: 75 rows, 75 distinct `product_id`/`url`, 0 blanks, 0 zero/negative prices, 100% GYD, price range $1.00–$50.00 (median $5.00). Prices are in MINOR UNITS (`currency_minor_unit: 2` on every product) — divided by 100 in the spider. `channel: marketplace` (third-party vendor listings, not one retailer's own catalog); the marketplace also hosts a "Courts Guyana Store" vendor page (same operator as pre-existing `courts_gy`) but that vendor's electronics/furniture products do not appear under any of the 9 selected grocery categories, so no double-count. 2/2 cold re-fetch spot checks (product 764 Carnation evaporated milk, product 1415 2L Coca-Cola) matched name and price exactly via `wp-json/wc/store/v1/products/<id>`. |
| Massy Stores Guyana | https://shopmassystoresgy.com/ | supermarket | **BLOCKED — Cloudflare Turnstile, confirmed via mandatory gate** | Real national chain (6+ branches), e-commerce launched Feb 2024 per press coverage — highest-credibility remaining lead by chain size. `curl_cffi` `chrome124`/`chrome120`/`safari17_0` ALL 403; headless Playwright ALSO 403 with `<title>Just a moment...</title>` and `challenges.cloudflare.com` in the response CSP — genuine block per the mandatory gate (both curl_cffi AND Playwright failed). Recorded in `known_blockers.md`. Worth a dedicated anti-bot pass (residential proxy/solver) if Guyana coverage is revisited. |
| gorchum.com ("Guyana's #1 online supermarket") | https://gorchum.com/ | — | **INCONCLUSIVE — HTTP 503, Retry-After 3600** | OpenCart-style URLs (`index.php?route=product/category`) seen in search index, suggesting a real catalog exists. Both probed paths returned 503 with a 1-hour retry-after — could be a transient outage or overload, not a hard block. Worth a re-check in a future pass at a different time of day. |
| newnigels.com | — | — | **DEAD — NXDOMAIN** | Domain does not resolve. |
| Survival Supermarket | — | — | **DEAD END — Facebook-only presence** | No dedicated e-commerce site found. |
| guyana.cyber-florist.com/foodstore/grocery | — | — | **INCONCLUSIVE — 403 Forbidden** | Bot-blocked on a basic fetch; not re-probed with curl_cffi/Playwright this pass given the food bar was already cleared by Francis De Gossiper. |
| TruValu Supermarket | — | — | **FALSE LEAD — Trinidad & Tobago only** | No Guyana presence despite appearing in search results. |
| GTEats | — | — | **DEAD END — app-only** | Food/grocery delivery aggregator, App Store/Google Play only, no web catalog found. |

## Outcome after this pass

Guyana ends at **3 food / 6 total** sources (`gtplaza`, `guystar_gy`,
`francisdegossiper_gy` — the last two `channel: supermarket`/`marketplace`
respectively). Massy Stores is a real, credible chain blocked by Cloudflare
Turnstile (recorded in `known_blockers.md`) — the single best lead for a
future dedicated anti-bot pass. gorchum.com's 503 is worth a cheap re-check
later; everything else probed this pass is a genuine dead end.
