# Cuba

_Inventory written: 2026-09-01_

Wave 7 pass. Cold start — no `lac/` inventory existed before this file. Already-covered
before this pass: `katapulk_cu` (marketplace), `mallhabana_cu` (marketplace),
`mercocaribe_habana_cu` (supermarket), `supermarket23_cu` (supermarket) — 4 sources / 2
food. Verified directly against `outputs/sources_pending_jero.xlsx`: Cuba has zero
workbook candidate rows; the only Cuba row anywhere in the workbook is the
"NO CANDIDATES - discovery" sheet's summary line (`sources_needed_to_reach_5: 1`),
confirming the brief's "no workbook candidates" claim. This pass needed 1 more source
of any channel; target was >=5 sources AND >=2 food.

All four pre-existing sources and both new ones are diaspora remittance/delivery
platforms: pay abroad (USD, occasionally EUR), deliver in Cuba. This is the dominant —
effectively only — form of Cuban e-commerce reachable from outside the island; genuine
CUP-denominated domestic online retail was searched for and not found (see TRD Caribe /
Tiendas Caribe row below).

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| TuAmbia | https://tuambia.com/ | marketplace | **SHIPPED** as `tuambia_cu` | Next.js storefront, server-rendered; each PDP embeds a schema.org `application/ld+json` Product block (name/sku/price/priceCurrency) — no Playwright needed. Catalog enumerable via `sitemap.xml` -> per-category sub-sitemaps under three regional URL prefixes (`hab`/`centro`/`occidente`); `hab` and `occidente` carry an identical product-slug set on a spot check, `centro` is a subset — only `hab` (Havana) was crawled to avoid `DuplicationPipeline` (keys on `item['url']`) 2-3x-counting the same SKU under region-prefixed URLs. Full unbounded run 2026-09-01: 1,113 rows, 1,113 distinct `product_id`, 1,113 distinct `url` (no dupes), 0 zero/negative price, 0 blank name, 100% USD, price range $0.33-$837.38 (median $5.39), 30 categories. Food share ~72% by category (groceries/beverages/prepared-food "jamazon" vertical dominate; real non-food breadth in ferreteria/textiles/personal-care/small-appliances keeps it `marketplace` rather than `supermarket`). 3/3 cold re-fetch spot checks matched exactly. |
| Alawao | https://alawao.com/ | marketplace | **SHIPPED** as `alawao_cu` | Standard WooCommerce storefront; the versioned Store API (`/wp-json/wc/store/v1/products`) is open with no anti-bot gate at all — plain `requests` + browser UA, no curl_cffi impersonation needed. `X-WP-Total: 2267`, pagination confirmed disjoint. Full unbounded run 2026-09-01: 2,267 rows, 2,267 distinct `product_id`/`url`, 3 zero-price rows (a free "postal de felicitación" gift-card insert + a $0 toy line, real catalog otherwise priced), 0 blank name, 100% USD, price range $0-$2589.95 (median $18.95), 154 distinct category tokens. Food share ~36% by category-token whitelist (groceries/beverages/prepared "Cantina" meals alongside real pharmacy/OTC, cleaning, perfumery, electronics, and giftcard breadth) — `marketplace`, not `supermarket` or `pharmacy`. 3/3 cold re-fetch spot checks (via sku lookup) matched exactly after minor-unit scaling. |
| Cubamax | https://www.cubamax.com/ | — | **DEAD (for now) — dynamic HMAC-signed API** | Next.js app; UI requires selecting a province+municipality (delivery-zone gate) before showing a large catalog (4,095+1,972+1,656+1,217+2,116+... rows visible across categories for a single Havana municipality — likely 10k+ products). The actual listing endpoint `api.cubamax.xyz/store/products?...` 422s with `"Unauthorized access"` on both bare curl and `curl_cffi impersonate=chrome124` — Playwright network capture shows the real browser attaches client-JS-computed `x-hmac-signature`/`x-hmac-nonce`/`x-hmac-timestamp` headers per request. Same failure class as `marketplace.com.mm`'s `x-security-key` — logged in `known_blockers.md` § "API requires dynamic security key / JWT". Worth revisiting only if the HMAC scheme is cracked; not pursued further this pass since the "any channel" bar was already cleared by TuAmbia/Alawao. |
| TRD Caribe / Tiendas Caribe (state-run retail) | trdcaribe.cu, tiendascaribe.cu, trd.cu (guessed) | — | **NOT REACHABLE — no working domain found** | All `.cu` guesses either NXDOMAIN or connection-timeout from this egress. Cuba's state retail chains do not appear to run a public, externally-reachable online catalogue — consistent with the island's internet-infrastructure constraints. This is the lead most likely to yield genuine CUP-denominated domestic prices (as opposed to diaspora USD pricing); worth a named follow-up only if an in-country vantage point or a different DNS path becomes available. |
| YuppyMarket | https://yuppymarket.com/ | — | **DEAD — stopped accepting Cuba orders 2026-08-08** | Same diaspora-delivery shape as the shipped sources, but per the site's own notice found via search, YuppyMarket stopped accepting new Cuba orders as of 2026-08-08 (still live for pre-existing order support only). Not probed further — a platform that has publicly wound down new-order intake for the target country is not a live source regardless of catalog reachability. |
| Bazar Regalo | https://www.bazarregalo.com/ | — | **DEAD — ad-redirect spam domain** | Not a retailer. Serves a `brandsmat.com` ad-tech fingerprinting/redirect script (`cheq`/`fp` tracking payload) that bounces every visitor to a tracked query-string URL. No product content at any layer. |
| D'Prisa | https://www.dprisa.com/ | — | **DEAD — domain parked for sale** | Generic "This domain may be for sale" parking page (Caddy server, `noindex`), not a retailer. |
| Carilatam | https://carilatam.com/ | — | **DEAD — domain parked** | JS-redirects to `/lander`, which loads a GoDaddy/`wsimg.com` parking-lander bundle (`window.LANDER_SYSTEM="PW"`, `ap:"parking"` signal). Not a retailer. |
| Tostoneshop | tostoneshop.com / tostoneshop.net (guessed) | — | **NOT REACHABLE — no working domain found** | Both apex guesses NXDOMAIN. Not spending WebSearch budget hunting the correct domain given the "any channel" bar was already cleared. |
| La Tienda de Alonso | latiendadealonso.com / .net, alonsocuba.com (guessed) | — | **NOT REACHABLE — no working domain found** | All guesses NXDOMAIN. Same as Tostoneshop — not pursued further this pass. |
| CompreMarket | https://www.compremarket.com/ | — | **NOT REACHABLE — NXDOMAIN** | Found via search ("mejor eCommerce para envíos a Cuba"); `www.compremarket.com` does not resolve. |
| SupermarketCuba | https://www.supermarketcuba.com/ | — | **DEAD — expired SSL certificate** | Found via search; TLS handshake fails with an expired certificate. Per the skill's rule 13 (expired cert + no legitimate fallback), record dead and move on rather than force a scrape over an insecure/degraded connection. |

## COICOP / channel gap after this pass

Cuba ends at **6 sources / 2 food** (`mercocaribe_habana_cu` supermarket +
`supermarket23_cu` supermarket), clearing both the 5-source and 2-food bars. Both new
sources this pass are `marketplace` and do not add food-channel coverage, though both
carry substantial real grocery/beverage assortment (TuAmbia ~72% food by category,
Alawao ~36%) alongside genuine non-food breadth (hardware, textiles, personal care,
electronics, pharmacy/OTC) — accurately reflecting how these platforms are actually
organized, not narrowed to qualify as `supermarket`.

Every source found for Cuba (6/6, existing and new) prices in USD (one existing source,
`mercocaribe_habana_cu`, prices in EUR) for delivery-to-Cuba diaspora buyers — none is a
domestic CUP retail price. A genuinely CUP-denominated domestic source would be the
highest-value future find; the state-retail lead (TRD Caribe / Tiendas Caribe) came back
unreachable this pass and is the most promising place to resume that search, ideally with
an in-country vantage point since Cuban government domains are frequently unreachable
from standard external egress.
