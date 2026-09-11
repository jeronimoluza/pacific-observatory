# Sri Lanka

_Inventory written: 2026-09-01_ (updated 2026-09-11: onboard4 shard)

Scope note: **food-and-beverage-focused seed** from the SAR agent-B depth pass (F&B retail only, division 01/02). No new source verified this pass despite extensive probing — recorded here so the next run does not repeat the same ~15 candidate checks. WebSearch budget was exhausted mid-pass (session-wide cap); everything below came from WebFetch on already-known URLs plus direct `curl_cffi` domain probing.

Already onboarded before this pass: colombosuper_lk, glomark_lk, onlinekade_lk, spar2u_lk (all supermarket), carkeells_lk (pharmacy, small grocery tail), singer_lk (electronics), dcs_weekly_retail (official_avg, Dept of Census & Statistics weekly wholesale/retail commodity prices — already fills much of the "fresh produce" gap at the official-average layer, though not as a retailer_sku fresh-market source).

**No new source shipped this pass.** Sri Lanka's easily-reachable F&B web storefronts of a genuinely different retailer type (fresh-market, convenience, specialty-food, marketplace) were not found within the timebox; every lead resolved to either (a) an existing type already covered (another national supermarket chain), (b) the wrong COICOP division, (c) a diaspora/export storefront priced in USD, or (d) app-only.

| Candidate | URL | Why not shipped |
|---|---|---|
| Cool Planet | https://coolplanet.lk/ | Shopify, reachable, paginates cleanly — but confirmed 100% apparel/fashion (T-shirts, blouses, jewellery) across a 5-page/865-item sample. Not F&B at all despite the "convenience store" brand association from the physical fuel-station chain. |
| Dilmah (shop.dilmahtea.com) | https://shop.dilmahtea.com/ | Real enumerable Shopify catalog, but `Shopify.currency active=USD` — international tea-lover export store, not local LKR retail. Recorded in `known_blockers.md`. |
| Grocerylanka | https://grocerylanka.com/ | Despite the name, a diaspora export shop (USD-priced) selling Sri Lankan cultural/kitchenware/religious items, not groceries. Recorded in `known_blockers.md`. |
| Kapruka | https://www.kapruka.com/ | Large diaspora gift/e-commerce platform (custom platform, not Shopify/Woo despite a stray `cdn.shopify` string). No grocery nav link found on the homepage; not deep-probed further given time budget — worth a real pass if a "Kapruka Fresh"-style grocery vertical is confirmed to exist and be reachable. |
| PickMe | https://pickme.lk/ | Super-app with a "Food & Market" nav item, but website is informational only — no browsable catalog; app-only. |
| Cargills Online | https://cargillsonline.com/ | **SHIPPED 2026-09-11 as `cargills_lk`** (scrapy_api), closing out the 2026-09-01 deferral above and overturning the `known_blockers.md` "Angular SPA … never hydrate" verdict. There is a wide-open ASP.NET MVC JSON API behind the AngularJS front-end. **The trap:** a cold `POST /Web/GetMenuCategoryItemsPagingV3/` returns one synthetic row `{"ItemName":"No Products Found"}` — a 200 with plausible JSON, not an error — so it reads as dead unless you run the bootstrap `GET /` → `POST /Web/CheckDeliveryOptionV1` (form `PinCode=Colombo`) → `POST /Web/GetCategoriesV1`. 3,967 SKUs across 23 categories; test run 1,021 rows, all priced. |
| HARTI daily food bulletin | http://www.harti.gov.lk/daily-price.php | **Not built — recorded as the best unclaimed Sri Lankan source.** The page is an index of ~3,000 daily bulletins back to 2015 (12 year-tables, `Date`/`Medium`/`Download`), each a downloadable retail+wholesale food-commodity price document. A genuine `official_avg` fetcher with ~10 years of history, complementary to the already-onboarded `dcs_weekly_retail`. Not attempted this pass because it is a `pdf`/`tabular_download` fetcher with a per-document parse, i.e. its own effort, not a shard task. |
| Celeste | https://www.celeste.lk/ | **Dead — brochure site, not a shop.** Its entire `sitemap.xml` is five pages: `/`, `/about.html`, `/services.html`, `/solutions.html`, `/contact.html`. Served from Vercel; `/products.json` 404s. See `known_blockers.md`. |
| Keells Super | https://keellssuper.com/ | Reachable but tiny (10KB) — landing/redirect page only, not the full storefront. Not investigated further (same "another supermarket" deprioritization as Cargills). |
| Arpico | https://www.arpico.com/ | Corporate holding-company site; supermarket division only linked out to Facebook, no first-party e-commerce on this domain. |
| Elephant House | https://elephanthouse.lk/ | Brand/corporate site (Ceylon Cold Stores ice cream & beverages) — no cart, no per-product price, sold through third-party supermarkets only. |
| spar.lk | https://www.spar.lk/ | 301-redirects to `spar2u.lk` — same operator, already onboarded. Not a new source. |
| wasi.lk | https://www.wasi.lk/ | HTTP 403 on curl_cffi chrome124. Not re-probed with other impersonation profiles this pass — worth a re-check. |

## Currency / locality note

Two separate candidates this pass were reachable, real, and enumerable, but priced in USD for an overseas/diaspora audience rather than the domestic LKR market (Dilmah's global shop, Grocerylanka's cultural-goods export shop). Flagging this as a pattern for Sri Lanka specifically: a ".lk"-branded or "Sri Lankan"-named storefront is not automatically local-market pricing — always confirm `Shopify.currency` / `priceCurrency` before assuming LKR.

## Next steps for a future pass

- Kapruka deserves a real (Playwright network-capture) probe for a grocery/fresh vertical before being written off.
- Cargills Online (Angular SPA) and Keells Super are both large enough to be worth a real probe once retailer-type breadth is no longer the binding constraint.
- wasi.lk 403 should be re-tried with `chrome120`/`safari17_0` before being recorded as blocked.
