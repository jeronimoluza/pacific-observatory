# Pakistan — price source inventory (menaap/pakistan)

_Inventory written: 2026-09-01_

Cold-start inventory. Final F&B sweep, MENAAP agent B. Pakistan started
this pass at 3 food sources (`ekissaan_pk` specialty-food, `kkmart_pk`
convenience, `metro_pk` hypermarket) out of 15 total (the rest are
dept-store, pharmacy, marketplace, and electronics sources — Pakistan is
NOT food-saturated despite the large total-source count). No WebSearch
budget available this pass (session-wide cap already exhausted by other
parallel agents) — discovery used direct domain guesses off known
Pakistani supermarket/retail chain names.

## Onboarded this pass

| Source | Channel | Platform | Notes |
|---|---|---|---|
| `naheed_pk` | supermarket | Magento 2, GraphQL open with no auth | Naheed Supermarket — a large general-merchandise online retailer. **Redirect-eats-POST-body trap**: bare `naheed.pk` 302-redirects to `www.naheed.pk` and the POST body does not survive that redirect (reproduced identically via `curl_cffi` and would reproduce via Scrapy) — every POST to the bare domain returned `{"errors":[{"message":"Syntax Error: Unexpected <EOF>"}]}` (empty body reaching the GraphQL parser); pinning `GRAPHQL_URL`/`BASE_URL` to the `www` host fixed it. **Deliberately scoped, not whole-catalog**: root categoryList spans ~20 top-level categories (Groceries & Pets 5,304; Fresh St! Cafe 89; Pharmacy 2,439; Health & Beauty 13,748; Phones & Computers; Fashion; Books; Home & Lifestyle...) — Health & Beauty and Fashion alone dwarf groceries, so walking the whole tree would read as a general department store, not a supermarket, and Pakistan already has 3 dept-store sources + 2 pharmacy sources. Spider scoped to ONLY `Groceries & Pets` (id=46) + `Fresh St! Cafe` (id=1079, prepared/cafe food). Verified live: 5,363 rows, 5,363/5,363 distinct product_id and url, 0 blanks, 0 zero/neg prices, PKR 10-22,725, ~95% food-and-beverage share (eyeballed 19/20 on a random sample). Cold re-fetch: 3/3 products matched exactly. |

## Candidates probed and rejected

| Candidate | URL | Verdict | Notes |
|---|---|---|---|
| Imtiaz | imtiaz.com.pk | DEAD — corporate WordPress, no shop | "Pakistan's No. 1 Retail Chain" branding, but `wp-json/` namespace list has no `wc/` route (WooCommerce inactive despite theme CSS mentioning it) and homepage nav is exclusively about-us/blog/career/loyalty links — no shop/product/order path anywhere. |
| Jalal Sons | jalalsons.com.pk | Genuinely live, NOT built — API param requirement not identified | "Fresh Groceries, Pan Asian, Bakery, Fast Food & Super Mart Essentials" — a Sixam-Mart/6amMart-family Next.js grocery-delivery platform (same family as `melat_shop_af`/`superstan_af`), `restId=55116`/`rest_brId=57503` embedded in page config, and the app calls its own `/api/menu-section?restId=...` at load per a Playwright network trace — but replaying that exact URL (cold curl AND via the live browser's own cookies) 400s with `{"msg":"Please provide restaurant id!"}` despite `restId` being present. Real requirement (extra param/header/session token, or a specific call-order dependency on `/api/geofence`→`/api/branch`) not identified within budget. See `known_blockers.md`. |
| Chase Up | chaseup.com.pk | Not pursued — thin response | Only a 145-byte response (likely a redirect stub); not investigated further given naheed_pk and jalalsons.com.pk were higher-signal leads found in the same batch. |
| Green Valley | greenvalley.pk | Not pursued — wrong content | Title tag reads bare "Person" — a generic/misconfigured template page, not a retail storefront. Not investigated further. |
| Carrefour Pakistan | carrefour.pk | DEAD — 403, likely not a real Carrefour operation | Carrefour does not operate in Pakistan; this domain 403s and was not investigated further (plausible squat/parked domain rather than a real storefront). |

## Dead ends worth remembering

- **A bare domain vs. `www.` redirect can silently eat a POST body** — this is a distinct trap from the usual TLS/WAF issues: the redirect itself succeeds (302, then 200 on the target), but the request body does not survive the hop through curl_cffi's (and by extension Scrapy's) redirect handling, so the downstream GraphQL/REST endpoint sees an empty body and returns a generic parse error that looks like a malformed-query bug rather than a redirect issue. Always test the exact `www`/no-`www` host that the API config specifies, not just "the domain."
- **A Sixam-Mart/6amMart-family platform's REST API can still gate a specific endpoint behind an undocumented parameter or call-order dependency even when the "obvious" required param is supplied** — `restId` being present didn't satisfy `jalalsons.com.pk`'s `/api/menu-section` endpoint. Worth trying the full documented call sequence (geofence → payment-gateways → branch → menu-section, in that exact order, same cookie jar) before writing off a platform of this family as inconclusive.
- **A country with a large total source count (15 for Pakistan) can still have a thin food-and-beverage layer (3/15)** — most of Pakistan's existing sources are dept-store/pharmacy/marketplace/electronics, not food. Worklist ranking by raw `#food now` (not `#food / #total`) correctly surfaced this as a priority despite the high total.
