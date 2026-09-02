# Russian Federation

_Inventory written: 2026-09-01_

Cold-start inventory (no prior EAP-style seed existed). Written after wave 8, which
closed Russia's food-and-beverage gap (0 -> 2 food sources: vkusvill_ru, delikateska_ru).
See `references/known_blockers.md` (Qrator / DDoS-Guard / ServicePipe sections, plus the
"reachable but not extractable" and "unreachable" buckets) for the full probe trace behind
every DEAD/PARKED row below — this table is the summary, that file is the evidence.

| Source name | URL | COICOP divisions covered | Source type | Cadence | Auth required? | Machine-readable? | Anti-bot risk | Per-SKU IDs? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VkusVill (onboarded: vkusvill_ru) | https://www.vkusvill.ru/ | 01, 02, 03, 05, 06, 09, 12, 13 | Retail / e-commerce grocery | daily | no | HTML (Schema.org JSON-LD, listing-page `@graph`) | none (curl_cffi impersonate=chrome124 clean, no city cookie) | yes | 44 top-level departments, full grocery + household assortment; single national price, no per-store gating found |
| Delikateska.ru (onboarded: delikateska_ru) | https://delikateska.ru/ | 01, 02, 09, 13 | Retail / e-commerce specialty-food | daily | no | HTML (`.product-card-new` cards, no JSON-LD) | low (a few requests 403 at concurrency>1, clears at concurrency=1) | yes | Moscow deli/specialty grocer — caviar, farm meat/dairy, imported cheese, plus staple-grocery aisles; ~53 categories, no pagination found (each category's first-screen grid appears to be the full listing) |
| Apteka.ru (onboarded, pre-wave-8: apteka_ru) | https://apteka.ru/ | 06, 13 | Pharmacy | daily | no | HTML (Schema.org JSON-LD) | none | yes | National online pharmacy; sitemap-driven |
| Komus.ru (onboarded, pre-wave-8: komus_ru) | https://www.komus.ru/ | 03, 05, 08, 09 | Dept-store / office & household | daily | no | HTML (microdata) | none | yes | Office-supplies-turned-broad-consumer catalog |
| Yandex Market (onboarded, pre-wave-8: yandex_market) | https://market.yandex.ru/ | 01, 03, 05, 06, 08, 09, 13 | Marketplace | daily | no | HTML (embedded widget JSON) | none for search pages | yes | Keyword-walk, no plain JSON API found; does not count toward the food target (`channel: marketplace`) |
| Rosstat average prices (onboarded, pre-wave-8: rosstat_avg_prices) | https://rosstat.gov.ru/statistics/price | 01-13 | National statistics office — average retail prices | monthly | no | XLSX | none (vendored CA chain needed for TLS trust) | no | ~561 named goods/services, national + subnational rows; full-basket benchmark |
| O'Key (okmarket.ru) | https://www.okmarket.ru/ | 01, 02, 05, 09 (candidate only — not built) | Hypermarket | — | no | none found | none (no WAF) but no enumerable catalogue | n/a | Real PDPs exist (`/product/<slug>/`) but no working category nav, broken sitemap (14.9k of 15.2k URLs are duplicate homepage entries), and `/search/` returns "nothing found" even with a city cookie set. Structurally a corporate/store-locator site, not a browsable online store. Not built. |
| SPAR Russia (myspar.ru) | https://myspar.ru/ | 01, 02, 05, 09 (candidate only — not built) | Grocery delivery (Moscow/SPb/Nizhny Novgorod) | — | no | none found (client-rendered) | curl_cffi clean; Playwright triggers a captcha | n/a | Full real grocery taxonomy in the mega-menu, but zero product data server-side — catalog renders entirely client-side via Bitrix+IndexedDB, no XHR/API endpoint found in a network capture. Not built; would need either a genuine warmed browser session or reverse-engineering the Dexie sync payload. |
| Metro Cash & Carry (metro-cc.ru) | https://www.metro-cc.ru/ | wholesale (does not count as food per programme definition) | Wholesale / cash-and-carry | — | no | HTML shell + JSON-LD w/o price | none | yes (PDPs exist) | Reachable, JSON-LD present but missing `price` (lives only in a minified Nuxt blob); channel would be `wholesale` regardless, so deprioritized behind the food-and-beverage push this wave. Candidate for a 5th/6th source, not for the food count. |
| Perekrestok (perekrestok.ru) | https://www.perekrestok.ru/ | 01, 02, 05, 09, 13 (candidate — DEAD) | Supermarket | — | — | — | ServicePipe (rotated-image captcha) | — | Blocked; same tenant as kuper.ru |
| Kuper / SberMarket (kuper.ru) | https://kuper.ru/ | grocery-delivery aggregator (candidate — DEAD) | Marketplace/aggregator | — | — | — | ServicePipe | — | Same tenant as perekrestok.ru |
| Samokat (samokat.ru) | https://samokat.ru/ | quick-commerce grocery (candidate — DEAD) | Quick-commerce | — | — | — | ServicePipe | — | Blocked |
| O'Key delivery (okeydostavka.ru) | https://okeydostavka.ru/ | — (candidate — DEAD) | Grocery delivery | — | — | — | ServicePipe | — | Blocked |
| Azbuka Vkusa (azbukavkusa.ru) | https://azbukavkusa.ru/ | 01, 02, 05, 09 (candidate — DEAD) | Premium supermarket | — | — | — | ServicePipe | — | Blocked |
| Lenta (lenta.com) | https://lenta.com/ | 01, 02, 05, 09 (candidate — DEAD) | Hypermarket | — | — | — | Qrator | — | 401, `server: QRATOR` header |
| Monetka (monetka.ru) | https://monetka.ru/ | 01, 02, 05 (candidate — DEAD) | Discount grocery | — | — | — | Qrator | — | 401, same shell as auchan.ru |
| Auchan Russia (auchan.ru) | https://www.auchan.ru/ | 01, 02, 05, 09 (candidate — DEAD, pre-wave-8) | Hypermarket | — | — | — | Qrator | — | See known_blockers.md |
| Utkonos (utkonos.ru) | https://www.utkonos.ru/ | 01, 02 (candidate — DEAD, pre-wave-8) | Grocery delivery | — | — | — | Qrator | — | Same shell as auchan.ru |
| Magnit (magnit.ru) | https://www.magnit.ru/ | 01, 02, 05 (candidate — PARKED, pre-wave-8) | Grocery | — | — | — | none (routing bug, not WAF) | — | Sitemap lists real product URLs but every sampled PDP soft-404s; worth a re-check, not diagnosed further |
| Vprok (vprok.ru) | https://www.vprok.ru/ | grocery delivery (candidate — DEAD) | Grocery delivery | — | — | — | bespoke WAF error page ("Ошибка #625116") | — | Perekrestok's old standalone delivery brand |
| Dixy (dixy.ru) | https://dixy.ru/ | 01, 02, 05 (candidate — DEAD) | Discount grocery | — | — | — | 403 (vendor unconfirmed) | — | Not Playwright-confirmed |
| Pyaterochka delivery (5ka.ru) | https://5ka.ru/ | grocery delivery (candidate — DEAD) | Grocery delivery | — | — | — | 403 (vendor unconfirmed) | — | — |
| Pyaterochka (pyaterochka.ru) | https://www.pyaterochka.ru/ | 01, 02, 05 (candidate — DEAD) | Discount grocery | — | — | — | connect timeout | — | Same X5 Group as perekrestok.ru/kuper.ru |
| Globus (globus.ru) | https://globus.ru/ | 01, 02, 05, 09 (candidate — DEAD) | Hypermarket | — | — | — | connect timeout | — | — |
| Myasnov (myasnov.ru) | https://myasnov.ru/ | 01 meat (candidate — DEAD) | Specialty meat chain | — | — | — | connect timeout | — | — |
| Karusel (karusel.ru) | https://www.karusel.ru/ | — (candidate — DEAD) | Former hypermarket brand | — | — | — | DNS does not resolve | — | Brand absorbed into Lenta |
| Verniy (verno-info.ru) | https://verno-info.ru/ | — (candidate — REJECTED, not e-commerce) | Discount grocery (physical only) | — | — | — | none | — | Corporate/investor site; no online store exists for this chain |
| Ozon (ozon.ru) | https://www.ozon.ru/ | n/a (candidate, deprioritized per wave-8 brief) | Marketplace | — | — | — | not probed this wave | — | Brief flags as weak-for-food and heavily bot-defended; not probed |
| Wildberries (wildberries.ru) | https://www.wildberries.ru/ | n/a (candidate, deprioritized per wave-8 brief) | Marketplace | — | — | — | not probed this wave | — | Same as above |
| Lemana Pro (lemanapro.ru) | https://lemanapro.ru/ | 05 home-improvement (candidate, deprioritized; also pre-wave-8 DEAD) | Home-improvement | — | — | — | Qrator | — | Ex-Leroy Merlin Russia; see known_blockers.md |
| Yandex Lavka (lavka.yandex.ru) | https://lavka.yandex.ru/ | quick-commerce grocery (candidate — not pursued) | Quick-commerce | — | — | — | not fully probed | — | Homepage embeds a React-Query state dump with a Moscow default geolocation (no login needed) and category tiles, but no product-level price data found in that dump; the real catalog API was not reverse-engineered this wave (Yandex market leader — inverse-correlation law, deprioritized per doctrine). Worth a real pass if RU quick-commerce coverage becomes a priority. |
| Fedstat / EMISS (fedstat.ru) | https://fedstat.ru/ | official stats portal (candidate — DEAD, pre-wave-8) | Official statistics | — | — | — | bare 403 | — | rosstat.gov.ru already covers the same survey with no WAF |
| Ministry of Agriculture (mcx.gov.ru) / FAS (fas.gov.ru) | — | wholesale/procurement monitoring (candidate — DEAD, pre-wave-8) | Official wholesale monitoring | — | — | — | connect timeout | — | Top statutory-source leads per an earlier brief; unreachable from this network path both times probed |
