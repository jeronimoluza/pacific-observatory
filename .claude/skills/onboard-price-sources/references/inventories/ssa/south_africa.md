# South Africa

_Inventory written: 2026-09-01_

Wave 10 pass. Already-covered before this pass: `superbhyper_za` (hypermarket),
`biltongboytjies_za` and `whiskybrother_za` (specialty-food), `canineandco_za`
(pet) — 4 sources / 3 food. Bar was >=5 sources AND >=2 food (1 more source of
any channel needed; food already satisfied). No workbook candidates for this
country — DISCOVER.

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| DMRE fuel price (via AA) | https://www.aa.co.za/fuel-pricing | tariff (non-retail) | **SHIPPED** as `za_dmre_fuel` | DMRE's own sites (dmre.gov.za, energy.gov.za) are both unreachable for automated collection (TCP timeout / expired-cert 503, confirmed with curl_cffi + DNS re-checked against 8.8.8.8 and 1.1.1.1). The Automobile Association of South Africa republishes the identical gazetted schedule via an open WordPress AJAX endpoint (`POST aa.co.za/wp-admin/admin-ajax.php`, `action=getFuelPricesStart`) returning the full 2008-present monthly history in one call. 2220 rows verified live 2026-09-01 (222 distinct months x 10 series: petrol 93/95 unleaded + LRP, diesel 500/50ppm, each Coastal+Inland), all COICOP 07.2.2, 0 dup hashes, 0 zero/negative prices, 100% ZAR, median R13.12/L, range R5.68-31.38. Source itself carried a small number of literal duplicate/near-duplicate raw records for the same date (2 dates out of 224) — deduped by keeping the highest internal `id` per date. |
| Stats SA CPI (P0141) | https://www.statssa.gov.za/publications/P0141/P0141\<Month\>\<Year\>.pdf | cpi_benchmark (non-retail) | **SHIPPED (bonus)** as `statssa_cpi` | Predictable monthly PDF URL, stable back to at least January 2017. `pdfplumber.extract_tables()` on "Table E" recovers top-level COICOP groups cleanly via table indentation structure. Two basket eras handled: pre-2025 (12 groups, "Dec 2021=100" and earlier) maps 11/12 cleanly to divisions 01-11 ("Miscellaneous goods and services" dropped — ambiguous, spans what the 2025 rebase split into divisions 12+13); post-2025 (Jan 2025 report onward, "Dec 2024=100") is a clean 13-group 1:1 match to divisions 01-13. 1291 rows verified live 2026-09-01 (115 distinct months, Jan 2017-Jul 2026), 0 dup hashes, index values 98.2-134.9. One month (April 2018) lost entirely to a pdfplumber word-splitting quirk on that specific PDF's table layout — logged, not silent. |
| Faithful to Nature | https://www.faithful-to-nature.co.za/ | specialty-food (organic) | **BUILT, NOT SHIPPED — 0 rows** | Legacy Magento 1 storefront; curl_cffi impersonate=chrome124 clears at 200 standalone, every PDP carries a clean JSON blob (`liftigniter-metadata`) with sku/name/price/category. But the identical request routed through Scrapy's `prices collect` (CrawlSpider + curl_cffi impersonation, RandomBrowserMiddleware/CustomUserAgentMiddleware disabled, matching the repo's own `carrefour_tw.py` convention) 403s on every impersonate profile tried (chrome124/safari17_0), while bare `curl_cffi`/`asyncio.run()` calls with the identical call shape clear every time. This is a repo-tooling integration issue (Scrapy 2.13's Twisted reactor hosting curl_cffi's async client), not a genuine site block — see `known_blockers.md` "Reachable, HTTP 200, but not extractable" section for the full diagnostic trail. Spider code was written and then removed (does not ship at 0 rows per the Phase 6 gate); worth revisiting once the Scrapy/curl_cffi integration issue is understood, or as a plain-Python fetcher instead of a Scrapy spider. |
| Checkers | https://www.checkers.co.za/ | — | **DEAD — AWS WAF CAPTCHA** | Next.js SSR itself reports `"serverError":true` and loads an `awswaf.com` CAPTCHA SDK script. Genuine challenge gate, not a TLS-fingerprint false positive (curl_cffi reaches the page fine at the HTTP layer). See `known_blockers.md` § AWS WAF. |
| Pick n Pay | https://www.pnp.co.za/ | — | **NOT PURSUED — pure client-side SPA** | Homepage HTML has zero server-rendered links beyond favicon/asset tags. No API endpoint found without a Playwright network trace (not run this pass — deprioritized after Checkers/Faithful to Nature above absorbed the anti-bot budget and the country's bar was already cleared). |
| Woolworths | https://www.woolworths.co.za/ | — | **NOT PURSUED — homepage prices are CMS nav copy, not a catalog** | 1.7MB React/SSR page has real "R89.95"-style strings, but they come from a Contentstack headless-CMS promo/nav blob (`"_content_type_uid":"menu"`), not per-SKU product data. Matches the skill's own "homepage carousel is not a catalog" warning. Real PLP/PDP + commerce API not located this pass. |
| Spar | https://www.spar.co.za/ | — | **NOT PURSUED — no prices found on homepage** | 1MB page, no product prices in raw HTML, no obvious CMS/e-commerce platform signature detected. Not deeply probed (SPAR SA is known to operate through independent franchise/delivery apps rather than one national storefront) — worth a named search for a SPAR delivery app in a future pass rather than re-probing this domain. |
| Food Lover's Market | https://www.foodloversmarket.co.za/ | — | **NOT PURSUED — no prices found on homepage** | WordPress site, no product prices in raw HTML, homepage reads as store-locator/marketing. Not deeply probed given budget; worth checking for a `/shop` or franchise delivery-app path in a future pass. |
| Takealot | https://www.takealot.com/ | marketplace | **NOT PURSUED** | Homepage is a small SPA shell (20KB); South Africa's largest marketplace, so per the discovery doctrine the seller directory (not the blended catalog) would be the target — not attempted this pass given the country's bar was already cleared via non-retail sources. |
| Faithful to Nature siblings not checked | — | — | — | Makro, Yuppiechef fetched (200 via curl_cffi, real content) but not probed further given budget — country bar was already cleared by the two non-retail sources before reaching them. |

## COICOP / channel gap after this pass

South Africa ends at **6 sources / 3 food** (existing `superbhyper_za`
hypermarket + `biltongboytjies_za` + `whiskybrother_za` specialty-food,
unchanged; `za_dmre_fuel` and `statssa_cpi` are both non-retail and don't move
the food count). `07.2.2` (fuel) and full 13-division CPI benchmark coverage
are new. The genuine remaining gap is retail depth: South Africa's big-four
grocers (Checkers/Shoprite, Pick n Pay, Woolworths, Spar) are either
CAPTCHA-gated (Checkers) or pure-SPA (Pick n Pay) or not yet proven to have a
reachable catalog at all (Woolworths' real commerce API, Spar, Food Lover's
Market). A future pass with more anti-bot/Playwright budget should: (1) find
Woolworths' real product API behind its Contentstack nav, (2) Playwright-trace
Pick n Pay's SPA for its backing API, (3) resolve the Scrapy/curl_cffi
integration issue that blocked `faithful_to_nature_za` (or rebuild it as a
plain-Python fetcher instead of a Scrapy spider), (4) search for SPAR's
delivery-app domain (spar2u or similar) instead of re-probing spar.co.za.
Eskom/NERSA electricity tariff and ICASA/telco plan pages (both flagged as
near-free non-retail wins in the brief) were not attempted this pass — the
bar was already cleared after the two fetchers above.
