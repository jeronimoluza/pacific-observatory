# Sudan

_Inventory written: 2026-09-01_

Wave 8 pass. This is a **food-only** task: Sudan already has 6 sources (`hypersale_sd`
supermarket, `dawana_sd` pharmacy, `rizqmarket_sd` marketplace, `mtn_prepaid_internet_sd`
+ `zain_prepaid_internet_sd` tariff, `wfp_prices`) but only 1 food source. Needed >=1 more
`supermarket`/`hypermarket`/`convenience`/`fresh-market`/`specialty-food` source. Wave 6
had already tried and come up short. This pass probed all 6 workbook candidates plus 4
fresh-discovery leads — **all 10 came back dead, too thin, or locality-disqualified.**
Sudan remains at 6 sources / 1 food after this pass. Full evidence for each is filed in
`known_blockers.md` under the matching heading (grep this domain list there).

| Source name | URL | Channel | Status | Notes |
|---|---|---|---|---|
| Hyper Express | https://hyper.sd/ (app backend at `hyper.sd/index.php/api/v1/...`, hypermarket module `web.hyper.sd`) | would be `hypermarket` | **DEAD — 98.7% seed/demo data** | Real live StackFood/6amMart-family API, real Sudan zones (Khartoum/Omdurman/Port Sudan/Kassala/Al Qadarif/Atbara) correctly separable from the contaminating Muscat/Oman zone the brief flagged (`zone_id=23`, `currency_id=22`). But of the one grocery module's 698 items, 689 (98.7%) carry a flat placeholder `price=1` SDG and item id=1 resolves to `"slug":"demo-product"` / `"footer_text":"تيست"` ("test") with a `created_at` that predates the store's own creation date. Only 8 SKUs have real-looking prices. See `known_blockers.md` § Placeholder / seed demo-data catalog. |
| LILY Delivery | https://www.lilydelivery.com/en (API `https://api.lilydelivery.com`) | would be `supermarket` | **DEAD — catalog too thin** | Real open Node/Mongo backend, no WAF (`/health` 200, `/api/services` lists vendors). Whole platform is only 14 vendors / ~34 items total; the sole grocery vendor ("بقالة النيل") carries exactly 7 SKUs at suspiciously round demo-like prices. Below the "handful of items, not a real price series" bar. See `known_blockers.md` § Placeholder / seed demo-data catalog. |
| Al Waha Supermarket | https://alwaha.sd/ | — | **DEAD — no e-commerce** | NOT WooCommerce (brief's guess was wrong) — static 11KB "Moderna" BootstrapMade corporate brochure template. `/wp-json/wc/store/products` and `/shop` both 404. See `known_blockers.md` § Brochure-only WordPress / no online store. |
| Zaad Delivery | https://zaad.delivery/ | — | **DEAD — marketing site, no catalogue** | Astro+Vue site behind an `hcdn` JS proof-of-work interstitial that curl_cffi (chrome124/120/safari17_0) never clears but headless Playwright does in ~8s. Fully rendered content is About/Contact/FAQ/Partners only — zero shop/menu/product links, zero price mentions. See `known_blockers.md` § App-only / no scrapeable web catalogue. |
| Storna | https://storna-shopping.vercel.app/ (canonical prod domain: `www.st-orna.com`) | — | **DEAD — backend unreachable** | Real business (custom domain, live Instagram/Twitter/YouTube), Next.js frontend renders fully with `/products`/`/categories` nav. But the API it calls, `https://storna-core.laravel.cloud/api/v1`, 404s with an empty body on every path including `/` itself — origin appears decommissioned or migrated. See `known_blockers.md` § API backend unreachable. |
| Talabaty | https://mytalabaty.com/ | — | **DEAD — unreachable** | curl_cffi chrome124 times out after 28s. Consistent with wave-6/brief note "app coming soon". |
| Murrsal ("Nine") | https://murrsal.com/ | — | **DEAD — discovery, fresh lead** | Found via WebSearch as a Sudan food-delivery platform. Broken/self-signed TLS forces `verify=False`; every path 404s regardless. Effectively dead. |
| Zad Fresh | https://zadfresh.com/ | — | **DEAD — discovery, fresh lead, parked** | Bare "Welcome to nginx!" default install page — nothing deployed. |
| Dukani | https://dukani.online/ (`dukani.sd` 403s) | — | **DEAD — discovery, fresh lead, not actually Sudanese** | Leftover white-label SaaS marketing/demo page for "Lezzoo" (a Kurdistan/Iraq delivery-app vendor), `cal.com/.../dukani-demo` booking link. No Sudan catalogue. Do not confuse with the Google-Play "Dukani" apps (`com.parmagh.dukani`, `com.hjtech.dukani`) — neither was probed further since no matching web domain surfaced. |
| Sudansoug / Al-Afnan Foods | https://www.sudansoug.com/ , https://alafnanfoods.com/ | — | **REJECTED-FOR-LOCALITY** | Diaspora e-commerce ("Sudanese products online" tagline; sudansoug.com mixes USD/AED pricing with SDG, no in-Sudan delivery-zone text found; Al-Afnan Foods lists a +971 UAE contact number). Same pattern as the deleted Antigua diaspora-grocer sources — do not build without independently re-confirming a genuine Sudan delivery zone. Not deep-probed beyond this locality check. |

## Depth-audit note

No commodity/COICOP-leaf depth audit was in scope this pass — this was a source-count
task (food channel count), not a leaf-coverage task.

## Wave 11 pass (2026-09-01) — re-confirmed, 3 more fresh-discovery leads, all dead

Wave 11 brief handed the same 6 workbook candidates above (all already dead per the wave-8
row set — re-confirmed against `known_blockers.md`, not re-probed). Since the candidate
list was exhausted, this pass did one more round of fresh-discovery search (2 WebSearch
calls, Arabic + English) specifically chasing the "what's left to try" leads below, plus
whatever else surfaced. Three new leads, all disqualified:

| Source name | URL | Status | Notes |
|---|---|---|---|
| Alburuj Market | alburujmarket.com (from Facebook page `facebook.com/alburuj.online`, Khartoum, phone +249 12 190 0021) | **DEAD — domain does not resolve** | `dig alburujmarket.com @1.1.1.1` returns NXDOMAIN. The Facebook page exists but the website it advertises has no DNS record at all. Closes out the "Alburuj Market" line item from the wave-8 what's-left-to-try list. |
| Sudan SuperMarket | sudansupermarket.com | **DEAD — empty catalog + diaspora signal** | WordPress/WooCommerce/Divi, 200 OK. `/wp-json/wc/store/v1/products` returns `[]`. `/shop/` renders "No products were found matching your selection." (confirmed via BeautifulSoup text extraction, not just a status code). Tagline is "لكل السودانيين حول العالم" ("for all Sudanese around the world") and the shop nav includes an "India" country-select artifact — reads as an inactive/never-launched diaspora storefront, not a Khartoum retailer. Would fail the locality rule even if it had products. |
| Green Trees Supermarket | greentreesupermarket.com | **REJECTED-FOR-LOCALITY** | Tagline "تسوق المنتجات المصرية والسودانية أونلاين" ("shop Egyptian and Sudanese products online") — explicitly an ethnic-foods diaspora grocer, same pattern as sudansoug.com / alafnanfoods.com. Not deep-probed beyond this locality check. |

**Conclusion unchanged: Sudan remains at 6 sources / 1 food.** Combined with the wave-8
pass this is now 13 candidates tried (6 workbook + 4 wave-8 discovery + 3 wave-11
discovery), all dead, too thin, or locality-disqualified. No new leads are known to be
outstanding.

Also noted, out of scope to fix here (existing source, not a candidate): `hypersale_sd`'s
most recent collect run (`hypersale_sd_20260827_013133.jsonl`) is a 0-row empty file,
where the prior run four runs back (`..._20260820_164609.jsonl`) had 324 rows. The spider
may have silently broken since 2026-08-20 — worth a look by whoever owns that source, since
it is currently Sudan's only food source.

## What's left to try (not exhausted, just not reached this pass)

- `Fresh-sudan`/`freshsudan` Facebook page — not probed; Facebook Shops/Marketplace pages
  are usually not catalog-API-backed and would need a dedicated feasibility check.
  ("Alburuj Market" closed out above — dead, not this one.)
- Re-check `zaad.delivery`, `dukani.sd`, `sudansupermarket.com`, and the two Google-Play
  "Dukani" apps in ~6 months — Sudan's e-commerce landscape is visibly early-stage/volatile
  (multiple May-2026-dated seed records seen in wave 8, an empty-but-live WooCommerce
  install seen in wave 11) and could mature.
- WFP/humanitarian price-monitoring feeds beyond `wfp_prices` were not explored (out of
  scope — food-and-beverage **retail** channel was the ask, not `official_avg`).
- `hypersale_sd`'s broken latest run (see above) — fixing it doesn't add a second food
  source, but it currently threatens the first one.
