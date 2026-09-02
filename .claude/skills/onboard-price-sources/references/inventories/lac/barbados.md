# Barbados

_Inventory written: 2026-09-01_

Wave 8 pass. Cold start — no `lac/` inventory existed for Barbados before this file.
Already covered before this pass: `aonesupermarkets` (supermarket), `massy_stores_bb`
(supermarket), `courts_bb` (dept-store) — 3 sources / 2 food. Target: >=5 sources AND
>=2 food. Entered at Phase 3 (probe) with a candidate list already supplied by the
wave-8 brief; no fresh discovery search was run except two frugal WebSearch calls to
chase down the brief's "if you need more" list once the primary candidates were
resolved.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| PriceSmart Barbados | https://www.pricesmart.com/en-BB/category/Groceries/G10D03 | hypermarket | **SHIPPED** as `pricesmart_bb` | Warehouse-club (Nuxt SPA, zero prices in raw HTML) — but its own network trace exposes a public, unauthenticated Bloomreach Discovery search endpoint (`POST /api/br_discovery/getProductsByKeyword`) that replays cold with plain curl_cffi, no cookies. Confirms and resolves an earlier wave-5 probe's USD/BBD uncertainty: currency is BBD. Full unbounded run of the Groceries node (key G10D03) 2026-09-01: 947 rows, 947 distinct `product_id`/`url`, 0 zero/negative price, 0 blank name, 100% BBD, price range 2.75-1016.18 (median 25.75), single category (100% food by construction — spider scoped to Groceries only). 3/3 cold re-fetch spot checks matched (name via rendered `<title>`, price via rendered body text — PDP is also SPA-shell). Warehouse-club pack sizes are large multi-unit packs, flagged in the YAML for downstream per-unit normalisation. |
| Chefette / BBQ Barn | https://chefette.com/ | other | **SHIPPED** as `chefette_bb` | Bajan fast-food chain (+BBQ Barn steakhouse brand), single-country (no country selector, +1-246 phone prefix). Vue SPA shell, but `/api/v2/food/<chefette\|barn>` is a plain unauthenticated JSON API (the sibling `/api/v2/cart` 403s — read and write endpoints have separate gates). Full run 2026-09-01: 158 distinct items after de-duplicating cross-category-listed menu items (raw API returns 201 rows because some items are cross-listed under both their home category and "Specials" — same price, same product, not a distinct SKU), 158/158 distinct `product_id`/`url`, 0 zero price, 0 blank name, 100% BBD, price range 1.50-109.95 (median 10.95). `channel: other` (dining, per GLOSSARY.md's hotpepper_jp precedent) — does not count as food-channel coverage but clears the source-count bar. 3/3 cold re-fetch spot checks matched. |
| Cave Shepherd | https://caveshepherd.com/ | — | **DEAD — retail business discontinued** | The historic Bridgetown department-store chain no longer operates from this domain. Now a WordPress/Avada corporate holding-company site: the group has pivoted to self-storage (Store All Inc.), souvenir shops (Ganzee, Caribbean Kidz, Spice It Up), a taxi app (pickUP Barbados), and financial-services subsidiaries. Zero e-commerce, zero prices, zero `/shop` path anywhere on the domain. Logged in `known_blockers.md` § "No products on the site". |
| iMart Pharmacy Barbados | https://imartstores.com/ | — | **PARKED — session/address-gated LocalExpress platform** | Corporate domain (`imartstores.com`) is a Joomla brochure, zero prices. Real catalog is on `online.imartstores.com` (LocalExpress platform). An anonymous JWT is obtainable client-side (`GET /rest-proxy/v2/whoami?anonymous=1`, no login wall) but the flow then gates all department/product listing behind an address/location-picker step before any product endpoint fires — no product links render without it. Same platform, same shape as the already-blocked `shop.realvalueiga.com` (Grenada). Logged in `known_blockers.md` § "API requires dynamic security key / JWT" (which despite the heading also covers this session/address-gate shape — see the LocalExpress entries there). Worth a dedicated Playwright address-selection pass if this platform is targeted again (would likely unlock both BB and GD at once). |
| PriceWhirl | http://www.pricewhirl.com/ | — | **DEAD — unreachable** | `curl_cffi impersonate=chrome124` times out after 30s on both http/https. No catalog exists to probe. |
| Automotive Art | http://www.automotiveart.com/Barbados/ | — | **DEAD — no online prices** | Confirmed Barbados-live (multi-Caribbean auto-parts/accessories chain, `geo.region: BB`), but `/Barbados/Featured-Products/` and homepage carry zero `$`/BBD price text anywhere — category-tile catalog only, in-store pricing. |
| Nassco | (brief guessed nassco.com.bb / nasscoltd.com — both NXDOMAIN) | — | **DEAD — wrong business + no online store** | Real domain is `nassco-barbados.com`. Confirmed via WebSearch to be a Toyota dealer/parts distributor (National Automotive Sales and Service Company), not a hardware store as the brief assumed. No online shopping regardless. |
| Popular Discount | (no domain found) | — | **NOT REACHABLE — no retailer website found** | WebSearch turns up only third-party directory/review listings (Tripadvisor, FindYello, business directories); no retailer-operated website of any kind. |
| Carlton / A1 Supermarkets / Emerald City | — | — | **NOT A NEW SOURCE — same chain as `aonesupermarkets`** | All three names in the brief's "if you need more" list are branches of the already-onboarded AOne Supermarkets chain (Carlton, Black Rock, and Emerald City/Six Roads locations), confirmed via WebSearch. Do not build separately. |

## COICOP / channel gap after this pass

Barbados ends at **5 sources / 3 food** (`aonesupermarkets` supermarket,
`massy_stores_bb` supermarket, `pricesmart_bb` hypermarket), clearing both the
5-source and 2-food bars with one food source to spare. `courts_bb` (dept-store) and
`chefette_bb` (other/dining) round out the non-food half.

Remaining gaps for a future pass: pharmacy (iMart is the only lead found and it is
session/address-gated — see above), real-estate/rentals (untried this pass),
telco/fuel tariff (untried — Barbados Light & Power / FCCC-style regulator feed would
be the next candidate generator), and a genuine second grocery competitor beyond the
three already covered (Popular Discount would have been the best candidate but has no
online presence).
